# file: server.py
"""MCP server for exfoliation-agent"""
from __future__ import annotations

import os
import sys
from typing import Dict

from fastmcp import FastMCP
from loguru import logger

# Add path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# --- 日志 ---
os.makedirs("logs", exist_ok=True)
logger.remove()
logger.add(sys.stderr, level="INFO")
logger.add("logs/system.log", rotation="50 MB", level="DEBUG")

logger.info("Initializing MCP server...")
mcp = FastMCP("exfoliation-agent-cloud")


# =============================================================================
# A. 系统与调试工具
# =============================================================================
@mcp.tool()
def set_debug_mode(enabled: bool) -> str:
    """开启或关闭全局调试模式 (生成快照 + 追踪日志)。"""
    from tools.debug_utils import set_debug_mode_impl

    return set_debug_mode_impl(enabled)


# =============================================================================
# B. 核心业务工具 (Smart & Batch)
# =============================================================================
@mcp.tool()
def smart_exfoliate_single(cif_text: str, source_name: str = "single_upload", top_k: int = 3) -> Dict:
    """【必须优先使用】处理单个 CIF 的主入口。"""
    from tools.workflow import smart_exfoliate_single_impl

    return smart_exfoliate_single_impl(cif_text, source_name, top_k)


@mcp.tool()
def batch_process_csv(
    input_csv_path: str,
    save_csv_path: str = "02_csv_extraction.csv",
    summary_path: str = "02_csv_summary.csv",
    top_k: int = 3,
) -> str:
    """
    【CSV 批量处理】从 CSV 文件批量提取 2D 层。

    CSV 格式要求:
    - original_file: 结构标识符 (e.g., mp-11107)
    - formula: 化学式 (e.g., Ac2O3)
    - cif_content: CIF 文件内容 (完整的 CIF 文本)
    - formation_energy: 形成能 (可选)
    - ehull: 能量距离凸包 (可选)
    - spacegroup: 空间群 (可选)

    输出将保留所有原始元数据，并添加提取的 2D 层信息。
    """
    from tools.batch_utils import batch_process_csv_impl

    return batch_process_csv_impl(input_csv_path, save_csv_path, summary_path, top_k)


@mcp.tool()
def batch_process_csv_no_passivation(
    input_csv_path: str,
    save_csv_path: str = "02_csv_extraction_no_pass.csv",
    summary_path: str = "02_csv_summary_no_pass.csv",
    top_k: int = 3,
) -> str:
    """
    【CSV 批量处理 - 无钝化版本】从 CSV 文件批量提取 2D 层，不进行表面钝化。

    CSV 格式要求:
    - original_file: 结构标识符 (e.g., mp-11107)
    - formula: 化学式 (e.g., Ac2O3)
    - cif_content: CIF 文件内容 (完整的 CIF 文本)
    - formation_energy: 形成能 (可选)
    - ehull: 能量距离凸包 (可选)
    - spacegroup: 空间群 (可选)

    此版本跳过表面钝化步骤，直接输出原始提取的 2D 层结构。
    适用于不需要钝化或后续手动处理的场景。
    """
    from tools.batch_utils_no_passivation import batch_process_csv_no_passivation_impl

    return batch_process_csv_no_passivation_impl(input_csv_path, save_csv_path, summary_path, top_k)


@mcp.tool()
def aiida_exfoliate_single(cif_text: str, source_name: str = "single_upload") -> Dict:
    """【文献范式】AiiDA 风格单结构二维剥离。"""
    from tools.literature_methods import aiida_exfoliate_single_impl

    return aiida_exfoliate_single_impl(cif_text=cif_text, source_name=source_name)


@mcp.tool()
def aiida_batch_process_csv(
    input_csv_path: str,
    save_csv_path: str = "02_csv_extraction_aiida.csv",
    summary_path: str = "02_csv_summary_aiida.csv",
    id_col: str = "original_file",
    cif_col: str = "cif_content",
    workers: int = 6,
) -> str:
    """【文献范式】AiiDA 风格批量二维剥离。"""
    from tools.literature_methods import aiida_batch_process_csv_impl

    return aiida_batch_process_csv_impl(
        input_csv_path=input_csv_path,
        save_csv_path=save_csv_path,
        summary_path=summary_path,
        id_col=id_col,
        cif_col=cif_col,
        workers=workers,
    )


