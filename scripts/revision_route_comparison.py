"""Recompute route-level comparisons from the released compact CSV tables."""

from __future__ import annotations

import csv
import gzip
import json
from collections import Counter, defaultdict
from pathlib import Path

from pymatgen.core import Composition


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"


def csv_rows(path: Path):
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8", newline="") as stream:
        yield from csv.DictReader(stream)


def route_of(row: dict[str, str]) -> str:
    routes = [
        name
        for name in ("topological", "layered", "hybrid")
        if row[f"route_{name}"] == "1"
    ]
    if len(routes) != 1:
        raise ValueError(f"Candidate has {len(routes)} route assignments: {row['candidate_file']}")
    return routes[0]


def main() -> None:
    parent_path = DATA / "computed_results/parent_exfoliability_labels.csv.gz"
    candidate_path = DATA / "final_2d_candidates/final_2d_candidates.csv.gz"
    dim_path = DATA / "dimensionality/no_pass_dimensionality_post_ml.csv.gz"
    layergroup_path = DATA / "computed_results/candidate_layergroup_labels.csv.gz"
    output_path = DATA / "computed_results/revision_route_comparison.json"

    parent_counts = Counter()
    parent_combinations = Counter()
    n_parents = 0
    for row in csv_rows(parent_path):
        n_parents += 1
        routes = tuple(
            name
            for name in ("topological", "layered", "hybrid")
            if row[f"route_{name}"] == "1"
        )
        parent_combinations["+".join(routes) if routes else "none"] += 1
        parent_counts.update(routes)

    candidate_counts = Counter()
    chemical_systems = defaultdict(set)
    formulas_missing = Counter()
    route_by_file: dict[str, str] = {}
    for row in csv_rows(candidate_path):
        route = route_of(row)
        filename = row["candidate_file"]
        if filename in route_by_file:
            raise ValueError(f"Repeated candidate filename: {filename}")
        route_by_file[filename] = route
        candidate_counts[route] += 1
        formula = row["candidate_formula"].strip()
        if formula:
            chemical_systems[route].add(Composition(formula).chemical_system)
        else:
            formulas_missing[route] += 1

    relaxed_2d_counts = Counter()
    dimensionality_rows = 0
    for row in csv_rows(dim_path):
        dimensionality_rows += 1
        filename = row["original_file"]
        route = route_by_file.get(filename)
        if route is None:
            raise ValueError(f"Dimensionality row has no candidate: {filename}")
        if row["is_relaxed"] == "True" and row["dim_type"] == "2D":
            relaxed_2d_counts[route] += 1
    if dimensionality_rows != len(route_by_file):
        raise ValueError("Candidate and dimensionality row counts disagree")

    layergroups = defaultdict(set)
    labeled_files = set()
    for row in csv_rows(layergroup_path):
        filename = row["candidate_file"]
        if filename not in route_by_file or filename in labeled_files:
            raise ValueError(f"Unmatched or duplicate layer-group label: {filename}")
        labeled_files.add(filename)
        layergroups[route_by_file[filename]].add(int(row["layergroup_number"]))
    if len(labeled_files) != len(route_by_file):
        raise ValueError("Candidate and layer-group label sets disagree")

    names = ("topological", "layered", "hybrid")
    route_data = {}
    for name in names:
        other_systems = set().union(*(chemical_systems[x] for x in names if x != name))
        route_data[name] = {
            "n_parent_ids": parent_counts[name],
            "n_unique_candidates": candidate_counts[name],
            "n_chemical_systems": len(chemical_systems[name]),
            "n_route_exclusive_chemical_systems": len(chemical_systems[name] - other_systems),
            "n_candidates_without_formula": formulas_missing[name],
            "n_archived_initial_slab_layergroups": len(layergroups[name]),
            "n_relaxed_2d": relaxed_2d_counts[name],
            "relaxed_2d_fraction_of_route_candidates": round(
                relaxed_2d_counts[name] / candidate_counts[name], 6
            ),
        }

    result = {
        "definitions": {
            "route_exclusive_chemical_system": "Element set present in exactly one route's candidate records within this screened dataset; not a claim of database novelty or physical stability.",
            "relaxed_2d": "is_relaxed == True and dim_type == 2D in the unpassivated post-ML dimensionality table; not DFT stability.",
            "route_assignment": "Single provenance flag assigned to each post-deduplication candidate record.",
            "archived_initial_slab_layergroup": "spglib layer-group label on archived post-deduplication CIFs; longest lattice vector chosen as aperiodic direction and symprec 1e-5. These labels are symmetry descriptors, not distinct prototypes or validated phases.",
        },
        "n_input_parents": n_parents,
        "parent_route_combinations": dict(parent_combinations),
        "n_unique_candidates": sum(candidate_counts.values()),
        "n_chemical_systems_total": len(set().union(*chemical_systems.values())),
        "routes": route_data,
    }
    output_path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
