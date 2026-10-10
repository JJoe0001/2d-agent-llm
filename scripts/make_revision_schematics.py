"""Generate editable vector workflow and journal-sized TOC graphics.

The numbers come from the audited screening summary. No DFT results are shown.
Usage: python scripts/make_revision_schematics.py /path/to/revision/figures
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas


ROOT = Path(__file__).resolve().parents[1]
COUNTS = json.loads((ROOT / "data/computed_results/revision_screening_summary.json").read_text())
INK = colors.HexColor("#18374b")
MUTED = colors.HexColor("#597280")
GREEN = colors.HexColor("#32846b")
BLUE = colors.HexColor("#4281a4")
ORANGE = colors.HexColor("#c8893c")
PALE = colors.HexColor("#edf4f6")


def box(c, x, y, w, h, title, subtitle="", fill=PALE, title_size=10):
    c.setFillColor(fill)
    c.setStrokeColor(colors.HexColor("#d4e1e6"))
    c.roundRect(x, y, w, h, 8, stroke=1, fill=1)
    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", title_size)
    c.drawCentredString(x + w / 2, y + h / 2 + (3 if subtitle else -3), title)
    if subtitle:
        c.setFillColor(MUTED)
        c.setFont("Helvetica", 8)
        c.drawCentredString(x + w / 2, y + h / 2 - 13, subtitle)


def arrow(c, x1, y, x2):
    c.setStrokeColor(MUTED)
    c.setFillColor(MUTED)
    c.setLineWidth(1.6)
    c.line(x1, y, x2 - 5, y)
    p = c.beginPath()
    p.moveTo(x2, y)
    p.lineTo(x2 - 6, y + 4)
    p.lineTo(x2 - 6, y - 4)
    p.close()
    c.drawPath(p, stroke=0, fill=1)


def workflow(out: Path):
    w, h = 840, 300
    c = canvas.Canvas(str(out), pagesize=(w, h))
    c.setTitle("Scripted multi-route 2D candidate workflow")
    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 17)
    c.drawString(28, 269, "Common-parent, multi-route 2D screening")
    c.setFillColor(MUTED)
    c.setFont("Helvetica", 9)
    c.drawString(28, 252, "Scientific criteria run in Python; GPT/MCP invokes coarse-grained batch tools")

    box(c, 27, 110, 132, 82, "MP parent library", "143,259 structures")
    box(c, 212, 175, 145, 48, "Topological", "periodic connectivity", colors.HexColor("#e7f3ed"))
    box(c, 212, 113, 145, 48, "Layered", "layer replication", colors.HexColor("#fff1de"))
    box(c, 212, 51, 145, 48, "Hybrid", "geometry + bond deletion", colors.HexColor("#e6f1f9"))
    for yy in (199, 137, 75):
        arrow(c, 159, 151, 197)
        c.setStrokeColor(MUTED)
        c.line(197, 151, 197, yy)
        arrow(c, 197, yy, 212)
        arrow(c, 357, yy, 405)
    c.setStrokeColor(MUTED)
    c.line(405, 75, 405, 199)
    box(c, 423, 110, 118, 82, "Merge + dedup", "73,105 unique CIFs")
    arrow(c, 541, 151, 570)
    box(c, 570, 110, 110, 82, "CHGNet", "69,624 relaxed")
    arrow(c, 680, 151, 704)
    box(c, 704, 110, 112, 82, "2D geometry", "68,089 retained")
    c.setFillColor(MUTED)
    c.setFont("Helvetica", 8)
    c.drawString(28, 17, "Counts describe computational screening stages; physical stability awaits first-principles validation.")
    c.showPage()
    c.save()


def toc(out: Path):
    w, h = 8 * cm, 4 * cm
    c = canvas.Canvas(str(out), pagesize=(w, h))
    c.setTitle("TOC: three exfoliation routes on a common parent library")
    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(10, h - 15, "One parent library. Three extraction routes.")
    route_y = h - 46
    for x, col, name in ((10, GREEN, "Topology"), (79, ORANGE, "Layered"), (148, BLUE, "Hybrid")):
        c.setFillColor(col)
        c.roundRect(x, route_y, 62, 22, 5, stroke=0, fill=1)
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 7)
        c.drawCentredString(x + 31, route_y + 8, name)
    c.setStrokeColor(MUTED)
    for x in (41, 110, 179):
        c.line(x, route_y, x, 37)
    c.line(41, 37, 179, 37)
    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 8)
    c.drawCentredString(w / 2, 20, "73,105 unique candidate CIFs")
    c.setFillColor(MUTED)
    c.setFont("Helvetica", 6)
    c.drawCentredString(w / 2, 8, "Shared deduplication and CHGNet screening")
    c.showPage()
    c.save()


def main():
    if len(sys.argv) != 2:
        raise SystemExit("usage: make_revision_schematics.py FIGURE_DIRECTORY")
    outdir = Path(sys.argv[1])
    outdir.mkdir(parents=True, exist_ok=True)
    assert COUNTS["n_parents"] == 143259
    assert COUNTS["n_unique_candidates"] == 73105
    assert COUNTS["final_is_relaxed"]["True"] == 69624
    workflow(outdir / "image1_revised.pdf")
    toc(outdir / "toc_8x4cm.pdf")
    print(outdir / "image1_revised.pdf")
    print(outdir / "toc_8x4cm.pdf")


if __name__ == "__main__":
    main()
