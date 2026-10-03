"""The scripted inspector: an offline stand-in for the ZooWork agent.

It calls the real tool router (so Band rooms, the vault, approvals and the
issuer all run for real) and emits the same trail events the live agent's
built-in tools produce. Used when ZooWork is off or out of credits, and for a
deterministic demo recording.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from typing import Any

from .bus import EventBus
from .cases import CaseBook
from .packet import build_argument_pdf
from .tools import ToolRouter
from .world import World


class SimInspector:
    def __init__(self, world: World, cases: CaseBook, router: ToolRouter, bus: EventBus, pace: float) -> None:
        self.world = world
        self.cases = cases
        self.router = router
        self.bus = bus
        self.pace = pace
        self.packets: dict[tuple[str, str], bytes] = {}
        router.packet_loader = self.load_packet

    async def load_packet(self, case_id: str, path: str) -> bytes:
        try:
            return self.packets[(case_id, path)]
        except KeyError as err:
            raise FileNotFoundError(f"{path} was never published") from err

    # ---- trail helpers -------------------------------------------------------------

    async def pause(self, seconds: float) -> None:
        if self.pace > 0:
            await asyncio.sleep(seconds * self.pace)

    def think(self, case_id: str, text: str) -> None:
        self.bus.publish("feed", item={"id": uuid.uuid4().hex[:12], "case_id": case_id, "channel": "zoo",
                                       "kind": "thought", "text": text, "ts": time.time()})

    def builtin(self, case_id: str, tool: str, args: dict[str, Any], preview: str, ms: int) -> None:
        call_id = uuid.uuid4().hex[:10]
        for phase in ("start", "end"):
            item = {"id": f"{call_id}-{phase}", "call_id": call_id, "case_id": case_id, "channel": "zoo",
                    "kind": "tool", "tool": tool, "phase": phase, "custom": False, "args": args, "ts": time.time()}
            if phase == "end":
                item.update({"preview": preview, "error": False, "ms": ms})
            self.bus.publish("feed", item=item)

    def run_event(self, case_id: str, status: str, outcome: str | None = None) -> None:
        self.bus.publish("feed", item={"id": uuid.uuid4().hex[:12], "case_id": case_id, "channel": "zoo",
                                       "kind": "run", "status": status, "outcome": outcome, "ts": time.time()})

    async def call(self, name: str, **args: Any) -> dict[str, Any]:
        result = await self.router.call(name, args)
        await self.pause(0.9)
        return result.value

    async def write_packet(self, case_id: str, claims: list[dict[str, Any]], summary: str) -> str:
        path = f"/workspace/cases/{case_id}/argument.pdf"
        self.builtin(case_id, "write", {"path": f"/workspace/cases/{case_id}/argument.py"},
                     "wrote 3.1 KB (reportlab layout for the rebuttal)", 140)
        await self.pause(1.1)
        case = self.cases.get(case_id)
        exhibits = {e.id: e for e in self.router.vault.for_case(case_id)}
        self.packets[(case_id, path)] = build_argument_pdf(case, claims, summary, exhibits)
        self.builtin(case_id, "exec", {"command": f"python3 /workspace/cases/{case_id}/argument.py"},
                     f"saved {path} (1 page)", 820)
        await self.pause(0.8)
        self.builtin(case_id, "artifact_publish", {"path": path}, "published argument.pdf (ready)", 410)
        await self.pause(0.6)
        return path

    def ids(self, result: dict[str, Any], *titles: str) -> dict[str, str]:
        """Map exhibit titles (prefix match) to ids from a tool result."""
        found = {}
        for ex in result.get("exhibits", []) + result.get("shared_exhibits", []):
            for t in titles:
                if ex["title"].lower().startswith(t.lower()):
                    found[t] = ex["exhibit_id"]
        return found

    # ---- investigations ------------------------------------------------------------

    async def investigate(self, case_id: str) -> None:
        self.run_event(case_id, "started")
        handler = getattr(self, f"_case_{case_id.replace('-', '_').lower()}", None)
        try:
            await self.call("get_dispute", dispute_id=case_id)
            if handler:
                await handler(case_id)
            self.run_event(case_id, "finished", "succeeded")
        except Exception as err:  # noqa: BLE001
            self.bus.publish("log", level="error", text=f"{case_id}: {err}")
            self.run_event(case_id, "finished", "failed")
            raise

    async def _case_dsp_1042(self, c: str) -> None:
        self.think(c, "Visa 13.1 'not received'. To win I need delivery to the cardholder's address plus proof "
                   "they had it. Starting with the order.")
        order = await self.call("get_order", dispute_id=c)
        mail = await self.call("get_support_thread", dispute_id=c)
        self.think(c, "The cardholder emailed us two days after the delivery date asking for the parka in another "
                   "colour. ShipCo holds the driver photo, so I'll ask them in the case room.")
        ship = await self.call("request_partner_evidence", dispute_id=c, partner="shipco",
                               request="Hi ShipCo! Dispute DSP-1042 says the Cloud Down Parka (order HS-20931, "
                               "tracking SC-77341920) never arrived. Could you share the scan history, delivery "
                               "GPS and the driver's photo?")
        self.think(c, "The photo shows the ShipCo box at the door of number 42 on Maple Lane, label SC-77341920, "
                   "GPS 9 m from the address. Strong case.")
        ex = {**self.ids(order, "Payment", "Checkout", "Order shipping"),
              **self.ids(mail, "Cardholder email"), **self.ids(ship, "ShipCo tracking", "Proof-of-delivery")}
        await self.call("set_strategy", dispute_id=c, decision="fight", win_probability=88,
                        rationale="Carrier photo at the door plus the cardholder's own email after delivery.")
        await self.call("pin_evidence", dispute_id=c, exhibit_id=ex["ShipCo tracking"], supports="Delivered to 42 Maple Lane")
        await self.call("pin_evidence", dispute_id=c, exhibit_id=ex["Proof-of-delivery"], supports="Parcel on the porch, GPS 9 m from the door")
        await self.call("pin_evidence", dispute_id=c, exhibit_id=ex["Cardholder email"], supports="Cardholder praised the parka after delivery")
        await self.call("pin_evidence", dispute_id=c, exhibit_id=ex["Checkout"], supports="Agreed to the refund policy at checkout")
        claims = [
            {"text": "ShipCo delivered the parka to the cardholder's address, 42 Maple Lane, Portland.",
             "exhibit_ids": [ex["ShipCo tracking"], ex["Order shipping"]]},
            {"text": "The driver photographed the parcel at the front door, 9 metres from the address's GPS point.",
             "exhibit_ids": [ex["Proof-of-delivery"]]},
            {"text": "Two days after delivery the cardholder emailed to praise the parka and ask for another colour.",
             "exhibit_ids": [ex["Cardholder email"]]},
            {"text": "The cardholder has a history of filing chargebacks with other merchants.", "exhibit_ids": []},
        ]
        summary = ("The cardholder received the Cloud Down Parka. ShipCo's tracking, GPS-stamped driver photo and the "
                   "cardholder's own email two days after delivery show the item arrived and was in their hands.")
        path = await self.write_packet(c, claims, summary)
        check = await self.call("check_packet", dispute_id=c, packet_path=path, claims=claims)
        if not check.get("ok"):
            self.think(c, "Vault rejected finding 4: I have no evidence for a chargeback history, so it goes. "
                       "No source, no claim.")
            claims = claims[:3] + [{"text": "The cardholder accepted the 30-day refund policy at checkout and never "
                                    "requested a return.", "exhibit_ids": [ex["Checkout"], ex["Cardholder email"]]}]
            path = await self.write_packet(c, claims, summary)
            await self.call("check_packet", dispute_id=c, packet_path=path, claims=claims)
        await self.call("submit_evidence", dispute_id=c, packet_path=path, claims=claims, summary=summary)

    async def _case_dsp_1043(self, c: str) -> None:
        self.think(c, "Visa 10.4 card-absent fraud. Best path is Compelling Evidence 3.0: two earlier undisputed "
                   "orders from the same device or IP.")
        order = await self.call("get_order", dispute_id=c)
        hist = await self.call("get_customer_history", dispute_id=c)
        self.think(c, "CE 3.0 holds: orders 205 and 297 days earlier share device dv_9f3ca71 and the shipping "
                   "address, and one also shares the IP. AVS and CVV matched too.")
        ship = await self.call("request_partner_evidence", dispute_id=c, partner="shipco",
                               request="ShipCo, for dispute DSP-1043 (order HS-21007, tracking SC-77980135): was an "
                               "adult signature collected at delivery?")
        ex = {**self.ids(order, "Payment", "Order shipping"), **self.ids(hist, "Prior undisputed"),
              **self.ids(ship, "Delivery signature", "ShipCo tracking")}
        await self.call("set_strategy", dispute_id=c, decision="fight", win_probability=84,
                        rationale="Visa CE 3.0 is satisfied, which shifts liability back to the issuer.")
        await self.call("pin_evidence", dispute_id=c, exhibit_id=ex["Prior undisputed"], supports="Same device and address on 2 undisputed orders")
        await self.call("pin_evidence", dispute_id=c, exhibit_id=ex["Payment"], supports="AVS and CVV matched")
        await self.call("pin_evidence", dispute_id=c, exhibit_id=ex["Delivery signature"], supports="Signed for by A. Chen")
        claims = [
            {"text": "Two prior undisputed orders, 205 and 297 days earlier, used the same device and shipping address "
             "(Visa Compelling Evidence 3.0).", "exhibit_ids": [ex["Prior undisputed"]]},
            {"text": "The purchase passed AVS and CVV checks from IP 73.158.22.41, the cardholder's usual IP.",
             "exhibit_ids": [ex["Payment"]]},
            {"text": "The espresso machine was delivered to the billing address and signed for by 'A. Chen'.",
             "exhibit_ids": [ex["Delivery signature"], ex["ShipCo tracking"]]},
        ]
        summary = ("This purchase matches the cardholder's established behaviour. Visa Compelling Evidence 3.0 is met, "
                   "and the item was signed for by the cardholder at their billing address.")
        path = await self.write_packet(c, claims, summary)
        await self.call("check_packet", dispute_id=c, packet_path=path, claims=claims)
        await self.call("submit_evidence", dispute_id=c, packet_path=path, claims=claims, summary=summary)

    async def _case_dsp_1044(self, c: str) -> None:
        self.think(c, "Visa 13.2 cancelled recurring. First question: did they cancel before the renewal?")
        await self.call("get_order", dispute_id=c)
        await self.call("get_billing_records", dispute_id=c)
        self.think(c, "They cancelled 3 days before the renewal, and our billing sync never passed it on. The "
                   "cardholder is right; fighting would cost more and damage trust.")
        await self.call("set_strategy", dispute_id=c, decision="accept", win_probability=4,
                        rationale="The cardholder cancelled before renewal; our billing sync failed. Refund and fix the sync.")
        await self.call("accept_dispute", dispute_id=c,
                        rationale="Customer cancelled before renewal; billing sync bug. Refunded. Flagged the sync job.")

    async def _case_dsp_1045(self, c: str) -> None:
        self.think(c, "Visa 13.3 'not as described': they say the jacket isn't waterproof. I need what we promised "
                   "and independent proof we delivered it.")
        order = await self.call("get_order", dispute_id=c)
        mail = await self.call("get_support_thread", dispute_id=c)
        self.think(c, "The product page promised 10,000 mm (ISO 811). No complaint or return request ever came in. "
                   "I can't prove the rating from our systems, so I'll ask the merchant.")
        answer = await self.call("ask_merchant", dispute_id=c,
                                 question="The cardholder says the StormShell jacket leaked. Do you have a lab test "
                                 "proving its 10,000 mm waterproof rating?",
                                 options=["📎 Share lab report", "We don't have one"])
        ex = {**self.ids(order, "Archived product page", "Checkout"), **self.ids(mail, "No contact"),
              **self.ids(answer, "ISO 811")}
        if "ISO 811" not in ex:
            await self.call("set_strategy", dispute_id=c, decision="accept", win_probability=20,
                            rationale="Without an independent test we can't prove the waterproof claim.")
            await self.call("accept_dispute", dispute_id=c, rationale="No independent proof of the waterproof rating.")
            return
        self.think(c, "Lab report CTL-24-0912: 10,400 mm, pass. That's the missing piece.")
        await self.call("set_strategy", dispute_id=c, decision="fight", win_probability=76,
                        rationale="Independent lab test proves the advertised rating; cardholder never asked for a return.")
        await self.call("pin_evidence", dispute_id=c, exhibit_id=ex["Archived product page"], supports="We promised 10,000 mm (ISO 811)")
        await self.call("pin_evidence", dispute_id=c, exhibit_id=ex["ISO 811"], supports="Lab measured 10,400 mm: pass")
        await self.call("pin_evidence", dispute_id=c, exhibit_id=ex["No contact"], supports="No complaint or return request")
        claims = [
            {"text": "At purchase the product page advertised a 10,000 mm waterproof rating (ISO 811).",
             "exhibit_ids": [ex["Archived product page"]]},
            {"text": "An independent ISO 811 lab test measured the fabric at 10,400 mm, above the advertised rating.",
             "exhibit_ids": [ex["ISO 811"]]},
            {"text": "The cardholder never contacted the merchant or used the 30-day return policy they accepted at checkout.",
             "exhibit_ids": [ex["No contact"], ex["Checkout"]]},
        ]
        summary = ("The jacket matched its description: an independent lab measured 10,400 mm against the advertised "
                   "10,000 mm. The cardholder never raised the issue with the merchant or returned the item.")
        path = await self.write_packet(c, claims, summary)
        await self.call("check_packet", dispute_id=c, packet_path=path, claims=claims)
        await self.call("submit_evidence", dispute_id=c, packet_path=path, claims=claims, summary=summary)

    async def _case_dsp_1046(self, c: str) -> None:
        self.think(c, "Visa 12.6.1 duplicate. A double-click did create two charges; let's see if we already "
                   "refunded one.")
        order = await self.call("get_order", dispute_id=c)
        bills = await self.call("get_billing_records", dispute_id=c)
        self.think(c, "The disputed charge ch_3Pa21142b was refunded 15 days before the dispute. The cardholder's "
                   "bank can trace it with the ARN.")
        ex = {**self.ids(order, "Payment"), **self.ids(bills, "Refund")}
        await self.call("set_strategy", dispute_id=c, decision="fight", win_probability=95,
                        rationale="The duplicate was already refunded; the ARN proves it.")
        await self.call("pin_evidence", dispute_id=c, exhibit_id=ex["Refund"], supports="Duplicate refunded before the dispute")
        claims = [
            {"text": "The duplicate charge ch_3Pa21142b was fully refunded before the dispute was opened.",
             "exhibit_ids": [ex["Refund"]]},
            {"text": "The remaining charge paid for one delivered order of a Capybara Plush 2-pack.",
             "exhibit_ids": [ex["Payment"]]},
        ]
        summary = "The duplicate charge was refunded before the dispute (ARN included), so the cardholder was never double-billed."
        path = await self.write_packet(c, claims, summary)
        await self.call("check_packet", dispute_id=c, packet_path=path, claims=claims)
        await self.call("submit_evidence", dispute_id=c, packet_path=path, claims=claims, summary=summary)
