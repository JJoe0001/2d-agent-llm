from __future__ import annotations
import os
import pandas as pd
import time
from pebble import ProcessPool
from concurrent.futures import as_completed, TimeoutError
from typing import Dict
from loguru import logger
from pymatgen.core import Structure as PymatgenStructure

# =============================================================================
# 崩溃保护配置
# =============================================================================
SINGLE_TASK_TIMEOUT = 300
PROCESS_RESTART_INTERVAL = 1000

# --- 内部模块导入 ---
from core.config import config
from core.store import delete_structure, get_structure
from tools.parse import parse_structure_impl, require_parsed_structure_id
from tools.dimensionality import dimensionality_rank_impl
from tools.planar_gap import planar_gap_scan_impl
from tools.extract_layer import extract_layer_component_impl
from tools.bond_del import BondDelAlgorithm
from tools.xcp_potential import UniversalPotential

# =============================================================================
# 日志配置
# =============================================================================
LOGS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
os.makedirs(LOGS_DIR, exist_ok=True)

BATCH_LOG_FILE = os.path.join(LOGS_DIR, "batch_no_passivation.log")
logger.add(
    BATCH_LOG_FILE,
    rotation="10 MB",
    retention="7 days",
    level="INFO",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
    enqueue=True
)
logger.info(f"Batch processing (no passivation) logs: {BATCH_LOG_FILE}")

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
POT_DATA_PATH = os.path.join(CURRENT_DIR, "POTDATA_morse_yukawa_2025")

if not os.path.exists(POT_DATA_PATH):
    raise FileNotFoundError(f"CRITICAL ERROR: Potential file NOT found at: {POT_DATA_PATH}")

logger.info(f"Loading XCP Potential from {POT_DATA_PATH}...")
GLOBAL_XCP_LOADER = UniversalPotential(POT_DATA_PATH)
logger.success("XCP potential loaded successfully.")

EXTRACTION_COLUMNS = [
    "original_file",
    "original_formula",
    "formation_energy",
    "ehull",
    "spacegroup",
    "extraction_route",
    "dim_rank",
    "hkl",
    "gap_score",
    "used_delta",
    "cif_content",
    "extracted_formula",
    "is_passivated",
    "passivation_note",
]


def _resolve_batch_worker_count() -> int:
    return max(1, int(config.BATCH_MAX_WORKERS))


def add_vacuum_to_layer(struct: PymatgenStructure, vacuum_size: float = 20.0) -> PymatgenStructure:
    """为2D层添加真空层，防止周期性边界条件问题"""
    import numpy as np
    from pymatgen.core import Lattice

    spreads = np.ptp(struct.frac_coords, axis=0)
    thickness_dir = np.argmin(spreads)

    matrix = struct.lattice.matrix.copy()
    current_length = np.linalg.norm(matrix[thickness_dir])
    scale = (current_length + vacuum_size) / current_length
    matrix[thickness_dir] *= scale

    new_lattice = Lattice(matrix)
    new_struct = PymatgenStructure(
        new_lattice,
        struct.species,
        struct.cart_coords,
        coords_are_cartesian=True
    )

    center_shift = 0.5 - np.mean(new_struct.frac_coords[:, thickness_dir])
    translation = [0, 0, 0]
    translation[thickness_dir] = center_shift
    new_struct.translate_sites(range(len(new_struct)), translation)

    return new_struct


