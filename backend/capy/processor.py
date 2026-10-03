"""A simulated card processor and issuer.

Real issuer decisions take weeks. This one rules in seconds, using simplified
versions of the evidence each Visa reason code needs, so the demo shows the
consequence of a strong or weak packet. It judges only the exhibits a claim
cites, never the inspector's prose.
"""

from __future__ import annotations

import asyncio
import time
from datetime import datetime
from typing import Any

from .bus import EventBus
from .cases import CaseBook
from .exhibits import Exhibit, Vault
from .world import World

# What wins each reason code. Shown to the inspector via get_dispute so it knows
# what to look for (mirrors the networks' published compelling-evidence lists).
REQUIREMENTS: dict[str, list[str]] = {
    "product_not_received": [
        "Carrier tracking showing delivery to the cardholder's address",
        "Proof the cardholder had the goods: delivery photo, signature, or cardholder "
        "communication after delivery",
    ],
    "fraudulent": [
        "Visa Compelling Evidence 3.0: two or more prior undisputed transactions on the same card, "
        "120-365 days before the dispute, sharing at least two of IP address, device ID, shipping "
        "address and account ID (one must be IP or device)",
        "Supporting: AVS/CVV match, delivery to the billing address, signature",
    ],
    "subscription_canceled": [
        "Proof the cardholder did NOT cancel before the renewal, or that they used the service "
        "after the cancellation date. If they cancelled first, accept the dispute.",
    ],
    "product_unacceptable": [
        "What the product page promised at the time of purchase",
        "Independent proof the item meets that description (test report, specification)",
        "Return/refund policy shown at checkout and evidence the cardholder did not try to return it",
    ],
    "duplicate": [
        "Proof the duplicate charge was already refunded (refund record with reference number), "
        "or that both charges were for separate goods",
    ],
}


