"""Per-dispute case files: the state the dashboard renders."""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from typing import Any

from .bus import EventBus
from .world import World

CAPY_FEE_RATE = 0.20  # Capy is paid only on recovered dollars

STATUS_LABELS = {
    "new": "New",
    "investigating": "Investigating",
    "waiting_partner": "Waiting on ShipCo",
    "waiting_merchant": "Needs you",
    "drafting": "Writing packet",
    "awaiting_approval": "Ready to submit",
    "submitted": "Issuer reviewing",
    "won": "Won",
    "lost": "Lost",
    "accepted": "Accepted",
}


@dataclass
class CaseFile:
    id: str
    order_id: str
    charge_id: str
    amount: float
    reason: str
    network_code: str
    reason_label: str
    customer_name: str
    customer_email: str
    item: str
    claim: str
    opened_at: str
    respond_by: str
    status: str = "new"
    strategy: str | None = None  # fight | accept
    win_probability: int | None = None
    rationale: str = ""
    activity: str = ""  # what the inspector is doing right now
    pins: list[dict[str, Any]] = field(default_factory=list)
    claims: list[dict[str, Any]] = field(default_factory=list)
    attention: list[dict[str, Any]] = field(default_factory=list)
    room: dict[str, Any] | None = None
    packet: dict[str, Any] | None = None
    decision: dict[str, Any] | None = None
    session_id: str | None = None
    updated_at: float = field(default_factory=time.time)

    def public(self) -> dict[str, Any]:
        data = asdict(self)
        data["status_label"] = STATUS_LABELS.get(self.status, self.status)
        return data


class CaseBook:
    def __init__(self, world: World, bus: EventBus) -> None:
        self.bus = bus
        self.cases: dict[str, CaseFile] = {}
        for d in world.disputes.values():
            self.cases[d["id"]] = CaseFile(
                id=d["id"],
                order_id=d["order_id"],
                charge_id=d["charge_id"],
                amount=d["amount"],
                reason=d["reason"],
                network_code=d["network_code"],
                reason_label=d["reason_label"],
                customer_name=d["customer_name"],
                customer_email=d["customer_email"],
                item=d["item"],
                claim=d["cardholder_claim"],
                opened_at=d["opened_at"],
                respond_by=d["respond_by"],
            )

    def get(self, case_id: str) -> CaseFile:
        key = case_id.strip().upper()
        if key not in self.cases:
            raise KeyError(f"Unknown dispute id {case_id!r}. Known: {', '.join(self.cases)}")
        return self.cases[key]

    def update(self, case_id: str, **changes: Any) -> CaseFile:
        case = self.get(case_id)
        for key, value in changes.items():
            setattr(case, key, value)
        case.updated_at = time.time()
        self.bus.publish("case", case=case.public())
        self.bus.publish("stats", stats=self.stats())
        return case

    def touch(self, case_id: str) -> None:
        self.update(case_id)

    def stats(self) -> dict[str, Any]:
        cases = list(self.cases.values())
        at_risk = sum(c.amount for c in cases if c.status not in {"won", "lost", "accepted"})
        recovered = sum(c.amount for c in cases if c.status == "won")
        lost = sum(c.amount for c in cases if c.status == "lost")
        accepted = sum(c.amount for c in cases if c.status == "accepted")
        decided = [c for c in cases if c.status in {"won", "lost"}]
        won = [c for c in decided if c.status == "won"]
        return {
            "total": len(cases),
            "open": sum(1 for c in cases if c.status not in {"won", "lost", "accepted"}),
            "at_risk": round(at_risk, 2),
            "recovered": round(recovered, 2),
            "lost": round(lost, 2),
            "accepted": round(accepted, 2),
            "won_count": len(won),
            "decided_count": len(decided),
            "win_rate": round(len(won) / len(decided), 3) if decided else None,
            "fee": round(recovered * CAPY_FEE_RATE, 2),
            "fee_rate": CAPY_FEE_RATE,
        }

    def snapshot(self) -> dict[str, Any]:
        return {
            "cases": [c.public() for c in sorted(self.cases.values(), key=lambda c: c.id)],
            "stats": self.stats(),
        }
