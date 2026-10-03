"""Inline fonts, art and the dashboard screenshot into ../../slide.html (works offline).

    uv run --no-project python docs/slides/build.py   # needs frontend/node_modules for the fonts
"""

from __future__ import annotations

import base64
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FONTS = ROOT / "frontend" / "node_modules" / "@fontsource"


def b64(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode()


def capy_svg(size: int) -> str:
    svg = (ROOT / "backend" / "capy" / "assets" / "art" / "inspector_capy.svg").read_text(encoding="utf-8")
    return re.sub(r'width="\d+" height="\d+"', f'width="{size}" height="{size}"', svg, count=1)


def main() -> None:
    # explicit UTF-8: the template has emoji, and Windows defaults to cp1252
    html = (Path(__file__).parent / "template.html").read_text(encoding="utf-8")
    values = {
        "FREDOKA_600": b64(FONTS / "fredoka/files/fredoka-latin-600-normal.woff2"),
        "FREDOKA_700": b64(FONTS / "fredoka/files/fredoka-latin-700-normal.woff2"),
        "NUNITO_600": b64(FONTS / "nunito/files/nunito-latin-600-normal.woff2"),
        "NUNITO_700": b64(FONTS / "nunito/files/nunito-latin-700-normal.woff2"),
        "NUNITO_800": b64(FONTS / "nunito/files/nunito-latin-800-normal.woff2"),
        "CAVEAT_600": b64(FONTS / "caveat/files/caveat-latin-600-normal.woff2"),
        "SCREENSHOT_B64": b64(ROOT / "docs" / "dashboard.jpg"),
        "CAPY_SVG_B64": base64.b64encode(capy_svg(64).encode()).decode(),
        "CAPY_SVG_HERO": capy_svg(500),
        "CAPY_SVG_SMALL": capy_svg(84),
    }
    for key, value in values.items():
        html = html.replace("{{" + key + "}}", value)
    target = ROOT / "slide.html"
    target.write_text(html, encoding="utf-8", newline="\n")
    print(f"{target} {target.stat().st_size / 1e6:.2f} MB")


if __name__ == "__main__":
    main()
