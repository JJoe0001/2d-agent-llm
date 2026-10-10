"""Count anonymous-stoichiometry × archived-layer-group classes by route.

This is a defined diversity descriptor, not a crystallographic prototype match.
"""

from __future__ import annotations

import csv
import gzip
import json
from collections import Counter, defaultdict
from pathlib import Path

from pymatgen.core import Composition


ROOT = Path(__file__).resolve().parents[1]
LABELS = ROOT / "data/computed_results/candidate_layergroup_labels.csv.gz"
CANDIDATES = ROOT / "data/final_2d_candidates/final_2d_candidates.csv.gz"
OUTPUT = ROOT / "data/computed_results/symmetry_composition_diversity.json"
ROUTES = ("topological", "layered", "hybrid")


def main():
    with gzip.open(LABELS, "rt", newline="") as stream:
        labels = {row["candidate_file"]: row["layergroup_number"] for row in csv.DictReader(stream)}

    route_classes = defaultdict(set)
    route_space = defaultdict(set)
    route_stoich = defaultdict(set)
    class_route_membership = defaultdict(set)
    missing = Counter()
    nrows = 0
    with gzip.open(CANDIDATES, "rt", newline="") as stream:
        for row in csv.DictReader(stream):
            nrows += 1
            filename = row["candidate_file"]
            lg = labels.get(filename)
            formula = row["candidate_formula"]
            if not lg or not lg.isdecimal():
                missing["layer_group"] += 1
                continue
            try:
                anon = Composition(formula).anonymized_formula
            except Exception:
                missing["formula"] += 1
                continue
            signature = (anon, int(lg))
            for route in ROUTES:
                if row[f"route_{route}"] == "1":
                    route_classes[route].add(signature)
                    route_space[route].add(int(lg))
                    route_stoich[route].add(anon)
                    class_route_membership[signature].add(route)

    results = {
        "definition": "Candidate-level class = (pymatgen anonymous reduced stoichiometric formula, archived 2D layer-group number). Species identities and atomic coordinates within a symmetry class are ignored. It is a coarse composition-symmetry descriptor, not an established structural prototype identifier.",
        "stage": "post-deduplication initial CIFs; archived layer-group labels, no new symmetry computation",
        "candidate_rows": nrows,
        "layer_group_label_rows": len(labels),
        "excluded": dict(missing),
        "unique_classes_all_routes": len(class_route_membership),
        "route_counts": {
            route: {
                "anonymous_stoichiometries": len(route_stoich[route]),
                "layer_groups": len(route_space[route]),
                "composition_symmetry_classes": len(route_classes[route]),
                "classes_exclusive_to_route": sum(class_route_membership[c] == {route} for c in route_classes[route]),
            }
            for route in ROUTES
        },
    }
    OUTPUT.write_text(json.dumps(results, indent=2) + "\n")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
