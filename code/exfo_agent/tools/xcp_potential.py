import numpy as np
import os
from dataclasses import dataclass
from typing import Dict, Tuple, Optional

@dataclass
class XCPParameters:
    D: float = 2.0      # depth (eV)
    alpha: float = 1.5  # expscale (1/A)
    r0: float = 2.5     # radius (A)
    C: float = 0.0      # coulomb_scale
    gamma: float = 1.0  # yukawa_exp

class UniversalPotential:
    
    # Fortran 代码硬编码为 118
    MAX_SPECIES = 118
    
    # 【Fix】补全了所有 1-118 号元素的映射表，防止 KeyError
    Z_TO_SYMBOL = {
        1: 'H', 2: 'He', 3: 'Li', 4: 'Be', 5: 'B', 6: 'C', 7: 'N', 8: 'O', 9: 'F', 10: 'Ne',
        11: 'Na', 12: 'Mg', 13: 'Al', 14: 'Si', 15: 'P', 16: 'S', 17: 'Cl', 18: 'Ar', 19: 'K', 20: 'Ca',
        21: 'Sc', 22: 'Ti', 23: 'V', 24: 'Cr', 25: 'Mn', 26: 'Fe', 27: 'Co', 28: 'Ni', 29: 'Cu', 30: 'Zn',
        31: 'Ga', 32: 'Ge', 33: 'As', 34: 'Se', 35: 'Br', 36: 'Kr', 37: 'Rb', 38: 'Sr', 39: 'Y', 40: 'Zr',
        41: 'Nb', 42: 'Mo', 43: 'Tc', 44: 'Ru', 45: 'Rh', 46: 'Pd', 47: 'Ag', 48: 'Cd', 49: 'In', 50: 'Sn',
        51: 'Sb', 52: 'Te', 53: 'I', 54: 'Xe', 55: 'Cs', 56: 'Ba', 57: 'La', 58: 'Ce', 59: 'Pr', 60: 'Nd',
        61: 'Pm', 62: 'Sm', 63: 'Eu', 64: 'Gd', 65: 'Tb', 66: 'Dy', 67: 'Ho', 68: 'Er', 69: 'Tm', 70: 'Yb',
        71: 'Lu', 72: 'Hf', 73: 'Ta', 74: 'W', 75: 'Re', 76: 'Os', 77: 'Ir', 78: 'Pt', 79: 'Au', 80: 'Hg',
        81: 'Tl', 82: 'Pb', 83: 'Bi', 84: 'Po', 85: 'At', 86: 'Rn', 87: 'Fr', 88: 'Ra', 89: 'Ac', 90: 'Th',
        91: 'Pa', 92: 'U', 93: 'Np', 94: 'Pu', 95: 'Am', 96: 'Cm', 97: 'Bk', 98: 'Cf', 99: 'Es', 100: 'Fm',
        101: 'Md', 102: 'No', 103: 'Lr', 104: 'Rf', 105: 'Db', 106: 'Sg', 107: 'Bh', 108: 'Hs', 109: 'Mt',
        110: 'Ds', 111: 'Rg', 112: 'Cn', 113: 'Nh', 114: 'Fl', 115: 'Mc', 116: 'Lv', 117: 'Ts', 118: 'Og'
    }
    
    # 建立反向映射: Symbol -> Z
    SYMBOL_TO_Z = {v: k for k, v in Z_TO_SYMBOL.items()}

    def __init__(self, potdata_path: str):
        self.raw_matrices = None
        self._load_from_file(potdata_path)

    def _load_from_file(self, filepath: str):
        if not os.path.exists(filepath):
            # 因为没有 try-catch，这里必须显式抛出异常
            raise FileNotFoundError(f"CRITICAL: POTDATA file not found at: {filepath}")

        try:
            with open(filepath, 'r') as f:
                # 读取全部内容并分割，处理所有空白符（空格、换行、Tab）
                tokens = f.read().split()
        except Exception as e:
            raise IOError(f"Failed to read POTDATA: {e}")

        if not tokens:
            raise ValueError("POTDATA file is empty.")

        # 1. 验证头部 potshape 
        try:
            potshape = int(tokens[0])
        except ValueError:
            raise ValueError(f"Invalid POTDATA header: expected integer, got '{tokens[0]}'")

        if potshape != 2:
            raise ValueError(f"Unsupported potential type: expected 2 (Morse), found {potshape}")
            
        # 转换数据部分
        try:
            data_tokens = [float(x) for x in tokens[1:]]
        except ValueError as e:
            raise ValueError(f"POTDATA contains non-numeric data: {e}")
        
        # 2. 验证数据大小
        n_params = 5
        dim = self.MAX_SPECIES
        expected_size = n_params * dim * dim # 5 * 118 * 118 = 69620
        
        if len(data_tokens) != expected_size:
            # 【Fix】数据对不齐时直接报错，防止后面 reshape 崩溃或数据错位
            raise ValueError(
                f"POTDATA size mismatch! Expected {expected_size} floats "
                f"(5 params * 118 * 118), but got {len(data_tokens)}. "
                "Ensure the file matches the Fortran '118' hardcoded dimension."
            )
            
        # 3. 解析矩阵
        # Fortran Output Order assumed:
        # Loop i=1..5 (Params) -> Loop j=1..118 (Spec1) -> Loop k=1..118 (Spec2)
        # Python 'reshape' (C-order) fills the last index fastest.
        # So reshape(5, 118, 118) matches (Param, Spec1, Spec2).
        self.raw_matrices = np.array(data_tokens).reshape(n_params, dim, dim)

    def get_params(self, el1: str, el2: str) -> XCPParameters:
        """
        根据元素符号获取参数。
        """
        # 处理不规则输入（如去掉电荷标记 'Fe2+' -> 'Fe'）
        # 这里做一个简单的清洗，只保留字母
        el1_clean = "".join([c for c in el1 if c.isalpha()])
        el2_clean = "".join([c for c in el2 if c.isalpha()])

        z1 = self.SYMBOL_TO_Z.get(el1_clean, 0)
        z2 = self.SYMBOL_TO_Z.get(el2_clean, 0)
        
        # 如果元素不在 1-118 范围内，返回默认值
        # 这是一个软处理，避免因为单一杂质原子导致整个算法崩溃
        if z1 == 0 or z2 == 0:
             # Fallback: Weak bond default
            return XCPParameters(D=0.5, alpha=1.5, r0=3.0, C=0.0, gamma=1.0)
            
        # 矩阵索引: [param_idx, z1-1, z2-1]
        idx1 = z1 - 1
        idx2 = z2 - 1
        
        p = self.raw_matrices[:, idx1, idx2]
        
        return XCPParameters(
            D=p[0],      # para(1)
            alpha=p[1],  # para(2)
            r0=p[2],     # para(3)
            C=p[3],      # para(4)
            gamma=p[4]   # para(5)
        )

