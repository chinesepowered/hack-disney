"""The evidence vault.

Every fact the inspector can cite becomes an Exhibit with an id like EX-1042-B
and a SHA-256 fingerprint of its original content. The inspector writes the
argument; the vault attaches the untouched originals to the final packet, so
an AI-written claim can only point at evidence, never invent it.
"""

from __future__ import annotations

import hashlib
import json
import string
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from .config import ASSETS, FONTS, OUTPUT_DIR
from .world import World

ART = ASSETS / "art"


@dataclass
class Exhibit:
    id: str
    case_id: str
    key: str  # stable dedupe key within a case
    kind: str  # photo | tracking | email | payment | history | refund | policy | document | subscription | product
    title: str
    source: str
    summary: str
    rows: list[list[str]] = field(default_factory=list)
    body: str = ""
    image: str | None = None  # file name under OUTPUT_DIR/exhibits
    sha256: str = ""

    def public(self) -> dict[str, Any]:
        data = asdict(self)
        data["image_url"] = f"/files/exhibits/{self.image}" if self.image else None
        return data

    def for_agent(self) -> dict[str, Any]:
        """What the inspector sees: the fact and the id to cite, not the vault internals."""
        out: dict[str, Any] = {
            "exhibit_id": self.id,
            "kind": self.kind,
            "title": self.title,
            "source": self.source,
            "summary": self.summary,
        }
        if self.rows:
            out["details"] = {k: v for k, v in self.rows}
        if self.body:
            out["text"] = self.body
        return out


class Vault:
    def __init__(self, world: World) -> None:
        self.world = world
        self.exhibits: dict[str, Exhibit] = {}
        self._by_key: dict[tuple[str, str], str] = {}
        self.image_dir = OUTPUT_DIR / "exhibits"
        self.image_dir.mkdir(parents=True, exist_ok=True)
        render_exhibit_images(world, self.image_dir)

    def add(
        self,
        case_id: str,
        key: str,
        *,
        kind: str,
        title: str,
        source: str,
        summary: str,
        rows: list[list[str]] | None = None,
        body: str = "",
        image: str | None = None,
    ) -> Exhibit:
        existing = self._by_key.get((case_id, key))
        if existing:
            return self.exhibits[existing]
        count = sum(1 for e in self.exhibits.values() if e.case_id == case_id)
        letter = string.ascii_uppercase[count]
        exhibit = Exhibit(
            id=f"EX-{case_id.split('-')[-1]}-{letter}",
            case_id=case_id,
            key=key,
            kind=kind,
            title=title,
            source=source,
            summary=summary,
            rows=rows or [],
            body=body,
            image=f"{image}.png" if image else None,
        )
        exhibit.sha256 = self._fingerprint(exhibit)
        self.exhibits[exhibit.id] = exhibit
        self._by_key[(case_id, key)] = exhibit.id
        return exhibit

    def _fingerprint(self, exhibit: Exhibit) -> str:
        digest = hashlib.sha256()
        digest.update(json.dumps([exhibit.rows, exhibit.body, exhibit.summary]).encode())
        if exhibit.image:
            digest.update((self.image_dir / exhibit.image).read_bytes())
        return digest.hexdigest()

    def get(self, exhibit_id: str) -> Exhibit | None:
        return self.exhibits.get(exhibit_id.strip().upper())

    def for_case(self, case_id: str) -> list[Exhibit]:
        return [e for e in self.exhibits.values() if e.case_id == case_id]

    def image_path(self, exhibit: Exhibit) -> Path | None:
        return self.image_dir / exhibit.image if exhibit.image else None


# ---- exhibit artwork -----------------------------------------------------------
# Static scenes live in assets/art (rendered by scripts/render_art.py). The parts
# that depend on the world's dates are stamped on at startup so a photo's
# timestamp always matches the tracking record it proves.


def _date(iso_ts: str) -> str:
    return iso_ts.replace("T", " ").replace("Z", " UTC")[:16]


def _font(name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONTS / name), size)


MONO = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"


def _mono(size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(MONO, size)
    except OSError:
        return _font("Nunito-Bold.ttf", size)


def _caption_bar(img: Image.Image, text: str) -> None:
    draw = ImageDraw.Draw(img, "RGBA")
    w, h = img.size
    draw.rectangle([0, h - 56, w, h], fill=(0, 0, 0, 165))
    draw.text((24, h - 40), text, font=_mono(19), fill=(255, 255, 255, 255))


def _stamp_delivery_photo(world: World, img: Image.Image) -> None:
    ship = world.shipments["SC-77341920"]
    gps = ship["delivery_gps"]
    _caption_bar(img, f"ShipCo POD  SC-77341920  {_date(ship['delivered_at'])}  GPS {gps['lat']:.5f}, {gps['lng']:.5f}")


def _stamp_product_page(world: World, img: Image.Image) -> None:
    page = world.orders["HS-20877"]["product_page"]
    _caption_bar(img, f"Archived product page  captured {_date(page['captured_at'])}  (at time of purchase)")


def _stamp_lab_report(world: World, img: Image.Image) -> None:
    issued = world.ago(120).date().isoformat()
    ImageDraw.Draw(img).text((50, 240), f"Client: Hot Spring Supply Co.    Issued: {issued}",
                             font=_font("Nunito-Regular.ttf", 17), fill=(61, 74, 87))


STAMPS = {
    "delivery_photo_1042": _stamp_delivery_photo,
    "product_page_1045": _stamp_product_page,
    "lab_report_1045": _stamp_lab_report,
}


def render_exhibit_images(world: World, out_dir: Path) -> None:
    for name, stamp in STAMPS.items():
        img = Image.open(ART / f"{name}.png").convert("RGB")
        stamp(world, img)
        img.save(out_dir / f"{name}.png", optimize=True)
