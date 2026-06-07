from __future__ import annotations

from typing import Optional, Dict, Any
from pymatgen.core import Structure

from core.store import new_structure_id, store_structure, is_path_allowed
from core.config import config
from tools.debug_utils import log_debug_trace, is_debug_enabled


def require_parsed_structure_id(parse_result: Dict[str, Any]) -> str:
    """Return the parsed structure id or raise the original parse error."""
    structure_id = parse_result.get("structure_id")
    if structure_id:
        return str(structure_id)

    error = parse_result.get("error", "结构解析失败。")
    error_type = parse_result.get("error_type")
    if error_type:
        raise ValueError(f"{error} [{error_type}]")
    raise ValueError(str(error))


def parse_structure_impl(
    cif_text: Optional[str] = None,
    file_path: Optional[str] = None,
    source_name: Optional[str] = None
) -> Dict[str, Any]:
    """
    解析 CIF 文本或文件，将结构存入内存，并返回元数据。
    包含错误捕获机制，防止因 CIF 格式错误导致整个 Server 崩溃。
    """
    if is_debug_enabled() and source_name:
        log_debug_trace(source_name, f"=== Starting Structure Parsing ===")

    # 0. 基本参数检查
    if not cif_text and not file_path:
        if is_debug_enabled() and source_name:
            log_debug_trace(source_name, "Error: Must provide either cif_text or file_path", "ERROR")
        return {"error": "必须提供 cif_text 或 file_path 其中之一。"}

    try:
        # 1. 加载结构
        if cif_text:
            # 可以在这里加一些简单的字符串清洗逻辑，例如去除多余空行
            if is_debug_enabled() and source_name:
                log_debug_trace(source_name, "Parsing CIF from text input")
            structure = Structure.from_str(cif_text, fmt="cif")
            used_path = None
        else:
            assert file_path is not None
            if is_debug_enabled() and source_name:
                log_debug_trace(source_name, f"Checking if file path is allowed: {file_path}")
            if not is_path_allowed(file_path):
                if is_debug_enabled() and source_name:
                    log_debug_trace(source_name, f"Error: File path not in whitelist directory: {config.WHITELIST_DIR}", "ERROR")
                return {"error": f"文件路径不在白名单目录内: {config.WHITELIST_DIR}"}
            if is_debug_enabled() and source_name:
                log_debug_trace(source_name, f"Parsing CIF from file: {file_path}")
            structure = Structure.from_file(file_path)
            used_path = file_path

        # 2. 结构有效性验证 (关键步骤)
        # 防止晶胞体积为 0 或原子数为 0 导致后续计算崩溃
        if structure.volume < 0.1:
            if is_debug_enabled() and source_name:
                log_debug_trace(source_name, f"Error: Invalid structure volume: {structure.volume:.4f} A^3", "ERROR")
            return {"error": f"解析出的结构体积无效 ({structure.volume:.4f} A^3)。请检查 CIF 晶格参数格式。"}

        if len(structure) == 0:
            if is_debug_enabled() and source_name:
                log_debug_trace(source_name, "Error: Structure contains no atoms", "ERROR")
            return {"error": "解析出的结构没有原子。请检查 CIF 的原子坐标部分。"}

        # 3. 存入 Store
        sid = new_structure_id()
        store_structure(
            sid,
            structure,
            meta={"source_name": source_name, "file_path": used_path}
        )

        # 4. 提取元数据
        comp = structure.composition
        lattice = structure.lattice
        elements = sorted([el.symbol for el in comp.elements])

        if is_debug_enabled() and source_name:
            log_debug_trace(source_name, f"=== Parsing Complete ===")
            log_debug_trace(source_name, f"Formula: {comp.reduced_formula}")
            log_debug_trace(source_name, f"Elements: {', '.join(elements)}")
            log_debug_trace(source_name, f"Number of sites: {len(structure)}")
            log_debug_trace(source_name, f"Lattice volume: {lattice.volume:.2f} A^3")
            log_debug_trace(source_name, f"Density: {structure.density:.2f} g/cm³")
            log_debug_trace(source_name, f"Structure ID: {sid}")

        return {
            "structure_id": sid,
            "source": {"source_name": source_name, "file_path": used_path},
            "formula_reduced": comp.reduced_formula,
            "elements": elements,
            "nelements": len(comp.elements),
            "nsites": len(structure),
            "lattice": {
                "a": float(lattice.a),
                "b": float(lattice.b),
                "c": float(lattice.c),
                "alpha": float(lattice.alpha),
                "beta": float(lattice.beta),
                "gamma": float(lattice.gamma),
                "volume": float(lattice.volume),
            },
            "density": float(structure.density),
            "warnings": [],
        }

    except Exception as e:
        # 捕获所有解析错误（包括 ZeroDivisionError），以 JSON 形式返回给 LLM
        # 这样 LLM 就会知道 CIF 错了，并尝试重新生成
        if is_debug_enabled() and source_name:
            log_debug_trace(source_name, f"Error: Structure parsing failed - {str(e)}", "ERROR")
        return {
            "error": f"结构解析失败: {str(e)}",
            "error_type": type(e).__name__
        }
