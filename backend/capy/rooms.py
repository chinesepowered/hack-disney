"""Case rooms: one per dispute, holding Inspector Capy, partners and the merchant.

With Band live, every line here is a real Band message routed by @mention, and
ShipCo's answer travels back over Band's WebSocket. Offline, the same
conversation happens locally so the dashboard looks identical.
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .band import BandLive
from .bus import EventBus
from .cases import CaseBook
from .exhibits import Exhibit, Vault
from .world import World

log = logging.getLogger("capy.rooms")

NAMES = {"capy": "Inspector Capy", "shipco": "ShipCo Warehouse", "merchant": "You (Hot Spring Supply)"}


def _date(iso_ts: str) -> str:
    return iso_ts.replace("T", " ").replace("Z", " UTC")[:16]


@dataclass
class PartnerReply:
    text: str
    exhibits: list[Exhibit] = field(default_factory=list)
    photo: Path | None = None


class ShipCoDesk:
    """The ShipCo warehouse's side: it owns tracking scans and driver photos."""

    def __init__(self, world: World, vault: Vault) -> None:
        self.world = world
        self.vault = vault

    def answer(self, case_id: str) -> PartnerReply:
        dispute = self.world.disputes[case_id]
        order = self.world.orders[dispute["order_id"]]
        ship = self.world.shipments.get(order["shipping"].get("tracking") or "")
        if not ship:
            return PartnerReply(f"We have no ShipCo shipment for order {order['id']}. 🤷")
        last = ship["events"][-1]
        exhibits = [
            self.vault.add(
                case_id, "shipco_tracking", kind="tracking",
                title=f"ShipCo tracking history {ship['tracking']}",
                source="ShipCo Warehouse (partner, shared on Band)",
                summary=f"Delivered {_date(ship['delivered_at'])} to {order['shipping']['address']}: "
                f"{last['status']}. Delivery GPS {ship.get('gps_distance_m', '?')} m from the address.",
                rows=[[_date(e["at"]), f"{e['status']}  ({e['where']})"] for e in ship["events"]]
                + [["Service", ship["service"]], ["Driver note", ship["driver_note"]],
                   ["GPS distance to address", f"{ship.get('gps_distance_m', '?')} m"]],
            )
        ]
        photo = None
        if ship.get("photo"):
            exhibits.append(self.vault.add(
                case_id, "shipco_pod_photo", kind="photo", title="Proof-of-delivery photo",
                source="ShipCo Warehouse (partner, shared on Band)",
                summary=f"Driver photo of the parcel at the front door of {order['shipping']['address']}, "
                f"taken {_date(ship['delivered_at'])}, GPS {ship['gps_distance_m']} m from the door.",
                image=ship["photo"],
            ))
            photo = self.vault.image_path(exhibits[-1])
        signature = order["shipping"].get("signature")
        if signature:
            exhibits.append(self.vault.add(
                case_id, "signature", kind="document", title="Delivery signature",
                source="ShipCo Warehouse (partner, shared on Band)",
                summary=f"Adult signature collected at delivery: '{signature}', "
                f"{order['shipping']['address']}, {_date(ship['delivered_at'])}.",
                rows=[["Signed by", signature], ["Address", order["shipping"]["address"]],
                      ["Service", ship["service"]]],
            ))
        extra = []
        if photo:
            extra.append(f"driver photo attached, GPS {ship['gps_distance_m']} m from the door")
        if signature:
            extra.append(f"signed by {signature}")
        text = (
            f"📦 Found it! {ship['tracking']} was delivered {_date(ship['delivered_at'])} to "
            f"{order['shipping']['address']}" + (f"; {', '.join(extra)}." if extra else ".")
            + " Full scan history below."
        )
        return PartnerReply(text, exhibits, photo)


