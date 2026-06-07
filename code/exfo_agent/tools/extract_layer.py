# tools/extract_layer.py
from __future__ import annotations

from typing import Any, Dict, List, Tuple, Optional
import numpy as np
from pymatgen.core import Structure
from pymatgen.core.surface import SlabGenerator

from core.utils import build_periodic_bond_graph, connected_components, translation_rank
from tools.debug_utils import log_debug_trace, is_debug_enabled


def extract_layer_component_impl(
    struct: Structure,
    hkl: List[int],
    shift: float,
    min_slab_size_A: float = 1.0,
    vacuum_A: float = 20.0,
    delta: float = 1.3,
    prefer_rank: int = 2,
    source_name: str = "extract_layer",
    timeout_seconds: float = 60.0,  # SAFETY: Hard timeout
) -> Dict[str, Any]:
    """
    TURBO + SAFETY: Extract layer component with strict timeout protection.
    """
    import time
    from loguru import logger

    start_time = time.time()

    def check_timeout(step_name: str = ""):
        elapsed = time.time() - start_time
        if elapsed > timeout_seconds:
            raise TimeoutError(f"Layer extraction timeout after {elapsed:.1f}s during: {step_name}")

    try:
        if is_debug_enabled():
            log_debug_trace(source_name, f"=== Starting Layer Extraction ===")
            log_debug_trace(source_name, f"Structure formula: {struct.composition.reduced_formula}")
            log_debug_trace(source_name, f"Parameters: HKL={hkl}, shift={shift:.3f}, min_slab_size={min_slab_size_A:.1f}A, vacuum={vacuum_A:.1f}A, delta={delta:.1f}")

        miller = (int(hkl[0]), int(hkl[1]), int(hkl[2]))

        check_timeout("slab generation start")

        sg = SlabGenerator(
            initial_structure=struct,
            miller_index=miller,
            min_slab_size=float(min_slab_size_A),
            min_vacuum_size=float(vacuum_A),
            center_slab=True,
            in_unit_planes=True,
            primitive=True,
            reorient_lattice=True,
        )

        if is_debug_enabled():
            log_debug_trace(source_name, f"Generating slab with Miller index {miller} and shift {shift:.3f}")

        check_timeout("before get_slab")
        slab = sg.get_slab(shift=float(shift))

        if is_debug_enabled():
            log_debug_trace(source_name, f"Generated slab with {len(slab)} sites")

        check_timeout("before bond graph")
        # [修改] 直接调用 core.utils 的函数 (now TURBO optimized)
        adj = build_periodic_bond_graph(slab, delta=float(delta))

        check_timeout("before connected components")
        comps = connected_components(adj)

        if is_debug_enabled():
            log_debug_trace(source_name, f"Found {len(comps)} connected components in slab")

        best_comp = None
        best_key = None  # (is_prefer_rank, size)

        check_timeout("before component analysis")
        for comp in comps:
            # [修改] 调用通用的 translation_rank
            r = translation_rank(adj, comp)
            is_pref = 1 if r == int(prefer_rank) else 0
            key = (is_pref, len(comp))
            if best_key is None or key > best_key:
                best_key = key
                best_comp = comp

        if best_comp is None:
            if is_debug_enabled():
                log_debug_trace(source_name, "No valid layers found", "WARNING")
            return {
                "hkl": list(miller),
                "shift": float(shift),
                "nsites": 0,
                "cif": "",
                "warnings": ["slab has no sites"],
            }

        keep = set(best_comp)
        remove = [i for i in range(len(slab)) if i not in keep]
        layer = slab.copy()
        layer.remove_sites(sorted(remove, reverse=True))

        check_timeout("before final rank calculation")
        # [修改] 再次检查提取后的秩
        if len(layer) > 0:
            layer_adj = build_periodic_bond_graph(layer, delta=float(delta))
            # 此时 layer 应该是单连通的，直接取所有原子计算秩
            rank_layer = translation_rank(layer_adj, list(range(len(layer))))
        else:
            rank_layer = 0

        elapsed = time.time() - start_time
        if is_debug_enabled():
            log_debug_trace(source_name, f"=== Layer Extraction Complete in {elapsed:.2f}s ===")
            log_debug_trace(source_name, f"Extracted layer: {layer.composition.reduced_formula}")
            log_debug_trace(source_name, f"Number of sites: {len(layer)}")
            log_debug_trace(source_name, f"Dimension rank: {rank_layer}D")

        return {
            "hkl": list(miller),
            "shift": float(shift),
            "slab_nsites": int(len(slab)),
            "layer_nsites": int(len(layer)),
            "layer_dim_rank_proxy": int(rank_layer),
            "layer_formula": layer.composition.reduced_formula if len(layer) > 0 else "",
            "cif": layer.to(fmt="cif"),
            "notes": "Used core.utils for graph algorithms.",
        }

    except TimeoutError as e:
        elapsed = time.time() - start_time
        logger.warning(f"Layer extraction TIMEOUT: {str(e)}")
        return {
            "hkl": list(hkl),
            "shift": float(shift),
            "nsites": 0,
            "cif": "",
            "warnings": [f"Timeout after {elapsed:.1f}s"],
        }
    except Exception as e:
        elapsed = time.time() - start_time
        logger.error(f"Layer extraction ERROR after {elapsed:.2f}s: {str(e)}")
        return {
            "hkl": list(hkl),
            "shift": float(shift),
            "nsites": 0,
            "cif": "",
            "warnings": [f"Error: {str(e)}"],
        }
