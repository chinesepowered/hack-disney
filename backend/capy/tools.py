"""Inspector Capy's custom tools.

ZooWork runs the agent loop and pauses on each of these; our backend executes
them (credentials and merchant data never enter the sandbox) and returns the
result. The scripted inspector calls the very same router, so offline sweeps
exercise identical code.
"""

from __future__ import annotations

import base64
import json
import time
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from .approvals import Approvals
from .bus import EventBus
from .cases import CaseBook
from .exhibits import Exhibit, Vault
from .packet import assemble_packet
from .processor import Processor, ce3_qualifying
from .rooms import Rooms
from .world import MERCHANT, World

PacketLoader = Callable[[str, str], Awaitable[bytes]]

_CASE = {"dispute_id": {"type": "string", "description": "Dispute id, e.g. DSP-1042"}}
_CLAIMS = {
    "type": "array",
    "description": "Each finding in the packet, with the exhibit ids that prove it.",
    "items": {
        "type": "object",
        "properties": {
            "text": {"type": "string", "description": "One factual finding, one sentence."},
            "exhibit_ids": {"type": "array", "items": {"type": "string"},
                            "description": "Vault exhibit ids (e.g. EX-1042-B) that prove this finding."},
        },
        "required": ["text", "exhibit_ids"],
    },
}


def _schema(properties: dict[str, Any], required: list[str]) -> dict[str, Any]:
    return {"type": "object", "properties": properties, "required": required}


TOOL_DEFS: list[dict[str, Any]] = [
    {
        "name": "list_disputes",
        "description": "List the merchant's open card disputes with amount, reason code and response deadline.",
        "input_schema": _schema({}, []),
    },
    {
        "name": "get_dispute",
        "description": "Get one dispute: the cardholder's claim, the network reason code, the deadline, and "
        "what evidence wins this reason code.",
        "input_schema": _schema(_CASE, ["dispute_id"]),
    },
    {
        "name": "get_order",
        "description": "Get the disputed order from the merchant's store: items, payment verification "
        "(AVS, CVV, IP, device), shipping record, checkout terms and the archived product page. Registers "
        "the relevant records as vault exhibits you can cite.",
        "input_schema": _schema(_CASE, ["dispute_id"]),
    },
    {
        "name": "get_customer_history",
        "description": "Get the cardholder's previous orders with this merchant, including IP, device and "
        "address matches. Says whether Visa Compelling Evidence 3.0 is satisfied. Registers an exhibit.",
        "input_schema": _schema(_CASE, ["dispute_id"]),
    },
    {
        "name": "get_support_thread",
        "description": "Get every email between the cardholder and the merchant's support desk for this order "
        "(or confirm there were none). Registers each as an exhibit.",
        "input_schema": _schema(_CASE, ["dispute_id"]),
    },
    {
        "name": "get_billing_records",
        "description": "Get refunds, duplicate charges and subscription history for this dispute's charge. "
        "Registers the relevant records as exhibits.",
        "input_schema": _schema(_CASE, ["dispute_id"]),
    },
    {
        "name": "request_partner_evidence",
        "description": "Ask a partner agent for evidence in the dispute's Band case room. Partner 'shipco' "
        "(the ShipCo Warehouse) holds carrier scans, delivery GPS, signatures and driver photos. Waits for "
        "the partner's reply and returns it with any photos for you to inspect.",
        "input_schema": _schema({**_CASE, "partner": {"type": "string", "enum": ["shipco"]},
                                 "request": {"type": "string", "description": "What you need, addressed to the partner."}},
                                ["dispute_id", "partner", "request"]),
    },
    {
        "name": "ask_merchant",
        "description": "Ask the merchant (a human) a question in the case room and wait for the answer. Use "
        "only for facts or files that no tool can give you. The merchant may share files from their records.",
        "input_schema": _schema({**_CASE, "question": {"type": "string"},
                                 "options": {"type": "array", "items": {"type": "string"},
                                             "description": "Optional quick replies, 2-3 short options."}},
                                ["dispute_id", "question"]),
    },
    {
        "name": "pin_evidence",
        "description": "Pin a vault exhibit to the case board with the point it proves. Pin each exhibit you "
        "will rely on, as soon as you have verified it.",
        "input_schema": _schema({**_CASE, "exhibit_id": {"type": "string"},
                                 "supports": {"type": "string", "description": "The point this exhibit proves, under 15 words."}},
                                ["dispute_id", "exhibit_id", "supports"]),
    },
    {
        "name": "set_strategy",
        "description": "Record whether to fight or accept the dispute, your estimated win probability and why. "
        "Call once you understand the case, before building a packet or accepting.",
        "input_schema": _schema({**_CASE, "decision": {"type": "string", "enum": ["fight", "accept"]},
                                 "win_probability": {"type": "integer", "minimum": 0, "maximum": 100},
                                 "rationale": {"type": "string", "description": "One or two sentences."}},
                                ["dispute_id", "decision", "win_probability", "rationale"]),
    },
    {
        "name": "check_packet",
        "description": "Vault check before submitting. Pass the path of your published argument PDF and the "
        "claims it makes. The vault verifies every claim cites a real exhibit for this dispute, attaches the "
        "original exhibits with SHA-256 fingerprints, and returns any problems to fix.",
        "input_schema": _schema({**_CASE, "packet_path": {"type": "string", "description": "e.g. /workspace/cases/DSP-1042/argument.pdf"},
                                 "claims": _CLAIMS}, ["dispute_id", "packet_path", "claims"]),
    },
    {
        "name": "submit_evidence",
        "description": "Submit the evidence packet to the card processor. Requires the merchant's approval. "
        "Only call after check_packet reports no problems.",
        "input_schema": _schema({**_CASE, "packet_path": {"type": "string"}, "claims": _CLAIMS,
                                 "summary": {"type": "string", "description": "Two-sentence summary for the merchant."}},
                                ["dispute_id", "packet_path", "claims", "summary"]),
    },
    {
        "name": "accept_dispute",
        "description": "Accept the dispute and let the cardholder keep the refund, when the merchant is at fault "
        "or the evidence cannot win. Requires the merchant's approval.",
        "input_schema": _schema({**_CASE, "rationale": {"type": "string"}}, ["dispute_id", "rationale"]),
    },
]

