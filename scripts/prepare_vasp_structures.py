"""Convert selected relaxed CIFs to slab-centered VASP POSCAR/KPOINTS files.

Requires ASE and NumPy. These are geometry inputs only: users must supply their
licensed POTCAR and converged, candidate-specific INCAR settings before running.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
from pathlib import Path

import numpy as np
from ase.io import read, write


ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "examples/dft_validation/chgnet_relaxed"
OUTPUT = ROOT / "examples/dft_validation/prepared_vasp"
MANIFEST = ROOT / "examples/dft_validation/structure_manifest.csv"
VACUUM = 20.0  # Angstrom, separation between outermost atoms in adjacent slabs
KSPACING = 0.25  # Angstrom^-1, starting grid only; converge in production


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    with MANIFEST.open(newline="", encoding="utf-8") as stream:
        rows = [row for row in csv.DictReader(stream) if row["geometry"] == "chgnet_relaxed"]
    for row in rows:
        name = row["candidate_file"]
        path = INPUT / name
        if sha256(path) != row["sha256"]:
            raise ValueError(f"source CIF checksum mismatch: {name}")
        atoms = read(path)
        original_count = len(atoms)
        initial_distances = atoms.get_all_distances(mic=True)
        np.fill_diagonal(initial_distances, np.inf)
        initial_nearest = np.sort(initial_distances.min(axis=1))
        a, b = np.asarray(atoms.cell[0]), np.asarray(atoms.cell[1])
        normal = np.cross(a, b)
        normal /= np.linalg.norm(normal)
        projection = atoms.positions @ normal
        thickness = float(np.ptp(projection))
        cell_height = thickness + VACUUM

        new_cell = np.array([a, b, normal * cell_height])
        shift = (cell_height - thickness) / 2 - float(np.min(projection))
        atoms.positions += normal * shift
        atoms.set_cell(new_cell, scale_atoms=False)
        atoms.wrap()
        if len(atoms) != original_count:
            raise ValueError(f"atom count changed: {name}")
        if abs(float(atoms.get_volume()) - np.linalg.norm(np.cross(a, b)) * cell_height) > 1e-5:
            raise ValueError(f"unexpected slab cell volume: {name}")

        stem = name.removesuffix(".cif")
        target = OUTPUT / stem
        target.mkdir(parents=True, exist_ok=True)
        write(target / "POSCAR", atoms, format="vasp", direct=True, sort=True)
        poscar_path = target / "POSCAR"
        poscar_path.write_text(
            "\n".join(line.rstrip() for line in poscar_path.read_text().splitlines()) + "\n",
            encoding="utf-8",
        )
        round_trip = read(target / "POSCAR")
        if sorted(round_trip.get_chemical_symbols()) != sorted(atoms.get_chemical_symbols()):
            raise ValueError(f"POSCAR chemistry mismatch: {name}")
        final_distances = round_trip.get_all_distances(mic=True)
        np.fill_diagonal(final_distances, np.inf)
        if np.max(np.abs(initial_nearest - np.sort(final_distances.min(axis=1)))) > 1e-3:
            raise ValueError(f"nearest-neighbor geometry changed during conversion: {name}")
        reciprocal = atoms.cell.reciprocal()  # ASE convention excludes 2*pi
        mesh = [max(1, math.ceil(2 * math.pi * np.linalg.norm(reciprocal[i]) / KSPACING)) for i in (0, 1)]
        (target / "KPOINTS").write_text(
            f"Gamma mesh, starting KSPACING ~ {KSPACING} A^-1\n0\nGamma\n{mesh[0]} {mesh[1]} 1\n0 0 0\n",
            encoding="utf-8",
        )
        (target / "geometry.json").write_text(
            json.dumps(
                {
                    "source_candidate_file": name,
                    "source_sha256": row["sha256"],
                    "n_atoms": original_count,
                    "formula": atoms.get_chemical_formula(),
                    "slab_thickness_A": round(thickness, 6),
                    "vacuum_between_outermost_atoms_A": VACUUM,
                    "cell_height_A": round(cell_height, 6),
                    "starting_k_mesh": mesh + [1],
                    "poscar_sha256": sha256(target / "POSCAR"),
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        print(name, original_count, f"{thickness:.2f} A thick", f"k={mesh[0]}x{mesh[1]}x1")


if __name__ == "__main__":
    main()
