"""End-to-end: a scripted sweep over all five disputes, merchant approving everything."""

from __future__ import annotations

import asyncio
import os
import tempfile

os.environ.update({"CAPY_ZOOWORK": "off", "CAPY_BAND": "off", "CAPY_PACE": "0", "CAPY_ISSUER_DELAY": "0.05",
                   "CAPY_DATA_DIR": tempfile.mkdtemp(prefix="capy-test-")})

from capy.app import CapyApp  # noqa: E402
from capy.config import load_settings  # noqa: E402


async def _merchant(app: CapyApp, stop: asyncio.Event) -> None:
    """Approve every request and share the lab report when asked."""
    replied = False
    while not stop.is_set():
        for approval in app.approvals.pending():
            app.resolve_approval(approval["id"], "approve")
        case = app.cases.cases["DSP-1045"]
        if not replied and any(a["status"] == "open" for a in case.attention):
            await app.reply("DSP-1045", "Yes, here's the lab report from Cascade Textile Labs.", "lab_report")
            replied = True
        await asyncio.sleep(0.01)


async def test_full_sweep_outcomes() -> None:
    app = CapyApp(load_settings())
    await app.startup()
    events = app.bus.subscribe()
    stop = asyncio.Event()
    merchant = asyncio.create_task(_merchant(app, stop))
    await app.start_sweep("scripted")
    await asyncio.wait_for(app._sweep_task, timeout=60)  # type: ignore[arg-type]
    stop.set()
    await merchant

    status = {cid: c.status for cid, c in app.cases.cases.items()}
    assert status == {
        "DSP-1042": "won",
        "DSP-1043": "won",
        "DSP-1044": "accepted",
        "DSP-1045": "won",
        "DSP-1046": "won",
    }
    stats = app.cases.stats()
    assert stats["recovered"] == 389 + 1240 + 149 + 64
    assert stats["accepted"] == 29
    assert stats["win_rate"] == 1.0

    # every submitted packet carries its argument plus fingerprinted originals
    for cid in ("DSP-1042", "DSP-1043", "DSP-1045", "DSP-1046"):
        packet = app.cases.cases[cid].packet
        assert packet and packet["page_count"] >= 3 and len(packet["sha256"]) == 64

    # the vault rejected the unsupported claim in DSP-1042 before it was fixed
    seen = []
    while not events.empty():
        seen.append(events.get_nowait())
    checks = [e for e in seen if e["type"] == "feed" and e["item"].get("tool") == "check_packet"
              and e["item"].get("case_id") == "DSP-1042" and e["item"]["phase"] == "end"]
    assert [c["item"]["error"] for c in checks] == [True, False]
    assert len(app.cases.cases["DSP-1042"].claims) == 4
    await app.shutdown()


async def test_merchant_can_hold_a_submission() -> None:
    app = CapyApp(load_settings())
    await app.startup()
    await app.start_sweep("scripted", cases=["DSP-1046"])
    for _ in range(500):
        if app.approvals.pending():
            break
        await asyncio.sleep(0.01)
    approval = app.approvals.pending()[0]
    assert approval["tool"] == "submit_evidence"
    assert approval["preview"]["packet"]["page_count"] >= 3
    app.resolve_approval(approval["id"], "deny")
    await asyncio.wait_for(app._sweep_task, timeout=30)  # type: ignore[arg-type]
    assert app.cases.cases["DSP-1046"].status == "drafting"
    await app.shutdown()
