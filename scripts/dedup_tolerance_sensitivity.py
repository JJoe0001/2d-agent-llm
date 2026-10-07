"""Stress-test StructureMatcher tolerance on a fixed archived-candidate panel.

The source archive is already deduplicated at the published settings. This
test can detect extra mergers under looser settings, but cannot recover
records removed during the original deduplication under tighter settings.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
import tarfile
import time
from collections import defaultdict
from importlib.metadata import version
from pathlib import Path

from pymatgen.analysis.structure_matcher import StructureMatcher
from pymatgen.core import Structure

ROOT = Path(__file__).resolve().parents[1]
CONFIGS = {
    "tight": (0.1, 0.2, 3),
    "baseline": (0.2, 0.3, 5),
    "loose": (0.3, 0.4, 7),
}
SEED = 20261007


def load_panel(table: Path, n_groups: int, per_group: int) -> list[dict]:
    grouped = defaultdict(list)
    with table.open(newline="") as stream:
        for row in csv.DictReader(stream):
            formula = row.get("candidate_formula", "")
            if formula and row.get("candidate_cif_exists") == "True":
                grouped[formula].append(row)
    eligible = sorted(
        (rows for rows in grouped.values() if len(rows) >= per_group),
        key=lambda rows: (-len(rows), rows[0]["candidate_formula"]),
    )
    if len(eligible) < n_groups:
        raise ValueError("Not enough formula groups for requested panel")
    rng = random.Random(SEED)
    return [
        row
        for group in eligible[:n_groups]
        for row in rng.sample(sorted(group, key=lambda r: r["candidate_file"]), per_group)
    ]


def read_archive_structures(archive: Path, panel: list[dict]) -> dict[str, dict]:
    wanted = {row["candidate_file"] for row in panel}
    found = {}
    with tarfile.open(archive, "r:gz") as stream:
        for member in stream:
            name = Path(member.name).name
            if name not in wanted or not member.isfile():
                continue
            raw = stream.extractfile(member).read()
            found[name] = {
                "structure": Structure.from_str(raw.decode(), fmt="cif"),
                "sha256": hashlib.sha256(raw).hexdigest(),
            }
            if len(found) == len(wanted):
                break
    missing = wanted - found.keys()
    if missing:
        raise ValueError(f"Missing {len(missing)} panel CIFs from archive")
    return found


def representatives(panel: list[dict], structures: dict, config: tuple) -> tuple[list[str], list[dict]]:
    matcher = StructureMatcher(
        ltol=config[0], stol=config[1], angle_tol=config[2],
        primitive_cell=True, attempt_supercell=False,
    )
    by_formula = defaultdict(list)
    for row in panel:
        by_formula[row["candidate_formula"]].append(row["candidate_file"])
    kept = []
    merges = []
    for formula in sorted(by_formula):
        existing = []
        for name in sorted(by_formula[formula]):
            structure = structures[name]["structure"]
            match = next(
                (old for old in existing if matcher.fit(structure, structures[old]["structure"])),
                None,
            )
            if match is None:
                existing.append(name)
                kept.append(name)
            else:
                merges.append({"formula": formula, "merged": name, "representative": match})
    return kept, merges


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--table", type=Path,
        default=ROOT / "data/final_2d_candidates/final_2d_candidates.csv",
    )
    parser.add_argument(
        "--archive", type=Path,
        default=ROOT / "data/external_large_files/unique_candidate_cifs.tar.gz",
    )
    parser.add_argument("--groups", type=int, default=50)
    parser.add_argument("--per-group", type=int, default=10)
    parser.add_argument(
        "--output", type=Path,
        default=ROOT / "data/computed_results/dedup_tolerance_sensitivity.json",
    )
    args = parser.parse_args()
    panel = load_panel(args.table, args.groups, args.per_group)
    structures = read_archive_structures(args.archive, panel)
    summary = {}
    for name, config in CONFIGS.items():
        start = time.monotonic()
        kept, merges = representatives(panel, structures, config)
        summary[name] = {
            "settings": {"ltol": config[0], "stol": config[1], "angle_tol": config[2]},
            "n_unique": len(kept),
            "n_merged": len(merges),
            "elapsed_seconds": round(time.monotonic() - start, 3),
            "merges": merges,
        }
        print(name, len(kept), "unique", len(merges), "merged", flush=True)
    output = {
        "interpretation": "Fixed stress panel sampled from already-deduplicated candidate CIF archive; not sensitivity of the original 76,852-to-73,105 deduplication.",
        "pymatgen_version": version("pymatgen"),
        "seed": SEED,
        "source_table_sha256": hashlib.sha256(args.table.read_bytes()).hexdigest(),
        "source_archive_sha256": hashlib.sha256(args.archive.read_bytes()).hexdigest(),
        "n_formula_groups": args.groups,
        "sampled_per_group": args.per_group,
        "n_candidates": len(panel),
        "panel": [
            {
                "candidate_file": row["candidate_file"],
                "candidate_formula": row["candidate_formula"],
                "cif_sha256": structures[row["candidate_file"]]["sha256"],
            }
            for row in panel
        ],
        "results": summary,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2) + "\n")


if __name__ == "__main__":
    main()
