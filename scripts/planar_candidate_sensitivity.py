"""Rerun planar-gap variants through layer extraction on a fixed parent panel.

This is a geometric-branch code-stage study. It does not run BONDDEL,
cross-route deduplication, CHGNet relaxation, or DFT.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
import time
from collections import Counter
from importlib.metadata import version
from pathlib import Path

from pymatgen.analysis.structure_matcher import StructureMatcher
from pymatgen.core import Structure

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "code/exfo_agent"))
from tools.extract_layer import extract_layer_component_impl  # noqa: E402
from tools.planar_gap import planar_gap_scan_impl  # noqa: E402
from tools.workflow import SMART_LAYER_DELTAS  # noqa: E402

VARIANTS = {
    "baseline": {},
    "gap_0p65": {"gap_level": 0.65},
    "gap_0p85": {"gap_level": 0.85},
    "dmin_1p5": {"dmin": 1.5},
    "dmin_2p1": {"dmin": 2.1},
    "grid_24": {"n_grid": (24, 24, 24)},
    "grid_48": {"n_grid": (48, 48, 48)},
    "gauss_0p35": {"gaussian_sigma_scale": 0.35},
    "gauss_0p65": {"gaussian_sigma_scale": 0.65},
}
MATCHER = StructureMatcher(
    ltol=0.2, stol=0.3, angle_tol=5, primitive_cell=True,
    attempt_supercell=False,
)


def unique_structures(candidates: list[dict]) -> list[dict]:
    retained = []
    for candidate in candidates:
        if not any(
            MATCHER.fit(candidate["structure"], old["structure"])
            for old in retained
            if candidate["formula"] == old["formula"]
        ):
            retained.append(candidate)
    return retained


def intersection_size(a: list[dict], b: list[dict]) -> int:
    used = set()
    matches = 0
    for left in a:
        for index, right in enumerate(b):
            if index not in used and left["formula"] == right["formula"] and MATCHER.fit(
                left["structure"], right["structure"]
            ):
                used.add(index)
                matches += 1
                break
    return matches


def extract_candidates(parent: Structure, settings: dict) -> tuple[list[dict], list[dict], int]:
    scanned = planar_gap_scan_impl(parent, top_k=3, **settings)
    planes = scanned.get("candidates", [])
    candidates = []
    failures = []
    attempts = 0
    for plane in planes:
        for delta in SMART_LAYER_DELTAS:
            attempts += 1
            result = extract_layer_component_impl(
                parent, hkl=plane["hkl"], shift=plane["gap_center_frac"],
                delta=delta, timeout_seconds=60,
            )
            if result.get("layer_dim_rank_proxy") == 2 and result.get("layer_nsites", 0) > 0:
                cif = result["cif"]
                child = Structure.from_str(cif, fmt="cif")
                candidates.append({
                    "structure": child,
                    "formula": child.composition.reduced_formula,
                    "hkl": plane["hkl"],
                    "delta": delta,
                    "n_sites": len(child),
                    "cif_sha256": hashlib.sha256(cif.encode()).hexdigest(),
                })
                break
            if result.get("warnings"):
                failures.append({
                    "hkl": plane["hkl"], "delta": delta,
                    "warnings": result["warnings"],
                })
    return unique_structures(candidates), failures, attempts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("parent_dir", type=Path)
    parser.add_argument(
        "--panel", type=Path,
        default=ROOT / "data/computed_results/planar_sensitivity_panel.csv",
    )
    parser.add_argument(
        "--output", type=Path,
        default=ROOT / "data/computed_results/planar_candidate_sensitivity.json",
    )
    parser.add_argument(
        "--variants", default="all",
        help="Comma-separated variant names including baseline, or all",
    )
    args = parser.parse_args()
    selected_variants = (
        VARIANTS if args.variants == "all"
        else {name: VARIANTS[name] for name in args.variants.split(",")}
    )
    if "baseline" not in selected_variants:
        raise ValueError("Selected variants must include baseline")
    with args.panel.open(newline="") as stream:
        panel = list(csv.DictReader(stream))
    results = {}
    parent_hashes = {}
    for number, row in enumerate(panel, 1):
        parent_id = row["parent_id"]
        cif_path = args.parent_dir / f"{parent_id}.cif"
        parent_hashes[parent_id] = hashlib.sha256(cif_path.read_bytes()).hexdigest()
        parent = Structure.from_file(cif_path)
        per_variant = {}
        for name, settings in selected_variants.items():
            start = time.monotonic()
            try:
                candidates, failures, attempts = extract_candidates(parent, settings)
                per_variant[name] = {
                    "status": "ok",
                    "candidates": candidates,
                    "failures": failures,
                    "n_delta_attempts": attempts,
                    "elapsed_seconds": round(time.monotonic() - start, 3),
                }
            except Exception as exc:
                per_variant[name] = {
                    "status": type(exc).__name__,
                    "error": str(exc),
                    "candidates": [],
                    "failures": [],
                    "n_delta_attempts": 0,
                    "elapsed_seconds": round(time.monotonic() - start, 3),
                }
        results[parent_id] = per_variant
        print(f"{number}/{len(panel)} {parent_id}", flush=True)
    summary = {}
    baseline_ids = {
        parent_id for parent_id in results
        if results[parent_id]["baseline"]["status"] == "ok"
    }
    for name, settings in selected_variants.items():
        comparable = [
            parent_id for parent_id in baseline_ids
            if results[parent_id][name]["status"] == "ok"
        ]
        overlaps = [
            (
                parent_id,
                len(results[parent_id]["baseline"]["candidates"]),
                len(results[parent_id][name]["candidates"]),
                intersection_size(
                    results[parent_id]["baseline"]["candidates"],
                    results[parent_id][name]["candidates"],
                ),
            )
            for parent_id in comparable
        ]
        nonempty = [(a, b, intersection) for _, a, b, intersection in overlaps if a or b]
        summary[name] = {
            "settings": settings,
            "status_counts": dict(Counter(results[p][name]["status"] for p in results)),
            "n_parents_with_candidates": sum(
                len(results[p][name]["candidates"]) > 0 for p in results
            ),
            "n_unique_within_parent_candidates": sum(
                len(results[p][name]["candidates"]) for p in results
            ),
            "n_same_candidate_set_as_baseline": sum(
                a == b == intersection for _, a, b, intersection in overlaps
            ),
            "n_comparable": len(comparable),
            "n_nonempty_union": len(nonempty),
            "micro_jaccard_parent_linked": (
                sum(intersection for _, _, intersection in nonempty)
                / sum(a + b - intersection for a, b, intersection in nonempty)
                if nonempty else None
            ),
            "total_elapsed_seconds": round(
                sum(results[p][name]["elapsed_seconds"] for p in results), 3
            ),
        }
    serializable = {}
    for parent_id, variants in results.items():
        serializable[parent_id] = {}
        for name, record in variants.items():
            serializable[parent_id][name] = {
                **{k: v for k, v in record.items() if k != "candidates"},
                "candidates": [
                    {k: v for k, v in candidate.items() if k != "structure"}
                    for candidate in record["candidates"]
                ],
            }
    output = {
        "description": "Current-code geometric-branch rerun through extracted rank-2 slabs; not the historical production run or final workflow sensitivity.",
        "pymatgen_version": version("pymatgen"),
        "panel_sha256": hashlib.sha256(args.panel.read_bytes()).hexdigest(),
        "parent_cif_sha256": parent_hashes,
        "n_parents": len(panel),
        "delta_sequence": SMART_LAYER_DELTAS,
        "matcher": {
            "ltol": 0.2, "stol": 0.3, "angle_tol": 5,
            "primitive_cell": True, "attempt_supercell": False,
        },
        "variants": summary,
        "records": serializable,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2) + "\n")
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    main()
