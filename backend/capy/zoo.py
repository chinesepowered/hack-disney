"""Inspector Capy as a ZooWork managed agent.

ZooWork runs the model, the tool loop and the sandbox where Capy writes its
argument PDF. This module provisions the agent, opens one session per dispute,
executes the agent's custom tools in our backend, relays always_ask approvals
to the merchant, and streams the whole trajectory to the dashboard.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
import uuid
from typing import Any

import httpx
from zoowork import ZooworkClient, ZooworkError, custom_tool_use, is_run_finished, run_outcome, tool_call

from .approvals import Approvals
from .bus import EventBus
from .cases import CaseBook
from .config import PACKAGE_ROOT, Settings
from .tools import APPROVAL_TOOLS, TOOL_DEFS, TOOL_NAMES, ToolRouter

log = logging.getLogger("capy.zoo")

PERSONA_FILES = ("IDENTITY.md", "SOUL.md", "AGENTS.md", "TOOLS.md")
TERMINAL = {"submitted", "won", "lost", "accepted"}


class ZooRunFailed(RuntimeError):
    """The managed agent's run failed before it did any work (e.g. no credits)."""


def agent_resource(model: str) -> dict[str, Any]:
    persona = [{"name": n, "content": (PACKAGE_ROOT / "persona" / n).read_text(encoding="utf-8")} for n in PERSONA_FILES]
    tools = [{**t, "timeoutMs": 1_800_000} for t in TOOL_DEFS]
    resource = {
        "name": "inspector-capy",
        "model": {"primary": model, "input": ["text", "image"]},
        "persona": {"docs": persona},
        "custom_tools": tools,
        "tool_policy": {"permissions": {name: "always_ask" for name in APPROVAL_TOOLS}},
        "userTimezone": "America/Los_Angeles",
    }
    digest = hashlib.sha256(json.dumps(resource, sort_keys=True).encode()).hexdigest()[:16]
    resource["labels"] = {"app": "chargeback-capy", "role": "inspector", "cfg": digest}
    return resource