def _process_single_csv_row_no_passivation(row_data: dict, top_k: int) -> dict:
    """处理 CSV 文件的单行数据 (不进行表面钝化)"""
    original_file = row_data.get("original_file", "unknown")
    formula = row_data.get("formula", "unknown")
    cif_content = row_data.get("cif_content", "")

    metadata = {
        "original_file": original_file,
        "original_formula": formula,
        "formation_energy": row_data.get("formation_energy", None),
        "ehull": row_data.get("ehull", None),
        "spacegroup": row_data.get("spacegroup", None)
    }

    file_candidates = []
    start_time = time.time()

    summary = {
        "original_file": original_file,
        "original_formula": formula,
        "status": "FAIL",
        "dim_rank": 3,
        "route": "NONE",
        "layers_extracted": 0,
        "note": "",
        **metadata
    }
    structure_id: str | None = None

    try:
        # 1. 解析 CIF 内容
        parse_res = parse_structure_impl(cif_text=cif_content, source_name=original_file)
        structure_id = require_parsed_structure_id(parse_res)
        struct = get_structure(structure_id)

        # 2. 初始维度判定
        dim_res = dimensionality_rank_impl(struct=struct)
        initial_dim = dim_res.get("dim_rank", 3)
        summary["dim_rank"] = initial_dim

        # 路径 A: Geometric Scan
        if initial_dim == 2:
            summary["route"] = "geometric"
            scan_res = planar_gap_scan_impl(struct, top_k=top_k)

            smart_deltas = [1.2, 1.3, 1.1, 1.4, 1.5]

            for idx, cand in enumerate(scan_res.get("candidates", [])):
                best_layer_data = None

                for d in smart_deltas:
                    try:
                        layer_data = extract_layer_component_impl(
                            struct=struct,
                            hkl=cand["hkl"],
                            shift=cand["gap_center_frac"],
                            delta=d,
                            min_slab_size_A=1.0
                        )

                        if layer_data.get("layer_dim_rank_proxy") == 2 and layer_data.get("layer_nsites", 0) > 0:
                            best_layer_data = layer_data
                            best_layer_data["used_delta"] = d
                            break

                    except Exception as e:
                        continue

                if best_layer_data is None:
                    continue

                # 不进行钝化，直接保存原始结构
                if "cif" in best_layer_data and best_layer_data["cif"].strip():
                    try:
                        raw_layer = PymatgenStructure.from_str(best_layer_data["cif"], fmt="cif")

                        file_candidates.append({
                            **metadata,
                            "extraction_route": "geometric",
                            "dim_rank": 2,
                            "hkl": cand["hkl"],
                            "gap_score": cand.get("score_proxy", 0.0),
                            "used_delta": best_layer_data.get("used_delta", "unknown"),
                            "cif_content": raw_layer.to(fmt="cif"),
                            "extracted_formula": raw_layer.composition.reduced_formula,
                            "is_passivated": False,
                            "passivation_note": "Passivation skipped"
                        })
                    except Exception as e:
                        continue

        # 路径 B: BONDDEL
        if not file_candidates or initial_dim == 3:
            summary["route"] = "bond_del" if not file_candidates else "both"

            algo = BondDelAlgorithm(
                structure=struct,
                universal_potential=GLOBAL_XCP_LOADER,
                timeout_seconds=60
            )
            res = algo.run(verbose=False)

            if res.success and res.final_clusters:
                for idx, atom_indices in enumerate(res.final_clusters):
                    indices = sorted(list(atom_indices))
                    sites = [struct.sites[i] for i in indices]
                    cluster_struct = PymatgenStructure.from_sites(sites).get_sorted_structure()

                    cluster_struct = add_vacuum_to_layer(cluster_struct, vacuum_size=20.0)

                    file_candidates.append({
                        **metadata,
                        "extraction_route": "bond_del",
                        "dim_rank": 2,
                        "hkl": [0, 0, 0],
                        "gap_score": 1.0,
                        "used_delta": "",
                        "cif_content": cluster_struct.to(fmt="cif"),
                        "extracted_formula": cluster_struct.composition.reduced_formula,
                        "is_passivated": False,
                        "passivation_note": "Passivation skipped"
                    })

        total_time = time.time() - start_time
        if file_candidates:
            summary["status"] = "SUCCESS"
            summary["layers_extracted"] = len(file_candidates)
            logger.info(
                f"{original_file}: Found {len(file_candidates)} 2D layers in {total_time:.2f}s "
                f"(route: {summary['route']})"
            )
        else:
            summary["status"] = "NO_LAYERS"
            summary["note"] = "No 2D layers identified by any method."
            logger.info(f"   {original_file}: No 2D layers found in {total_time:.2f}s")

    except Exception as e:
        summary["status"] = "ERROR"
        summary["note"] = f"Exception: {str(e)}"
        logger.error(f"{original_file}: ERROR - {str(e)}")
    finally:
        if structure_id:
            delete_structure(structure_id)

    return {"candidates": file_candidates, "summary": summary}


