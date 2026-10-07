"""Recompute layer-group labels for a directory of initial candidate CIFs."""

from __future__ import annotations

import argparse
import csv
import gzip
from pathlib import Path

import spglib
from pymatgen.core import Structure


FIELDS = (
    "candidate_file",
    "aperiodic_axis",
    "symprec_used",
    "layergroup_number",
    "layergroup_symbol",
    "error",
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cif_dir", type=Path, help="Directory of initial post-deduplication CIFs")
    parser.add_argument("output", type=Path, help="CSV or CSV.gz output path")
    parser.add_argument("--symprec", type=float, default=1e-5)
    args = parser.parse_args()

    paths = sorted(args.cif_dir.glob("*.cif"))
    if not paths:
        raise SystemExit(f"No CIF files found in {args.cif_dir}")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    opener = gzip.open if args.output.suffix == ".gz" else open
    with opener(args.output, "wt", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        for path in paths:
            result = dict.fromkeys(FIELDS, "")
            result["candidate_file"] = path.name
            result["symprec_used"] = args.symprec
            try:
                structure = Structure.from_file(str(path))
                aperiodic_dir = max(range(3), key=lambda i: structure.lattice.abc[i])
                result["aperiodic_axis"] = "abc"[aperiodic_dir]
                cell = (
                    structure.lattice.matrix,
                    structure.frac_coords,
                    [site.specie.Z for site in structure],
                )
                label = spglib.get_layergroup(
                    cell, aperiodic_dir=aperiodic_dir, symprec=args.symprec
                )
                if label is None:
                    result["error"] = "spglib_get_layergroup_failed"
                else:
                    result["layergroup_number"] = int(label.number)
                    result["layergroup_symbol"] = str(label.international)
            except Exception as exc:
                result["error"] = f"{type(exc).__name__}: {exc}"
            writer.writerow(result)
    print(f"Wrote {len(paths)} labels to {args.output}")


if __name__ == "__main__":
    main()
