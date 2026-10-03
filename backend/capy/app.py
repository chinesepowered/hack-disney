"""Application container: one merchant world, the sponsors' connections, and sweeps."""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from typing import Any

from .approvals import Approvals
from .band import BandLive
from .bus import EventBus
from .cases import CaseBook
from .config import Settings
from .exhibits import Vault
from .processor import Processor
from .rooms import Rooms
from .sim import SimInspector
from .tools import ToolRouter
from .world import MERCHANT, build_world
from .zoo import ZooInspector, ZooRunFailed

log = logging.getLogger("capy.app")

STAGGER = 1.6  # seconds between case starts, so the inbox lights up one by one
# The scripted inspector starts cases in story order: the honest refund first, then the
# delivery-photo case reaches its approval before the quicker ones.
SCRIPTED_START = {"DSP-1042": 0.0, "DSP-1044": 1.6, "DSP-1043": 3.2, "DSP-1045": 4.8, "DSP-1046": 12.0}


class CapyApp:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.bus = EventBus()
        self.bus.snapshot_provider = self.snapshot
        self.band: BandLive | None = None
        self.zoo: ZooInspector | None = None
        self.band_error: str | None = None
        self.sweep: dict[str, Any] = {"status": "idle"}
        self._sweep_task: asyncio.Task[None] | None = None
        self.build()

    # ---- world -----------------------------------------------------------------------

    def build(self, *, use_band: bool = True) -> None:
        self.world = build_world()
        self.vault = Vault(self.world)
        self.cases = CaseBook(self.world, self.bus)
        self.processor = Processor(self.world, self.vault, self.cases, self.bus, self.settings.issuer_delay)
        self.rooms = Rooms(self.world, self.vault, self.cases, self.bus,
                           self.band if use_band else None, self.settings.pace)
        self.processor.on_decision = self.rooms.announce_decision
        self.approvals = Approvals(self.bus, self.cases)
        self.router = ToolRouter(self.world, self.vault, self.cases, self.processor, self.rooms,
                                 self.approvals, self.bus)
        self.sim = SimInspector(self.world, self.cases, self.router, self.bus, self.settings.pace)
        if self.zoo:
            self.zoo.bind(self.cases, self.router, self.approvals)

    async def startup(self) -> None:
        if self.settings.band_live:
            try:
                self.band = BandLive(self.settings)
                await self.band.start({"capy": self._on_capy, "shipco": self._on_shipco})
                self.rooms.band = self.band
            except Exception as err:  # noqa: BLE001 - run offline rather than not at all
                self.band_error = str(err)
                self.band = None
                log.exception("Band unavailable, continuing with local case rooms")
        if self.settings.zoowork_live:
            self.zoo = ZooInspector(self.settings, self.cases, self.router, self.approvals, self.bus)

    async def shutdown(self) -> None:
        if self._sweep_task:
            self._sweep_task.cancel()
        if self.band:
            await self.band.stop()
        if self.zoo:
            await self.zoo.close()

    async def _on_capy(self, role: str, room_id: str, sender: str, name: str, text: str,
                       attachments: list[dict[str, Any]]) -> None:
        await self.rooms.on_capy_mention(room_id, sender, text)

    async def _on_shipco(self, role: str, room_id: str, sender: str, name: str, text: str,
                         attachments: list[dict[str, Any]]) -> None:
        if sender == "capy":
            await self.rooms.on_shipco_mention(room_id, text)

    # ---- state --------------------------------------------------------------------------

    def modes(self) -> dict[str, Any]:
        return {
            "zoowork": "live" if self.zoo else "off",
            "band": "live" if self.band else "off",
            "band_error": self.band_error,
            "band_user": (self.band.user.get("handle") if self.band else None),
            "model": self.settings.zoowork_model if self.zoo else None,
            "voices": bool(self.settings.elevenlabs_api_key),
        }

    def snapshot(self) -> dict[str, Any]:
        return {
            **self.cases.snapshot(),
            "approvals": self.approvals.pending(),
            "sweep": self.sweep,
            "modes": self.modes(),
            "merchant": MERCHANT,
        }

    # ---- sweeps -------------------------------------------------------------------------

    @property
    def running(self) -> bool:
        return self._sweep_task is not None and not self._sweep_task.done()

    async def start_sweep(self, brain: str = "auto", use_band: bool | None = None,
                          cases: list[str] | None = None) -> dict[str, Any]:
        if self.running:
            raise RuntimeError("A sweep is already running")
        use_band = (self.band is not None) if use_band is None else (use_band and self.band is not None)
        if brain == "auto":
            brain = "zoowork" if self.zoo else "scripted"
        if brain == "zoowork" and not self.zoo:
            raise RuntimeError("ZooWork is not configured (set ZOOWORK_API_KEY)")
        self.build(use_band=use_band)
        sweep_id = time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:4]
        self.sweep = {"id": sweep_id, "status": "running", "brain": brain, "band": use_band, "started_at": time.time()}
        self.bus.publish("reset", **self.snapshot())
        self.bus.start_recording(sweep_id)
        self.bus.publish("sweep", sweep=self.sweep)
        targets = cases or sorted(self.cases.cases)
        self._sweep_task = asyncio.create_task(self._run_sweep(targets, brain))
        return self.sweep

    async def _run_sweep(self, case_ids: list[str], brain: str) -> None:
        try:
            await asyncio.gather(*(self.rooms.open(c) for c in case_ids))
            delay = (lambda i, c: SCRIPTED_START.get(c, i * STAGGER)) if brain == "scripted" else (lambda i, c: i * STAGGER)
            runs = [asyncio.create_task(self._investigate(c, brain, delay(i, c))) for i, c in enumerate(case_ids)]
            await asyncio.gather(*runs, return_exceptions=True)
            # let pending issuer rulings land before closing the recording
            for _ in range(int(self.settings.issuer_delay * 4) + 8):
                if not any(c.status == "submitted" for c in self.cases.cases.values()):
                    break
                await asyncio.sleep(0.5)
        finally:
            self.sweep = {**self.sweep, "status": "done", "finished_at": time.time()}
            self.bus.publish("sweep", sweep=self.sweep)
            self.bus.stop_recording()

    async def _investigate(self, case_id: str, brain: str, delay: float) -> None:
        await asyncio.sleep(delay * max(self.settings.pace, 0.2))
        if brain == "zoowork" and self.zoo:
            try:
                await self.zoo.investigate(case_id)
                return
            except ZooRunFailed as err:
                self.bus.publish("log", level="warn",
                                 text=f"{case_id}: {err}. The scripted inspector took over this case.")
            except Exception as err:  # noqa: BLE001
                log.exception("ZooWork investigation failed")
                self.bus.publish("log", level="error", text=f"{case_id}: ZooWork error {err}. Scripted inspector took over.")
        await self.sim.investigate(case_id)

    def reset(self) -> dict[str, Any]:
        """Fresh inbox with no sweep (used before recording a demo)."""
        if self.running:
            raise RuntimeError("A sweep is running")
        self.build(use_band=self.band is not None)
        self.sweep = {"status": "idle"}
        self.bus.publish("reset", **self.snapshot())
        return self.snapshot()

    # ---- merchant actions -------------------------------------------------------------

    def resolve_approval(self, approval_id: str, decision: str) -> dict[str, Any]:
        return self.approvals.resolve(approval_id, decision).public()

    async def reply(self, case_id: str, text: str, share: str | None) -> dict[str, Any]:
        return await self.rooms.merchant_reply(case_id, text, share)
