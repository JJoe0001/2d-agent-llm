from __future__ import annotations

from typing import Dict, Any, List, Optional
from pymatgen.core import Structure

from core.utils import (
    build_periodic_bond_graph,
    connected_components,
    translation_rank_of_largest_component,
)
from tools.debug_utils import log_debug_trace, is_debug_enabled


def dimensionality_rank_impl(
    struct: Structure,
    deltas: Optional[List[float]] = None,
    min_coverage: float = 0.0,
    source_name: str = "dimensionality_check",
) -> Dict[str, Any]:
    """
    Geometry-first dimensionality signal (0/1/2/3) using a simplified TSA/Mounet-style idea.

    Method:
      - build periodic bond graph using vdW-radius threshold: d_ij < rvdw_i + rvdw_j - delta
      - scan delta over a small list for robustness
      - take the largest connected component and compute:
          coverage = |largest_component| / N
          dim_rank = rank of non-zero periodic image vectors inside the largest component
        where rank in {0,1,2,3} corresponds to 0D/1D/2D/3D connectivity.

    Returns a JSON-serializable dict:
      {
        "dim_rank": int,
        "coverage": float,
        "rank_delta_used": float,
        "delta_scan": [{"delta": float, "rank": int, "coverage": float}, ...],
        "note": str (optional)
      }
    """
    if is_debug_enabled():
        log_debug_trace(source_name, f"=== Starting Dimensionality Rank Calculation ===")
        log_debug_trace(source_name, f"Structure formula: {struct.composition.reduced_formula}")
        log_debug_trace(source_name, f"Number of sites: {len(struct)}")

    if deltas is None:
        deltas = [1.2, 1.3, 1.4]
        if is_debug_enabled():
            log_debug_trace(source_name, f"Using default delta values: {deltas}")

    n = max(1, len(struct))
    scan: List[Dict[str, Any]] = []

    best_key = None  # (rank, -coverage, delta)
    best_payload = None

    for d in deltas:
        d = float(d)
        if is_debug_enabled():
            log_debug_trace(source_name, f"  - Scanning with delta = {d:.1f}")

        adj = build_periodic_bond_graph(struct, delta=d)
        comps = connected_components(adj)
        largest = max(comps, key=len)
        coverage = len(largest) / n
        rank = translation_rank_of_largest_component(adj, comps)

        if is_debug_enabled():
            log_debug_trace(source_name, f"    Rank: {rank}D, Coverage: {coverage:.3f}")

        scan.append({"delta": d, "rank": int(rank), "coverage": float(coverage)})

        # pick the "most low-dimensional" result; tie-breaker: higher coverage; then smaller delta
        key = (int(rank), -float(coverage), d)
        if best_key is None or key < best_key:
            best_key = key
            best_payload = {
                "dim_rank": int(rank),
                "coverage": float(coverage),
                "rank_delta_used": d,
            }

    assert best_payload is not None
    best_payload["delta_scan"] = scan

    if is_debug_enabled():
        log_debug_trace(source_name, f"=== Dimensionality Rank Result ===")
        log_debug_trace(source_name, f"Best rank: {best_payload['dim_rank']}D")
        log_debug_trace(source_name, f"Coverage: {best_payload['coverage']:.3f}")
        log_debug_trace(source_name, f"Delta used: {best_payload['rank_delta_used']:.1f}")

    if best_payload["coverage"] < float(min_coverage):
        best_payload["note"] = (
            f"coverage({best_payload['coverage']:.3f}) < min_coverage({min_coverage}); "
            "结果可能不稳定（建议检查结构是否含分子/插层单元，或调整 deltas/成键规则）。"
        )

    return best_payload
