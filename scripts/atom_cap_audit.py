"""Audit how the CHGNet 500-atom safeguard affects candidate eligibility."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--table", type=Path,
        default=ROOT / "data/final_2d_candidates/final_2d_candidates.csv",
    )
    parser.add_argument(
        "--output", type=Path,
        default=ROOT / "data/computed_results/atom_cap_audit.json",
    )
    args = parser.parse_args()
    rows = []
    with args.table.open(newline="") as stream:
        for row in csv.DictReader(stream):
            rows.append({
                "atoms": int(float(row["num_atoms"])),
                "status": row["validation_status"],
                "relaxed": row["is_relaxed"].strip().lower() == "true",
            })
    bins = {}
    for label, low, high in (
        ("at_most_400", 0, 400),
        ("401_to_500", 400, 500),
        ("501_to_600", 500, 600),
        ("over_600", 600, float("inf")),
    ):
        selected = [row for row in rows if low < row["atoms"] <= high]
        bins[label] = {
            "n_candidates": len(selected),
            "n_relaxed_flag": sum(row["relaxed"] for row in selected),
            "status_counts": dict(Counter(row["status"] for row in selected)),
        }
    output = {
        "interpretation": "Recorded eligibility and statuses only; raising the cap cannot predict CHGNet outcomes for previously skipped structures.",
        "table_sha256": hashlib.sha256(args.table.read_bytes()).hexdigest(),
        "n_records": len(rows),
        "bins": bins,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2) + "\n")
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
