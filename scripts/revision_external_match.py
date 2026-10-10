"""Match candidate slabs to pinned 2DMatPedia, MC2D, or C2DB structures."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import tarfile
import warnings
import zipfile
from collections import Counter, defaultdict
from dataclasses import dataclass
from importlib.metadata import version
from pathlib import Path

import numpy as np
from pymatgen.analysis.structure_matcher import StructureMatcher
from pymatgen.core import Lattice, Structure

warnings.filterwarnings("ignore", category=UserWarning, module="pymatgen")

AREA_TOL = 0.05
THICKNESS_TOL = 0.20
MAX_MATCHER_CANDIDATES = 25
MATCHER = StructureMatcher(
    primitive_cell=True,
    scale=True,
    attempt_supercell=False,
    allow_subset=False,
    ltol=0.2,
    stol=0.3,
    angle_tol=5,
)


@dataclass
class Record:
    identifier: str
    formula: str
    area_per_fu: float
    thickness: float
    structure: Structure


def make_record(identifier: str, structure: Structure) -> Record:
    lattice = np.asarray(structure.lattice.matrix, dtype=float)
    vacuum_axis = max(range(3), key=lambda i: structure.lattice.abc[i])
    inplane = [i for i in range(3) if i != vacuum_axis]
    area = float(np.linalg.norm(np.cross(lattice[inplane[0]], lattice[inplane[1]])))
    normal = lattice[vacuum_axis] / np.linalg.norm(lattice[vacuum_axis])
    heights = np.asarray(structure.cart_coords) @ normal
    thickness = float(np.ptp(heights))
    n_formula_units = (
        structure.composition.num_atoms / structure.composition.reduced_composition.num_atoms
    )
    canonical_lattice = lattice[[inplane[0], inplane[1], vacuum_axis]].copy()
    canonical_lattice[2] = normal * 25.0
    canonical = Structure(
        Lattice(canonical_lattice),
        structure.species,
        structure.cart_coords,
        coords_are_cartesian=True,
    )
    frac = canonical.frac_coords
    z = frac[:, 2]
    frac[:, 2] = (z + 0.5 - (z.min() + np.ptp(z) / 2.0)) % 1.0
    canonical = Structure(canonical.lattice, canonical.species, frac)
    return Record(identifier, structure.composition.reduced_formula, area / n_formula_units, thickness, canonical)


def load_references(dataset: str, path: Path) -> tuple[list[Record], list[str]]:
    records = []
    errors = []
    if dataset == "2DMatPedia":
        with path.open(encoding="utf-8") as stream:
            for line in stream:
                item = json.loads(line)
                try:
                    records.append(make_record(item["material_id"], Structure.from_dict(item["structure"])))
                except Exception as exc:
                    errors.append(f"{item.get('material_id')}: {type(exc).__name__}: {exc}")
    elif dataset == "MC2D":
        with zipfile.ZipFile(path) as archive:
            for name in sorted(x for x in archive.namelist() if x.endswith(".cif")):
                try:
                    structure = Structure.from_str(archive.read(name).decode("utf-8"), fmt="cif")
                    records.append(make_record(Path(name).name, structure))
                except Exception as exc:
                    errors.append(f"{name}: {type(exc).__name__}: {exc}")
    elif dataset == "C2DB":
        from ase.db import connect
        from pymatgen.io.ase import AseAtomsAdaptor

        database = connect(str(path))
        for row in database.select():
            identifier = str(row.get("uid", row.get("unique_id", row.id)))
            try:
                structure = AseAtomsAdaptor.get_structure(row.toatoms())
                records.append(make_record(identifier, structure))
            except Exception as exc:
                errors.append(f"{identifier}: {type(exc).__name__}: {exc}")
    else:
        raise ValueError(dataset)
    return records, errors


def load_candidates(archive_path: Path, candidate_table: Path, formulas: set[str]):
    from pymatgen.core import Composition

    selected = set()
    with __import__("gzip").open(candidate_table, "rt", newline="") as stream:
        for row in csv.DictReader(stream):
            if row["candidate_formula"]:
                formula = Composition(row["candidate_formula"]).reduced_formula
                if formula in formulas:
                    selected.add(row["candidate_file"])
    by_formula = defaultdict(list)
    parse_errors = []
    with tarfile.open(archive_path, "r:gz") as archive:
        for member in archive:
            filename = Path(member.name).name
            if filename not in selected or not member.isfile():
                continue
            try:
                stream = archive.extractfile(member)
                if stream is None:
                    raise ValueError("missing archive member stream")
                structure = Structure.from_str(stream.read().decode("utf-8"), fmt="cif")
                record = make_record(filename, structure)
                by_formula[record.formula].append(record)
            except Exception as exc:
                parse_errors.append(f"{filename}: {type(exc).__name__}: {exc}")
    return by_formula, selected, parse_errors


def relative_difference(candidate: float, reference: float) -> float:
    return abs(candidate - reference) / reference if reference > 0 else math.inf


def compare(
    ref: Record,
    candidates: list[Record],
    area_tol: float,
    thickness_tol: float,
    max_matcher_candidates: int,
) -> dict:
    row = {
        "reference_id": ref.identifier,
        "formula": ref.formula,
        "n_candidates_same_formula": len(candidates),
        "n_geometry_close": 0,
        "match_level": "no_formula_match",
        "candidate_file": "",
        "area_diff_percent": "",
        "thickness_diff_percent": "",
    }
    if not candidates:
        return row
    ranked = sorted(
        (
            (relative_difference(c.area_per_fu, ref.area_per_fu),
             relative_difference(c.thickness, ref.thickness), c)
            for c in candidates
        ),
        key=lambda item: (item[0], item[1], len(item[2].structure)),
    )
    close = [item for item in ranked if item[0] <= area_tol and item[1] <= thickness_tol]
    row["n_geometry_close"] = len(close)
    picked = close[0] if close else ranked[0]
    row["match_level"] = "formula_and_geometry_match" if close else "formula_only_match"
    for item in close[:max_matcher_candidates]:
        try:
            if MATCHER.fit(ref.structure, item[2].structure):
                picked = item
                row["match_level"] = "structure_match"
                break
        except Exception:
            continue
    area_diff, thickness_diff, candidate = picked
    row["candidate_file"] = candidate.identifier
    row["area_diff_percent"] = round(area_diff * 100, 4)
    row["thickness_diff_percent"] = round(thickness_diff * 100, 4)
    return row


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", choices=("2DMatPedia", "MC2D", "C2DB"), required=True)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--candidate-archive", type=Path, required=True)
    parser.add_argument("--candidate-table", type=Path, required=True)
    parser.add_argument("--output-prefix", type=Path, required=True)
    parser.add_argument("--area-tol", type=float, default=AREA_TOL)
    parser.add_argument("--thickness-tol", type=float, default=THICKNESS_TOL)
    parser.add_argument("--max-matcher-candidates", type=int, default=MAX_MATCHER_CANDIDATES)
    args = parser.parse_args()
    if args.area_tol <= 0 or args.thickness_tol <= 0 or args.max_matcher_candidates < 1:
        parser.error("Matching tolerances and candidate cap must be positive")

    refs, reference_errors = load_references(args.dataset, args.reference)
    candidates, selected, candidate_errors = load_candidates(
        args.candidate_archive, args.candidate_table, {r.formula for r in refs}
    )
    args.output_prefix.parent.mkdir(parents=True, exist_ok=True)
    detail_path = args.output_prefix.with_suffix(".csv")
    summary_path = args.output_prefix.with_suffix(".json")
    counts = Counter()
    with detail_path.open("w", encoding="utf-8", newline="") as stream:
        fieldnames = ["dataset", "reference_id", "formula", "n_candidates_same_formula", "n_geometry_close", "match_level", "candidate_file", "area_diff_percent", "thickness_diff_percent"]
        writer = csv.DictWriter(stream, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for i, ref in enumerate(refs, 1):
            row = compare(
                ref,
                candidates.get(ref.formula, []),
                args.area_tol,
                args.thickness_tol,
                args.max_matcher_candidates,
            )
            row["dataset"] = args.dataset
            writer.writerow(row)
            counts[row["match_level"]] += 1
            if i % 500 == 0:
                print(f"{args.dataset}: {i}/{len(refs)} references", flush=True)
    summary = {
        "dataset": args.dataset,
        "reference_file": str(args.reference),
        "reference_sha256": sha256(args.reference),
        "candidate_archive_sha256": sha256(args.candidate_archive),
        "reference_records_parsed": len(refs),
        "reference_parse_errors": reference_errors,
        "selected_candidate_filenames": len(selected),
        "candidate_records_parsed": sum(map(len, candidates.values())),
        "candidate_parse_errors": candidate_errors,
        "match_counts": dict(counts),
        "software_versions": {
            "pymatgen": version("pymatgen"),
            "spglib": version("spglib"),
            "numpy": version("numpy"),
        },
        "matcher": {
            "formula": "pymatgen reduced_formula",
            "vacuum_axis": "longest lattice vector",
            "canonical_vacuum_angstrom": 25.0,
            "area_per_formula_unit_relative_tolerance": args.area_tol,
            "thickness_relative_tolerance": args.thickness_tol,
            "maximum_geometry_close_candidates_tested": args.max_matcher_candidates,
            "ltol": 0.2,
            "stol": 0.3,
            "angle_tol_degrees": 5,
            "primitive_cell": True,
            "attempt_supercell": False,
        },
    }
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"dataset": args.dataset, "counts": counts, "summary": str(summary_path)}, default=dict), flush=True)


if __name__ == "__main__":
    main()