TOOL_NAMES = {t["name"] for t in TOOL_DEFS}
APPROVAL_TOOLS = {"submit_evidence", "accept_dispute"}
ACTIVITY = {
    "list_disputes": "Reviewing the dispute queue",
    "get_dispute": "Reading the cardholder's claim",
    "get_order": "Pulling the order and payment records",
    "get_customer_history": "Checking this customer's order history",
    "get_support_thread": "Reading support emails",
    "get_billing_records": "Checking refunds and billing",
    "request_partner_evidence": "Asking ShipCo for proof",
    "ask_merchant": "Asking you a question",
    "pin_evidence": "Pinning evidence",
    "set_strategy": "Deciding the strategy",
    "check_packet": "Running the vault check",
    "submit_evidence": "Submitting the packet",
    "accept_dispute": "Accepting the dispute",
}


@dataclass
class ToolResult:
    value: Any
    is_error: bool = False
    images: list[str] = field(default_factory=list)  # file paths shown to the model

    def content(self) -> list[dict[str, Any]]:
        blocks: list[dict[str, Any]] = [{"type": "json", "value": self.value}]
        for path in self.images:
            with open(path, "rb") as fh:
                data = base64.b64encode(fh.read()).decode()
            blocks.append({"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": data}})
        return blocks


class ToolError(Exception):
    pass


def _d(iso_ts: str | None) -> str:
    return (iso_ts or "").replace("T", " ").replace("Z", " UTC")[:16]


