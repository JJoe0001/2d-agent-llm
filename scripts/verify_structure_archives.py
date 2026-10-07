"""逐文件核对三个 CIF 归档与公开 SHA-256 清单。"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import tarfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STEMS = (
    "unique_candidate_cifs",
    "relaxed_unpassivated_cifs",
    "relaxed_passivated_cifs",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify(directory: Path, stem: str, expected: dict) -> None:
    archive = directory / f"{stem}.tar.gz"
    manifest = directory / f"{stem}_manifest.tsv"
    assert archive.stat().st_size == expected["archive_size_bytes"], stem
    assert sha256(archive) == expected["archive_sha256"], stem
    assert sha256(manifest) == expected["manifest_sha256"], stem
    with manifest.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream, delimiter="\t"))
    by_name = {row["candidate_file"]: row for row in rows}
    assert len(by_name) == len(rows) == expected["n_cifs"], stem
    seen: set[str] = set()
    with tarfile.open(archive, "r:gz") as stream:
        for member in stream:
            if not member.isfile():
                continue
            name = Path(member.name).name
            assert name in by_name and name not in seen, (stem, name)
            seen.add(name)
            row = by_name[name]
            assert member.size == int(row["size_bytes"]), (stem, name)
            content = stream.extractfile(member)
            assert content is not None
            digest = hashlib.sha256()
            for chunk in iter(lambda: content.read(1024 * 1024), b""):
                digest.update(chunk)
            assert digest.hexdigest() == row["sha256"], (stem, name)
    assert len(seen) == expected["n_cifs"], stem
    print(f"{stem}: {len(seen)} 个 CIF 全部通过校验")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--directory", type=Path, default=ROOT / "data/external_large_files"
    )
    args = parser.parse_args()
    summary = json.loads((args.directory / "archive_summary.json").read_text())
    for stem, expected in (
        (STEMS[0], {k: summary[k] for k in ("n_cifs", "archive_size_bytes", "archive_sha256", "manifest_sha256")}),
        (STEMS[1], summary["relaxed_unpassivated_cifs"]),
        (STEMS[2], summary["relaxed_passivated_cifs"]),
    ):
        verify(args.directory, stem, expected)


if __name__ == "__main__":
    main()
