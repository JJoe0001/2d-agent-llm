from __future__ import annotations

from typing import Dict, Any, List, Tuple
from pymatgen.core import Structure, Element

from core.utils import build_periodic_bond_graph, connected_components, translation_rank_of_largest_component
from tools.dimensionality import dimensionality_rank_impl



A_CANDIDATES = {"Al","Si","Ga","Ge","In","Sn","Tl","Pb","P","As","Sb","Bi"}


def _hints(structure: Structure) -> Dict[str, bool]:
    elems = structure.composition.elements
    symbols = {el.symbol for el in elems}

    has_cn = ("C" in symbols) or ("N" in symbols)
    has_tm = any(Element(s).is_transition_metal for s in symbols if s not in {"C","N"})
    has_a = any(s in A_CANDIDATES for s in symbols)
    max_like = has_cn and has_tm and has_a

    has_o = "O" in symbols
    has_h = "H" in symbols
    metals = [s for s in symbols if Element(s).is_metal]
    ldh_like = has_o and has_h and (len(set(metals)) >= 2)

    return {"max_like": max_like, "ldh_like": ldh_like}


def _dim_rank(structure: Structure) -> Dict[str, Any]:
    return dimensionality_rank_impl(structure)


def _decision(signals: Dict[str, Any], hints: Dict[str, bool]) -> Tuple[str, List[str], str, float]:
    if hints["max_like"]:
        return (
            "chemistry",
            ["maxene_operator_plan"],
            "检测到 MAX-like 特征：更可能需要“选择性去除 A 层（MAX→MXene）+ 表面终止”而非几何剥离。",
            0.90,
        )
    if hints["ldh_like"]:
        return (
            "chemistry",
            ["ldh_intercalation_plan"],
            "检测到 LDH-like 特征：更可能需要插层/离子交换/溶胀分层，而非纯几何切层。",
            0.90,
        )
    if signals["dim_rank"] == 2 and signals["coverage"] >= 0.80:
        return (
            "geometry",
            ["planar_gap_scan", "extract_layer_geometry"],
            f"几何连通维度显示存在 2D 连通层（coverage={signals['coverage']:.2f}）：可先走几何切层，再做能量/表面验证。",
            0.85,
        )
    return (
        "hybrid",
        ["bond_weight_model", "bonddel_search_2d", "surface_risk_assessment"],
        "几何上更像 3D 连通或信号不强：建议走“断键/解理代价 + 表面稳定性”的混合策略寻找隐藏 2D。",
        0.70,
    )


def route_router_impl(structure: Structure) -> Dict[str, Any]:
    signals = _dim_rank(structure)
    hints = _hints(structure)
    route_family, recommended_tools, reason, confidence = _decision(signals, hints)

    return {
        "route_family": route_family,
        "signals": signals,
        "hints": hints,
        "recommended_tools": recommended_tools,
        "reason": reason,
        "confidence": float(confidence),
    }
