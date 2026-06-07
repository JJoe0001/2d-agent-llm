from __future__ import annotations
import os
import glob
import pandas as pd
import networkx as nx
import time
import traceback
import signal
from pebble import ProcessPool
from concurrent.futures import as_completed, TimeoutError
import concurrent.futures
from typing import List, Dict, Any
from loguru import logger
from pymatgen.core import Structure as PymatgenStructure
import torch
import multiprocessing as mp
from joblib import Parallel, delayed

# =============================================================================
# 崩溃保护配置
# =============================================================================
SINGLE_TASK_TIMEOUT = 300  # 单个任务最大执行时间（秒）
PROCESS_RESTART_INTERVAL = 1000  # 每处理N个任务后重启进程池

# --- 内部模块导入 ---
from core.store import delete_structure, get_structure
from core.config import config
from tools.parse import parse_structure_impl, require_parsed_structure_id
from tools.dimensionality import dimensionality_rank_impl
from tools.planar_gap import planar_gap_scan_impl
from tools.extract_layer import extract_layer_component_impl
from tools.bond_del import BondDelAlgorithm, XCPParameters
from tools.surface_passivation import PassivatorFactory
from tools.xcp_potential import UniversalPotential

# =============================================================================
# 批处理专用日志配置
# =============================================================================
LOGS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
os.makedirs(LOGS_DIR, exist_ok=True)

if __name__ == '__main__':
    mp.set_start_method('spawn', force=True)

BATCH_LOG_FILE = os.path.join(LOGS_DIR, "batch_processing.log")
logger.add(
    BATCH_LOG_FILE,
    rotation="10 MB",
    retention="7 days",
    level="INFO",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
    enqueue=True  # 多进程下保证日志不乱码的安全锁
)
logger.info(f"Batch processing logs will be written to: {BATCH_LOG_FILE}")

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


def _resolve_batch_worker_count(default_limit: int | None = None) -> int:
    configured = max(1, int(config.BATCH_MAX_WORKERS))
    if default_limit is None:
        return configured
    return max(1, min(configured, default_limit))


# =============================================================================
# 1. 核心处理逻辑：单文件多路径并行
# =============================================================================

def add_vacuum_to_layer(struct: PymatgenStructure, vacuum_size: float = 20.0) -> PymatgenStructure:
    """
    为2D层添加真空层，防止周期性边界条件问题

    Args:
        struct: 输入的2D结构
        vacuum_size: 真空层厚度（Angstroms）

    Returns:
        添加了真空层的结构
    """
    import numpy as np
    from pymatgen.core import Lattice

    # 找到最薄的方向（2D层的法向）
    spreads = np.ptp(struct.frac_coords, axis=0)
    thickness_dir = np.argmin(spreads)

    # 扩展该方向的晶格矢量
    matrix = struct.lattice.matrix.copy()
    current_length = np.linalg.norm(matrix[thickness_dir])
    scale = (current_length + vacuum_size) / current_length
    matrix[thickness_dir] *= scale

    # 创建新晶格和结构
    new_lattice = Lattice(matrix)
    new_struct = PymatgenStructure(
        new_lattice,
        struct.species,
        struct.cart_coords,
        coords_are_cartesian=True
    )

    # 将层居中到晶胞中
    center_shift = 0.5 - np.mean(new_struct.frac_coords[:, thickness_dir])
    translation = [0, 0, 0]
    translation[thickness_dir] = center_shift
    new_struct.translate_sites(range(len(new_struct)), translation)

    return new_struct


def _apply_passivation(structure: PymatgenStructure) -> dict:
    """应用表面钝化，带错误保护"""
    try:
        passivated_struct = PassivatorFactory.passivate(structure, method="auto")
        return {
            "cif": passivated_struct.to(fmt="cif"),
            "formula": passivated_struct.composition.reduced_formula,
            "is_passivated": True,
            "error": ""
        }
    except Exception as e:
        # 钝化失败时返回原始结构
        logger.warning(f"Passivation failed: {e}, using original structure")
        return {
            "cif": structure.to(fmt="cif"),
            "formula": structure.composition.reduced_formula,
            "is_passivated": False,
            "error": str(e)
        }