class ZooInspector:
    def __init__(self, settings: Settings, cases: CaseBook, router: ToolRouter, approvals: Approvals,
                 bus: EventBus) -> None:
        self.settings = settings
        self.cases = cases
        self.router = router
        self.approvals = approvals
        self.bus = bus
        self.client = ZooworkClient(api_key=settings.zoowork_api_key,
                                    base_url=settings.zoowork_base_url or None, timeout=60)
        self.agent_id: str | None = None
        self.sessions: dict[str, str] = {}
        self.errors: dict[str, str] = {}
        self.bind(cases, router, approvals)

    def bind(self, cases: CaseBook, router: ToolRouter, approvals: Approvals) -> None:
        """Point at a fresh world (each sweep rebuilds the merchant's data)."""
        self.cases = cases
        self.router = router
        self.approvals = approvals
        router.packet_loader = self.load_packet

    async def close(self) -> None:
        await self.client.aclose()

    # ---- provisioning ----------------------------------------------------------------

    async def ensure_agent(self) -> str:
        if self.agent_id:
            return self.agent_id
        resource = agent_resource(self.settings.zoowork_model)
        page = await self.client.list_agents(labels={"app": "chargeback-capy", "role": "inspector"})
        existing = next(iter(page.data), None)
        if existing is None:
            created = await self.client.create_agent(resource, idempotency_key=f"capy-{resource['labels']['cfg']}")
            agent_id = created["agent_id"]
            self._log(f"Created ZooWork managed agent {agent_id}")
        else:
            agent_id = existing["agent_id"]
            if (existing.get("labels") or {}).get("cfg") != resource["labels"]["cfg"]:
                sections = {k: v for k, v in resource.items() if k != "name"}
                await self.client.update_agent(agent_id, sections)
                await self.client.stop_agent(agent_id)
                self._log(f"Updated ZooWork agent {agent_id} to config {resource['labels']['cfg']}")
        await self.client.start_agent(agent_id)
        await self.client.wait_until_running(agent_id, timeout=120)
        self.agent_id = agent_id
        return agent_id

    def _log(self, text: str, level: str = "info") -> None:
        log.info(text)
        self.bus.publish("log", level=level, text=text)

    # ---- artifacts --------------------------------------------------------------------

    async def load_packet(self, case_id: str, path: str) -> bytes:
        assert self.agent_id
        path = path if path.startswith("/") else f"/workspace/{path.lstrip('./')}"
        session_id = self.sessions.get(case_id)
        for _ in range(10):
            listing = await self.client.list_artifacts(self.agent_id, session_id=session_id, source_path=path, limit=20)
            ready = [a for a in listing.get("artifacts", []) if a.get("status") == "ready"]
            if ready:
                newest = max(ready, key=lambda a: a.get("created_at") or "")
                download = await self.client.download_artifact(self.agent_id, newest["artifact_id"])
                async with httpx.AsyncClient(follow_redirects=True, timeout=60) as http:
                    response = await http.get(download["url"])
                    response.raise_for_status()
                    return response.content
            await asyncio.sleep(1.5)
        raise FileNotFoundError(f"No published artifact at {path}")

    # ---- one dispute = one session -----------------------------------------------------

    async def investigate(self, case_id: str) -> None:
        agent_id = await self.ensure_agent()
        session = await self.client.create_session(agent_id, {"title": f"Dispute {case_id}"},
                                                   idempotency_key=f"{case_id}-{uuid.uuid4().hex[:8]}")
        session_id = session["session_id"]
        self.sessions[case_id] = session_id
        self.cases.update(case_id, session_id=session_id, status="investigating", activity="Inspector Capy is on it")
        message = (
            f"Dispute {case_id} needs a response before its deadline. Investigate it end to end following your "
            f"operating manual, working in /workspace/cases/{case_id}/. Use the custom tools for all merchant data "
            "and the case room; cite only vault exhibit ids."
        )
        await self.client.post_events(agent_id, session_id, [{"type": "user.message", "content": message}])
        pending: set[asyncio.Task[None]] = set()
        outcome = None
        tools_used = 0
        try:
            async for event in self.client.stream_events(agent_id, session_id):
                self._relay(case_id, event)
                use = custom_tool_use(event)
                if use and use.phase == "requested" and use.name in TOOL_NAMES:
                    tools_used += 1
                    task = asyncio.create_task(self._run_tool(case_id, use.call_id, use.name, use.input or {}))
                    pending.add(task)
                    task.add_done_callback(pending.discard)
                if event.event_type == "agent.approval" and event.payload.get("phase") == "requested":
                    task = asyncio.create_task(self._approve(case_id, event.payload))
                    pending.add(task)
                    task.add_done_callback(pending.discard)
                if is_run_finished(event):
                    outcome = run_outcome(event)
                    break
        finally:
            for task in pending:
                task.cancel()
        if outcome == "failed" and tools_used == 0:
            raise ZooRunFailed(self.errors.get(case_id, "ZooWork run failed"))
        case = self.cases.get(case_id)
        if case.status not in TERMINAL:
            self.cases.update(case_id, activity="Run ended before a submission")

    async def _run_tool(self, case_id: str, call_id: str, name: str, args: dict[str, Any]) -> None:
        assert self.agent_id
        result = await self.router.call(name, args, case_hint=case_id)
        try:
            await self.client.resolve_custom_tool_call(self.agent_id, call_id, content=result.content(),
                                                       is_error=result.is_error, resolved_by="capy-backend")
        except ZooworkError as err:
            self._log(f"{case_id}: could not return {name} result: {err}", "error")

    async def _approve(self, case_id: str, payload: dict[str, Any]) -> None:
        assert self.agent_id
        tool = payload.get("toolName") or ""
        args = payload.get("arguments") or {}
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except ValueError:
                args = {}
        if tool not in APPROVAL_TOOLS:
            await self.client.resolve_approval(self.agent_id, payload["approvalId"], decision="allow-once",
                                               resolved_by="capy-backend")
            return
        target = str(args.get("dispute_id") or case_id)
        prepared = None
        if tool == "submit_evidence":
            prepared = await self.router.prepare(target, str(args.get("packet_path", "")), list(args.get("claims") or []))
        approval = self.approvals.open(target, tool, args, self.router.approval_preview(target, tool, args, prepared),
                                       approval_id=payload["approvalId"])
        decision = await self.approvals.wait(approval.id)
        await self.client.resolve_approval(self.agent_id, approval.id,
                                           decision="allow-once" if decision == "approve" else "deny",
                                           resolved_by="merchant")
        if decision != "approve":
            self.cases.update(target, status="drafting", activity="You held the submission")

    # ---- trail -------------------------------------------------------------------------

    def _relay(self, case_id: str, event: Any) -> None:
        kind = event.event_type
        now = time.time()
        call = tool_call(event)
        if call and call.tool_name not in TOOL_NAMES and call.phase in {"start", "end", "blocked"}:
            item: dict[str, Any] = {"id": f"{call.tool_call_id}-{call.phase}", "call_id": call.tool_call_id,
                                    "case_id": case_id, "channel": "zoo", "kind": "tool", "tool": call.tool_name,
                                    "phase": "end" if call.phase != "start" else "start", "custom": False, "ts": now}
            if call.args:
                item["args"] = call.args
            if call.phase != "start":
                item.update({"preview": (call.result_preview or call.phase)[:400], "error": bool(call.is_error) or call.phase == "blocked"})
            self.bus.publish("feed", item=item)
        elif kind == "agent.thinking":
            text = str(event.payload.get("text") or "").strip()
            if text:
                self.bus.publish("feed", item={"id": f"th-{event.seq}", "case_id": case_id, "channel": "zoo",
                                               "kind": "thought", "text": text[:600], "ts": now})
        elif kind == "agent.assistant":
            message = event.payload.get("message") or {}
            content = message.get("content") if isinstance(message, dict) else None
            text = content if isinstance(content, str) else "".join(
                b.get("text", "") for b in (content or []) if isinstance(b, dict))
            if text.strip():
                self.bus.publish("feed", item={"id": f"as-{event.seq}", "case_id": case_id, "channel": "zoo",
                                               "kind": "assistant", "text": text.strip()[:1200], "ts": now})
        elif kind in {"run.started", "run.finished"}:
            self.bus.publish("feed", item={"id": f"run-{event.seq}", "case_id": case_id, "channel": "zoo",
                                           "kind": "run", "status": kind.split(".")[1],
                                           "outcome": run_outcome(event), "ts": now})
        elif kind == "agent.error":
            message = str(event.payload.get("errorMessage"))
            self.errors[case_id] = "ZooWork account has insufficient credits" if "insufficient_credits" in message else message[:300]
            self._log(f"{case_id}: {self.errors[case_id]}", "error")
