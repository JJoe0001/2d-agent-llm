# tools/planar_gap.py
from __future__ import annotations

from typing import Any, Dict, List, Tuple
from pymatgen.core import Structure

# [变更] 不再引用本地的 cleavage_analysis，直接引用合并后的 core.utils
from core.utils import get_planar_gap_candidates
from tools.debug_utils import log_debug_trace, is_debug_enabled


def planar_gap_scan_impl(
    struct: Structure,
    dmin: float = 1.8,
    gap_level: float = 0.75,
    n_grid: Tuple[int, int, int] = (32, 32, 32),
    d_smooth: float = 0.1,
    top_k: int = 5,
    fallback_to_axis_mvp: bool = True,
    source_name: str = "planar_gap_scan",
) -> Dict[str, Any]:
    """
    C2: 平面 gap 扫描（基于 Core Utils 的几何电子密度投影）

    返回（JSON-serializable）：
      {
        "backend": "core.utils",
        "candidates": [
           {"hkl":[h,k,l], "cleavage_ability_raw":..., "gap_center_frac":..., ...},
           ...
        ],
        "best": {...},
        "params": {...},
        "warnings": [...]
      }
    """
    if is_debug_enabled():
        log_debug_trace(source_name, f"=== Starting Planar Gap Scan ===")
        log_debug_trace(source_name, f"Structure formula: {struct.composition.reduced_formula}")
        log_debug_trace(source_name, f"Number of sites: {len(struct)}")
        log_debug_trace(source_name, f"Parameters: dmin={dmin:.2f}, gap_level={gap_level:.2f}, n_grid={n_grid}, d_smooth={d_smooth:.2f}, top_k={top_k}")

    warnings: List[str] = []

    # 1) 参数安全检查
    # 动态调整 dmin：如果 dmin 太小导致计算量爆炸，强制调大
    # 经验公式：最小间距不应小于晶格最小边长的 1/15 或 1.5A
    if struct.lattice:
        min_lattice_vec = min(struct.lattice.abc)
        safe_dmin = max(float(dmin), 1.5, min_lattice_vec / 15.0)

        if safe_dmin > dmin + 0.01: # 允许微小浮点误差
            if is_debug_enabled():
                log_debug_trace(source_name, f"Auto-adjusting dmin from {dmin} to {safe_dmin:.2f} to prevent timeout")
            warnings.append(f"Auto-adjusted dmin from {dmin} to {safe_dmin:.2f} to prevent timeout.")
            dmin = safe_dmin

    try:
        # 2) 调用 Core Utils 进行计算
        # get_planar_gap_candidates 已经在 utils 里完成了 HKL生成、密度计算、投影和 Gap 分析
        if is_debug_enabled():
            log_debug_trace(source_name, "Calling core.utils.get_planar_gap_candidates for gap analysis")

        raw_results = get_planar_gap_candidates(
            structure=struct,
            dmin=float(dmin),
            gap_level=float(gap_level),
            n_grid=tuple(int(x) for x in n_grid),
            d_smooth=float(d_smooth)
        )

        if is_debug_enabled():
            log_debug_trace(source_name, f"Found {len(raw_results)} gap candidates in initial scan")

        # 3) 格式化输出结果
        candidates: List[Dict[str, Any]] = []

        # utils 返回的已经按 score 降序排列
        for i, item in enumerate(raw_results[:int(top_k)]):
            # core.utils 返回的字典键值包括: hkl, width, center, depth, score
            candidates.append({
                "hkl": [int(x) for x in item["hkl"]],

                # 兼容旧字段名 cleavage_ability_raw (对应 Gap 宽度)
                "cleavage_ability_raw": float(item["width"]),

                # 关键字段：gap 中心位置 (shift)
                "gap_center_frac": float(item["center"]),

                # 统计指标
                "gap_width_frac": float(item["width"]),
                "gap_depth_proxy": float(item["depth"]),
                "score_proxy": float(item["score"]),
            })

            if is_debug_enabled():
                log_debug_trace(source_name, f"  Candidate {i+1}: HKL={item['hkl']}, Width={item['width']:.3f}, Depth={item['depth']:.3f}, Score={item['score']:.3f}")

        best = candidates[0] if candidates else None

        if is_debug_enabled():
            log_debug_trace(source_name, f"=== Planar Gap Scan Complete ===")
            if best:
                log_debug_trace(source_name, f"Best candidate: HKL={best['hkl']}, Score={best['score_proxy']:.3f}")
            else:
                log_debug_trace(source_name, "No valid gap candidates found")

        return {
            "backend": "core.utils",
            "params": {
                "dmin": float(dmin),
                "gap_level": float(gap_level),
                "n_grid": [int(x) for x in n_grid],
                "d_smooth": float(d_smooth),
                "top_k": int(top_k),
            },
            "candidates": candidates,
            "best": best,
            "warnings": warnings,
        }

    except Exception as e:
        import traceback
        err_msg = f"Planar gap scan failed: {str(e)}"
        if is_debug_enabled():
            log_debug_trace(source_name, err_msg, "ERROR")
            log_debug_trace(source_name, traceback.format_exc(), "DEBUG")
        warnings.append(err_msg)

        # 失败时的 Fallback 逻辑 (保留原始接口结构)
        if not fallback_to_axis_mvp:
            return {
                "backend": "failed",
                "params": {"dmin": dmin, "gap_level": gap_level},
                "candidates": [],
                "best": None,
                "warnings": warnings,
            }

        # 如果需要 axis_mvp 回退，在这里实现简单逻辑
        return {
            "backend": "axis_mvp_placeholder",
            "params": {"top_k": top_k},
            "candidates": [],
            "best": None,
            "warnings": warnings + ["Fallback triggered but Axis MVP not implemented."],
        }
