"""Band: case rooms where Inspector Capy, partner agents and the merchant meet.

Provisioning uses the merchant's Band user key to register two external agents
(Inspector Capy and the ShipCo Warehouse partner) and keeps their one-time API
keys in backend/.state. Both agents then connect over Band's WebSocket through
the Band SDK, so messages are routed by @mention exactly as for any remote agent.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

import httpx

from .config import STATE_DIR, Settings

log = logging.getLogger("capy.band")

AGENTS = {
    "capy": (
        "Inspector Capy",
        "Chargeback detective for Hot Spring Supply Co. Investigates card disputes, gathers "
        "evidence from partners and builds evidence packets for the merchant to approve.",
    ),
    "shipco": (
        "ShipCo Warehouse",
        "Fulfilment and delivery partner. Shares tracking history and proof-of-delivery "
        "photos with merchants when they need evidence for a dispute.",
    ),
}

# (role, room_id, sender_name, sender_type, text, attachments)
MessageHandler = Callable[[str, str, str, str, str, list[dict[str, Any]]], Awaitable[None]]


class BandError(RuntimeError):
    pass


class BandLive:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.base = settings.band_rest_url.rstrip("/") + "/api/v1"
        self.user_http = httpx.AsyncClient(timeout=30, headers={"X-API-Key": settings.band_api_key})
        self.agent_http: dict[str, httpx.AsyncClient] = {}
        self.agents: dict[str, dict[str, Any]] = {}
        self.user: dict[str, Any] = {}
        self.handlers: dict[str, MessageHandler] = {}
        self._runtimes: list[Any] = []
        self.state_file = STATE_DIR / "band_agents.json"
        self.features: dict[str, bool] = {}

    # ---- HTTP -------------------------------------------------------------------

    async def _call(self, client: httpx.AsyncClient, method: str, path: str, **kwargs: Any) -> Any:
        response = await client.request(method, self.base + path, **kwargs)
        if response.status_code >= 400:
            raise BandError(f"Band {method} {path} -> {response.status_code}: {response.text[:300]}")
        if not response.content:
            return {}
        return response.json().get("data", response.json())

    async def as_user(self, method: str, path: str, **kwargs: Any) -> Any:
        return await self._call(self.user_http, method, path, **kwargs)

    async def as_agent(self, role: str, method: str, path: str, **kwargs: Any) -> Any:
        return await self._call(self.agent_http[role], method, path, **kwargs)

    # ---- provisioning -----------------------------------------------------------

    async def provision(self) -> None:
        me = await self.as_user("GET", "/me")
        self.user = me.get("user", me)
        stored = json.loads(self.state_file.read_text()) if self.state_file.exists() else {}
        for role, creds in self.settings.band_agent_creds.items():  # .env wins over local state
            stored[role] = {**creds, "name": AGENTS[role][0]}
        existing = {a["name"]: a for a in await self.as_user("GET", "/me/agents")}
        for role, (name, description) in AGENTS.items():
            creds = stored.get(role)
            current = existing.get(name)
            if creds and current and current["id"] == creds["id"]:
                self.agents[role] = creds
                continue
            if creds and role in self.settings.band_agent_creds:
                log.warning("Band agent %s from .env was not found in your account; registering a new one", name)
            if current:  # ours by name, but its one-time key is lost: recreate it
                await self.as_user("DELETE", f"/me/agents/{current['id']}")
            made = await self.as_user(
                "POST", "/me/agents/register", json={"agent": {"name": name, "description": description}}
            )
            self.agents[role] = {"id": made["agent"]["id"], "api_key": made["credentials"]["api_key"], "name": name}
            log.info("registered Band agent %s (%s)", name, self.agents[role]["id"])
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        self.state_file.write_text(json.dumps(self.agents, indent=2))
        self.state_file.chmod(0o600)
        for role, creds in self.agents.items():
            self.agent_http[role] = httpx.AsyncClient(timeout=30, headers={"X-API-Key": creds["api_key"]})
        me_agent = await self.as_agent("capy", "GET", "/agent/me")
        self.features = me_agent.get("feature_flags") or {}

    @property
    def can_upload(self) -> bool:
        return bool(self.features.get("ff_file_transfer"))

    @property
    def has_tasks(self) -> bool:
        return bool(self.features.get("ff_room_tasks"))

    async def start(self, handlers: dict[str, MessageHandler]) -> None:
        """Provision agents and connect them to Band's WebSocket."""
        from band import Agent  # noqa: PLC0415 (heavy import, only when Band is live)

        self.handlers = handlers
        await self.provision()
        for role, creds in self.agents.items():
            agent = Agent.create(
                adapter=_relay_adapter(role, self),
                agent_id=creds["id"],
                api_key=creds["api_key"],
                ws_url=self.settings.band_ws_url,
                rest_url=self.settings.band_rest_url,
            )
            await agent.start()
            self._runtimes.append(agent)
        log.info("Band agents online: %s", ", ".join(c["name"] for c in self.agents.values()))

    async def stop(self) -> None:
        for agent in self._runtimes:
            try:
                await agent.stop(timeout=3)
            except Exception:  # noqa: BLE001 - shutdown is best effort
                pass
        for client in [self.user_http, *self.agent_http.values()]:
            await client.aclose()

    # ---- rooms ------------------------------------------------------------------

    async def create_room(self, title: str) -> str:
        room = await self.as_agent("capy", "POST", "/agent/chats", json={"chat": {"title": title[:120]}})
        room_id = room["id"]
        await self.add_participant(room_id, self.user["id"])
        return room_id

    async def add_participant(self, room_id: str, participant_id: str) -> None:
        try:
            await self.as_agent("capy", "POST", f"/agent/chats/{room_id}/participants",
                                json={"participant": {"participant_id": participant_id}})
        except BandError as err:
            if "already" not in str(err).lower():
                raise

    async def post(self, role: str, room_id: str, text: str, mention_roles: list[str],
                   attachment_ids: list[str] | None = None) -> str:
        mentions = [{"id": self.participant_id(r)} for r in mention_roles]
        message: dict[str, Any] = {"content": text, "mentions": mentions}
        if attachment_ids:
            message["attachment_ids"] = attachment_ids
        if role == "merchant":
            sent = await self.as_user("POST", f"/me/chats/{room_id}/messages", json={"message": message})
        else:
            sent = await self.as_agent(role, "POST", f"/agent/chats/{room_id}/messages", json={"message": message})
        return sent.get("id", "")

    async def upload(self, role: str, room_id: str, path: Path) -> dict[str, Any]:
        data = path.read_bytes()
        headers = {
            "content-type": "application/octet-stream",
            "x-file-name": path.name,
            "x-file-sha256": hashlib.sha256(data).hexdigest(),
        }
        return await self.as_agent(role, "PUT", f"/agent/chats/{room_id}/files", content=data, headers=headers)

    async def attention(self, room_id: str, question: str, *, blocking: bool = True,
                        resolves: str | None = None, answer: str | None = None) -> str:
        metadata: dict[str, Any] = {"kind": "question", "blocking": blocking}
        if resolves:
            metadata.update({"resolves": resolves, "resolution": answer or "answered"})
        event = await self.as_agent("capy", "POST", f"/agent/chats/{room_id}/events", json={
            "event": {"content": question if not resolves else f"Answered: {answer}",
                      "message_type": "attention", "metadata": metadata}
        })
        return event.get("id", "")

    async def set_goal(self, room_id: str, title: str, summary: str) -> None:
        await self.as_agent("capy", "PUT", f"/agent/chats/{room_id}/board",
                            json={"goal_title": title[:200], "goal_summary": summary[:4000]})

    def participant_id(self, role: str) -> str:
        if role == "merchant":
            return self.user["id"]
        return self.agents[role]["id"]

    def role_of(self, sender_id: str) -> str:
        if sender_id == self.user.get("id"):
            return "merchant"
        for role, creds in self.agents.items():
            if creds["id"] == sender_id:
                return role
        return "other"


