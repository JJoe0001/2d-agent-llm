"""Check how bond-length delta scans change the initial dimensionality gate."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
import time
from collections import Counter
from pathlib import Path

from pymatgen.core import Structure

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "code/exfo_agent"))
from tools.dimensionality import dimensionality_rank_impl  # noqa: E402

VARIANTS = {
    "baseline": [1.2, 1.3, 1.4],
    "delta_1p2_only": [1.2],
    "delta_1p4_only": [1.4],
    "narrow": [1.2, 1.3],
    "wide": [1.1, 1.2, 1.3, 1.4, 1.5],
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("parent_dir", type=Path)
    parser.add_argument(
        "--panel", type=Path,
        default=ROOT / "data/computed_results/parameter_sensitivity_panel_200.csv",
    )
    parser.add_argument(
        "--output", type=Path,
        default=ROOT / "data/computed_results/dimensionality_delta_sensitivity.json",
    )
    args = parser.parse_args()
    with args.panel.open(newline="") as stream:
        panel = list(csv.DictReader(stream))
    records = []
    parent_hashes = {}
    for index, row in enumerate(panel, 1):
        path = args.parent_dir / f"{row['parent_id']}.cif"
        parent_hashes[row["parent_id"]] = hashlib.sha256(path.read_bytes()).hexdigest()
        structure = Structure.from_file(path)
        for name, deltas in VARIANTS.items():
            start = time.monotonic()
            try:
                result = dimensionality_rank_impl(structure, deltas=deltas)
                records.append({
                    "parent_id": row["parent_id"],
                    "variant": name,
                    "status": "ok",
                    "rank": result["dim_rank"],
                    "coverage": result["coverage"],
                    "delta_used": result["rank_delta_used"],
                    "elapsed_seconds": round(time.monotonic() - start, 3),
                })
            except Exception as exc:
                records.append({
                    "parent_id": row["parent_id"],
                    "variant": name,
                    "status": type(exc).__name__,
                    "error": str(exc),
                    "elapsed_seconds": round(time.monotonic() - start, 3),
                })
        if index % 25 == 0:
            print(f"{index}/{len(panel)}", flush=True)
    by_parent = {
        parent_id: {r["variant"]: r for r in records if r["parent_id"] == parent_id}
        for parent_id in (row["parent_id"] for row in panel)
    }
    summary = {}
    for name, deltas in VARIANTS.items():
        rows = [by_parent[row["parent_id"]][name] for row in panel]
        comparable = [
            row["parent_id"] for row in panel
            if by_parent[row["parent_id"]]["baseline"]["status"] == "ok"
            and by_parent[row["parent_id"]][name]["status"] == "ok"
        ]
        summary[name] = {
            "deltas": deltas,
            "rank_counts": dict(Counter(r.get("rank") for r in rows if r["status"] == "ok")),
            "status_counts": dict(Counter(r["status"] for r in rows)),
            "n_comparable": len(comparable),
            "n_same_rank_as_baseline": sum(
                by_parent[p][name]["rank"] == by_parent[p]["baseline"]["rank"]
                for p in comparable
            ),
            "n_rank2_vs_baseline_rank2": sum(
                by_parent[p][name]["rank"] == by_parent[p]["baseline"]["rank"] == 2
                for p in comparable
            ),
            "total_elapsed_seconds": round(
                sum(r["elapsed_seconds"] for r in rows), 3
            ),
        }
    output = {
        "interpretation": "Initial-dimensionality code-stage check on the 200-parent panel; no layer extraction, BONDDEL, deduplication, or CHGNet.",
        "panel_sha256": hashlib.sha256(args.panel.read_bytes()).hexdigest(),
        "parent_cif_sha256": parent_hashes,
        "variants": summary,
        "records": records,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2) + "\n")
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    main()
