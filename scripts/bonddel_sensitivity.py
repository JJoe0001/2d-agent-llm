"""Stratified, code-stage-only sensitivity of BONDDEL energy settings."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
import time
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

from pymatgen.core import Structure


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "code/exfo_agent"))
from core.config import config  # noqa: E402
from tools.bond_del import BondDelAlgorithm  # noqa: E402
from tools.xcp_potential import UniversalPotential  # noqa: E402


VARIANTS = {
    "baseline": (0.03, -2.0),
    "cluster_0p02": (0.02, -2.0),
    "cluster_0p05": (0.05, -2.0),
    "floor_m1p5": (0.03, -1.5),
    "floor_m2p5": (0.03, -2.5),
}
POTENTIAL = ROOT / "code/exfo_agent/tools/POTDATA_morse_yukawa_2025"


def select_panel(panel_path: Path, parent_dir: Path, n_per_signature: int):
    groups = defaultdict(list)
    with panel_path.open(newline="") as stream:
        for row in csv.DictReader(stream):
            parent_id = row["parent_id"]
            path = parent_dir / f"{parent_id}.cif"
            structure = Structure.from_file(path)
            groups[row["route_signature_topological_layered_hybrid"]].append(
                (len(structure), parent_id, path)
            )
    selected = []
    for signature in sorted(groups):
        choices = sorted(groups[signature])[:n_per_signature]
        if len(choices) != n_per_signature:
            raise ValueError(f"Too few parents in signature {signature}")
        selected.extend((signature, atoms, parent_id, str(path)) for atoms, parent_id, path in choices)
    return selected


def run_one(task):
    signature, n_atoms, parent_id, path, variant, cluster_tol, energy_floor, timeout = task
    config.ENERGY_CLUSTER_TOLERANCE_EV = cluster_tol
    config.ENERGY_CUTOFF_THRESHOLD_EV = energy_floor
    structure = Structure.from_file(path)
    potential = UniversalPotential(str(POTENTIAL))
    t0 = time.monotonic()
    try:
        algorithm = BondDelAlgorithm(
            structure, universal_potential=potential, timeout_seconds=timeout
        )
        result = algorithm.run()
        components = sorted(
            tuple(sorted(int(x) for x in cluster)) for cluster in result.final_clusters
        )
        threshold = (
            float(result.deleted_bonds[0]["energy_threshold"])
            if result.deleted_bonds else None
        )
        status = "SUCCESS" if result.success else "NO_2D"
        message = result.message
    except Exception as exc:
        components = []
        threshold = None
        status = "ERROR"
        message = f"{type(exc).__name__}: {exc}"
    if "TIMEOUT" in (message or "").upper():
        status = "TIMEOUT"
    return {
        "parent_id": parent_id,
        "route_signature": signature,
        "n_parent_atoms": n_atoms,
        "variant": variant,
        "cluster_tolerance_eV": cluster_tol,
        "energy_scan_floor_eV": energy_floor,
        "status": status,
        "threshold_eV": threshold,
        "component_atom_indices": components,
        "message": message,
        "elapsed_seconds": round(time.monotonic() - t0, 3),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("parent_dir", type=Path)
    parser.add_argument("--panel", type=Path, default=ROOT / "data/computed_results/planar_sensitivity_panel.csv")
    parser.add_argument("--parents-per-signature", type=int, default=2)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--timeout-seconds", type=int, default=60)
    parser.add_argument("--output", type=Path, default=ROOT / "data/computed_results/bonddel_sensitivity.json")
    args = parser.parse_args()
    panel = select_panel(args.panel, args.parent_dir, args.parents_per_signature)
    tasks = [
        (*parent, variant, *values, args.timeout_seconds)
        for parent in panel
        for variant, values in VARIANTS.items()
    ]
    results = []
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(run_one, task) for task in tasks]
        for future in as_completed(futures):
            results.append(future.result())
            if len(results) % 10 == 0:
                print(f"Completed {len(results)}/{len(tasks)}", flush=True)
    results.sort(key=lambda r: (r["parent_id"], r["variant"]))
    baseline = {r["parent_id"]: r for r in results if r["variant"] == "baseline"}
    summary = {}
    for variant in VARIANTS:
        rows = [r for r in results if r["variant"] == variant]
        summary[variant] = {
            "settings": {"cluster_tolerance_eV": VARIANTS[variant][0], "energy_scan_floor_eV": VARIANTS[variant][1]},
            "status_counts": dict(Counter(r["status"] for r in rows)),
            "n_same_component_atom_sets_as_baseline": sum(
                r["component_atom_indices"] == baseline[r["parent_id"]]["component_atom_indices"]
                and r["status"] == baseline[r["parent_id"]]["status"]
                for r in rows
            ),
            "total_elapsed_seconds": round(sum(r["elapsed_seconds"] for r in rows), 3),
        }
    output = {
        "description": "Code-stage BONDDEL rerun on the smallest-site parents per route-signature stratum of the supplied panel; not full candidate extraction or CHGNet validation.",
        "selection": {
            "panel_file": args.panel.name,
            "panel_sha256": hashlib.sha256(args.panel.read_bytes()).hexdigest(),
            "parents_per_signature": args.parents_per_signature,
        },
        "n_parents": len(panel),
        "n_tasks": len(tasks),
        "potential_sha256": hashlib.sha256(POTENTIAL.read_bytes()).hexdigest(),
        "variants": summary,
        "records": results,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"n_parents": len(panel), "variants": summary}, indent=2), flush=True)


if __name__ == "__main__":
    main()
