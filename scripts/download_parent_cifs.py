"""按仓库父体 ID 表从 Materials Project API 下载当前可用结构。

这是重新获取输入的辅助工具；MP 数据库会更新，不能保证下载的 CIF
与历史生产运行使用的结构逐字或逐原子排序相同。
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_IDS = ROOT / "data/parents/parent_level_metadata.csv.gz"


def read_ids(path: Path) -> list[str]:
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        if "parent_id" not in (reader.fieldnames or []):
            raise ValueError("输入表缺少 parent_id 列")
        return sorted({row["parent_id"].strip() for row in reader if row["parent_id"].strip()})


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ids", type=Path, default=DEFAULT_IDS)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--batch-size", type=int, default=100)
    parser.add_argument("--limit", type=int, default=None, help="先试跑前 N 个 ID")
    args = parser.parse_args()
    if args.batch_size < 1 or (args.limit is not None and args.limit < 1):
        parser.error("batch-size 和 limit 必须为正整数")
    if not os.environ.get("MP_API_KEY"):
        parser.error("请先设置 MP_API_KEY 环境变量；不要把密钥写入仓库")

    try:
        from mp_api.client import MPRester
    except ImportError as exc:
        parser.error(f"缺少 mp-api：{exc}；请安装 `pip install mp-api`")

    ids = read_ids(args.ids)
    if args.limit is not None:
        ids = ids[: args.limit]
    args.output_dir.mkdir(parents=True, exist_ok=True)
    remaining = [pid for pid in ids if not (args.output_dir / f"{pid}.cif").exists()]
    failures: list[tuple[str, str]] = []

    with MPRester() as mpr:
        for start in range(0, len(remaining), args.batch_size):
            batch = remaining[start : start + args.batch_size]
            try:
                docs = mpr.materials.summary.search(
                    material_ids=batch, fields=["material_id", "structure"]
                )
                by_id = {str(doc.material_id): doc.structure for doc in docs if doc.structure}
            except Exception as exc:
                failures.extend((pid, f"API {type(exc).__name__}: {exc}") for pid in batch)
                print(f"批次 {start // args.batch_size + 1} 请求失败：{exc}", flush=True)
                continue
            for pid in batch:
                structure = by_id.get(pid)
                if structure is None:
                    failures.append((pid, "当前 summary API 没有返回结构；旧 ID 可另查 tasks API"))
                    continue
                try:
                    structure.to(filename=str(args.output_dir / f"{pid}.cif"))
                except Exception as exc:
                    failures.append((pid, f"写入 {type(exc).__name__}: {exc}"))
            print(f"已请求 {min(start + len(batch), len(remaining))}/{len(remaining)} 个待下载 ID", flush=True)

    with (args.output_dir / "download_manifest.tsv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream, delimiter="\t", lineterminator="\n")
        writer.writerow(["parent_id", "sha256", "size_bytes"])
        for pid in ids:
            path = args.output_dir / f"{pid}.cif"
            if path.exists():
                writer.writerow([pid, sha256(path), path.stat().st_size])
    with (args.output_dir / "download_failed.tsv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream, delimiter="\t", lineterminator="\n")
        writer.writerow(["parent_id", "reason"])
        writer.writerows(failures)
    print(f"完成：目标 {len(ids)}；失败 {len(failures)}。清单见 {args.output_dir}")


if __name__ == "__main__":
    main()
