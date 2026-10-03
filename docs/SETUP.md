# Chargeback Capy · setup and demo guide

## Run it locally

Prerequisites: Python 3.11+ with [uv](https://docs.astral.sh/uv/), Node 22+.

```bash
cp .env.example .env            # add your keys (all optional, see below)

cd frontend && npm install && npm run build && cd ..
cd backend && uv sync
uv run uvicorn capy.server:app --port 8000
# open http://localhost:8000 and click "Run dispute sweep"
```

For frontend development, run `npm run dev` in `frontend/` (port 5173, proxies to the backend).

| Key | What it enables | Without it |
|---|---|---|
| `ZOOWORK_API_KEY` | Inspector Capy runs as a ZooWork managed agent | A scripted inspector drives the same tools |
| `BAND_API_KEY` (user key) | Real Band case rooms, ShipCo agent, merchant on Band | Case rooms run locally in the dashboard |
| `BAND_CAPY_*`, `BAND_SHIPCO_*` (agent id + key) | Reuse the already-registered Inspector Capy and ShipCo agents | New agents are registered on first start |
| `ELEVENLABS_API_KEY` | Demo video narration, music and sound effects | Video can be rendered `--silent` with captions |

Optional settings: `ZOOWORK_MODEL` (default `litellm/claude-sonnet-5`), `CAPY_ZOOWORK` / `CAPY_BAND`
(`auto` | `on` | `off`), `CAPY_PACE` (scripted-inspector speed), `CAPY_ISSUER_DELAY` (seconds).

The ⚙ menu next to *Run dispute sweep* chooses ZooWork or the scripted inspector, toggles Band, and replays
recorded sweeps. If ZooWork fails (for example, no credits), the scripted inspector takes over that case and
a warning toast says so.

Tests: `cd backend && uv run pytest`.

## Live demo script (3 minutes)

1. **Problem (20s).** "Chargebacks drain small shops: scattered evidence, short deadlines, friendly fraud."
2. **Run sweep.** Five Visa disputes light up; the Agent trail shows five parallel ZooWork sessions.
3. **DSP-1042.** In the Band case room, ShipCo's agent returns the driver photo; the board fills with pinned
   evidence and red string.
4. **DSP-1045.** Capy asks you for the lab report → click **📎 Share** (or answer in the Band app).
5. **DSP-1044.** The refund approval appears: "Honest call: this one is on us." Approve.
6. **DSP-1042 approval.** Show the packet: argument, then vault-sealed originals (click the photo page). Approve.
   **WON** stamp, confetti, recovered ticker.
7. **Close** on KPIs: $1,842 recovered, 100% win rate, Capy's fee only on wins. Open the Band app to show
   the real rooms.

## Demo video

`video/make_video.py` records the real dashboard during a live sweep on a virtual display, then mixes
ElevenLabs narration (Jessica as narrator, George as Inspector Capy), ElevenLabs sound effects and an
ElevenLabs music bed:

```bash
Xvfb :99 -screen 0 1920x1200x24 &
cd video && DISPLAY=:99 uv run --project ../backend --with playwright python make_video.py
# → video/out/chargeback-capy.mp4    (--brain scripted for an offline take, --silent without ElevenLabs)
```

## Layout

```
backend/capy/      world, vault, processor, tools, Band rooms, ZooWork runner, scripted inspector, API
backend/capy/persona/   Inspector Capy's ZooWork persona docs (operating manual, identity, soul)
backend/capy/assets/    exhibit artwork (SVG → PNG), fonts (OFL)
frontend/src/      React dashboard: inbox, corkboard, Band room, agent trail, approvals, story cards
video/             narration script and recorder
```

## Offline demo (no network, no backend)

`offline.html` is a single self-contained file that replays a recorded **live** sweep (ZooWork agent +
Band rooms, Oct 3, 2026). Open it in any browser, click **Run dispute sweep**, answer Capy's question and
approve the packets: the replay pauses wherever the merchant acted, so you drive the pace. Add
`?speed=1.5` to the URL to speed it up.

Rebuild it from a newer recorded run:

```bash
cd frontend && npm run build:offline
cd ../backend && uv run python scripts/build_offline.py [RUN_ID]   # -> ../offline.html
```

## Pitch deck

`slide.html` is a 4-slide deck (arrow keys or click; also prints to PDF). Edit `docs/slides/template.html`,
then run `python3 docs/slides/build.py` to inline fonts and images.

## Simulated pieces (by design)
- The merchant, its orders and the five disputes are fictional (`backend/capy/world.py`).
- The card processor/issuer is simulated: it rules in seconds using simplified per-reason-code evidence
  rules (`backend/capy/processor.py`). Real issuers take weeks.
- ShipCo's agent runs in our process (same Band owner) with a deterministic evidence desk.

