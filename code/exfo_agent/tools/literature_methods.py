from __future__ import annotations

import importlib.util
import os
import tempfile
from concurrent.futures import ProcessPoolExecutor, as_completed
from concurrent.futures.process import BrokenProcessPool
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Tuple

import pandas as pd
from pymatgen.core import Structure

from tools.parse import parse_structure_impl, require_parsed_structure_id


_REPO_ROOT = Path(__file__).resolve().parents[1]
_ROUTE_DIR = Path(__file__).resolve().parent / "literature_routes"
_AIIDA_SCRIPT = _ROUTE_DIR / "aiida_exfo_test.py"
_MATPEDIA_SCRIPT = _ROUTE_DIR / "exfo_2dmatpedia.py"


def _load_module(module_name: str, script_path: Path):
    if not script_path.exists():
        raise FileNotFoundError(f"找不到脚本: {script_path}")

    spec = importlib.util.spec_from_file_location(module_name, script_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"无法加载脚本: {script_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@lru_cache(maxsize=4)
def _get_aiida_module():
    return _load_module("exfo_aiida_method", _AIIDA_SCRIPT)


@lru_cache(maxsize=4)
def _get_matpedia_module():
    return _load_module("exfo_matpedia_method", _MATPEDIA_SCRIPT)


def _normalize_source_name(source_name: str) -> str:
    return str(source_name).replace("/", "_").replace("\\", "_")


def _read_text_if_exists(path: str) -> str:
    if path and os.path.exists(path):
        with open(path, "r", encoding="utf-8") as fh:
            return fh.read()
    return ""


def _build_candidate_row(
    row_data: Dict[str, Any],
    method_name: str,
    extracted_cif: str,
    has_2d_layer: bool,
    extra: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    extra = extra or {}
    original_file = row_data.get("original_file", row_data.get("material_id", "UNKNOWN"))
    original_formula = row_data.get("original_formula", row_data.get("formula", "UNKNOWN"))

    extracted_formula = ""
    if extracted_cif:
        try:
            extracted_formula = Structure.from_str(extracted_cif, fmt="cif").composition.reduced_formula
        except Exception:
            extracted_formula = ""

    return {
        "original_file": original_file,
        "original_formula": original_formula,
        "formation_energy": row_data.get("formation_energy"),
        "ehull": row_data.get("ehull"),
        "spacegroup": row_data.get("spacegroup"),
        "extraction_route": method_name,
        "dim_rank": 2 if has_2d_layer else None,
        "hkl": None,
        "gap_score": None,
        "used_delta": None,
        "cif_content": extracted_cif,
        "extracted_formula": extracted_formula,
        "is_passivated": False,
        "passivation_note": "No passivation",
        **extra,
    }


def _build_summary_row(
    row_data: Dict[str, Any],
    method_name: str,
    task_result: Dict[str, Any],
) -> Dict[str, Any]:
    original_file = row_data.get("original_file", row_data.get("material_id", "UNKNOWN"))
    has_2d = bool(task_result.get("has_2d_layer", False))
    status = task_result.get("status", "Failed")
    error_message = task_result.get("error_message", "")

    if status == "Success" and has_2d:
        summary_status = "SUCCESS"
    elif status == "Success":
        summary_status = "NO_2D"
    else:
        summary_status = "ERROR"

    return {
        "original_file": original_file,
        "status": summary_status,
        "route": method_name if has_2d else "NONE",
        "has_2d_layer": has_2d,
        "error_message": error_message,
    }


def _single_result_with_structure_id(
    method_name: str,
    source_name: str,
    task_result: Dict[str, Any],
) -> Dict[str, Any]:
    extracted_cif = _read_text_if_exists(task_result.get("extracted_file", ""))
    response = {
        "method": method_name,
        "source_name": source_name,
        "status": task_result.get("status", "Failed"),
        "has_2d_layer": bool(task_result.get("has_2d_layer", False)),
        "error_message": task_result.get("error_message", ""),
        "extracted_cif": extracted_cif,
    }

    if "dimensionalities" in task_result:
        response["dimensionalities"] = task_result.get("dimensionalities", [])

    if extracted_cif:
        parse_res = parse_structure_impl(cif_text=extracted_cif, source_name=f"{source_name}_{method_name}")
        response["parsed_structure"] = parse_res
        if "structure_id" in parse_res:
            response["structure_id"] = require_parsed_structure_id(parse_res)

    return response


def aiida_exfoliate_single_impl(cif_text: str, source_name: str = "single_upload") -> Dict[str, Any]:
    module = _get_aiida_module()
    safe_name = _normalize_source_name(source_name)

    with tempfile.TemporaryDirectory(prefix="aiida_single_") as tmpdir:
        task_result = module.process_material(
            {
                "id": safe_name,
                "cif_string": cif_text,
                "output_dir": tmpdir,
            }
        )
        return _single_result_with_structure_id("aiida", safe_name, task_result)


def matpedia_exfoliate_single_impl(cif_text: str, source_name: str = "single_upload") -> Dict[str, Any]:
    module = _get_matpedia_module()
    safe_name = _normalize_source_name(source_name)

    with tempfile.TemporaryDirectory(prefix="matpedia_single_") as tmpdir:
        task_result = module.process_material(
            {
                "id": safe_name,
                "cif_string": cif_text,
                "output_dir": tmpdir,
            }
        )
        return _single_result_with_structure_id("2dmatpedia", safe_name, task_result)


def _run_aiida_task(task: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    module = _get_aiida_module()
    return task["row_data"], module.process_material(task["task_dict"])


def _run_matpedia_task(task: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    module = _get_matpedia_module()
    return task["row_data"], module.process_material(task["task_dict"])


def _prepare_batch_tasks(
    input_csv_path: str,
    output_dir: str,
    id_col: str,
    cif_col: str,
) -> list[Dict[str, Any]]:
    df = pd.read_csv(input_csv_path)
    tasks: list[Dict[str, Any]] = []

    for _, row in df.iterrows():
        row_data = row.to_dict()
        material_id = row_data.get(id_col)
        cif_string = row_data.get(cif_col, "")
        tasks.append(
            {
                "row_data": row_data,
                "task_dict": {
                    "id": material_id,
                    "cif_string": cif_string,
                    "output_dir": output_dir,
                },
            }
        )
    return tasks


def _run_batch(
    method_name: str,
    runner,
    input_csv_path: str,
    save_csv_path: str,
    summary_path: str,
    extracted_dir_name: str,
    id_col: str,
    cif_col: str,
    workers: int,
) -> str:
    save_path = Path(save_csv_path).resolve()
    summary_out = Path(summary_path).resolve()
    output_dir = save_path.parent / extracted_dir_name
    output_dir.mkdir(parents=True, exist_ok=True)
    save_path.parent.mkdir(parents=True, exist_ok=True)
    summary_out.parent.mkdir(parents=True, exist_ok=True)

    tasks = _prepare_batch_tasks(input_csv_path, str(output_dir), id_col=id_col, cif_col=cif_col)

    candidate_rows = []
    summary_rows = []

    def record_result(row_data: Dict[str, Any], task_result: Dict[str, Any]) -> None:
        extracted_cif = _read_text_if_exists(task_result.get("extracted_file", ""))
        candidate_rows.append(
            _build_candidate_row(
                row_data=row_data,
                method_name=method_name,
                extracted_cif=extracted_cif,
                has_2d_layer=bool(task_result.get("has_2d_layer", False)),
                extra={
                    "dimensionalities": ",".join(map(str, task_result.get("dimensionalities", [])))
                    if "dimensionalities" in task_result
                    else None,
                    "method_status": task_result.get("status", "Failed"),
                    "method_error": task_result.get("error_message", ""),
                },
            )
        )
        summary_rows.append(_build_summary_row(row_data, method_name, task_result))

    if workers <= 1:
        for task in tasks:
            row_data, task_result = runner(task)
            record_result(row_data, task_result)
    else:
        try:
            with ProcessPoolExecutor(max_workers=workers) as executor:
                futures = [executor.submit(runner, task) for task in tasks]
                for future in as_completed(futures):
                    row_data, task_result = future.result()
                    record_result(row_data, task_result)
        except BrokenProcessPool:
            for task in tasks:
                row_data, task_result = runner(task)
                record_result(row_data, task_result)

    df_cand = pd.DataFrame(candidate_rows)
    df_sum = pd.DataFrame(summary_rows)

    if not df_cand.empty:
        df_cand = df_cand.sort_values(by=["original_file"], kind="stable")
    if not df_sum.empty:
        df_sum = df_sum.sort_values(by=["original_file"], kind="stable")

    df_cand.to_csv(save_path, index=False)
    df_sum.to_csv(summary_out, index=False)

    return (
        f"{method_name} 批处理完成。候选结果保存至 {save_path}，"
        f"进度摘要保存至 {summary_out}，提取的 CIF 保存在 {output_dir}"
    )


def aiida_batch_process_csv_impl(
    input_csv_path: str,
    save_csv_path: str = "02_csv_extraction_aiida.csv",
    summary_path: str = "02_csv_summary_aiida.csv",
    id_col: str = "original_file",
    cif_col: str = "cif_content",
    workers: int = 6,
) -> str:
    return _run_batch(
        method_name="aiida",
        runner=_run_aiida_task,
        input_csv_path=input_csv_path,
        save_csv_path=save_csv_path,
        summary_path=summary_path,
        extracted_dir_name="extracted_aiida_cifs",
        id_col=id_col,
        cif_col=cif_col,
        workers=workers,
    )


def matpedia_batch_process_csv_impl(
    input_csv_path: str,
    save_csv_path: str = "02_csv_extraction_2dmatpedia.csv",
    summary_path: str = "02_csv_summary_2dmatpedia.csv",
    id_col: str = "original_file",
    cif_col: str = "cif_content",
    workers: int = 6,
) -> str:
    return _run_batch(
        method_name="2dmatpedia",
        runner=_run_matpedia_task,
        input_csv_path=input_csv_path,
        save_csv_path=save_csv_path,
        summary_path=summary_path,
        extracted_dir_name="extracted_2dmatpedia_cifs",
        id_col=id_col,
        cif_col=cif_col,
        workers=workers,
    )
