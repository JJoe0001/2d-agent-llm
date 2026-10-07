"""Verify the compact repository payload without scientific Python dependencies."""

from __future__ import annotations

import csv
import gzip
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def fail(message: str) -> None:
    raise SystemExit(f"Package verification failed: {message}")


def count_rows(relative_path: str) -> tuple[int, list[str]]:
    with gzip.open(ROOT / relative_path, "rt", encoding="utf-8-sig", newline="") as handle:
        rows = csv.reader(handle)
        header = next(rows)
        return sum(1 for _ in rows), header


def main() -> None:
    summary = json.loads((ROOT / "PACKAGE_SUMMARY.json").read_text(encoding="utf-8"))
    dataset = json.loads(
        (ROOT / "data/computed_results/dataset_summary.json").read_text(encoding="utf-8")
    )

    with (ROOT / "FILE_MANIFEST.tsv").open(encoding="utf-8", newline="") as handle:
        records = list(csv.DictReader(handle, delimiter="\t"))
    expected_hashes = {}
    for record in records:
        relative_path = record["path"]
        path = ROOT / relative_path
        if not path.is_file():
            fail(f"missing file: {relative_path}")
        content = path.read_bytes()
        digest = hashlib.sha256(content).hexdigest()
        if len(content) != int(record["size_bytes"]) or digest != record["sha256"]:
            fail(f"manifest mismatch: {relative_path}")
        expected_hashes[relative_path] = digest

    checksum_lines = (ROOT / "SHA256SUMS").read_text(encoding="utf-8").splitlines()
    listed_hashes = {}
    for line in checksum_lines:
        digest, relative_path = line.split("  ", 1)
        if relative_path in listed_hashes:
            fail(f"duplicate checksum: {relative_path}")
        listed_hashes[relative_path] = digest
    if listed_hashes != expected_hashes:
        fail("SHA256SUMS differs from FILE_MANIFEST.tsv")

    if summary["n_files"] != len(records):
        fail("PACKAGE_SUMMARY.json file count differs from manifest")
    if summary["total_size_bytes"] != sum(int(r["size_bytes"]) for r in records):
        fail("PACKAGE_SUMMARY.json byte count differs from manifest")

    expected_rows = {
        "data/parents/parent_level_metadata.csv.gz": dataset["n_parent_rows"],
        "data/computed_results/parent_exfoliability_labels.csv.gz": dataset["n_parent_rows"],
        "data/final_2d_candidates/final_2d_candidates.csv.gz": dataset["n_candidate_rows"],
    }
    for relative_path, expected in expected_rows.items():
        actual, header = count_rows(relative_path)
        if actual != expected:
            fail(f"{relative_path}: {actual} rows, expected {expected}")
        if not header:
            fail(f"{relative_path}: empty header")

    print(f"Verified {len(records)} payload files and three compact tables.")
    print("Full CIF archives are not included in this verification.")


if __name__ == "__main__":
    main()
