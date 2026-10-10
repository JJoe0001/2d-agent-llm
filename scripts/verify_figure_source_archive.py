"""Verify archived historical figure tables and scripts against member hashes."""

import hashlib
import json
import tarfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / "data/figure_sources"


def main():
    records = json.loads((FOLDER / "historical_figure_source_manifest.json").read_text())
    with tarfile.open(FOLDER / "historical_figure_source_tables_and_scripts.tar.gz", "r:gz") as archive:
        names = set(archive.getnames())
        expected = {r["path"] for r in records}
        if names != expected:
            raise SystemExit(f"archive members differ: {len(names)} vs {len(expected)}")
        for row in records:
            content = archive.extractfile(row["path"]).read()
            if len(content) != row["size_bytes"] or hashlib.sha256(content).hexdigest() != row["sha256"]:
                raise SystemExit(f"hash mismatch: {row['path']}")
    print(f"Verified {len(records)} historical figure-source members.")


if __name__ == "__main__":
    main()