def _relay_adapter(role: str, band: BandLive) -> Any:
    """A Band SDK adapter that forwards @mentions to our handlers instead of an LLM."""
    from band.core.simple_adapter import SimpleAdapter  # noqa: PLC0415

    class RelayAdapter(SimpleAdapter[Any]):
        async def on_message(self, msg, tools, history, participants_msg, contacts_msg, *,  # type: ignore[override]
                             is_session_bootstrap: bool, room_id: str) -> None:
            handler = band.handlers.get(role)
            if handler is None or msg.message_type not in (None, "text"):
                return
            metadata = msg.metadata if isinstance(msg.metadata, dict) else {}
            attachments = metadata.get("attachments") or []
            sender_role = band.role_of(msg.sender_id)
            try:
                await handler(role, room_id, sender_role, msg.sender_name or sender_role, msg.content, attachments)
            except Exception:  # noqa: BLE001 - never kill the WebSocket loop
                log.exception("Band handler for %s failed", role)

    return RelayAdapter()


async def probe(settings: Settings) -> dict[str, Any]:
    band = BandLive(settings)
    try:
        await band.provision()
        return {"user": band.user.get("handle"), "agents": {r: a["id"] for r, a in band.agents.items()}}
    finally:
        await band.stop()


if __name__ == "__main__":  # uv run python -m capy.band  -> provision and print agent ids
    from .config import load_settings

    print(asyncio.run(probe(load_settings())))
