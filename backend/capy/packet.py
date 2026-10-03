"""Evidence packets.

A packet is the inspector's argument (written by the ZooWork agent in its
sandbox, or by the scripted inspector offline) followed by vault pages: an
exhibit index with SHA-256 fingerprints and one page per cited original.
"""

from __future__ import annotations

import hashlib
import io
import textwrap
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pymupdf
from pypdf import PdfReader, PdfWriter
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen.canvas import Canvas

from .cases import CaseFile
from .config import ASSETS, FONTS, OUTPUT_DIR
from .exhibits import Exhibit, Vault

for _name in ("Nunito-Regular", "Nunito-Bold", "Fredoka-SemiBold"):
    pdfmetrics.registerFont(TTFont(_name, str(FONTS / f"{_name}.ttf")))

INK = HexColor("#2b2118")
MUTED = HexColor("#7a6a5a")
BROWN = HexColor("#8d5d39")
CREAM = HexColor("#fbf5ea")
TEAL = HexColor("#2f8f86")
RULE = HexColor("#e6d9c4")
W, H = LETTER
MARGIN = 54
LOGO = ASSETS / "art" / "inspector_capy.png"


def _wrap(canvas: Canvas, text: str, x: float, y: float, width: float, font: str, size: float,
          leading: float | None = None, color: Any = INK) -> float:
    leading = leading or size * 1.35
    canvas.setFont(font, size)
    canvas.setFillColor(color)
    chars = max(20, int(width / (size * 0.5)))
    for para in text.split("\n"):
        for line in textwrap.wrap(para, chars) or [""]:
            canvas.drawString(x, y, line)
            y -= leading
    return y


def _header(canvas: Canvas, title: str, subtitle: str) -> float:
    canvas.setFillColor(CREAM)
    canvas.rect(0, H - 96, W, 96, stroke=0, fill=1)
    canvas.drawImage(ImageReader(str(LOGO)), MARGIN - 6, H - 88, 76, 76, mask="auto")
    canvas.setFillColor(INK)
    canvas.setFont("Fredoka-SemiBold", 20)
    canvas.drawString(MARGIN + 80, H - 46, title)
    canvas.setFont("Nunito-Regular", 10.5)
    canvas.setFillColor(MUTED)
    canvas.drawString(MARGIN + 80, H - 64, subtitle)
    canvas.setStrokeColor(RULE)
    canvas.line(MARGIN, H - 104, W - MARGIN, H - 104)
    return H - 132


def _footer(canvas: Canvas, text: str) -> None:
    canvas.setFont("Nunito-Regular", 8.5)
    canvas.setFillColor(MUTED)
    canvas.drawString(MARGIN, 30, text)
    canvas.drawRightString(W - MARGIN, 30, f"Page {canvas.getPageNumber()}")


# ---- the argument (scripted inspector; the live agent writes its own) ----------


def build_argument_pdf(case: CaseFile, claims: list[dict[str, Any]], summary: str,
                       exhibits: dict[str, Exhibit]) -> bytes:
    buf = io.BytesIO()
    c = Canvas(buf, pagesize=LETTER)
    c.setTitle(f"Rebuttal {case.id}")
    y = _header(c, f"Dispute rebuttal  {case.id}",
                f"Hot Spring Supply Co.  |  {case.network_code} {case.reason_label}  |  "
                f"${case.amount:,.2f}  |  Prepared by Inspector Capy")

    c.setFont("Nunito-Bold", 11)
    c.setFillColor(INK)
    rows = [
        ("Cardholder", case.customer_name),
        ("Order", f"{case.order_id}  ({case.item})"),
        ("Disputed charge", f"{case.charge_id}  ${case.amount:,.2f} USD"),
        ("Cardholder claim", case.claim),
    ]
    for label, value in rows:
        c.setFont("Nunito-Bold", 10.5)
        c.setFillColor(MUTED)
        c.drawString(MARGIN, y, label.upper())
        y = _wrap(c, value, MARGIN + 130, y, W - 2 * MARGIN - 130, "Nunito-Regular", 11)
        y -= 4

    y -= 8
    c.setFont("Fredoka-SemiBold", 14)
    c.setFillColor(BROWN)
    c.drawString(MARGIN, y, "Summary")
    y = _wrap(c, summary, MARGIN, y - 20, W - 2 * MARGIN, "Nunito-Regular", 11.5)

    y -= 10
    c.setFont("Fredoka-SemiBold", 14)
    c.setFillColor(BROWN)
    c.drawString(MARGIN, y, "Findings")
    y -= 22
    for n, claim in enumerate(claims, 1):
        if y < 120:
            _footer(c, f"{case.id}  |  Every finding cites an exhibit held in the evidence vault.")
            c.showPage()
            y = H - MARGIN
        c.setFillColor(TEAL)
        c.circle(MARGIN + 9, y + 4, 9, stroke=0, fill=1)
        c.setFillColor(HexColor("#ffffff"))
        c.setFont("Nunito-Bold", 10)
        c.drawCentredString(MARGIN + 9, y + 0.5, str(n))
        y = _wrap(c, claim["text"], MARGIN + 28, y, W - 2 * MARGIN - 28, "Nunito-Bold", 11.5)
        cites = ", ".join(
            f"{i} ({exhibits[i].title})" if i in exhibits else i for i in claim.get("exhibit_ids", [])
        )
        y = _wrap(c, f"Evidence: {cites}", MARGIN + 28, y - 1, W - 2 * MARGIN - 28,
                  "Nunito-Regular", 10, color=MUTED)
        y -= 10

    _footer(c, f"{case.id}  |  Every finding cites an exhibit held in the evidence vault.")
    c.showPage()
    c.save()
    return buf.getvalue()