@mcp.tool()
def matpedia_exfoliate_single(cif_text: str, source_name: str = "single_upload") -> Dict:
    """【文献范式】2DMatPedia 风格单结构二维剥离。"""
    from tools.literature_methods import matpedia_exfoliate_single_impl

    return matpedia_exfoliate_single_impl(cif_text=cif_text, source_name=source_name)


@mcp.tool()
def matpedia_batch_process_csv(
    input_csv_path: str,
    save_csv_path: str = "02_csv_extraction_2dmatpedia.csv",
    summary_path: str = "02_csv_summary_2dmatpedia.csv",
    id_col: str = "original_file",
    cif_col: str = "cif_content",
    workers: int = 6,
) -> str:
    """【文献范式】2DMatPedia 风格批量二维剥离。"""
    from tools.literature_methods import matpedia_batch_process_csv_impl

    return matpedia_batch_process_csv_impl(
        input_csv_path=input_csv_path,
        save_csv_path=save_csv_path,
        summary_path=summary_path,
        id_col=id_col,
        cif_col=cif_col,
        workers=workers,
    )


@mcp.tool()
def batch_ml_validation(input_csv: str, save_csv: str, threshold: float = -0.1) -> Dict:
    """
    启动高通量 ML 验证任务。
    注意：当前为同步执行，调用会在任务完成后返回。
    """
    from tools.batch_utils import batch_ml_validation_impl

    msg = batch_ml_validation_impl(
        input_csv_path=input_csv,
        save_csv_path=save_csv,
        stability_threshold=threshold,
    )

    return {
        "status": "Completed",
        "message": msg,
        "tip": "ML 验证已完成，可直接查看输出 CSV。",
    }


@mcp.tool()
def check_batch_status(summary_csv: str) -> Dict:
    """检查批处理进度。"""
    import os

    import pandas as pd

    if not os.path.exists(summary_csv):
        return {"error": f"尚未生成进度文件 {summary_csv}"}

    df = pd.read_csv(summary_csv)
    total = len(df)
    if total == 0:
        return {"total_processed": 0, "status": "Empty"}

    if "status" in df.columns:
        success = int((df["status"] == "SUCCESS").sum())
        known_error_states = {"ERROR", "TIMEOUT", "CRASH", "FAIL"}
        error = int(df["status"].isin(known_error_states).sum())
    else:
        success = 0
        error = 0

    last_col = "filename" if "filename" in df.columns else ("original_file" if "original_file" in df.columns else None)
    last_file = df.iloc[-1][last_col] if last_col else "UNKNOWN"

    return {
        "total_processed": total,
        "success_count": success,
        "error_count": error,
        "last_file": last_file,
    }


# =============================================================================
# C. 数据管理工具
# =============================================================================
@mcp.tool()
def deduplicate_structures(input_csv: str, output_csv: str = "logs/candidates_unique.csv") -> dict:
    """
    【初筛查重工具】对第一阶段剥离出的候选 2D 结构 CSV 进行严格的物理几何去重。
    该工具基于 pymatgen 的 StructureMatcher 还原原胞并对比，能剔除平移、扩胞及微小形变产生的重复结构，极大节省后续 ML 算力。
    """
    import os

    from tools.deduplicate_utils import deduplicate_candidates_csv

    if not os.path.exists(input_csv):
        return {"status": "error", "message": f"找不到输入文件: {input_csv}"}

    try:
        deduplicate_candidates_csv(input_csv, output_csv)
        return {
            "status": "success",
            "message": f"查重清洗完成，纯净数据已保存至 {output_csv}，可以继续进行 ML 验证。",
        }
    except Exception as e:
        return {"status": "error", "message": f"查重过程发生错误: {str(e)}"}


