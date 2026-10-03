"""Render capy/assets/art/*.svg to PNG with headless Chromium (dev-time only).

The PNGs are committed, so running the app never needs a browser. Run after
editing the artwork:

    uv run --with playwright python scripts/render_art.py
"""

from __future__ import annotations

import asyncio
import os
import re
from pathlib import Path

from playwright.async_api import async_playwright

ART = Path(__file__).resolve().parents[1] / "capy" / "assets" / "art"
CHROMIUM = os.getenv("CHROMIUM_PATH", "/opt/pw-browsers/chromium-1194/chrome-linux/chrome")


async def main() -> None:
    async with async_playwright() as p:
        browser = await p.chromium.launch(executable_path=CHROMIUM if Path(CHROMIUM).exists() else None)
        for svg in sorted(ART.glob("*.svg")):
            markup = svg.read_text()
            width, height = (int(v) for v in re.search(r'width="(\d+)" height="(\d+)"', markup).groups())
            page = await browser.new_page(viewport={"width": width, "height": height}, device_scale_factor=1)
            await page.set_content(f"<html><body style='margin:0;background:transparent'>{markup}</body></html>")
            await page.screenshot(path=str(svg.with_suffix(".png")), omit_background=True, clip={"x": 0, "y": 0, "width": width, "height": height})
            await page.close()
            print("rendered", svg.with_suffix(".png").name)
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