# -----------------------------------------------------------------------------
# 4. 能量计算函数
# -----------------------------------------------------------------------------

def compute_xcp_energy(r: float, params: XCPParameters) -> float:
    """
    计算键能 V(r) = Morse + Yukawa
    """
    # 物理距离保护，防止原子完全重合导致数值爆炸
    if r < 0.1: return 1.0e5 # 返回一个大的正数（强排斥）
    
    # Morse Potential
    # V_morse = D * ((1 - exp(a(r0-r)))^2 - 1)
    # The term '- 1' ensures V(r0) = -D (Binding Energy) and V(inf) = 0
    # Note: params.alpha is positive. r0 is equilibrium distance.
    val = params.alpha * (params.r0 - r)
    
    # 防止 exp 溢出
    if val > 20: val = 20
    if val < -20: val = -20
    
    expo = np.exp(val)
    morse = params.D * ((1.0 - expo)**2 - 1.0)
    
    # Yukawa Potential (Screened Coulomb)
    # V_yukawa = C * exp(-gamma * r) / r
    yukawa = 0.0
    if abs(params.C) > 1e-10:
        # gamma 通常也为正
        y_val = -params.gamma * r
        if y_val < -50: y_val = -50 # 截断过小的项
        yukawa = params.C * np.exp(y_val) / r
        
    return morse + yukawa