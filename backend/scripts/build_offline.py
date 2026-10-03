"""Bundle a recorded live sweep into one self-contained HTML file (no backend, no network).

    cd frontend && npm run build:offline
    cd ../backend && uv run python scripts/build_offline.py [RUN_ID]   # -> ../offline.html

Without RUN_ID the newest ZooWork-brained run in backend/runs is used. Images the run
refers to (exhibits, packet pages) are inlined once as data URIs.
"""

from __future__ import annotations

import base64
import json
import re
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from capy.config import OUTPUT_DIR, RUNS_DIR  # noqa: E402

TEMPLATE = ROOT / "frontend" / "dist-offline" / "index.html"
TARGET = ROOT / "offline.html"
ARTIFACT_URL = re.compile(r"https://a\.zoowork\.ai/artifacts/[^\s\"\\)]+")  # bearer links: never ship them
FILE_REF = re.compile(r"/files/[A-Za-z0-9_./-]+\.(?:png|jpg|jpeg)")


def pick_run(arg: str | None) -> Path:
    if arg:
        return RUNS_DIR / f"{arg}.jsonl"
    for path in sorted(RUNS_DIR.glob("*.jsonl"), reverse=True):
        for line in path.read_text(encoding="utf-8").splitlines()[:3]:
            event = json.loads(line)["event"]
            if event.get("type") == "sweep" and event["sweep"].get("brain") == "zoowork":
                return path
    raise SystemExit("No recorded ZooWork sweep found in backend/runs")


def main() -> None:
    run = pick_run(sys.argv[1] if len(sys.argv) > 1 else None)
    raw = ARTIFACT_URL.sub("[artifact link]", run.read_text(encoding="utf-8"))
    lines = [json.loads(line) for line in raw.splitlines() if line.strip()]
    assets = {}
    for ref in sorted(set(FILE_REF.findall(raw))):
        path = OUTPUT_DIR / ref.removeprefix("/files/")
        if path.exists():
            mime = "image/png" if path.suffix == ".png" else "image/jpeg"
            assets[ref] = f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode()
        else:
            print("missing asset", ref)
    started = next((e["event"]["sweep"]["started_at"] for e in lines if e["event"].get("type") == "sweep"), None)
    if started:
        when = datetime.fromtimestamp(started)
        recorded_at = f"{when:%b} {when.day}, {when:%Y}"  # portable: Windows strftime has no %-d
    else:
        recorded_at = run.stem
    payload = json.dumps({"run_id": run.stem, "recorded_at": recorded_at, "assets": assets, "events": lines},
                         separators=(",", ":")).replace("</", "<\\/")
    # explicit UTF-8: the bundle has non-ASCII text, and Windows defaults to cp1252
    html = TEMPLATE.read_text(encoding="utf-8")
    tag = f'<script id="capy-replay" type="application/json">{payload}</script>'
    html = html.replace("</body>", f"{tag}\n</body>")
    html = html.replace("<title>Chargeback Capy</title>", "<title>Chargeback Capy · offline demo</title>")
    favicon = ROOT / "frontend" / "public" / "favicon.svg"
    icon = 'href="data:image/svg+xml;base64,' + base64.b64encode(favicon.read_bytes()).decode() + '"'
    html = html.replace('href="./favicon.svg"', icon).replace('href="/favicon.svg"', icon)
    TARGET.write_text(html, encoding="utf-8", newline="\n")
    print(f"{TARGET} from {run.stem}: {len(lines)} events, {len(assets)} images, {TARGET.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