# ---- vault pages ---------------------------------------------------------------


def _vault_pages(case: CaseFile, cited: list[Exhibit], vault: Vault) -> bytes:
    buf = io.BytesIO()
    c = Canvas(buf, pagesize=LETTER)
    stamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")

    y = _header(c, f"Exhibit index  {case.id}",
                f"Originals attached by the evidence vault on {stamp}. The inspector cannot edit these.")
    for ex in cited:
        c.setFont("Nunito-Bold", 11)
        c.setFillColor(INK)
        c.drawString(MARGIN, y, f"{ex.id}   {ex.title}")
        c.setFont("Nunito-Regular", 9.5)
        c.setFillColor(MUTED)
        c.drawString(MARGIN + 14, y - 14, f"Source: {ex.source}")
        c.drawString(MARGIN + 14, y - 27, f"SHA-256: {ex.sha256}")
        y -= 46
    _footer(c, f"{case.id}  |  Fingerprints let the issuer verify each exhibit is unaltered.")
    c.showPage()

    for ex in cited:
        y = _header(c, f"{ex.id}  {ex.title}", f"Source: {ex.source}  |  SHA-256 {ex.sha256[:32]}...")
        y = _wrap(c, ex.summary, MARGIN, y, W - 2 * MARGIN, "Nunito-Bold", 11.5) - 6
        image = vault.image_path(ex)
        if image:
            reader = ImageReader(str(image))
            iw, ih = reader.getSize()
            max_w, max_h = W - 2 * MARGIN, y - 70
            scale = min(max_w / iw, max_h / ih)
            dw, dh = iw * scale, ih * scale
            c.drawImage(reader, (W - dw) / 2, y - dh, dw, dh)
        for key, value in ex.rows:
            if y < 90:
                break
            c.setFont("Nunito-Bold", 10)
            c.setFillColor(MUTED)
            c.drawString(MARGIN, y, str(key))
            y = _wrap(c, str(value), MARGIN + 150, y, W - 2 * MARGIN - 150, "Nunito-Regular", 10.5)
            c.setStrokeColor(RULE)
            c.line(MARGIN, y + 6, W - MARGIN, y + 6)
            y -= 6
        if ex.body:
            c.setFillColor(CREAM)
            box_top = y
            c.rect(MARGIN - 6, 80, W - 2 * MARGIN + 12, box_top - 80 + 8, stroke=0, fill=1)
            _wrap(c, ex.body, MARGIN, y - 10, W - 2 * MARGIN, "Nunito-Regular", 11)
        _footer(c, f"{case.id}  |  {ex.id}  |  original record, attached unmodified")
        c.showPage()
    c.save()
    return buf.getvalue()


def assemble_packet(case: CaseFile, argument_pdf: bytes, claims: list[dict[str, Any]],
                    vault: Vault) -> dict[str, Any]:
    """Argument + exhibit index + originals -> final PDF and page previews."""
    cited_ids: list[str] = []
    for claim in claims:
        for ex_id in claim.get("exhibit_ids", []):
            if ex_id not in cited_ids and vault.get(ex_id):
                cited_ids.append(vault.get(ex_id).id)  # type: ignore[union-attr]
    cited = [vault.get(i) for i in cited_ids]
    vault_pdf = _vault_pages(case, [e for e in cited if e], vault)

    writer = PdfWriter()
    for blob in (argument_pdf, vault_pdf):
        for page in PdfReader(io.BytesIO(blob)).pages:
            writer.add_page(page)
    out_dir = OUTPUT_DIR / "packets" / case.id
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob("*"):
        old.unlink()
    pdf_path = out_dir / "packet.pdf"
    with pdf_path.open("wb") as fh:
        writer.write(fh)

    pages = render_previews(pdf_path, out_dir)
    digest = hashlib.sha256(pdf_path.read_bytes()).hexdigest()
    rel = Path("packets") / case.id
    return {
        "pdf_url": f"/files/{rel}/packet.pdf",
        "pages": [f"/files/{rel}/{p.name}" for p in pages],
        "page_count": len(pages),
        "argument_pages": len(PdfReader(io.BytesIO(argument_pdf)).pages),
        "exhibits": cited_ids,
        "sha256": digest,
    }


def render_previews(pdf_path: Path, out_dir: Path, zoom: float = 1.1) -> list[Path]:
    doc = pymupdf.open(pdf_path)
    paths = []
    for index, page in enumerate(doc, 1):
        pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom))
        target = out_dir / f"page-{index:02d}.png"
        pix.save(target)
        paths.append(target)
    doc.close()
    return paths
