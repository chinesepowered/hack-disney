"""Record the Chargeback Capy demo video.

Drives the real dashboard (backend must be running on :8000) through a live
sweep, records the screen from a virtual display, then mixes ElevenLabs
narration, sound effects and music into an MP4.

    Xvfb :99 -screen 0 1920x1200x24 &
    uv run --project ../backend --with playwright python make_video.py

Options:
    --brain zoowork|scripted   who investigates (default: zoowork)
    --silent                   skip ElevenLabs; captions only, estimated timing
    --out PATH                 output file (default out/chargeback-capy.mp4)
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import subprocess
import sys
import time
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from playwright.async_api import Page, async_playwright

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
load_dotenv(HERE.parent / ".env")

import eleven  # noqa: E402
from script import LINES, MUSIC, SFX  # noqa: E402

BASE = os.getenv("CAPY_URL", "http://localhost:8000")
DISPLAY = os.getenv("DISPLAY", ":99")
CHROMIUM = os.getenv("CHROMIUM_PATH", "/opt/pw-browsers/chromium-1194/chrome-linux/chrome")
CHROME_UI = 87  # browser tab strip + address bar height; the capture crops it away
OUT = HERE / "out"
AUDIO = OUT / "audio"


def api(path: str, body: Any = None) -> Any:
    req = urllib.request.Request(BASE + path, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"content-type": "application/json"}, method="POST" if body is not None else "GET")
    return json.loads(urllib.request.urlopen(req).read() or b"{}")


# ---- audio assets -------------------------------------------------------------------


class Voice:
    def __init__(self, silent: bool) -> None:
        self.silent = silent
        AUDIO.mkdir(parents=True, exist_ok=True)
        self.clips: dict[str, tuple[Path | None, float]] = {}

    def prepare(self) -> None:
        for key, (voice, text) in LINES.items():
            if self.silent:
                self.clips[key] = (None, max(1.6, len(text.split()) / 2.6))
            else:
                path = eleven.speak(text, voice, AUDIO)
                self.clips[key] = (path, eleven.duration(path))
            print(f"  line {key:<13} {self.clips[key][1]:5.1f}s")
        if not self.silent:
            for key, (prompt, seconds) in SFX.items():
                try:
                    self.clips[f"sfx:{key}"] = (eleven.sound(prompt, seconds, AUDIO), seconds)
                except Exception as err:  # noqa: BLE001 - effects are optional
                    print("  sfx failed", key, err)


# ---- the director -----------------------------------------------------------------


class Director:
    def __init__(self, page: Page, voice: Voice) -> None:
        self.page = page
        self.voice = voice
        self.t0 = 0.0
        self.cues: list[tuple[float, str]] = []  # (seconds since recording start, clip key)
        self.marks: list[tuple[float, str]] = []

    def now(self) -> float:
        return time.monotonic() - self.t0

    def mark(self, label: str) -> None:
        self.marks.append((round(self.now(), 2), label))
        print(f"[{self.now():6.1f}s] {label}", flush=True)

    async def js(self, expr: str) -> Any:
        return await self.page.evaluate(expr)

    async def state(self) -> dict[str, Any]:
        return await self.js("window.__capy.state()")

    async def wait_for(self, label: str, pred: Callable[[dict[str, Any]], bool], timeout: float = 240) -> bool:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                if pred(await self.state()):
                    return True
            except (KeyError, TypeError, IndexError):
                pass
            await asyncio.sleep(0.3)
        self.mark(f"TIMEOUT waiting for {label}")
        return False

    async def say(self, key: str, *, caption: bool = True) -> None:
        """Play a narration line now: cue its audio, show captions sentence by sentence."""
        _, text = LINES[key]
        _, length = self.voice.clips[key]
        self.cues.append((self.now(), key))
        self.mark(f"say {key} ({length:.1f}s)")
        sentences = [s for s in re.split(r"(?<=[.!?:])\s+", text) if s]
        total = sum(len(s) for s in sentences)
        for sentence in sentences:
            share = length * len(sentence) / total
            if caption:
                await self.js(f"window.__capy.caption({json.dumps(sentence)})")
            await asyncio.sleep(share)
        await self.js("window.__capy.caption(null)")
        await asyncio.sleep(0.35)

    def sfx(self, key: str) -> None:
        if f"sfx:{key}" in self.voice.clips:
            self.cues.append((self.now(), f"sfx:{key}"))

    async def click(self, selector: str) -> bool:
        ok = await self.js(f"window.__capy.click({json.dumps(selector)})")
        if not ok:
            self.mark(f"click target missing: {selector}")
        return bool(ok)

    async def focus(self, target: str | None, scale: float = 1.3, mode: str = "fit") -> None:
        await self.js(f"window.__capy.focus({json.dumps(target)}, {scale}, {json.dumps(mode)})")

    async def card(self, name: str | None) -> None:
        await self.js(f"window.__capy.card({json.dumps(name)})")

    async def select(self, case_id: str) -> None:
        await self.js(f"window.__capy.select({json.dumps(case_id)})")

    async def approve(self, case_id: str, linger: float = 0.8) -> bool:
        if not await self.wait_for(f"approval {case_id}", lambda s: any(a["case_id"] == case_id for a in s["approvals"])):
            return False
        await self.select(case_id)
        await self.js(f"window.__capy.showApproval({json.dumps(case_id)})")
        await self.js("window.__capy.modals(true)")
        await asyncio.sleep(linger)
        ok = await self.click(".modal-actions .go")
        await asyncio.sleep(0.6)
        await self.js("window.__capy.modals(false)")
        return ok

    async def watch_decisions(self) -> None:
        seen: set[int] = set()
        while True:
            try:
                for d in (await self.state())["decisions"]:
                    if d["key"] not in seen:
                        seen.add(d["key"])
                        self.sfx("stamp")
                        if d["decision"]["status"] == "won":
                            self.cues.append((self.now() + 0.45, "sfx:chaching") if "sfx:chaching" in self.voice.clips else (0, ""))
            except Exception:  # noqa: BLE001
                pass
            await asyncio.sleep(0.2)


def zoo_steps(s: dict[str, Any], case_id: str) -> list[dict[str, Any]]:
    return s["zoo"].get(case_id, [])


def band_items(s: dict[str, Any], case_id: str) -> list[dict[str, Any]]:
    return s["band"].get(case_id, [])


async def approve_remaining(d: Director, timeout: float = 240) -> None:
    """Approve whatever reaches the gate next, until every case has been submitted or decided."""
    deadline = time.monotonic() + timeout
    done = {"submitted", "won", "lost", "accepted"}
    while time.monotonic() < deadline:
        s = await d.state()
        if all(c["status"] in done for c in s["cases"].values()):
            return
        pending = [a["case_id"] for a in s["approvals"]]
        if pending:
            await d.approve(pending[0], linger=0.9)
            await asyncio.sleep(0.4)
        else:
            await asyncio.sleep(0.5)
    d.mark("TIMEOUT approving remaining cases")


async def storyboard(d: Director, brain: str) -> None:
    """The demo, beat by beat. Waits are generous so a live agent can take its time."""
    await d.card("title")
    await asyncio.sleep(1.2)
    await d.say("title")
    await asyncio.sleep(0.3)
    d.sfx("whoosh")
    await d.card("problem")
    await asyncio.sleep(1.0)
    await d.say("problem")
    d.sfx("whoosh")
    await d.card(None)
    await asyncio.sleep(1.0)

    await d.focus("inbox", 1.55, "top")
    await asyncio.sleep(0.8)
    await d.say("inbox")
    await d.focus(None)
    await asyncio.sleep(0.8)

    # start the sweep with a visible click
    await d.select("DSP-1042")
    if brain == "scripted":
        api("/api/sweep", {"brain": "scripted"})
    await d.click(".run-btn")
    await d.say("capy_go", caption=False)

    await asyncio.sleep(1.2)
    await d.focus("zoo", 1.9)
    await d.say("zoowork")
    await d.focus(None)

    await d.wait_for("ShipCo reply", lambda s: any(m["sender"] == "shipco" for m in band_items(s, "DSP-1042")), 180)
    await asyncio.sleep(0.6)
    await d.focus("band", 1.9)
    await d.say("band")
    await d.focus(None)

    # the merchant's lab report: the live agent asks early, so answer early
    if await d.wait_for("question", lambda s: any(a["status"] == "open" for a in s["cases"]["DSP-1045"]["attention"]), 90):
        await d.select("DSP-1045")
        await asyncio.sleep(1.0)
        await d.focus("band", 1.9)
        narration = asyncio.create_task(d.say("question"))
        await asyncio.sleep(5.0)
        await d.click(".attention .quick button.primary")
        await narration
        await asyncio.sleep(1.2)
        await d.focus(None)
        await d.select("DSP-1042")
        await asyncio.sleep(0.8)

    await d.wait_for("pins", lambda s: len(s["cases"]["DSP-1042"]["pins"]) >= 3, 180)
    await asyncio.sleep(0.6)
    await d.focus("casefile", 1.15)
    await d.say("board")
    await d.focus(None)

    await d.wait_for("packet", lambda s: s["cases"]["DSP-1042"]["packet"] is not None, 300)
    await asyncio.sleep(0.6)
    await d.focus("zoo", 1.9)
    await d.say("vault")
    await d.focus(None)

    # the honest refund
    if await d.wait_for("accept approval", lambda s: any(a["case_id"] == "DSP-1044" for a in s["approvals"]), 240):
        await d.select("DSP-1044")
        await d.js("window.__capy.showApproval('DSP-1044')")
        await d.js("window.__capy.modals(true)")
        await asyncio.sleep(1.0)
        await d.say("honest")
        await d.click(".modal-actions .go")
        await asyncio.sleep(0.4)
        await d.js("window.__capy.modals(false)")
        await asyncio.sleep(3.0)

    # approve the delivery-photo case on camera
    if await d.wait_for("approval DSP-1042", lambda s: any(a["case_id"] == "DSP-1042" for a in s["approvals"]), 300):
        await d.select("DSP-1042")
        await d.js("window.__capy.showApproval('DSP-1042')")
        await d.js("window.__capy.modals(true)")
        await asyncio.sleep(1.0)
        narration = asyncio.create_task(d.say("approval"))
        await asyncio.sleep(4.2)
        photo_page = await d.js(
            """(() => { const c = window.__capy.state().cases['DSP-1042'];
                 const ids = c.packet ? c.packet.exhibits : [];
                 const pin = c.pins.find(p => p.exhibit.key === 'shipco_pod_photo');
                 if (!pin || !c.packet) return null;
                 return c.packet.argument_pages + 2 + ids.indexOf(pin.exhibit.id); })()"""
        )
        if photo_page:
            await d.click(f".modal-left .thumbs button:nth-child({photo_page})")
        await narration
        await d.click(".modal-actions .go")
        await asyncio.sleep(0.5)
        await d.js("window.__capy.modals(false)")
        await d.wait_for("DSP-1042 won", lambda s: s["cases"]["DSP-1042"]["status"] == "won", 90)
        await asyncio.sleep(0.5)
        await d.say("capy_won", caption=False)
        await asyncio.sleep(2.2)

    results = asyncio.create_task(d.say("results"))
    await approve_remaining(d)
    await d.focus("kpis", 1.7)
    await results
    await d.wait_for("all decided", lambda s: all(c["status"] in ("won", "lost", "accepted") for c in s["cases"].values()), 60)
    await asyncio.sleep(2.0)
    await d.focus(None)
    await asyncio.sleep(0.8)

    d.sfx("whoosh")
    await d.card("architecture")
    await asyncio.sleep(1.2)
    await d.say("architecture")
    await asyncio.sleep(0.4)
    d.sfx("whoosh")
    await d.card("closing")
    await asyncio.sleep(1.0)
    await d.say("closing")
    await asyncio.sleep(2.5)


# ---- capture + mix --------------------------------------------------------------


async def record(voice: Voice, brain: str, raw: Path) -> Director:
    api("/api/reset", {})
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            executable_path=CHROMIUM if Path(CHROMIUM).exists() else None,
            headless=False,
            env={**os.environ, "DISPLAY": DISPLAY},
            args=[f"--window-size=1920,{1080 + CHROME_UI}", "--window-position=0,0", "--hide-scrollbars",
                  "--no-first-run", "--disable-infobars", "--force-device-scale-factor=1", "--test-type"],
        )
        context = await browser.new_context(no_viewport=True)
        page = await context.new_page()
        await page.goto(f"{BASE}/?director=1")
        await page.wait_for_function("window.__capy && Object.keys(window.__capy.state().cases).length === 5")
        await page.evaluate("window.__capy.follow(false); window.__capy.modals(false); window.__capy.select('DSP-1042'); window.__capy.card('title')")
        await asyncio.sleep(1.5)
        director = Director(page, voice)
        ffmpeg = subprocess.Popen(
            ["ffmpeg", "-y", "-loglevel", "error", "-f", "x11grab", "-video_size", "1920x1080", "-framerate", "30",
             "-i", f"{DISPLAY}.0+0,{CHROME_UI}", "-c:v", "libx264", "-preset", "ultrafast", "-crf", "12",
             "-pix_fmt", "yuv420p", str(raw)],
            stdin=subprocess.PIPE,
        )
        director.t0 = time.monotonic()
        watcher = asyncio.create_task(director.watch_decisions())
        try:
            await storyboard(director, brain)
        finally:
            watcher.cancel()
            ffmpeg.communicate(b"q", timeout=60)
            await browser.close()
    return director


def mix(director: Director, voice: Voice, raw: Path, out: Path, silent: bool) -> None:
    length = eleven.duration(raw)
    inputs: list[str] = ["-i", str(raw)]
    filters: list[str] = []
    labels: list[str] = []
    n = 1
    if not silent:
        try:
            bed = eleven.music(MUSIC, min(length + 2, 300), AUDIO)
            inputs += ["-stream_loop", "-1", "-i", str(bed)]
            filters.append(f"[{n}:a]atrim=0:{length:.2f},volume=0.16,afade=t=in:d=1.5,afade=t=out:st={max(length - 3, 0):.2f}:d=3[music]")
            labels.append("[music]")
            n += 1
        except Exception as err:  # noqa: BLE001
            print("music unavailable:", err)
    for t, key in director.cues:
        path, _ = voice.clips.get(key, (None, 0))
        if not path or t <= 0:
            continue
        gain = 0.55 if key.startswith("sfx:") else 1.0
        inputs += ["-i", str(path)]
        ms = int(max(t, 0) * 1000)
        filters.append(f"[{n}:a]adelay={ms}|{ms},volume={gain}[a{n}]")
        labels.append(f"[a{n}]")
        n += 1
    cmd = ["ffmpeg", "-y", "-loglevel", "error", *inputs]
    if labels:
        graph = ";".join(filters) + f";{''.join(labels)}amix=inputs={len(labels)}:normalize=0,loudnorm=I=-16:TP=-1.5:LRA=11[mix]"
        cmd += ["-filter_complex", graph, "-map", "0:v", "-map", "[mix]", "-c:a", "aac", "-b:a", "192k", "-ar", "48000"]
    else:
        cmd += ["-map", "0:v"]
    cmd += ["-c:v", "libx264", "-preset", "slow", "-crf", "18", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
            "-t", f"{length:.2f}", str(out)]
    subprocess.run(cmd, check=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--brain", default="zoowork", choices=["zoowork", "scripted"])
    parser.add_argument("--silent", action="store_true")
    parser.add_argument("--out", default=str(OUT / "chargeback-capy.mp4"))
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    voice = Voice(args.silent)
    print("Preparing audio…")
    voice.prepare()
    raw = OUT / "raw-capture.mp4"
    print("Recording…")
    director = asyncio.run(record(voice, args.brain, raw))
    (OUT / "timeline.json").write_text(json.dumps({"cues": director.cues, "marks": director.marks}, indent=2))
    print("Mixing…")
    mix(director, voice, raw, Path(args.out), args.silent)
    print("Done:", args.out, f"{eleven.duration(Path(args.out)):.1f}s")


if __name__ == "__main__":
    main()
