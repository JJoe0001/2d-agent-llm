"""Select a fixed route-stratified parent panel for parameter reruns."""

from __future__ import annotations

import argparse
import csv
import gzip
import random
from collections import defaultdict
from pathlib import Path

from pymatgen.core import Structure

ROOT = Path(__file__).resolve().parents[1]
SEED = 20261007


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("parent_dir", type=Path)
    parser.add_argument("--per-signature", type=int, default=25)
    parser.add_argument("--max-sites", type=int, default=80)
    parser.add_argument(
        "--output", type=Path,
        default=ROOT / "data/computed_results/parameter_sensitivity_panel_200.csv",
    )
    args = parser.parse_args()
    groups = defaultdict(list)
    source = ROOT / "data/computed_results/parent_exfoliability_labels.csv.gz"
    with gzip.open(source, "rt", encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            signature = "".join(
                row[f"route_{name}"] for name in ("topological", "layered", "hybrid")
            )
            groups[signature].append(row["parent_id"])
    rng = random.Random(SEED)
    panel = []
    for signature in sorted(groups):
        ids = sorted(groups[signature])
        rng.shuffle(ids)
        chosen = 0
        for parent_id in ids:
            path = args.parent_dir / f"{parent_id}.cif"
            if not path.is_file():
                continue
            try:
                n_sites = len(Structure.from_file(path))
            except Exception:
                continue
            if n_sites > args.max_sites:
                continue
            panel.append((parent_id, signature, n_sites))
            chosen += 1
            if chosen == args.per_signature:
                break
        if chosen != args.per_signature:
            raise ValueError(f"Only {chosen} eligible parents for {signature}")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(["parent_id", "route_signature_topological_layered_hybrid", "n_sites"])
        writer.writerows(panel)
    print(f"Wrote {len(panel)} parents to {args.output}")


if __name__ == "__main__":
    main()