def _run_csv_batch_no_passivation(input_csv_path: str, save_csv_path: str, summary_path: str, top_k: int):
    """批处理主函数（不进行表面钝化），带崩溃保护和超时控制"""
    batch_start_time = time.time()

    logger.info(f"\n{'='*80}")
    logger.info("CSV batch exfoliation started (no passivation mode)")
    logger.info(f"{'='*80}")
    logger.info(f"Single task timeout: {SINGLE_TASK_TIMEOUT}s")
    logger.info(f"Process pool restart interval: {PROCESS_RESTART_INTERVAL} tasks")

    try:
        df = pd.read_csv(input_csv_path)
        total_rows_original = len(df)
        processed_ids = set()

        # 断点续传逻辑
        if os.path.exists(summary_path):
            try:
                summary_df = pd.read_csv(summary_path)
                if "original_file" in summary_df.columns:
                    processed_ids = set(summary_df["original_file"].values)
                    logger.info(f"Resume mode: found {len(processed_ids)} processed structures")
            except Exception as e:
                pass

        if processed_ids:
            df_remaining = df[~df["original_file"].isin(processed_ids)]
            skipped_count = len(df) - len(df_remaining)
            df = df_remaining
            logger.info(f"Skipping {skipped_count} processed structures. {len(df)} remaining.")
            if len(df) == 0:
                logger.info("All done. Nothing to process.")
                return

        total_rows = len(df)
    except Exception as e:
        logger.error(f"Failed to read CSV: {e}")
        return

    # 统计变量
    completed_count = 0
    success_count = 0
    no_layers_count = 0
    error_count = 0
    timeout_count = 0
    crash_count = 0
    total_layers = 0

    # 自动识别核心数
    max_workers = _resolve_batch_worker_count()
    logger.info(f"Using {max_workers} worker processes")

    # 分批处理，定期重启进程池
    batch_size = PROCESS_RESTART_INTERVAL
    for batch_start in range(0, total_rows, batch_size):
        batch_end = min(batch_start + batch_size, total_rows)
        df_batch = df.iloc[batch_start:batch_end]

        batch_num = batch_start // batch_size + 1
        total_batches = (total_rows + batch_size - 1) // batch_size
        logger.info(f"\n{'─'*80}")
        logger.info(f"Processing batch {batch_num}/{total_batches}: rows {batch_start}-{batch_end}")
        logger.info(f"{'─'*80}")

        with ProcessPool(max_workers=max_workers) as pool:
            futures = {
                pool.schedule(
                    _process_single_csv_row_no_passivation,
                    args=(row.to_dict(), top_k),
                    timeout=SINGLE_TASK_TIMEOUT
                ): (batch_start + idx, row.to_dict())
                for idx, row in df_batch.iterrows()
            }

            for future in as_completed(futures):
                row_idx, row_data = futures[future]
                original_file = row_data.get("original_file", f"row_{row_idx}")

                try:
                    res = future.result()
                    candidates = res["candidates"]
                    summary_row = res["summary"]

                    completed_count += 1

                    if summary_row["status"] == "SUCCESS":
                        success_count += 1
                        total_layers += len(candidates)
                    elif summary_row["status"] == "NO_LAYERS":
                        no_layers_count += 1
                    else:
                        error_count += 1

                    progress_pct = (completed_count / total_rows) * 100
                    logger.info(
                        f"Progress: {completed_count}/{total_rows} ({progress_pct:.1f}%) | "
                        f"successes: {success_count} | layers: {total_layers}"
                    )

                    if candidates:
                        df_cand = pd.DataFrame(candidates, columns=EXTRACTION_COLUMNS)
                        df_cand.to_csv(save_csv_path, mode='a', header=not os.path.exists(save_csv_path), index=False)

                    df_sum = pd.DataFrame([summary_row])
                    df_sum.to_csv(summary_path, mode='a', header=not os.path.exists(summary_path), index=False)

                except TimeoutError:
                    completed_count += 1
                    timeout_count += 1
                    error_count += 1
                    logger.error(f"{original_file}: TIMEOUT (exceeded {SINGLE_TASK_TIMEOUT}s)")

                    progress_pct = (completed_count / total_rows) * 100
                    logger.info(
                        f"Progress: {completed_count}/{total_rows} ({progress_pct:.1f}%) | "
                        f"successes: {success_count} | layers: {total_layers}"
                    )

                    error_summary = {
                        "original_file": original_file,
                        "original_formula": row_data.get("formula", "unknown"),
                        "status": "TIMEOUT",
                        "dim_rank": -1,
                        "route": "NONE",
                        "layers_extracted": 0,
                        "note": f"Task timeout after {SINGLE_TASK_TIMEOUT}s",
                        "formation_energy": row_data.get("formation_energy"),
                        "ehull": row_data.get("ehull"),
                        "spacegroup": row_data.get("spacegroup")
                    }
                    pd.DataFrame([error_summary]).to_csv(summary_path, mode='a', header=not os.path.exists(summary_path), index=False)

                except Exception as e:
                    completed_count += 1
                    crash_count += 1
                    error_count += 1
                    logger.error(f"{original_file}: CRASHED - {str(e)}")

                    progress_pct = (completed_count / total_rows) * 100
                    logger.info(
                        f"Progress: {completed_count}/{total_rows} ({progress_pct:.1f}%) | "
                        f"successes: {success_count} | layers: {total_layers}"
                    )

                    error_summary = {
                        "original_file": original_file,
                        "original_formula": row_data.get("formula", "unknown"),
                        "status": "CRASH",
                        "dim_rank": -1,
                        "route": "NONE",
                        "layers_extracted": 0,
                        "note": f"Process crash: {str(e)}",
                        "formation_energy": row_data.get("formation_energy"),
                        "ehull": row_data.get("ehull"),
                        "spacegroup": row_data.get("spacegroup")
                    }
                    pd.DataFrame([error_summary]).to_csv(summary_path, mode='a', header=not os.path.exists(summary_path), index=False)

        logger.info(f"Batch {batch_num} completed, restarting process pool...")

    # 最终统计
    batch_total_time = time.time() - batch_start_time
    logger.info(f"\n{'='*80}")
    logger.info("Batch processing completed (no passivation)")
    logger.info(f"{'='*80}")
    logger.info(f"Total time: {batch_total_time:.2f}s")
    logger.info(f"Processed: {completed_count}/{total_rows}")
    logger.info(f"Success: {success_count} ({total_layers} layers)")
    logger.info(f"No layers: {no_layers_count}")
    logger.info(f"Timeout: {timeout_count}")
    logger.info(f"Crashed: {crash_count}")
    logger.info(f"Total errors: {error_count}")
    logger.info(f"{'='*80}\n")


def batch_process_csv_no_passivation_impl(input_csv_path: str, save_csv_path: str, summary_path: str, top_k: int = 3) -> str:
    """批处理CSV文件（不进行表面钝化）"""
    if not os.path.exists(input_csv_path):
        return "Error: input CSV not found."
    _run_csv_batch_no_passivation(input_csv_path, save_csv_path, summary_path, top_k)
    return "CSV batch exfoliation completed (no passivation)."