# =============================================================================
# D. 原子能力工具 (Atomic Capabilities) - 供高级调用
# =============================================================================
@mcp.tool()
def parse_structure(cif_text: str = None, file_path: str = None, source_name: str = None) -> Dict:
    from tools.parse import parse_structure_impl

    return parse_structure_impl(cif_text=cif_text, file_path=file_path, source_name=source_name)


@mcp.tool()
def dimensionality_rank(structure_id: str) -> Dict:
    from core.store import get_structure
    from tools.dimensionality import dimensionality_rank_impl

    struct = get_structure(structure_id)
    out = dimensionality_rank_impl(struct)
    out["structure_id"] = structure_id
    return out


@mcp.tool()
def route_router(structure_id: str) -> Dict:
    """【底层】根据当前结构信号推荐更合适的自适应工作流路径。"""
    from core.store import get_structure
    from tools.route import route_router_impl

    struct = get_structure(structure_id)
    out = route_router_impl(struct)
    out["structure_id"] = structure_id
    return out


@mcp.tool()
def planar_gap_scan(structure_id: str, dmin: float = 1.8, top_k: int = 10) -> Dict:
    """【底层】几何切片扫描。"""
    from core.store import get_structure
    from tools.planar_gap import planar_gap_scan_impl

    struct = get_structure(structure_id)
    out = planar_gap_scan_impl(struct, dmin=dmin, top_k=top_k)
    out["structure_id"] = structure_id
    return out


@mcp.tool()
def extract_layer_component(
    structure_id: str,
    hkl: list[int],
    shift: float,
    min_slab_size_A: float = 1.0,
    vacuum_A: float = 20.0,
    delta: float | None = None,
    prefer_rank: int = 2,
    timeout_seconds: float = 60.0,
) -> Dict:
    """【底层】按指定 hkl 和 shift 真正切出候选层。

    默认扫描 [1.2, 1.3, 1.1, 1.4, 1.5]，与批处理层保持一致；
    若显式传入 delta，则只使用该单一 delta。
    """
    from core.store import get_structure
    from tools.extract_layer import extract_layer_component_impl

    struct = get_structure(structure_id)

    deltas = [float(delta)] if delta is not None else [1.2, 1.3, 1.1, 1.4, 1.5]
    attempts = []
    best_out = None

    for d in deltas:
        out = extract_layer_component_impl(
            struct=struct,
            hkl=hkl,
            shift=shift,
            min_slab_size_A=min_slab_size_A,
            vacuum_A=vacuum_A,
            delta=d,
            prefer_rank=prefer_rank,
            source_name=f"extract_{structure_id}",
            timeout_seconds=timeout_seconds,
        )
        attempts.append(
            {
                "delta": d,
                "rank": out.get("layer_dim_rank_proxy"),
                "nsites": out.get("layer_nsites", out.get("nsites", 0)),
                "warnings": out.get("warnings", []),
            }
        )
        out["used_delta"] = d
        out["delta_scan"] = attempts
        best_out = out

        if out.get("layer_dim_rank_proxy") == int(prefer_rank) and out.get("layer_nsites", 0) > 0:
            break

    out = best_out or {
        "hkl": hkl,
        "shift": float(shift),
        "nsites": 0,
        "cif": "",
        "warnings": ["No extraction attempt was performed."],
        "delta_scan": attempts,
    }
    out["structure_id"] = structure_id
    return out


@mcp.tool()
def run_bonddel_exfoliation(structure_id: str, D: float = 2.0, timeout: int = 300) -> Dict:
    """【底层】手动化学断键 (BONDDEL)。"""
    from core.store import get_structure
    from tools.bond_del import BondDelAlgorithm
    from tools.debug_utils import is_debug_enabled

    struct = get_structure(structure_id)

    algo = BondDelAlgorithm(
        structure=struct,
        universal_potential=None,
        timeout_seconds=timeout,
    )
    algo.default_params.D = D

    res = algo.run(verbose=is_debug_enabled())

    return {
        "success": res.success,
        "message": res.message,
        "steps_taken": res.steps_taken,
    }


