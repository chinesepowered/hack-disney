"""Event bus feeding the dashboard over WebSocket, with a recorder for replays."""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .config import RUNS_DIR


class EventBus:
    def __init__(self) -> None:
        self._subscribers: set[asyncio.Queue[dict[str, Any]]] = set()
        self._seq = 0
        self._record: Path | None = None
        self._record_t0 = 0.0
        self.snapshot_provider: Callable[[], dict[str, Any]] | None = None

    def subscribe(self) -> asyncio.Queue[dict[str, Any]]:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=5000)
        if self.snapshot_provider:
            queue.put_nowait({"type": "snapshot", "seq": self._seq, **self.snapshot_provider()})
        self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[dict[str, Any]]) -> None:
        self._subscribers.discard(queue)

    def publish(self, type_: str, **data: Any) -> dict[str, Any]:
        self._seq += 1
        event = {"type": type_, "seq": self._seq, "ts": time.time(), **data}
        for queue in list(self._subscribers):
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                self._subscribers.discard(queue)
        if self._record:
            line = {"t": round(time.monotonic() - self._record_t0, 3), "event": event}
            with self._record.open("a") as fh:
                fh.write(json.dumps(line, default=str) + "\n")
        return event

    # ---- recording ------------------------------------------------------------

    def start_recording(self, run_id: str) -> Path:
        RUNS_DIR.mkdir(parents=True, exist_ok=True)
        self._record = RUNS_DIR / f"{run_id}.jsonl"
        self._record.write_text("")
        self._record_t0 = time.monotonic()
        if self.snapshot_provider:
            with self._record.open("a") as fh:
                snap = {"type": "snapshot", **self.snapshot_provider()}
                fh.write(json.dumps({"t": 0, "event": snap}, default=str) + "\n")
        return self._record

    def stop_recording(self) -> None:
        self._record = None


def list_runs() -> list[dict[str, Any]]:
    if not RUNS_DIR.exists():
        return []
    runs = []
    for path in sorted(RUNS_DIR.glob("*.jsonl"), reverse=True):
        lines = path.read_text().splitlines()
        duration = json.loads(lines[-1])["t"] if lines else 0
        runs.append({"id": path.stem, "events": len(lines), "duration": duration})
    return runs


async def replay(bus: EventBus, run_id: str, speed: float = 1.0) -> None:
    """Re-broadcast a recorded sweep with its original timing (scaled by speed)."""
    path = RUNS_DIR / f"{run_id}.jsonl"
    started = time.monotonic()
    for raw in path.read_text().splitlines():
        line = json.loads(raw)
        delay = line["t"] / max(speed, 0.01) - (time.monotonic() - started)
        if delay > 0:
            await asyncio.sleep(delay)
        event = dict(line["event"])
        kind = event.pop("type")
        event.pop("seq", None)
        event.pop("ts", None)
        bus.publish(kind, replay=True, **event)
