"""Reproduce the current-code Zn2Cr2O5 bond-deletion graph example.

Usage: PYTHONPATH=code/exfo_agent python scripts/reproduce_bonddel_example.py MP_PARENT_CIF
The parent MP CIF is not redistributed here; verify its SHA-256 first.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

from pymatgen.core import Structure


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "code/exfo_agent"))
from tools.bond_del import BondDelAlgorithm  # noqa: E402
from tools.xcp_potential import UniversalPotential  # noqa: E402


PARENT_SHA256 = "3c89c30381259bbbaf1ae44afee8951f8b945367f55923c98abf6b25a0bacf46"
POTENTIAL = ROOT / "code/exfo_agent/tools/POTDATA_morse_yukawa_2025"


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python scripts/reproduce_bonddel_example.py MP_PARENT_CIF")
    parent = Path(sys.argv[1])
    if hashlib.sha256(parent.read_bytes()).hexdigest() != PARENT_SHA256:
        raise ValueError("parent CIF differs from the archived calculation input")
    structure = Structure.from_file(parent)
    algorithm = BondDelAlgorithm(
        structure,
        universal_potential=UniversalPotential(str(POTENTIAL)),
        timeout_seconds=60,
    )
    result = algorithm.run()
    if not result.success:
        raise ValueError(f"BONDDEL did not find a 2D graph: {result.message}")
    threshold = float(result.deleted_bonds[0]["energy_threshold"])
    clusters = []
    for nodes in result.final_clusters:
        indices = [int(value) for value in sorted(nodes)]
        fragment = Structure(
            structure.lattice,
            [structure.sites[i].species for i in indices],
            [structure.frac_coords[i] for i in indices],
        )
        clusters.append({"atom_indices_zero_based": indices, "n_atoms": len(indices), "formula": fragment.composition.reduced_formula})
    output = {
        "parent_id": "mp-1376393",
        "parent_cif_sha256": PARENT_SHA256,
        "parent_formula": structure.composition.reduced_formula,
        "n_parent_atoms": len(structure),
        "potential_sha256": hashlib.sha256(POTENTIAL.read_bytes()).hexdigest(),
        "bond_energy_cluster_tolerance_eV": 0.03,
        "weak_bond_scan_floor_eV": -2.0,
        "n_weighted_graph_edges": len(algorithm.bonds),
        "first_successful_threshold_eV": threshold,
        "n_edges_with_energy_at_or_above_threshold": int(sum(bond["energy"] >= threshold for bond in algorithm.bonds)),
        "threshold_step_index": int(result.steps_taken),
        "two_dimensional_components": clusters,
        "interpretation": "graph-search example only; no cleavage energy or DFT stability inferred",
    }
    target = ROOT / "data/computed_results/bonddel_worked_example.json"
    target.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