def _parse(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def ce3_qualifying(world: World, dispute: dict[str, Any]) -> list[dict[str, Any]]:
    """Prior orders that satisfy Visa CE 3.0 for this dispute."""
    order = world.orders[dispute["order_id"]]
    pay = order["payment"]
    opened = _parse(dispute["opened_at"])
    qualifying = []
    for row in world.customer_history(dispute["customer_email"]):
        if row["order_id"] == order["id"] or row["disputed"]:
            continue
        age = (opened - _parse(row["placed_at"])).days
        if not 120 <= age <= 365:
            continue
        matches = []
        if row["ip"] == pay["ip"]:
            matches.append("ip")
        if row["device_id"] == pay["device_id"]:
            matches.append("device")
        if row["shipping_address"] == order["shipping"]["address"]:
            matches.append("shipping_address")
        if row["account_id"] == world.customers[dispute["customer_email"]]["account_id"]:
            matches.append("account_id")
        if len(matches) >= 2 and {"ip", "device"} & set(matches):
            qualifying.append({**row, "age_days": age, "matches": matches})
    return qualifying


class Processor:
    def __init__(self, world: World, vault: Vault, cases: CaseBook, bus: EventBus, issuer_delay: float) -> None:
        self.world = world
        self.vault = vault
        self.cases = cases
        self.bus = bus
        self.issuer_delay = issuer_delay
        self._tasks: set[asyncio.Task[None]] = set()

    def requirements(self, reason: str) -> list[str]:
        return REQUIREMENTS.get(reason, [])

    # ---- packet checks --------------------------------------------------------

    def check_claims(self, case_id: str, claims: list[dict[str, Any]]) -> list[str]:
        """The vault rule: no source, no claim."""
        problems = []
        if not claims:
            problems.append("The packet has no claims.")
        for n, claim in enumerate(claims, 1):
            text = str(claim.get("text", "")).strip()
            ids = claim.get("exhibit_ids") or []
            if not text:
                problems.append(f"Claim {n} is empty.")
            if not ids:
                problems.append(f"Claim {n} ({text[:60]!r}) cites no exhibit. No source, no claim.")
            for ex_id in ids:
                ex = self.vault.get(str(ex_id))
                if ex is None:
                    problems.append(f"Claim {n} cites {ex_id}, which is not in the evidence vault.")
                elif ex.case_id != case_id:
                    problems.append(f"Claim {n} cites {ex_id}, which belongs to {ex.case_id}.")
        return problems

    # ---- outcomes -------------------------------------------------------------

    def submit(self, case_id: str, claims: list[dict[str, Any]], packet: dict[str, Any]) -> dict[str, Any]:
        case = self.cases.get(case_id)
        receipt = {
            "submission_id": f"sub_{case_id.lower()}_{int(time.time())}",
            "dispute_id": case_id,
            "status": "under_review",
            "packet_sha256": packet.get("sha256"),
            "pages": packet.get("page_count"),
            "note": "Simulated issuer: rules in seconds instead of weeks.",
        }
        self.cases.update(case.id, status="submitted", activity="Issuer reviewing the packet")
        self.world.disputes[case.id]["status"] = "under_review"
        task = asyncio.create_task(self._rule(case.id, claims))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return receipt

    def accept(self, case_id: str, rationale: str) -> dict[str, Any]:
        case = self.cases.get(case_id)
        self.world.disputes[case.id]["status"] = "accepted"
        decision = {
            "status": "accepted",
            "amount": case.amount,
            "reasons": [rationale or "Merchant accepted the dispute and refunded the cardholder."],
            "decided_at": time.time(),
        }
        self.cases.update(case.id, status="accepted", decision=decision, activity="Accepted and refunded")
        self.bus.publish("decision", case_id=case.id, **decision)
        return {"dispute_id": case.id, "status": "accepted", "refunded": case.amount}

    async def _rule(self, case_id: str, claims: list[dict[str, Any]]) -> None:
        await asyncio.sleep(self.issuer_delay)
        case = self.cases.get(case_id)
        cited = [ex for c in claims for i in c.get("exhibit_ids", []) if (ex := self.vault.get(str(i)))]
        won, reasons = self._evaluate(case_id, case.reason, cited)
        status = "won" if won else "lost"
        self.world.disputes[case_id]["status"] = status
        decision = {"status": status, "amount": case.amount, "reasons": reasons, "decided_at": time.time()}
        self.cases.update(case_id, status=status, decision=decision,
                          activity="Funds returned to merchant" if won else "Issuer sided with cardholder")
        self.bus.publish("decision", case_id=case_id, **decision)

    def _evaluate(self, case_id: str, reason: str, cited: list[Exhibit]) -> tuple[bool, list[str]]:
        keys = {ex.key for ex in cited}
        has = lambda *prefixes: any(k.startswith(p) for k in keys for p in prefixes)  # noqa: E731
        dispute = self.world.disputes[case_id]

        if reason == "product_not_received":
            delivered = has("shipco_tracking", "order_shipping")
            possession = has("shipco_pod_photo", "signature", "support_email")
            if delivered and possession:
                why = ["Carrier confirms delivery at the cardholder's address."]
                if has("shipco_pod_photo"):
                    why.append("Delivery photo shows the parcel at the door, GPS within metres of the address.")
                if has("support_email"):
                    why.append("Cardholder wrote to the merchant about the item after it was delivered.")
                return True, why
            return False, ["Proof of delivery to the cardholder was not established."]

        if reason == "fraudulent":
            qualifying = ce3_qualifying(self.world, dispute)
            if has("ce3_history") and len(qualifying) >= 2:
                return True, [
                    f"Compelling Evidence 3.0 met: {len(qualifying)} prior undisputed orders share "
                    "device and address with this purchase.",
                    "Liability shifts back to the issuer; the cardholder's claim is rejected.",
                ]
            return False, ["Insufficient evidence that the cardholder authorised the purchase."]

        if reason == "subscription_canceled":
            return False, ["Records show the cardholder cancelled before the renewal was charged."]

        if reason == "product_unacceptable":
            if has("product_page") and has("lab_report") and has("support_none", "checkout_terms"):
                return True, [
                    "The item matched its advertised 10,000 mm waterproof rating (independent lab test).",
                    "The cardholder never contacted the merchant or used the 30-day return policy.",
                ]
            if has("product_page") and not has("lab_report"):
                return False, ["Nothing independent shows the item met its waterproof claim."]
            return False, ["The item was not shown to match its description."]

        if reason == "duplicate":
            if has("refund_record"):
                return True, ["The duplicate charge was refunded before the dispute (refund ARN provided)."]
            return False, ["No proof the duplicate charge was refunded."]

        return False, ["Unsupported reason code."]
