"""Draw a vector PDF of audited route and screening counts.

Requires reportlab. Usage: python scripts/make_revision_figure.py OUTPUT.pdf
"""

from __future__ import annotations

import csv
import gzip
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

from reportlab.lib import colors
from reportlab.pdfgen import canvas


ROOT = Path(__file__).resolve().parents[1]
SUMMARY = json.loads((ROOT / "data/computed_results/revision_screening_summary.json").read_text())
PARENT_TABLE = ROOT / "data/computed_results/parent_exfoliability_labels.csv.gz"
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "docs/revision_route_screening.pdf"
W, H = 840, 540
INK = colors.HexColor("#213445")
GREY = colors.HexColor("#61717e")
GRID = colors.HexColor("#dbe2e7")
PALETTE = {
    "topological": colors.HexColor("#347d65"),
    "hybrid": colors.HexColor("#326f9b"),
    "layered": colors.HexColor("#c07836"),
}


def label(c: canvas.Canvas, x: float, y: float, value: str, size: int = 9, color=INK) -> None:
    c.setFillColor(color)
    c.setFont("Helvetica", size)
    c.drawString(x, y, value)


def panel_title(c: canvas.Canvas, x: float, y: float, text: str) -> None:
    c.setFont("Helvetica-Bold", 12)
    c.setFillColor(INK)
    c.drawString(x, y, text)


def main() -> None:
    groups: dict[str, list[int]] = defaultdict(list)
    with gzip.open(PARENT_TABLE, "rt", encoding="utf-8-sig") as stream:
        for row in csv.DictReader(stream):
            signature = "".join(row[f"route_{name}"] for name in ("topological", "layered", "hybrid"))
            if signature != "000":
                groups[signature].append(int(row["candidate_count"]))
    order = ["100", "010", "001", "110", "101", "011", "111"]
    route_names = {"100": "T only", "010": "L only", "001": "H only", "110": "T+L", "101": "T+H", "011": "L+H", "111": "T+L+H"}

    OUT.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(OUT), pagesize=(W, H))
    c.setTitle("Audited route yield and post-relaxation 2D screening")
    c.setFont("Helvetica-Bold", 16)
    c.setFillColor(INK)
    c.drawString(38, 505, "Multi-route candidate generation and screening")
    label(c, 38, 486, "T = topological, L = layered, H = hybrid; all values recomputed from packaged CSVs", 9, GREY)

    # A. Seven mutually exclusive parent-overlap groups.
    panel_title(c, 38, 457, "a  Parent overlap (47,617 mapped parents)")
    max_parent = max(len(groups[k]) for k in order)
    for i, sig in enumerate(order):
        x = 38 + i * 51
        value = len(groups[sig])
        h = 128 * value / max_parent
        c.setFillColor(PALETTE["hybrid"] if "1" == sig[2] else PALETTE["topological"])
        c.rect(x, 294, 29, h, fill=1, stroke=0)
        label(c, x - 1, 298 + h, f"{value:,}", 7)
        label(c, x - 3, 279, route_names[sig], 7)
    c.setStrokeColor(GRID)
    c.line(36, 293, 401, 293)

    # B. Candidate counts before and after structural deduplication.
    panel_title(c, 440, 457, "b  Candidates by route")
    for i, route in enumerate(("topological", "layered", "hybrid")):
        y = 418 - i * 48
        pre = SUMMARY["route_counts_pre_deduplication"][route]
        post = SUMMARY["route_counts_post_deduplication"][route]
        label(c, 440, y + 7, route.title(), 9)
        c.setFillColor(PALETTE[route])
        c.rect(535, y + 5, 190 * pre / 40000, 11, fill=1, stroke=0)
        label(c, 730, y + 7, f"{pre:,}", 8)
        c.setFillColor(colors.HexColor("#b8c3cc"))
        c.rect(535, y - 10, 190 * post / 40000, 10, fill=1, stroke=0)
        label(c, 730, y - 8, f"{post:,}", 8)
    label(c, 535, 278, "Color: before dedup   Grey: after dedup", 8, GREY)

    # C. Mean yield for each parent overlap region.
    panel_title(c, 38, 244, "c  Mean candidates per mapped parent")
    for i, sig in enumerate(order):
        x = 38 + i * 51
        value = statistics.mean(groups[sig])
        h = 112 * value / 4
        c.setFillColor(colors.HexColor("#7593ac"))
        c.rect(x, 81, 29, h, fill=1, stroke=0)
        label(c, x + 2, 84 + h, f"{value:.2f}", 8)
        label(c, x - 3, 67, route_names[sig], 7)
    c.setStrokeColor(GRID)
    c.line(36, 80, 401, 80)

    # D. Screening funnel with exact denominators.
    panel_title(c, 440, 244, "d  Post-merge screening funnel")
    funnel = [
        ("Merged route CIFs", 76852),
        ("Unique candidate rows", 73105),
        ("CHGNet relaxed", 69624),
        ("Relaxed and 2D", 68089),
    ]
    for i, (name, value) in enumerate(funnel):
        y = 210 - i * 38
        label(c, 440, y + 13, name, 9)
        c.setFillColor(colors.HexColor("#6c9aa2") if i < 3 else colors.HexColor("#347d65"))
        c.rect(440, y - 1, 250 * value / 76852, 10, fill=1, stroke=0)
        label(c, 701, y + 1, f"{value:,}", 9)

    label(c, 38, 30, "2D denotes the unpassivated geometry classifier after a successful CHGNet relaxation; no DFT stability is implied.", 8, GREY)
    c.showPage()
    c.save()
    print(OUT)


if __name__ == "__main__":
    main()