@mcp.tool()
def cross_batch_deduplicate(old_csv: str, new_csv: str, output_csv: str, max_atoms: int = 150) -> str:
    """
    【物理查重工具】基于 3D 晶体结构的物理坐标匹配查重与过滤。
    将新批次提取的二维结构 (new_csv) 与历史已知数据库 (old_csv) 进行空间对称性物理比对。
    作用：
    1. 剔除完全重复的物理相。
    2. 自动拦截并丢弃原子数超过 max_atoms (默认150) 的“算力黑洞”结构。
    """
    from tools.deduplicate_utils import cross_batch_deduplicate_impl

    return cross_batch_deduplicate_impl(old_csv, new_csv, output_csv, max_atoms)


# =============================================================================
# E. 结果分析工具
# =============================================================================
@mcp.tool()
def filter_true_2d(
    input_csv: str,
    output_csv: str,
    output_dir: str = "true_2d_cifs",
) -> str:
    """
    【结果提纯】按当前项目默认几何标准过滤真正的二维结构。

    说明：
    - 读取 `optimized_cif` 列作为判断对象
    - 沿用 analysis_utils 中现有的项目口径，不额外改判据
    """
    from tools.analysis_utils import filter_true_2d_impl

    return filter_true_2d_impl(
        input_csv=input_csv,
        output_csv=output_csv,
        output_dir=output_dir,
    )


@mcp.tool()
def single_structure_ml_validation(
    structure_id: str,
    threshold: float = -0.1,
    fmax: float = 0.1,
    steps: int = 200,
) -> Dict:
    """
    【单结构 ML 预验证】对单个结构执行 CHGNet 弛豫与形成能预筛。
    返回字段与批量 ML 验证保持一致，便于工作流复用。
    """
    from tools.ml_ops import ml_stage1_fast_evaluate

    eval_res = ml_stage1_fast_evaluate(structure_id, fmax=fmax, steps=steps)
    error_msg = eval_res.get("error", "")
    e_form = eval_res.get("formation_energy_2d", 999.0)

    if error_msg:
        if "too large" in error_msg:
            validation_status = "Skipped (Too Large)"
        else:
            validation_status = "Error/Explosion"
        is_stable = False
    else:
        is_stable = e_form < threshold
        validation_status = "Thermo Stable (No Mech)" if is_stable else "Skipped (Unstable)"

    return {
        "structure_id": structure_id,
        "initial_energy": eval_res.get("initial_energy"),
        "final_energy": eval_res.get("final_energy"),
        "formation_energy_eV": e_form,
        "is_thermo_stable": is_stable,
        "is_mechanically_stable": None,
        "is_relaxed": eval_res.get("converged", False),
        "optimized_structure_id": eval_res.get("optimized_id"),
        "num_atoms": eval_res.get("num_atoms"),
        "optimized_cif": eval_res.get("optimized_cif", ""),
        "validation_status": validation_status,
        "error_message": error_msg,
    }


@mcp.tool()
def passivate_covalent_surface(structure_id: str, passivant: str = "H") -> Dict:
    """【细分钝化】对偏共价表面执行定向钝化。"""
    from tools.surface_passivation import passivate_covalent_surface_impl

    return passivate_covalent_surface_impl(structure_id, passivant=passivant)


@mcp.tool()
def passivate_compound_semiconductor(structure_id: str) -> Dict:
    """【细分钝化】对化合物半导体表面执行定向钝化。"""
    from tools.surface_passivation import passivate_compound_semiconductor_impl

    return passivate_compound_semiconductor_impl(structure_id)


@mcp.tool()
def passivate_polar_surface(structure_id: str) -> Dict:
    """【细分钝化】对极性表面执行定向钝化。"""
    from tools.surface_passivation import passivate_polar_surface_impl

    return passivate_polar_surface_impl(structure_id)


@mcp.tool()
def auto_passivate_surface(structure_id: str) -> Dict:
    from tools.surface_passivation import auto_passivate_surface_impl

    return auto_passivate_surface_impl(structure_id)


if __name__ == "__main__":
    mcp.run(transport="http", port=8000)
