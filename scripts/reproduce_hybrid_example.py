"""Reproduce the BaYMgCuAgO5 hybrid-route extraction from its local MP parent CIF.

Usage: PYTHONPATH=code/exfo_agent python scripts/reproduce_hybrid_example.py MP_PARENT_CIF
The parent CIF is not redistributed in this repository; verify its SHA-256.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

from pymatgen.analysis.structure_matcher import StructureMatcher
from pymatgen.core import Structure


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "code/exfo_agent"))
from tools.workflow import smart_exfoliate_single_impl  # noqa: E402


PARENT_SHA256 = "beb52aa25b2e242a39986e88ca7cbc060a414d9839d703a8af9afaef5e61a8ec"
REFERENCES = {
    "mp-2222863_4606.cif": ROOT / "examples/hybrid_worked_example/mp-2222863_4606.cif",
    "mp-2222863_4607.cif": ROOT / "examples/dft_validation/initial/mp-2222863_4607.cif",
}


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python scripts/reproduce_hybrid_example.py MP_PARENT_CIF")
    parent = Path(sys.argv[1])
    raw = parent.read_bytes()
    if hashlib.sha256(raw).hexdigest() != PARENT_SHA256:
        raise ValueError("parent CIF differs from the archived calculation input")
    result = smart_exfoliate_single_impl(raw.decode("utf-8"), source_name="mp-2222863", top_k=3)
    matcher = StructureMatcher(ltol=0.2, stol=0.3, angle_tol=5)
    output = {
        "parent_id": "mp-2222863",
        "parent_cif_sha256": PARENT_SHA256,
        "formula": result.get("formula"),
        "detected_parent_dimensionality": result.get("dimensionality_detected"),
        "branch": result.get("route_taken"),
        "layers": [],
    }
    for layer in result.get("layers", []):
        structure = Structure.from_str(layer["cif_content"], fmt="cif")
        output["layers"].append(
            {
                "hkl": layer["hkl"],
                "score": layer["score"],
                "used_delta": layer["used_delta"],
                "n_sites": len(structure),
                "formula": layer["formula"],
                "matches_archived_candidate": [
                    name for name, path in REFERENCES.items() if matcher.fit(structure, Structure.from_file(path))
                ],
            }
        )
    if len(output["layers"]) != 3:
        raise ValueError("expected three extracted layers in this frozen example")
    target = ROOT / "data/computed_results/hybrid_worked_example.json"
    target.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
