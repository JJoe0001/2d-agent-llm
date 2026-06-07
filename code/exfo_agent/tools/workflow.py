# file: tools/workflows.py
from __future__ import annotations

from typing import Any, Dict

from pymatgen.core import Structure as PymatgenStructure

# 导入 Debug 工具
from tools.debug_utils import dump_error_artifact, is_debug_enabled, log_debug_trace, save_debug_snapshot

# 导入核心逻辑
from core.store import delete_structure, get_structure
from tools.bond_del import BondDelAlgorithm
from tools.dimensionality import dimensionality_rank_impl
from tools.extract_layer import extract_layer_component_impl
from tools.parse import parse_structure_impl, require_parsed_structure_id
from tools.planar_gap import planar_gap_scan_impl

SMART_LAYER_DELTAS = [1.2, 1.3, 1.1, 1.4, 1.5]


def smart_exfoliate_single_impl(
    cif_text: str,
    source_name: str = "single_upload",
    top_k: int = 3,
) -> Dict[str, Any]:
    """
    Implementation of the smart exfoliation workflow.
    """
    # 开启黑匣子记录
    log_debug_trace(source_name, f"=== Workflow Started for {source_name} ===")
    sid: str | None = None

    try:
        # 1. 解析
        log_debug_trace(source_name, "Step 1: Parsing Structure...")
        try:
            parse_res = parse_structure_impl(cif_text=cif_text, source_name=source_name)
            sid = require_parsed_structure_id(parse_res)
            struct = get_structure(sid)
            save_debug_snapshot(struct, "01_input_parsed", source_name, f"Formula: {struct.composition.reduced_formula}")
        except Exception as e:
            log_debug_trace(source_name, f"Parsing Failed: {e}", "FATAL")
            dump_error_artifact(source_name, e)
            raise e

        # 2. 判维
        log_debug_trace(source_name, "Step 2: Checking Dimensionality...")
        dim_res = dimensionality_rank_impl(struct=struct)
        dim_rank = dim_res.get("dim_rank", 3)
        log_debug_trace(source_name, f"Dimensionality Result: {dim_rank}D")

        result = {
            "original_id": sid,
            "formula": struct.composition.reduced_formula,
            "dimensionality_detected": dim_rank,
            "route_taken": "None",
            "layers": [],
        }

        # 3. 路由分发
        if dim_rank == 2:
            # === 路线 A ===
            result["route_taken"] = "Geometric Slicing"
            log_debug_trace(source_name, "Decision: Route A (Geometric) selected.")

            scan_res = planar_gap_scan_impl(struct, top_k=top_k, n_grid=(32, 32, 32))
            candidates = scan_res.get("candidates", [])
            log_debug_trace(source_name, f"Planar Gap Scan found {len(candidates)} candidates.")

            for idx, cand in enumerate(candidates[:top_k]):
                try:
                    log_debug_trace(source_name, f"  - Extracting layer {idx + 1}: hkl={cand['hkl']}")
                    layer_dict = None
                    attempts = []

                    for d in SMART_LAYER_DELTAS:
                        trial = extract_layer_component_impl(
                            struct,
                            hkl=cand["hkl"],
                            shift=cand["gap_center_frac"],
                            delta=d,
                        )
                        attempts.append(
                            {
                                "delta": d,
                                "rank": trial.get("layer_dim_rank_proxy"),
                                "nsites": trial.get("layer_nsites", trial.get("nsites", 0)),
                            }
                        )
                        if trial.get("layer_dim_rank_proxy") == 2 and trial.get("layer_nsites", 0) > 0:
                            layer_dict = trial
                            layer_dict["used_delta"] = d
                            layer_dict["delta_scan"] = attempts
                            break

                    if layer_dict is None:
                        log_debug_trace(
                            source_name,
                            f"  - No 2D layer extracted for candidate {idx} after delta scan: {attempts}",
                            "WARN",
                        )
                        continue

                    if "cif" in layer_dict:
                        layer_struct = PymatgenStructure.from_str(layer_dict["cif"], fmt="cif")
                        save_debug_snapshot(layer_struct, f"02_geo_layer_{idx}", source_name)

                    result["layers"].append(
                        {
                            "hkl": cand["hkl"],
                            "score": cand["score_proxy"],
                            "used_delta": layer_dict.get("used_delta"),
                            "cif_content": layer_dict.get("cif"),
                            "formula": layer_dict.get("layer_formula"),
                        }
                    )
                except Exception as e:
                    log_debug_trace(source_name, f"  - Extraction failed for candidate {idx}: {e}", "ERROR")

        elif dim_rank == 3:
            # === 路线 B ===
            result["route_taken"] = "Chemical Bond Deletion"
            log_debug_trace(source_name, "Decision: Route B (BONDDEL) selected. Structure is 3D.")

            # 注意：如需按元素对势参数，请在外层注入 universal_potential
            algo = BondDelAlgorithm(struct)
            log_debug_trace(source_name, "Starting BondDelAlgorithm (Threshold Mode)...")

            try:
                algo_res = algo.run(verbose=is_debug_enabled())

                if algo_res.success:
                    log_debug_trace(source_name, f"BONDDEL Success! Message: {algo_res.message}")

                    # 直接使用 run() 返回的 final_clusters，避免调用已删除的方法
                    if algo_res.final_clusters:
                        log_debug_trace(source_name, f"BONDDEL returned {len(algo_res.final_clusters)} candidate clusters.")

                        for idx, nodes in enumerate(algo_res.final_clusters):
                            if len(nodes) < 4:
                                continue

                            nodes = sorted(nodes)
                            species = [struct.sites[i].species for i in nodes]
                            coords = [struct.frac_coords[i] for i in nodes]
                            cluster_struct = PymatgenStructure(struct.lattice, species, coords)

                            save_debug_snapshot(cluster_struct, f"02_bonddel_cluster_{idx}", source_name)

                            # 二次判维（保留原行为）
                            c_dim = dimensionality_rank_impl(cluster_struct).get("dim_rank", 0)
                            log_debug_trace(source_name, f"  - Cluster {idx}: Dimension check = {c_dim}D")

                            if c_dim == 2:
                                result["layers"].append(
                                    {
                                        "cluster_id": idx,
                                        "bonds_broken": len(algo_res.deleted_bonds),
                                        "cif_content": cluster_struct.to(fmt="cif"),
                                        "formula": cluster_struct.composition.reduced_formula,
                                    }
                                )
                    else:
                        log_debug_trace(source_name, "BONDDEL returned success but no clusters found.", "WARN")
                else:
                    log_debug_trace(source_name, f"BONDDEL Failed. Reason: {algo_res.message}", "WARN")
                    result["message"] = algo_res.message

            except Exception as e:
                log_debug_trace(source_name, f"BONDDEL Algorithm Crashed: {e}", "FATAL")
                dump_error_artifact(source_name, e)
                raise e

        else:
            log_debug_trace(source_name, f"Decision: Skipped. Dimension {dim_rank}D.", "WARN")
            result["message"] = f"Material is {dim_rank}D."

        log_debug_trace(source_name, "=== Workflow Completed Successfully ===")
        return result

    except Exception as e:
        log_debug_trace(source_name, f"Workflow Crashed at Top Level: {e}", "FATAL")
        dump_error_artifact(source_name, e)
        return {"error": str(e), "note": "Check debug_artifacts for traceback log."}
    finally:
        if sid:
            delete_structure(sid)
