"""Recompute revision screening counts from the compact, published tables.

This audit is deliberately limited to counts and labels represented in the
packaged CSVs. It does not infer DFT stability or validate missing CIFs.
"""

from __future__ import annotations

import csv
import gzip
import json
import re
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data/computed_results/revision_screening_summary.json"


def read_table(name: str, key: str) -> dict[str, dict[str, str]]:
    with gzip.open(ROOT / name, "rt", encoding="utf-8-sig", newline="") as stream:
        rows = csv.DictReader(stream)
        result: dict[str, dict[str, str]] = {}
        for row in rows:
            value = row[key]
            if value in result:
                raise ValueError(f"duplicate {key}: {value} in {name}")
            result[value] = row
    return result


def route_from_filename(filename: str) -> str:
    if filename.endswith("_2D_ortho.cif"):
        return "topological"
    if filename.endswith("_2DMatPedia.cif"):
        return "layered"
    if filename.endswith(".cif") and filename.rsplit("_", 1)[-1][:-4].isdigit():
        return "hybrid"
    raise ValueError(f"unrecognized candidate filename: {filename}")


def count_by_route(rows: dict[str, dict[str, str]]) -> dict[str, int]:
    return dict(sorted(Counter(route_from_filename(name) for name in rows).items()))


def chemical_system(formula: str) -> str:
    elements = set(re.findall(r"[A-Z][a-z]?", formula))
    if not elements:
        raise ValueError(f"cannot parse elements from formula: {formula}")
    return "-".join(sorted(elements))


def main() -> None:
    merged = read_table("data/route_outputs/merged_candidate_manifest.csv.gz", "candidate_file")
    final = read_table("data/final_2d_candidates/final_2d_candidates.csv.gz", "candidate_file")
    dimensionality = {}
    for variant in ("no_pass", "passivated"):
        dimensionality[variant] = read_table(
            f"data/dimensionality/{variant}_dimensionality_post_ml.csv.gz", "original_file"
        )
    parents = read_table("data/computed_results/parent_exfoliability_labels.csv.gz", "parent_id")

    for name, row in merged.items():
        if row["route"] != route_from_filename(name):
            raise ValueError(f"route mismatch in merged manifest: {name}")
    if not set(final).issubset(merged):
        raise ValueError("final candidates missing from merged manifest")

    orphan_candidates = []
    for name, row in final.items():
        route = route_from_filename(name)
        flags = {r: row[f"route_{r}"] for r in ("topological", "layered", "hybrid")}
        if flags[route] != "1" or sum(x == "1" for x in flags.values()) != 1:
            raise ValueError(f"route flags inconsistent with filename: {name}")
        if row["parent_id"] not in parents:
            orphan_candidates.append(name)

    result: dict[str, object] = {
        "definitions": {
            "pre_deduplication": "Merged route CIF filenames before cross-route deduplication",
            "post_deduplication": "Final candidate CSV filenames after deduplication",
            "raw_2d_label": "dim_type == 2D, including failed or skipped relaxations",
            "relaxed_2d": "dim_type == 2D AND is_relaxed == True",
            "stability_caution": "CHGNet validation_status is a workflow label, not a DFT 2D convex-hull or dynamical-stability test",
        },
        "n_parents": len(parents),
        "n_distinct_parent_id_values_including_blank": len({row["parent_id"] for row in final.values()}),
        "n_mapped_parents_with_candidates": len({row["parent_id"] for row in final.values() if row["parent_id"] in parents}),
        "candidates_without_parent_mapping": orphan_candidates,
        "n_merged_candidates": len(merged),
        "n_unique_candidates": len(final),
        "n_deduplicated": len(merged) - len(final),
        "route_counts_pre_deduplication": count_by_route(merged),
        "route_counts_post_deduplication": count_by_route(final),
        "final_validation_status": dict(sorted(Counter(row["validation_status"] for row in final.values()).items())),
        "final_is_relaxed": dict(sorted(Counter(row["is_relaxed"] for row in final.values()).items())),
        "n_distinct_candidate_formula_strings": len({row["candidate_formula"] for row in final.values() if row["candidate_formula"]}),
        "n_candidates_without_formula": sum(not row["candidate_formula"] for row in final.values()),
        "n_distinct_chemical_systems": len({chemical_system(row["candidate_formula"]) for row in final.values() if row["candidate_formula"]}),
        "diversity_by_route": {
            route: {
                "n_formula_strings": len({row["candidate_formula"] for name, row in final.items() if route_from_filename(name) == route}),
                "n_chemical_systems": len({chemical_system(row["candidate_formula"]) for name, row in final.items() if route_from_filename(name) == route and row["candidate_formula"]}),
            }
            for route in ("topological", "layered", "hybrid")
        },
    }
    dim_summary = {}
    for variant, rows in dimensionality.items():
        if set(rows) != set(final):
            raise ValueError(f"dimensionality table filename set differs: {variant}")
        for name, row in rows.items():
            if row["validation_status"] != final[name]["validation_status"] and variant == "no_pass":
                raise ValueError(f"validation status mismatch: {name}")
            if row["is_true_2d"] != str(row["dim_type"] == "2D"):
                raise ValueError(f"is_true_2d inconsistent: {name}")
        dim_summary[variant] = {
            "dim_type_counts": dict(sorted(Counter(row["dim_type"] for row in rows.values()).items())),
            "n_raw_2d": sum(row["dim_type"] == "2D" for row in rows.values()),
            "n_relaxed_2d": sum(row["dim_type"] == "2D" and row["is_relaxed"] == "True" for row in rows.values()),
            "n_2d_without_successful_relaxation": sum(row["dim_type"] == "2D" and row["is_relaxed"] != "True" for row in rows.values()),
            "n_relaxed": sum(row["is_relaxed"] == "True" for row in rows.values()),
            "relaxed_2d_by_route": dict(sorted(Counter(route_from_filename(name) for name, row in rows.items() if row["dim_type"] == "2D" and row["is_relaxed"] == "True").items())),
        }
    result["dimensionality"] = dim_summary
    OUTPUT.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