class ToolRouter:
    def __init__(self, world: World, vault: Vault, cases: CaseBook, processor: Processor,
                 rooms: Rooms, approvals: Approvals, bus: EventBus) -> None:
        self.world = world
        self.vault = vault
        self.cases = cases
        self.processor = processor
        self.rooms = rooms
        self.approvals = approvals
        self.bus = bus
        self.packet_loader: PacketLoader | None = None
        self.prepared: dict[str, dict[str, Any]] = {}  # case -> last vault-checked packet

    # ---- dispatch -----------------------------------------------------------------

    async def call(self, name: str, args: dict[str, Any], *, case_hint: str | None = None) -> ToolResult:
        call_id = uuid.uuid4().hex[:10]
        case_id = str(args.get("dispute_id") or case_hint or "")
        started = time.monotonic()
        self._feed(case_id, call_id, name, "start", args=args)
        if case_id and name in ACTIVITY and case_id in self.cases.cases:
            case = self.cases.get(case_id)
            status = "investigating" if case.status in {"new", "investigating"} else case.status
            self.cases.update(case_id, activity=ACTIVITY[name], status=status)
        try:
            handler = getattr(self, f"_t_{name}", None)
            if handler is None:
                raise ToolError(f"Unknown tool {name}")
            result = await handler(args)
        except (ToolError, KeyError, ValueError) as err:
            result = ToolResult({"error": str(err).strip("'\"")}, is_error=True)
        self._feed(case_id, call_id, name, "end", result=result.value, error=result.is_error,
                   ms=int((time.monotonic() - started) * 1000))
        return result

    def _feed(self, case_id: str, call_id: str, tool: str, phase: str, **extra: Any) -> None:
        item = {"id": f"{call_id}-{phase}", "call_id": call_id, "case_id": case_id, "channel": "zoo",
                "kind": "tool", "tool": tool, "phase": phase, "custom": True, "ts": time.time()}
        if "args" in extra:
            item["args"] = extra["args"]
        if "result" in extra:
            item["preview"] = json.dumps(extra["result"], default=str)[:400]
            item["error"] = extra["error"]
            item["ms"] = extra["ms"]
        self.bus.publish("feed", item=item)

    def _dispute(self, args: dict[str, Any]) -> dict[str, Any]:
        did = str(args.get("dispute_id", "")).strip().upper()
        if did not in self.world.disputes:
            raise ToolError(f"Unknown dispute {did!r}. Open disputes: {', '.join(self.world.disputes)}")
        return self.world.disputes[did]

    @staticmethod
    def _ex(exhibits: list[Exhibit]) -> list[dict[str, Any]]:
        return [e.for_agent() for e in exhibits]

    # ---- read tools ---------------------------------------------------------------

    async def _t_list_disputes(self, args: dict[str, Any]) -> ToolResult:
        rows = []
        for d in self.world.disputes.values():
            case = self.cases.get(d["id"])
            rows.append({"dispute_id": d["id"], "amount": d["amount"], "reason": d["reason"],
                         "network_code": d["network_code"], "customer": d["customer_name"], "item": d["item"],
                         "respond_by": d["respond_by"], "status": case.status})
        return ToolResult({"merchant": MERCHANT["name"], "disputes": rows})

    async def _t_get_dispute(self, args: dict[str, Any]) -> ToolResult:
        d = self._dispute(args)
        return ToolResult({**{k: d[k] for k in ("id", "order_id", "charge_id", "amount", "currency", "network",
                                                   "reason", "network_code", "reason_label", "customer_name",
                                                   "customer_email", "item", "cardholder_claim", "opened_at",
                                                   "respond_by")},
                           "evidence_that_wins": self.processor.requirements(d["reason"])})

    async def _t_get_order(self, args: dict[str, Any]) -> ToolResult:
        d = self._dispute(args)
        o = self.world.orders[d["order_id"]]
        pay, ship = o["payment"], o["shipping"]
        exhibits = [
            self.vault.add(
                d["id"], "payment_verification", kind="payment",
                title="Payment verification (AVS, CVV, IP, device)", source="Payments (order database)",
                summary=f"{pay['card_brand']} ****{pay['last4']}: AVS {pay['avs']}, CVV {pay['cvv']}, "
                f"IP {pay['ip']}, device {pay['device_id']}.",
                rows=[["Charge", pay["charge_id"]], ["Card", f"{pay['card_brand']} **** {pay['last4']}"],
                      ["AVS", pay["avs"]], ["CVV", pay["cvv"]], ["3-D Secure", pay["three_ds"]],
                      ["IP address", pay["ip"]], ["Device ID", pay["device_id"]],
                      ["Billing address", pay["billing_address"]], ["Placed", _d(o["placed_at"])]],
            ),
            self.vault.add(
                d["id"], "checkout_terms", kind="policy", title="Checkout terms and refund policy acceptance",
                source="Storefront checkout log",
                summary=f"The cardholder ticked 'I agree to the Terms & Refund Policy' at "
                f"{_d(o['checkout']['terms_accepted_at'])}. Policy: {MERCHANT['refund_policy']}",
                rows=[["Accepted at", _d(o["checkout"]["terms_accepted_at"])],
                      ["Refund policy", MERCHANT["refund_policy"]]],
            ),
        ]
        if ship.get("shipped_at"):
            exhibits.append(self.vault.add(
                d["id"], "order_shipping", kind="tracking", title="Order shipping record",
                source="Order database",
                summary=f"Shipped {_d(ship['shipped_at'])} via {ship['carrier']} {ship['tracking']} to "
                f"{ship['address']}; carrier reports delivered {_d(ship['delivered_at'])}.",
                rows=[["Carrier", ship["carrier"]], ["Tracking", ship["tracking"]],
                      ["Ship to", ship["address"]], ["Shipped", _d(ship["shipped_at"])],
                      ["Delivered", _d(ship["delivered_at"])]],
            ))
        if "product_page" in o:
            page = o["product_page"]
            exhibits.append(self.vault.add(
                d["id"], "product_page", kind="product", title="Archived product page at time of purchase",
                source="Storefront page archive",
                summary=f"Captured {_d(page['captured_at'])}: " + "; ".join(page["claims"]),
                rows=[["URL", page["url"]], ["Captured", _d(page["captured_at"])]] + [["Claim", c] for c in page["claims"]],
                image=page["image"],
            ))
        order = {k: o[k] for k in ("id", "placed_at", "items", "total", "currency")}
        order["payment"] = {k: pay[k] for k in ("charge_id", "card_brand", "last4", "avs", "cvv", "three_ds", "ip", "device_id", "billing_address")}
        if "duplicate_charge" in pay:
            order["payment"]["duplicate_charge"] = pay["duplicate_charge"]
        order["shipping"] = ship
        return ToolResult({"order": order, "exhibits": self._ex(exhibits)})

    async def _t_get_customer_history(self, args: dict[str, Any]) -> ToolResult:
        d = self._dispute(args)
        history = [r for r in self.world.customer_history(d["customer_email"]) if r["order_id"] != d["order_id"]]
        qualifying = ce3_qualifying(self.world, d)
        exhibits = []
        if history:
            key = "ce3_history" if len(qualifying) >= 2 else "customer_history"
            summary = (
                f"{len(qualifying)} prior undisputed orders, {', '.join(str(q['age_days']) for q in qualifying)} days "
                "before the dispute, share " + " and ".join(sorted({m for q in qualifying for m in q['matches']}))
                + " with the disputed purchase (Visa CE 3.0)."
                if qualifying else f"{len(history)} earlier orders; none meet Visa CE 3.0."
            )
            exhibits.append(self.vault.add(
                d["id"], key, kind="history", title="Prior undisputed orders (Visa CE 3.0)" if qualifying else "Customer order history",
                source="Order database", summary=summary,
                rows=[[f"{r['order_id']} ({_d(r['placed_at'])[:10]})",
                       f"${r['total']:,.2f}  IP {r['ip']}  device {r['device_id']}  {r['shipping_address']}"
                       f"{'  DISPUTED' if r['disputed'] else ''}"] for r in history],
            ))
        return ToolResult({"prior_orders": history,
                           "ce3": {"eligible": len(qualifying) >= 2, "qualifying_orders": [q["order_id"] for q in qualifying],
                                   "rule": "2+ undisputed orders 120-365 days old sharing 2+ of IP/device/address/account (one must be IP or device)"},
                           "exhibits": self._ex(exhibits)})

    async def _t_get_support_thread(self, args: dict[str, Any]) -> ToolResult:
        d = self._dispute(args)
        thread = self.world.support.get(d["order_id"], [])
        delivered = self.world.orders[d["order_id"]]["shipping"].get("delivered_at")
        exhibits = []
        n = 0
        for msg in thread:
            if msg["from"] == d["customer_email"]:
                n += 1
                after = bool(delivered and msg["at"] > delivered)
                exhibits.append(self.vault.add(
                    d["id"], f"support_email_{n}", kind="email",
                    title="Cardholder email after delivery" if after else "Cardholder email",
                    source="Support desk", summary=f"{_d(msg['at'])}, {msg['from']}: “{msg['body']}”",
                    rows=[["From", msg["from"]], ["Sent", _d(msg["at"])], ["Subject", msg["subject"]]],
                    body=msg["body"],
                ))
        if not thread:
            exhibits.append(self.vault.add(
                d["id"], "support_none", kind="email", title="No contact from the cardholder",
                source="Support desk",
                summary="The cardholder never contacted support, reported a problem or requested a return "
                "before disputing the charge.",
                rows=[["Support tickets", "0"], ["Return requests", "0"], ["Searched", "email, chat, returns portal"]],
            ))
        return ToolResult({"messages": thread, "exhibits": self._ex(exhibits)})

    async def _t_get_billing_records(self, args: dict[str, Any]) -> ToolResult:
        d = self._dispute(args)
        o = self.world.orders[d["order_id"]]
        exhibits = []
        refund = self.world.refunds.get(d["charge_id"])
        if refund:
            exhibits.append(self.vault.add(
                d["id"], "refund_record", kind="refund", title=f"Refund {refund['refund_id']} for {refund['charge_id']}",
                source="Payments (refund ledger)",
                summary=f"${refund['amount']:,.2f} refunded on {_d(refund['created_at'])}, before the dispute "
                f"opened ({_d(d['opened_at'])}). Acquirer reference {refund['arn']}.",
                rows=[["Refund", refund["refund_id"]], ["Charge", refund["charge_id"]],
                      ["Amount", f"${refund['amount']:,.2f}"], ["Refunded", _d(refund["created_at"])],
                      ["ARN", refund["arn"]], ["Status", refund["status"]]],
            ))
        sub = self.world.subscriptions.get(d["customer_email"])
        if sub:
            exhibits.append(self.vault.add(
                d["id"], "subscription_log", kind="subscription", title=f"Subscription log: {sub['plan']}",
                source="Billing system",
                summary="; ".join(f"{_d(e['at'])} {e['event']}" for e in sub["events"][-3:]),
                rows=[[_d(e["at"]), e["event"] + (f" ({e['note']})" if e.get("note") else "")] for e in sub["events"]],
            ))
        return ToolResult({"disputed_charge": d["charge_id"],
                           "refunds": [refund] if refund else [],
                           "duplicate_charge": o["payment"].get("duplicate_charge"),
                           "subscription": sub, "exhibits": self._ex(exhibits)})

    # ---- collaboration tools ----------------------------------------------------------

    async def _t_request_partner_evidence(self, args: dict[str, Any]) -> ToolResult:
        d = self._dispute(args)
        if str(args.get("partner", "")).lower() != "shipco":
            raise ToolError("Only partner 'shipco' is connected to this merchant.")
        reply = await self.rooms.ask_partner(d["id"], str(args.get("request", "")).strip())
        case = self.cases.get(d["id"])
        if case.status == "waiting_partner":
            self.cases.update(d["id"], status="investigating", activity="Reviewing ShipCo's evidence")
        return ToolResult({"partner": "ShipCo Warehouse", "reply": reply.text, "exhibits": self._ex(reply.exhibits)},
                          images=[str(reply.photo)] if reply.photo else [])

    async def _t_ask_merchant(self, args: dict[str, Any]) -> ToolResult:
        d = self._dispute(args)
        options = [str(o) for o in (args.get("options") or [])][:3]
        answer = await self.rooms.ask_merchant(d["id"], str(args.get("question", "")).strip(), options)
        images = [str(self.vault.image_path(self.vault.get(e["exhibit_id"])))  # type: ignore[arg-type]
                  for e in answer["shared_exhibits"] if self.vault.get(e["exhibit_id"]) and self.vault.get(e["exhibit_id"]).image]  # type: ignore[union-attr]
        return ToolResult({"merchant_answer": answer["text"], "shared_exhibits": answer["shared_exhibits"]}, images=images)

    async def _t_pin_evidence(self, args: dict[str, Any]) -> ToolResult:
        d = self._dispute(args)
        ex = self.vault.get(str(args.get("exhibit_id", "")))
        if ex is None or ex.case_id != d["id"]:
            raise ToolError(f"{args.get('exhibit_id')} is not an exhibit for {d['id']}. Pin only exhibits returned by tools.")
        case = self.cases.get(d["id"])
        if any(p["exhibit"]["id"] == ex.id for p in case.pins):
            return ToolResult({"pinned": ex.id, "note": "already pinned"})
        supports = str(args.get("supports", "")).strip()
        pin = {"exhibit": ex.public(), "supports": supports, "pinned_at": time.time()}
        self.cases.update(d["id"], pins=[*case.pins, pin])
        await self.rooms.say(d["id"], f"📌 Pinned {ex.id} · {ex.title}: {supports}", kind="pin", exhibit_id=ex.id)
        return ToolResult({"pinned": ex.id, "board": [p["exhibit"]["id"] for p in self.cases.get(d["id"]).pins]})

    async def _t_set_strategy(self, args: dict[str, Any]) -> ToolResult:
        d = self._dispute(args)
        decision = str(args.get("decision", "")).lower()
        if decision not in {"fight", "accept"}:
            raise ToolError("decision must be 'fight' or 'accept'")
        probability = max(0, min(100, int(args.get("win_probability", 0))))
        rationale = str(args.get("rationale", "")).strip()
        self.cases.update(d["id"], strategy=decision, win_probability=probability, rationale=rationale)
        verb = "Fighting" if decision == "fight" else "Recommending we accept"
        await self.rooms.say(d["id"], f"🧭 {verb} {d['id']} ({probability}% win chance). {rationale}", kind="strategy")
        return ToolResult({"dispute_id": d["id"], "strategy": decision, "win_probability": probability})

    # ---- packet and money-moving tools ----------------------------------------------

    async def prepare(self, case_id: str, packet_path: str, claims: list[dict[str, Any]]) -> dict[str, Any]:
        """Vault check + assembly. Shared by check_packet, approval previews and submit."""
        case = self.cases.get(case_id)
        claims = [{"text": str(c.get("text", "")), "exhibit_ids": [str(i).strip().upper() for i in c.get("exhibit_ids", [])]}
                  for c in claims]
        problems = self.processor.check_claims(case.id, claims)
        if self.packet_loader is None:
            raise ToolError("No packet loader configured")
        try:
            argument = await self.packet_loader(case.id, packet_path)
        except Exception as err:  # noqa: BLE001 - surface to the agent as a fixable problem
            problems.append(f"Could not load {packet_path}: {err}. Publish the PDF with artifact_publish first.")
            argument = b""
        result: dict[str, Any] = {"ok": not problems, "problems": problems, "claims": claims}
        if argument and not any("not in the evidence vault" in p or "belongs to" in p for p in problems):
            packet = assemble_packet(case, argument, claims, self.vault)
            result["packet"] = packet
            self.cases.update(case.id, claims=claims, packet=packet,
                              status="drafting" if case.status not in {"awaiting_approval"} else case.status,
                              activity="Vault check passed" if not problems else "Fixing vault check problems")
        self.prepared[case.id] = result
        return result

    async def _t_check_packet(self, args: dict[str, Any]) -> ToolResult:
        d = self._dispute(args)
        result = await self.prepare(d["id"], str(args.get("packet_path", "")), list(args.get("claims") or []))
        packet = result.get("packet") or {}
        if result["ok"]:
            await self.rooms.say(d["id"], f"🔐 Vault check passed: {len(result['claims'])} findings, "
                                 f"{len(packet.get('exhibits', []))} original exhibits fingerprinted, "
                                 f"{packet.get('page_count', 0)} pages.", kind="system_note")
        return ToolResult({"ok": result["ok"], "problems": result["problems"],
                           "pages": packet.get("page_count"), "exhibits_attached": packet.get("exhibits"),
                           "packet_sha256": packet.get("sha256")}, is_error=not result["ok"])

    def approval_preview(self, case_id: str, tool: str, args: dict[str, Any], prepared: dict[str, Any] | None) -> dict[str, Any]:
        case = self.cases.get(case_id)
        packet = (prepared or {}).get("packet") or case.packet or {}
        claims = (prepared or {}).get("claims") or case.claims
        exhibits = [self.vault.get(i).public() for i in packet.get("exhibits", []) if self.vault.get(i)]  # type: ignore[union-attr]
        checks = [
            {"label": "Every finding cites vault evidence", "ok": bool(prepared and prepared.get("ok")) or tool == "accept_dispute"},
            {"label": "Original exhibits attached with SHA-256", "ok": bool(packet.get("exhibits")) or tool == "accept_dispute"},
            {"label": f"Before the deadline ({_d(case.respond_by)})", "ok": True},
        ]
        return {"amount": case.amount, "case": case.public(), "summary": args.get("summary") or args.get("rationale", ""),
                "claims": claims, "packet": packet if tool == "submit_evidence" else None,
                "exhibits": exhibits, "checks": checks, "win_probability": case.win_probability}

    async def _gate(self, case_id: str, tool: str, args: dict[str, Any], prepared: dict[str, Any] | None) -> bool:
        """Approval: granted upstream by ZooWork's always_ask gate, or asked here when simulated."""
        if self.approvals.consume_grant(case_id, tool):
            return True
        approval = self.approvals.open(case_id, tool, args, self.approval_preview(case_id, tool, args, prepared))
        return await self.approvals.wait(approval.id) == "approve"

    async def _t_submit_evidence(self, args: dict[str, Any]) -> ToolResult:
        d = self._dispute(args)
        prepared = await self.prepare(d["id"], str(args.get("packet_path", "")), list(args.get("claims") or []))
        if not prepared["ok"]:
            return ToolResult({"submitted": False, "problems": prepared["problems"]}, is_error=True)
        if not await self._gate(d["id"], "submit_evidence", args, prepared):
            self.cases.update(d["id"], status="drafting", activity="Merchant held the submission")
            return ToolResult({"submitted": False, "reason": "The merchant declined to submit. Ask what to change."})
        receipt = self.processor.submit(d["id"], prepared["claims"], prepared["packet"])
        await self.rooms.say(d["id"], f"📨 Packet submitted to the processor ({prepared['packet']['page_count']} pages, "
                             f"sha256 {prepared['packet']['sha256'][:12]}...). Issuer is reviewing.", kind="submitted")
        return ToolResult(receipt)

    async def _t_accept_dispute(self, args: dict[str, Any]) -> ToolResult:
        d = self._dispute(args)
        if not await self._gate(d["id"], "accept_dispute", args, None):
            self.cases.update(d["id"], status="investigating", activity="Merchant wants to keep fighting")
            return ToolResult({"accepted": False, "reason": "The merchant declined. Ask what they want to do."})
        result = self.processor.accept(d["id"], str(args.get("rationale", "")))
        await self.rooms.say(d["id"], f"🤝 Accepted {d['id']} and refunded ${d['amount']:,.2f}. "
                             f"{args.get('rationale', '')}", kind="accepted")
        return ToolResult(result)
