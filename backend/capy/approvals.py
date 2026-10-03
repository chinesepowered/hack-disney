"""Merchant approvals for actions that move money (submit evidence, accept a dispute).

Live, the gate is ZooWork's always_ask permission: the approval id comes from
the agent.approval event and the merchant's click resolves it on ZooWork.
Simulated sweeps open approvals with a local id. Either way the dashboard sees
one 'approval' event and answers through /api/approvals/{id}.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from .bus import EventBus
from .cases import CaseBook


@dataclass
class Approval:
    id: str
    case_id: str
    tool: str
    args: dict[str, Any]
    preview: dict[str, Any]
    created_at: float = field(default_factory=time.time)
    status: str = "pending"
    future: asyncio.Future[str] | None = None

    def public(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "case_id": self.case_id,
            "tool": self.tool,
            "args": self.args,
            "preview": self.preview,
            "created_at": self.created_at,
            "status": self.status,
        }


class Approvals:
    def __init__(self, bus: EventBus, cases: CaseBook) -> None:
        self.bus = bus
        self.cases = cases
        self.items: dict[str, Approval] = {}
        # Approval granted at the platform gate, consumed by the tool call that follows it.
        self._granted: dict[tuple[str, str], str] = {}

    def open(self, case_id: str, tool: str, args: dict[str, Any], preview: dict[str, Any],
             approval_id: str | None = None) -> Approval:
        approval = Approval(
            id=approval_id or f"apr_sim_{uuid.uuid4().hex[:10]}",
            case_id=case_id,
            tool=tool,
            args=args,
            preview=preview,
            future=asyncio.get_running_loop().create_future(),
        )
        self.items[approval.id] = approval
        self.cases.update(case_id, status="awaiting_approval",
                          activity="Waiting for your approval")
        self.bus.publish("approval", approval=approval.public())
        return approval

    async def wait(self, approval_id: str) -> str:
        approval = self.items[approval_id]
        assert approval.future is not None
        return await approval.future

    def resolve(self, approval_id: str, decision: str, by: str = "merchant") -> Approval:
        approval = self.items.get(approval_id)
        if approval is None:
            raise KeyError(approval_id)
        if approval.status != "pending":
            return approval
        approval.status = "approved" if decision == "approve" else "denied"
        if approval.status == "approved":
            self._granted[(approval.case_id, approval.tool)] = approval.id
        if approval.future and not approval.future.done():
            approval.future.set_result(decision)
        self.bus.publish("approval_resolved", approval_id=approval.id, case_id=approval.case_id,
                         decision=approval.status, by=by)
        return approval

    def consume_grant(self, case_id: str, tool: str) -> bool:
        return self._granted.pop((case_id, tool), None) is not None

    def pending(self) -> list[dict[str, Any]]:
        return [a.public() for a in self.items.values() if a.status == "pending"]
