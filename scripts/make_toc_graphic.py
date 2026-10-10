"""Generate the 8 × 4 cm vector PDF TOC graphic from audited candidate counts.

Usage: python scripts/make_toc_graphic.py OUTPUT.pdf
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas

ROOT = Path(__file__).resolve().parents[1]
COUNTS = json.loads((ROOT / 'data/computed_results/revision_screening_summary.json').read_text())
INK = colors.HexColor('#18374b')
MUTED = colors.HexColor('#597280')
ROUTES = ((10, '#32846b', 'Topology'), (79, '#c8893c', 'Layered'), (148, '#4281a4', 'Hybrid'))


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit('usage: make_toc_graphic.py OUTPUT.pdf')
    if COUNTS['n_parents'] != 143259 or COUNTS['n_unique_candidates'] != 73105:
        raise SystemExit('audited counts changed; review the TOC wording before regenerating')
    out = Path(sys.argv[1])
    out.parent.mkdir(parents=True, exist_ok=True)
    w, h = 8 * cm, 4 * cm
    c = canvas.Canvas(str(out), pagesize=(w, h))
    c.setTitle('TOC: three exfoliation routes on a common parent library')
    c.setFillColor(INK)
    c.setFont('Helvetica-Bold', 9)
    c.drawString(10, h - 15, 'One parent library. Three extraction routes.')
    route_y = h - 46
    for x, color, name in ROUTES:
        c.setFillColor(colors.HexColor(color))
        c.roundRect(x, route_y, 62, 22, 5, stroke=0, fill=1)
        c.setFillColor(colors.white)
        c.setFont('Helvetica-Bold', 7)
        c.drawCentredString(x + 31, route_y + 8, name)
    c.setStrokeColor(MUTED)
    for x in (41, 110, 179):
        c.line(x, route_y, x, 37)
    c.line(41, 37, 179, 37)
    c.setFillColor(INK)
    c.setFont('Helvetica-Bold', 8)
    c.drawCentredString(w / 2, 20, '73,105 unique candidate CIFs')
    c.setFillColor(MUTED)
    c.setFont('Helvetica', 6)
    c.drawCentredString(w / 2, 8, 'Shared deduplication and CHGNet screening')
    c.showPage()
    c.save()
    print(out)


if __name__ == '__main__':
    main()
