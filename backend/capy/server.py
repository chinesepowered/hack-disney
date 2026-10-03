"""HTTP + WebSocket API for the dashboard.

Run:  uv run uvicorn capy.server:app --port 8000
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .app import CapyApp
from .bus import list_runs, replay
from .config import FRONTEND_DIST, OUTPUT_DIR, load_settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
for noisy in ("band", "httpx", "websockets"):
    logging.getLogger(noisy).setLevel(logging.WARNING)

capy = CapyApp(load_settings())


@asynccontextmanager
async def lifespan(_: FastAPI):  # type: ignore[no-untyped-def]
    await capy.startup()
    yield
    await capy.shutdown()


app = FastAPI(title="Chargeback Capy", lifespan=lifespan)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/files", StaticFiles(directory=OUTPUT_DIR), name="files")


class SweepRequest(BaseModel):
    brain: str = "auto"  # auto | zoowork | scripted
    band: bool | None = None
    cases: list[str] | None = None


class Decision(BaseModel):
    decision: str  # approve | deny


class Reply(BaseModel):
    text: str
    share: str | None = None


class ReplayRequest(BaseModel):
    run_id: str
    speed: float = 1.0


@app.get("/api/state")
async def state() -> dict[str, Any]:
    return capy.snapshot()


@app.post("/api/sweep")
async def sweep(req: SweepRequest) -> dict[str, Any]:
    try:
        return await capy.start_sweep(req.brain, req.band, req.cases)
    except RuntimeError as err:
        raise HTTPException(409, str(err)) from err


@app.post("/api/approvals/{approval_id}")
async def approve(approval_id: str, body: Decision) -> dict[str, Any]:
    if body.decision not in {"approve", "deny"}:
        raise HTTPException(400, "decision must be approve or deny")
    try:
        return capy.resolve_approval(approval_id, body.decision)
    except KeyError as err:
        raise HTTPException(404, "unknown approval") from err


@app.post("/api/cases/{case_id}/reply")
async def reply(case_id: str, body: Reply) -> dict[str, Any]:
    try:
        return await capy.reply(case_id, body.text, body.share)
    except KeyError as err:
        raise HTTPException(404, str(err)) from err


@app.get("/api/runs")
async def runs() -> list[dict[str, Any]]:
    return list_runs()


@app.post("/api/replay")
async def start_replay(body: ReplayRequest) -> dict[str, Any]:
    if capy.running:
        raise HTTPException(409, "A sweep is running")
    asyncio.create_task(replay(capy.bus, body.run_id, body.speed))
    return {"replaying": body.run_id}


@app.websocket("/ws")
async def ws(socket: WebSocket) -> None:
    await socket.accept()
    queue = capy.bus.subscribe()
    try:
        while True:
            event = await queue.get()
            await socket.send_json(event)
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        capy.bus.unsubscribe(queue)


if FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

    @app.get("/{path:path}")
    async def spa(path: str) -> FileResponse:
        target = FRONTEND_DIST / path
        if path and target.is_file():
            return FileResponse(target)
        return FileResponse(FRONTEND_DIST / "index.html")
