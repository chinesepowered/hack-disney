"""Bundle a recorded live sweep into one self-contained HTML file (no backend, no network).

    cd frontend && pnpm run build:offline
    cd ../backend && uv run python scripts/build_offline.py [RUN_ID]    # -> ../offline.html
    cd ../backend && uv run python scripts/build_offline.py --refresh   # new frontend, same replay

Without RUN_ID the newest ZooWork-brained run in backend/runs is used. Images the run
refers to (exhibits, packet pages) are inlined once as data URIs. --refresh keeps the
replay already embedded in offline.html, for machines that don't have the recorded run.
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
# The payload escapes "</", so the first closing tag after the opening one is the real one.
REPLAY_TAG = re.compile(r'<script id="capy-replay" type="application/json">.*?</script>', re.S)


def pick_run(arg: str | None) -> Path:
    if arg:
        return RUNS_DIR / f"{arg}.jsonl"
    for path in sorted(RUNS_DIR.glob("*.jsonl"), reverse=True):
        for line in path.read_text(encoding="utf-8").splitlines()[:3]:
            event = json.loads(line)["event"]
            if event.get("type") == "sweep" and event["sweep"].get("brain") == "zoowork":
                return path
    raise SystemExit("No recorded ZooWork sweep found in backend/runs")


def replay_tag(run: Path) -> tuple[str, int, int]:
    """The <script> tag carrying a recorded run, plus its event and image counts."""
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
    return f'<script id="capy-replay" type="application/json">{payload}</script>', len(lines), len(assets)


def bundle(tag: str) -> None:
    # explicit UTF-8: the bundle has non-ASCII text, and Windows defaults to cp1252
    html = TEMPLATE.read_text(encoding="utf-8")
    html = html.replace("</body>", f"{tag}\n</body>")
    html = html.replace("<title>Chargeback Capy</title>", "<title>Chargeback Capy · offline demo</title>")
    favicon = ROOT / "frontend" / "public" / "favicon.svg"
    icon = 'href="data:image/svg+xml;base64,' + base64.b64encode(favicon.read_bytes()).decode() + '"'
    html = html.replace('href="./favicon.svg"', icon).replace('href="/favicon.svg"', icon)
    TARGET.write_text(html, encoding="utf-8", newline="\n")


def main() -> None:
    args = sys.argv[1:]
    if args[:1] == ["--refresh"]:
        match = REPLAY_TAG.search(TARGET.read_text(encoding="utf-8"))
        if not match:
            raise SystemExit(f"No embedded replay found in {TARGET}")
        bundle(match.group(0))
        print(f"{TARGET} refreshed with the current frontend, {TARGET.stat().st_size / 1e6:.1f} MB")
        return
    run = pick_run(args[0] if args else None)
    tag, events, images = replay_tag(run)
    bundle(tag)
    print(f"{TARGET} from {run.stem}: {events} events, {images} images, {TARGET.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