def _process_single_csv_row(row_data: dict, top_k: int) -> dict:
    """处理 CSV 文件的单行数据 (移除了 Thread Lock，因为多进程不需要)"""
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

            # 【新增】：定义智能扫描的 delta 列表 (优先测试1.2和1.3，兼容极端情况)
            smart_deltas = [1.2, 1.3, 1.1, 1.4, 1.5]

            for idx, cand in enumerate(scan_res.get("candidates", [])):
                best_layer_data = None
                
                # 【新增】：动态扫描 delta 以确保提取出完美的 2D 骨架
                for d in smart_deltas:
                    try:
                        # 注意：强制设置 min_slab_size_A=1.0 以提取物理极限单层
                        layer_data = extract_layer_component_impl(
                            struct=struct, 
                            hkl=cand["hkl"], 
                            shift=cand["gap_center_frac"],
                            delta=d,
                            min_slab_size_A=1.0  
                        )
                        
                        # 检查是否成功提取出 2D 单层 (Rank=2 且有原子)
                        if layer_data.get("layer_dim_rank_proxy") == 2 and layer_data.get("layer_nsites", 0) > 0:
                            best_layer_data = layer_data
                            best_layer_data["used_delta"] = d  # 记录是哪个 delta 成功的
                            break  # 命中目标后立即早停，节省计算时间
                            
                    except Exception as e:
                        # 某个 delta 切割失败不影响全局，继续尝试下一个
                        continue 
                
                # 如果 5 个 delta 都没能切出 2D 层（说明这个面上没有真正的 2D 结构），直接跳过
                if best_layer_data is None:
                    continue 

                # 走到这里说明提取成功，继续你原有的钝化和记录流程
                if "cif" in best_layer_data and best_layer_data["cif"].strip():
                    try:
                        raw_layer = PymatgenStructure.from_str(best_layer_data["cif"], fmt="cif")
                        pass_res = _apply_passivation(raw_layer)

                        file_candidates.append({
                            **metadata,
                            "extraction_route": "geometric",
                            "dim_rank": 2,
                            "hkl": cand["hkl"],
                            "gap_score": cand.get("score_proxy", 0.0),
                            "used_delta": best_layer_data.get("used_delta", "unknown"), # 【新增】：记录成功的参数，方便日后溯源
                            "cif_content": pass_res["cif"],
                            "extracted_formula": pass_res["formula"],
                            "is_passivated": pass_res["is_passivated"],
                            "passivation_note": pass_res["error"]
                        })
                    except Exception as e:
                        # 如果 Pymatgen 解析或钝化出错，安全跳过
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

                    # 【关键修复】为bond_del提取的2D簇添加真空层
                    # 防止周期性边界条件问题，确保ML评估正确
                    cluster_struct = add_vacuum_to_layer(cluster_struct, vacuum_size=20.0)

                    pass_res = _apply_passivation(cluster_struct)

                    file_candidates.append({
                        **metadata,
                        "extraction_route": "bond_del",
                        "dim_rank": 2,
                        "hkl": [0, 0, 0],
                        "gap_score": 1.0,
                        "used_delta": "",
                        "cif_content": pass_res["cif"],
                        "extracted_formula": pass_res["formula"],
                        "is_passivated": pass_res["is_passivated"],
                        "passivation_note": pass_res["error"]
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

# =============================================================================
# 2. 批量调度与保存 (多进程全核心起飞版)
# =============================================================================

def _run_csv_batch_background_task(input_csv_path: str, save_csv_path: str, summary_path: str, top_k: int):
    """批处理主函数，带崩溃保护和超时控制"""
    batch_start_time = time.time()

    logger.info(f"\n{'='*80}")
    logger.info("CSV batch exfoliation started (crash-protected mode)")
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
                    logger.info(f"Resume mode: found {len(processed_ids)} processed structures in summary")
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

    # 【崩溃保护】分批处理，定期重启进程池
    batch_size = PROCESS_RESTART_INTERVAL
    for batch_start in range(0, total_rows, batch_size):
        batch_end = min(batch_start + batch_size, total_rows)
        df_batch = df.iloc[batch_start:batch_end]

        batch_num = batch_start // batch_size + 1
        total_batches = (total_rows + batch_size - 1) // batch_size
        logger.info(f"\n{'─'*80}")
        logger.info(f"Processing batch {batch_num}/{total_batches}: rows {batch_start}-{batch_end}")
        logger.info(f"{'─'*80}")

        # 创建新的进程池（使用 pebble 支持真正的进程超时）
        with ProcessPool(max_workers=max_workers) as pool:
            # 提交任务，直接在 schedule 中设置超时
            futures = {
                pool.schedule(
                    _process_single_csv_row,
                    args=(row.to_dict(), top_k),
                    timeout=SINGLE_TASK_TIMEOUT
                ): (batch_start + idx, row.to_dict())
                for idx, row in df_batch.iterrows()
            }

            # 处理结果
            for future in as_completed(futures):
                row_idx, row_data = futures[future]
                original_file = row_data.get("original_file", f"row_{row_idx}")

                try:
                    # Pebble 自动处理超时，无需额外的 timeout 参数
                    res = future.result()
                    candidates = res["candidates"]
                    summary_row = res["summary"]

                    completed_count += 1

                    # 统计
                    if summary_row["status"] == "SUCCESS":
                        success_count += 1
                        total_layers += len(candidates)
                    elif summary_row["status"] == "NO_LAYERS":
                        no_layers_count += 1
                    else:
                        error_count += 1

                    # 进度显示
                    progress_pct = (completed_count / total_rows) * 100
                    logger.info(
                        f"Progress: {completed_count}/{total_rows} ({progress_pct:.1f}%) | "
                        f"successes: {success_count} | layers: {total_layers}"
                    )

                    # 实时保存
                    if candidates:
                        df_cand = pd.DataFrame(candidates, columns=EXTRACTION_COLUMNS)
                        df_cand.to_csv(save_csv_path, mode='a', header=not os.path.exists(save_csv_path), index=False)

                    df_sum = pd.DataFrame([summary_row])
                    df_sum.to_csv(summary_path, mode='a', header=not os.path.exists(summary_path), index=False)

                except TimeoutError:
                    # 【崩溃保护】Future超时
                    completed_count += 1
                    timeout_count += 1
                    error_count += 1
                    logger.error(f"{original_file}: TIMEOUT (future exceeded {SINGLE_TASK_TIMEOUT}s)")

                    # 进度显示
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
                    # 【崩溃保护】进程崩溃
                    completed_count += 1
                    crash_count += 1
                    error_count += 1
                    logger.error(f"{original_file}: CRASHED - {str(e)}")

                    # 进度显示
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
    logger.info("Batch processing completed")
    logger.info(f"{'='*80}")
    logger.info(f"Total time: {batch_total_time:.2f}s")
    logger.info(f"Processed: {completed_count}/{total_rows}")
    logger.info(f"Success: {success_count} ({total_layers} layers)")
    logger.info(f"No layers: {no_layers_count}")
    logger.info(f"Timeout: {timeout_count}")
    logger.info(f"Crashed: {crash_count}")
    logger.info(f"Total errors: {error_count}")
    logger.info(f"{'='*80}\n")


def batch_process_csv_impl(input_csv_path: str, save_csv_path: str, summary_path: str, top_k: int = 3) -> str:
    if not os.path.exists(input_csv_path):
        return "Error: input CSV not found."
    _run_csv_batch_background_task(input_csv_path, save_csv_path, summary_path, top_k)
    return "CSV batch exfoliation completed."


# =============================================================================
# 3. ML 验证批处理
# =============================================================================

def _process_single_ml_validation(res_dict: dict, stability_threshold: float, current_idx: int, total_rows: int) -> dict:
    """在独立进程中运行单个结构的 ML 验证"""
    import time
    from tools.ml_ops import ml_stage1_fast_evaluate
    from tools.parse import parse_structure_impl
    
    start_time = time.time()
    original_file = res_dict.get('original_file', 'unknown')
    cif_content = res_dict.get('cif_content', '')
    current_id: str | None = None
    
    try:
        temp_name = f"row_{current_idx}_{original_file}"
        parse_res = parse_structure_impl(cif_text=cif_content, source_name=temp_name)
        current_id = require_parsed_structure_id(parse_res)

        # 运行 CHGNet 结构优化
        eval_res = ml_stage1_fast_evaluate(current_id, fmax=0.1, steps=200)

        # 接收 ml_ops.py 返回的结构优化结果
        error_msg = eval_res.get("error", "")
        e_form = eval_res.get("formation_energy_2d", 999.0)
        is_stable = e_form < stability_threshold
        
        res_dict.update({
            "initial_energy": eval_res.get("initial_energy"),
            "final_energy": eval_res.get("final_energy"),
            "formation_energy_eV": e_form,
            "is_thermo_stable": is_stable if not error_msg else False,
            "is_relaxed": eval_res.get("converged", False),
            "optimized_structure_id": eval_res.get("optimized_id"),
            "num_atoms": eval_res.get("num_atoms"), # 接收原子数量
            "optimized_cif": eval_res.get("optimized_cif", ""),
            "error_message": error_msg
        })

        # 细化状态分类
        if error_msg:
            if "too large" in error_msg:
                res_dict["validation_status"] = "Skipped (Too Large)"
            else:
                res_dict["validation_status"] = "Error/Explosion"
        else:
            if e_form < stability_threshold:
                # 强行关闭力学计算！把它留到第二阶段的专属脚本里去算
                res_dict["validation_status"] = "Thermo Stable (No Mech)"
            else:
                res_dict["validation_status"] = "Skipped (Unstable)"

        res_dict["is_mechanically_stable"] = None
        res_dict["process_time"] = time.time() - start_time
        return res_dict

    except Exception as e:
        res_dict.update({
            "validation_status": f"Crash: {str(e)}",
            "is_thermo_stable": None,
            "is_mechanically_stable": None,
            "error_message": str(e),
            "process_time": time.time() - start_time
        })
        return res_dict
    finally:
        if current_id:
            delete_structure(current_id)

def _run_ml_validation_background(input_csv_path, save_csv_path, stability_threshold):
    """【多进程版】ML验证批处理主函数"""
    ml_start_time = time.time()

    logger.info(f"\n{'='*80}")
    logger.info("ML validation started (parallel execution)")
    logger.info(f"{'='*80}")

    df = pd.read_csv(input_csv_path)
    
    # 断点续传逻辑
    processed_ids = set()
    if os.path.exists(save_csv_path):
        try:
            # 开启 on_bad_lines='skip'，直接无视并跳过损坏的最后半行
            done_df = pd.read_csv(save_csv_path, on_bad_lines='skip', engine='python')
            if "original_file" in done_df.columns:
                processed_ids = set(done_df["original_file"].dropna().astype(str).values)
                logger.info(f"恢复执行: 跳过 {len(processed_ids)} 个已处理结构。")
        except Exception as e:
            logger.error(f"读取历史进度失败: {e}")
            logger.warning("如果输出 CSV 末尾损坏，请先清理最后一行再恢复执行。")
        
    if processed_ids:
        df["original_file"] = df["original_file"].astype(str)
        df = df[~df["original_file"].isin(processed_ids)]
        if len(df) == 0:
            logger.info("所有结构均已完成验证，无需重复计算。")
            return

    total_rows = len(df)
    logger.info(f"剩余待验证结构: {total_rows}")

    save_dir = os.path.dirname(os.path.abspath(save_csv_path))
    if save_dir and not os.path.exists(save_dir): os.makedirs(save_dir)

    stable_count = 0
    unstable_count = 0
    full_pass_count = 0
    completed_count = 0

    max_workers = _resolve_batch_worker_count(default_limit=5)
    logger.info(f"启动 {max_workers} 个并行计算进程。")

    from concurrent.futures import ProcessPoolExecutor, as_completed

    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        # 提交所有任务
        futures = {
            executor.submit(_process_single_ml_validation, row.to_dict(), stability_threshold, i, total_rows): i 
            for i, row in df.iterrows()
        }

        # 实时接收并写入结果（主进程负责安全写入 CSV）
        for future in as_completed(futures):
            res_dict = future.result()
            completed_count += 1
            
            # 统计
            status = res_dict.get("validation_status", "")
            if res_dict.get("is_thermo_stable") is True: stable_count += 1
            elif res_dict.get("is_thermo_stable") is False: unstable_count += 1
            
            # 这里的统计逻辑也做了对应更新
            if status == "Thermo Stable (No Mech)": full_pass_count += 1

            # 写入 CSV
            df_row = pd.DataFrame([res_dict])
            header_mode = not os.path.exists(save_csv_path)
            df_row.to_csv(save_csv_path, mode='a', header=header_mode, index=False)

            # 打印精简进度 (现在你能看到具体的跳过原因了)
            e_form = res_dict.get("formation_energy_eV", 999.0)
            orig_file = res_dict.get("original_file", "unknown")
            p_time = res_dict.get("process_time", 0)
            logger.info(
                f"[{completed_count}/{total_rows}] {orig_file} | Status: {status} | "
                f"E_form: {e_form:.3f} | Time: {p_time:.1f}s"
            )

    ml_total_time = time.time() - ml_start_time
    logger.info(f"\n{'='*80}")
    logger.info("ML validation completed")
    logger.info(f"Total time: {ml_total_time:.2f}s ({ml_total_time/60:.1f} min)")
    logger.info(f"Thermo stable found: {full_pass_count} | unstable/errors: {unstable_count}")
    logger.info(f"{'='*80}\n")

def batch_ml_validation_impl(input_csv_path: str, save_csv_path: str, stability_threshold: float) -> str:
    if not os.path.exists(input_csv_path):
        return f"Error: input file {input_csv_path} not found."
    logger.info("Starting ML validation (synchronous mode)...")
    _run_ml_validation_background(input_csv_path, save_csv_path, stability_threshold)
    return f"ML validation completed. Results saved to {save_csv_path}"
