# tools/ml_ops.py
from __future__ import annotations
import threading
import gc
from typing import Dict, Any
from loguru import logger
import numpy as np
import torch
from chgnet.model.dynamics import CHGNetCalculator
from chgnet.model import CHGNet
from pymatgen.io.ase import AseAtomsAdaptor
from ase.optimize import FIRE

HAS_ML = True
from core.store import get_structure, new_structure_id, store_structure

# --- 元素参考能量表 (CHGNet 计算) ---
# 使用 CHGNet 计算的单质能量，确保与形成能计算的方法一致性
# 生成脚本: tools/generate_chgnet_ref_energies.py
REF_ENERGIES = {
    "Ag": -0.7002, "Al": -0.9161, "As": -2.2281, "Au": -0.8004, "Ba": -0.9414,
    "Bi": -1.9112, "Br": -0.1884, "C": -2.291, "Ca": -0.4921, "Cd": -0.4569,
    "Cl": -0.217, "Co": -3.5138, "Cr": -4.7692, "Cs": -0.4251, "Cu": -1.0208,
    "Fe": -4.1771, "Ga": -0.6016, "Ge": -0.5553, "H": -0.5719, "Hf": -4.9554,
    "Hg": -0.2754, "I": -0.2324, "In": -1.0416, "Ir": -2.2072, "K": -0.5434,
    "La": -2.4473, "Li": -0.9368, "Mg": -0.7977, "Mo": -5.3459, "N": -0.4156,
    "Na": -0.6434, "Nb": -5.0104, "Ni": -1.4363, "O": -0.321, "Os": -5.5826,
    "P": -0.4934, "Pb": -0.9136, "Pd": -1.2964, "Pt": -1.5179, "Rb": -0.4671,
    "Re": -6.2232, "Rh": -1.8212, "Ru": -4.5664, "S": -0.1611, "Sb": -2.0328,
    "Sc": -3.1371, "Se": -1.0252, "Si": -0.664, "Sn": -1.6179, "Sr": -0.4161,
    "Ta": -5.9249, "Tc": -5.1674, "Te": -1.0289, "Ti": -3.9085, "Tl": -1.1621,
    "V": -4.5339, "W": -6.3768, "Y": -3.2208, "Zn": -0.6312, "Zr": -4.2543,
}

_CALC_CACHE = None
_calc_lock = threading.Lock()

def _get_calculator():
    """加载 CHGNet 模型 (单例模式)"""
    global _CALC_CACHE
    if _CALC_CACHE is not None: return _CALC_CACHE
    with _calc_lock:
        if _CALC_CACHE is not None: return _CALC_CACHE
        use_device = "cuda" if torch.cuda.is_available() else ("mps" if torch.backends.mps.is_available() else "cpu")
        logger.info(f"Initializing CHGNet calculator on {use_device}")
        _CALC_CACHE = CHGNetCalculator(model=CHGNet.load(), use_device=use_device)
        return _CALC_CACHE

# =====================================================================
# 核心高通量初筛流水线：生产级稳定版
# =====================================================================
def ml_stage1_fast_evaluate(
    structure_id: str,
    fmax: float = 0.2,
    steps: int = 200,
    force_cleanup: bool = True  # 默认强制清理，防止 VRAM 泄漏
) -> Dict[str, Any]:
    """
    执行结构弛豫并计算形成能（生产级稳定防丢失版）


    返回字典键（所有路径保证一致）：
        - original_id: str
        - optimized_id: str | None
        - initial_energy: float | None
        - final_energy: float | None
        - formation_energy_2d: float (失败时为 999.0)
        - converged: bool
        - num_atoms: int
        - error: str
        - optimized_cif: str (成功时为 CIF 内容，失败时为空字符串)
    """
    calc = _get_calculator()
    struct = get_structure(structure_id)
    num_atoms = len(struct)

    # 动态原子数拦截（根据硬件调整）
    max_atoms = 500 if torch.cuda.is_available() else 600
    if num_atoms > max_atoms:
        return {
            "original_id": structure_id,
            "optimized_id": None,
            "initial_energy": None,
            "final_energy": None,
            "formation_energy_2d": 999.0,  # 哨兵值，表示失败
            "converged": False,
            "num_atoms": num_atoms,
            "error": f"Skipped: Structure too large ({num_atoms} atoms > {max_atoms})",
            "optimized_cif": ""
        }

    atoms = AseAtomsAdaptor.get_atoms(struct)
    atoms.calc = calc

    # 计算初始能量（即使后续失败也能返回）
    initial_e = None
    try:
        initial_e = atoms.get_potential_energy()
    except Exception as e:
        # 如果连初始能量都算不出来，直接返回
        return {
            "original_id": structure_id,
            "optimized_id": None,
            "initial_energy": None,
            "final_energy": None,
            "formation_energy_2d": 999.0,
            "converged": False,
            "num_atoms": num_atoms,
            "error": f"Failed to compute initial energy: {str(e)}",
            "optimized_cif": ""
        }

    opt = FIRE(atoms, logfile=None)

    # 爆炸检测
    def check_explosion():
        forces = atoms.get_forces()
        max_f = np.max(np.linalg.norm(forces, axis=1))
        if max_f > 500.0:
            raise RuntimeError(f"结构爆炸: 最大受力 {max_f:.2f} eV/A > 500.0")

    opt.attach(check_explosion, interval=10)

    try:
        converged = opt.run(fmax=fmax, steps=steps)

        # 计算最终能量和形成能
        final_e = atoms.get_potential_energy()
        final_struct = AseAtomsAdaptor.get_structure(atoms)
        
        # 直接将优化后的 3D 坐标转成文本，便于后续流程消费
        optimized_cif_str = final_struct.to(fmt="cif")

        # 预计算参考能量
        composition = final_struct.composition
        ref_sum = sum(REF_ENERGIES.get(str(el), 0.0) * amt
                      for el, amt in composition.items())
        e_form = (final_e - ref_sum) / num_atoms

        # 存储优化后的结构 (虽然缓存会丢，但可以留着作为后备)
        new_sid = new_structure_id()
        store_structure(new_sid, final_struct, meta={
            "parent": structure_id,
            "method": "chgnet_fast_relax_v2"
        })

        return {
            "original_id": structure_id,
            "optimized_id": new_sid,
            "initial_energy": float(initial_e) if initial_e is not None else None,
            "final_energy": float(final_e),
            "formation_energy_2d": float(round(e_form, 4)),
            "converged": bool(converged),
            "num_atoms": num_atoms,
            "error": "",
            "optimized_cif": optimized_cif_str
        }

    except RuntimeError as e:
        return {
            "original_id": structure_id,
            "optimized_id": None,
            "initial_energy": float(initial_e) if initial_e is not None else None,
            "final_energy": None,
            "formation_energy_2d": 999.0,  # 哨兵值，表示优化失败
            "converged": False,
            "num_atoms": num_atoms,
            "error": str(e),
            "optimized_cif": ""
        }

    except Exception as e:
        # 捕获其他未预期的异常
        return {
            "original_id": structure_id,
            "optimized_id": None,
            "initial_energy": float(initial_e) if initial_e is not None else None,
            "final_energy": None,
            "formation_energy_2d": 999.0,
            "converged": False,
            "num_atoms": num_atoms,
            "error": f"Unexpected error: {str(e)}",
            "optimized_cif": ""
        }

    finally:
        # 强制 VRAM 清理，避免显存持续增长
        del atoms, opt
        if force_cleanup:
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
