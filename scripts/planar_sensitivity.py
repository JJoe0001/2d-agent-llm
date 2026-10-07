"""Run a deterministic planar-gap parameter sensitivity panel.

Requires the project scientific dependencies and a local parent CIF directory.
Example:
  PYTHONPATH=code/exfo_agent python scripts/planar_sensitivity.py /path/to/parent_cifs

The result tests the planar-gap stage only; it is not a whole-pipeline rerun.
"""

from __future__ import annotations

import csv
import gzip
import json
import random
import sys
import time
from collections import defaultdict
from pathlib import Path

from pymatgen.core import Structure

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "code/exfo_agent"))
from tools.planar_gap import planar_gap_scan_impl  # noqa: E402


SEED = 20261007
PER_GROUP = 6
VARIANTS = {
    "baseline": {},
    "gap_0p65": {"gap_level": 0.65},
    "gap_0p85": {"gap_level": 0.85},
    "dmin_1p5": {"dmin": 1.5},
    "dmin_2p1": {"dmin": 2.1},
    "grid_24": {"n_grid": (24, 24, 24)},
    "grid_48": {"n_grid": (48, 48, 48)},
}


def select_panel(cif_dir: Path) -> list[tuple[str, str]]:
    groups: dict[str, list[str]] = defaultdict(list)
    with gzip.open(ROOT / "data/computed_results/parent_exfoliability_labels.csv.gz", "rt", encoding="utf-8-sig") as stream:
        for row in csv.DictReader(stream):
            signature = "".join(row[f"route_{route}"] for route in ("topological", "layered", "hybrid"))
            groups[signature].append(row["parent_id"])
    rng = random.Random(SEED)
    panel = []
    for signature in sorted(groups):
        available = [id for id in groups[signature] if (cif_dir / f"{id}.cif").is_file()]
        if len(available) < PER_GROUP:
            raise ValueError(f"too few local CIFs for group {signature}: {len(available)}")
        panel.extend((signature, id) for id in rng.sample(available, PER_GROUP))
    return panel


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python scripts/planar_sensitivity.py PARENT_CIF_DIRECTORY")
    cif_dir = Path(sys.argv[1]).expanduser().resolve()
    panel = select_panel(cif_dir)
    outdir = ROOT / "data/computed_results"
    panel_path = outdir / "planar_sensitivity_panel.csv"
    with panel_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(["parent_id", "route_signature_topological_layered_hybrid"])
        writer.writerows((id, signature) for signature, id in panel)

    records = []
    for index, (signature, id) in enumerate(panel, 1):
        structure = Structure.from_file(cif_dir / f"{id}.cif")
        for variant, settings in VARIANTS.items():
            start = time.monotonic()
            record: dict[str, object] = {
                "parent_id": id,
                "route_signature": signature,
                "n_atoms": len(structure),
                "variant": variant,
            }
            try:
                result = planar_gap_scan_impl(structure, top_k=3, **settings)
                candidates = result.get("candidates", [])
                record["status"] = "ok"
                record["n_planes"] = len(candidates)
                record["top_hkl"] = "|".join(",".join(map(str, x["hkl"])) for x in candidates)
                record["best_score"] = candidates[0]["score_proxy"] if candidates else ""
            except Exception as exc:
                record.update(status=type(exc).__name__, n_planes=0, top_hkl="", best_score="", error=str(exc))
            record["elapsed_seconds"] = round(time.monotonic() - start, 3)
            records.append(record)
        print(f"{index}/{len(panel)} {id}", flush=True)

    details_path = outdir / "planar_sensitivity_details.csv"
    fields = ["parent_id", "route_signature", "n_atoms", "variant", "status", "n_planes", "top_hkl", "best_score", "elapsed_seconds", "error"]
    with details_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(records)

    by_parent: dict[str, dict[str, dict[str, object]]] = defaultdict(dict)
    for record in records:
        by_parent[str(record["parent_id"])][str(record["variant"])] = record
    summary = {"seed": SEED, "parents_per_signature": PER_GROUP, "n_parents": len(panel), "interpretation": "planar-gap scan only; no layer extraction, CHGNet, or DFT", "variants": {}}
    for variant in VARIANTS:
        rows = [by_parent[id][variant] for _, id in panel]
        comparable = [id for _, id in panel if by_parent[id][variant]["status"] == by_parent[id]["baseline"]["status"] == "ok"]
        summary["variants"][variant] = {
            "settings": VARIANTS[variant],
            "n_ok": sum(r["status"] == "ok" for r in rows),
            "n_with_gap_planes": sum(r["status"] == "ok" and r["n_planes"] > 0 for r in rows),
            "n_comparable_to_baseline": len(comparable),
            "n_same_top_hkl_as_baseline": sum(by_parent[id][variant]["top_hkl"].split("|")[0] == by_parent[id]["baseline"]["top_hkl"].split("|")[0] for id in comparable),
            "total_elapsed_seconds": round(sum(float(r["elapsed_seconds"]) for r in rows), 3),
        }
    (outdir / "planar_sensitivity_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