class Rooms:
    def __init__(self, world: World, vault: Vault, cases: CaseBook, bus: EventBus,
                 band: BandLive | None, pace: float) -> None:
        self.world = world
        self.vault = vault
        self.cases = cases
        self.bus = bus
        self.band = band
        self.pace = pace
        self.shipco = ShipCoDesk(world, vault)
        self.room_case: dict[str, str] = {}
        self._partner_waits: dict[str, asyncio.Future[PartnerReply]] = {}
        self._merchant_waits: dict[str, tuple[str, asyncio.Future[dict[str, Any]]]] = {}

    # ---- feed -------------------------------------------------------------------

    def feed(self, case_id: str, sender: str, text: str, *, kind: str = "message",
             attachments: list[dict[str, Any]] | None = None, **extra: Any) -> None:
        self.bus.publish("feed", item={
            "id": uuid.uuid4().hex[:12],
            "case_id": case_id,
            "channel": "band",
            "sender": sender,
            "name": NAMES.get(sender, sender),
            "text": text,
            "kind": kind,
            "attachments": attachments or [],
            "live": self.band is not None,
            "ts": time.time(),
            **extra,
        })

    async def _band(self, coro: Any) -> Any:
        if self.band is None:
            return None
        try:
            return await coro
        except Exception as err:  # noqa: BLE001 - the case continues even if Band hiccups
            log.warning("Band call failed: %s", err)
            self.bus.publish("log", level="warn", text=f"Band: {err}")
            return None

    # ---- room lifecycle ---------------------------------------------------------

    async def open(self, case_id: str) -> None:
        case = self.cases.get(case_id)
        title = f"🔍 {case.id} · {case.reason_label} · ${case.amount:,.0f}"
        room: dict[str, Any] = {"id": None, "title": title, "live": self.band is not None, "members": ["capy", "merchant"]}
        if self.band:
            room_id = await self._band(self.band.create_room(title))
            if room_id:
                room["id"] = room_id
                self.room_case[room_id] = case.id
                await self._band(self.band.set_goal(
                    room_id, f"Win {case.id} before the deadline",
                    f"{case.network_code} {case.reason_label} on {case.item} (${case.amount:,.2f}). "
                    f"Cardholder: {case.claim} Respond by {_date(case.respond_by)}.",
                ))
        self.cases.update(case.id, room=room)
        self.feed(case.id, "system", f"Case room opened{' on Band' if room['id'] else ''}: {title}", kind="system")

    async def say(self, case_id: str, text: str, mention: list[str] | None = None,
                  kind: str = "message", **extra: Any) -> None:
        self.feed(case_id, "capy", text, kind=kind, mentions=mention or [], **extra)
        room_id = self._room_id(case_id)
        if self.band and room_id:
            await self._band(self.band.post("capy", room_id, text, mention or []))

    def _room_id(self, case_id: str) -> str | None:
        room = self.cases.get(case_id).room
        return room.get("id") if room else None

    async def _ensure_member(self, case_id: str, role: str) -> None:
        case = self.cases.get(case_id)
        room = dict(case.room or {})
        if role in room.get("members", []):
            return
        room["members"] = [*room.get("members", []), role]
        self.cases.update(case_id, room=room)
        if self.band and room.get("id"):
            await self._band(self.band.add_participant(room["id"], self.band.participant_id(role)))
        self.feed(case_id, "system", f"{NAMES[role]} was added to the case room", kind="system")

    # ---- partner evidence -------------------------------------------------------

    async def ask_partner(self, case_id: str, request: str) -> PartnerReply:
        await self._ensure_member(case_id, "shipco")
        self.cases.update(case_id, status="waiting_partner", activity="Asking ShipCo for proof of delivery")
        await self.say(case_id, request, mention=["shipco"])
        room_id = self._room_id(case_id)
        if self.band and room_id:
            future: asyncio.Future[PartnerReply] = asyncio.get_running_loop().create_future()
            self._partner_waits[room_id] = future
            try:
                return await asyncio.wait_for(future, timeout=60)
            except TimeoutError:
                self.bus.publish("log", level="warn", text="ShipCo did not answer on Band; using its desk directly")
            finally:
                self._partner_waits.pop(room_id, None)
        await asyncio.sleep(2.2 * self.pace)
        reply = self.shipco.answer(case_id)
        self._feed_partner(case_id, reply)
        return reply

    def _feed_partner(self, case_id: str, reply: PartnerReply) -> None:
        attachments = []
        if reply.photo:
            attachments.append({"name": reply.photo.name, "url": f"/files/exhibits/{reply.photo.name}"})
        self.feed(case_id, "shipco", reply.text, attachments=attachments)

    async def on_shipco_mention(self, room_id: str, text: str) -> None:
        """ShipCo's Band runtime: answer Inspector Capy's request in the room."""
        case_id = self.room_case.get(room_id) or _case_from_text(text)
        if not case_id:
            return
        reply = self.shipco.answer(case_id)
        attachment_ids = []
        if reply.photo and self.band:
            uploaded = await self._band(self.band.upload("shipco", room_id, reply.photo))
            if uploaded:
                attachment_ids.append(uploaded["id"])
        if self.band:
            await self._band(self.band.post("shipco", room_id, reply.text, ["capy"], attachment_ids))
        self._feed_partner(case_id, reply)
        future = self._partner_waits.get(room_id)
        if future and not future.done():
            future.set_result(reply)

    # ---- merchant questions -----------------------------------------------------

    async def ask_merchant(self, case_id: str, question: str, options: list[str]) -> dict[str, Any]:
        attention_id = uuid.uuid4().hex[:10]
        case = self.cases.get(case_id)
        item = {"id": attention_id, "question": question, "options": options, "status": "open", "answer": None}
        self.cases.update(case_id, status="waiting_merchant", activity="Waiting for your answer",
                          attention=[*case.attention, item])
        self.feed(case_id, "capy", question, kind="attention", attention_id=attention_id, options=options,
                  mentions=["merchant"])
        room_id = self._room_id(case_id)
        band_event = None
        if self.band and room_id:
            band_event = await self._band(self.band.attention(room_id, question))
            await self._band(self.band.post("capy", room_id, question, ["merchant"]))
        future: asyncio.Future[dict[str, Any]] = asyncio.get_running_loop().create_future()
        self._merchant_waits[case_id] = (attention_id, future)
        answer = await future
        if self.band and room_id and band_event:
            await self._band(self.band.attention(room_id, question, resolves=band_event, answer=answer["text"]))
        return answer

    async def merchant_reply(self, case_id: str, text: str, share: str | None = None,
                             *, from_band: bool = False) -> dict[str, Any]:
        case = self.cases.get(case_id)
        shared: list[Exhibit] = []
        wants_share = share or ("lab" in text.lower() or "report" in text.lower() or "attach" in text.lower())
        if wants_share and case.id == "DSP-1045":
            f = self.world.merchant_files["stormshell_lab_report"]
            shared.append(self.vault.add(
                case.id, "lab_report", kind="document", title=f["title"],
                source=f"{f['lab']} (shared by you from your files)",
                summary=f"Independent ISO 811 test of the StormShell fabric: {f['result']}.",
                rows=[["Lab", f["lab"]], ["Method", "ISO 811 hydrostatic head"], ["Result", f["result"]]],
                image=f["image"],
            ))
        attachments = [{"name": e.image, "url": f"/files/exhibits/{e.image}"} for e in shared if e.image]
        self.feed(case.id, "merchant", text, attachments=attachments)
        room_id = self._room_id(case.id)
        if self.band and room_id and not from_band:
            attachment_ids = []
            for ex in shared:
                path = self.vault.image_path(ex)
                if path:
                    up = await self._band(self.band.upload("capy", room_id, path))
                    if up:
                        attachment_ids.append(up["id"])
            await self._band(self.band.post("merchant", room_id, text, ["capy"], attachment_ids))

        answer = {"text": text, "shared_exhibits": [e.for_agent() for e in shared]}
        waiting = self._merchant_waits.pop(case.id, None)
        if waiting:
            attention_id, future = waiting
            case.attention = [
                {**a, "status": "answered", "answer": text} if a["id"] == attention_id else a
                for a in case.attention
            ]
            self.cases.update(case.id, status="investigating", activity="Got your answer")
            if not future.done():
                future.set_result(answer)
        return answer

    async def on_capy_mention(self, room_id: str, sender: str, text: str) -> None:
        """Inspector Capy's Band runtime: replies from ShipCo or the merchant."""
        case_id = self.room_case.get(room_id)
        if not case_id:
            return
        if sender == "shipco":
            return  # ShipCo replies are delivered by on_shipco_mention in this process
        if sender == "merchant" and case_id in self._merchant_waits:
            cleaned = re.sub(r"@\S+\s*", "", text).strip()
            await self.merchant_reply(case_id, cleaned, from_band=True)


def _case_from_text(text: str) -> str | None:
    match = re.search(r"DSP-\d{4}", text)
    return match.group(0) if match else None
