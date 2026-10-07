from __future__ import annotations

from typing import List, Tuple, Dict, Union, Optional
import numpy as np
from collections import deque
from functools import lru_cache
import scipy.ndimage as ndimage
from scipy.ndimage import map_coordinates

from pymatgen.core import Structure
from core.config import config

# =============================================================================
# PART A: 图论与拓扑工具 (Graph & Topology Utils)
# 用于 dimensionality.py 和 extract_layer.py
# =============================================================================

@lru_cache(maxsize=200)
def get_element_radius(element_symbol: str, prefer_vdw: bool = True) -> float:
    """
    Get atomic radius for an element (cached).

    Args:
        element_symbol: Element symbol (e.g., 'C', 'Si')
        prefer_vdw: If True, prefer van der Waals radius over atomic radius

    Returns:
        Radius in Angstroms
    """
    from pymatgen.core import Element

    try:
        elem = Element(element_symbol)

        if prefer_vdw:
            r = getattr(elem, 'van_der_waals_radius', None)
            if r: return float(r)
            r = getattr(elem, 'atomic_radius', None)
            if r: return float(r)
        else:
            r = getattr(elem, 'atomic_radius', None)
            if r: return float(r)
            r = getattr(elem, 'van_der_waals_radius', None)
            if r: return float(r)
    except Exception:
        pass

    return config.DEFAULT_ATOMIC_RADIUS

def get_site_element_symbol(site) -> str:
    """
    Get element symbol from site, handling disordered structures.

    For disordered sites (e.g., {Ti: 0.8, Zr: 0.2}), returns the
    most abundant element ('Ti' in this case).
    """
    if getattr(site, 'is_ordered', True):
        return site.specie.symbol
    else:
        # Disordered: find element with max occupancy
        dominant_el = max(site.species, key=site.species.get)
        return dominant_el.symbol

def get_site_radius(site, prefer_vdw: bool = True) -> float:
    """
    Get radius for a site, handling disordered structures.
    Uses cached element lookup for performance.
    """
    element_symbol = get_site_element_symbol(site)
    return get_element_radius(element_symbol, prefer_vdw=prefer_vdw)

def get_rvdw(site) -> float:
    """vdW radius first, atomic radius as fallback. (Legacy wrapper)"""
    return get_site_radius(site, prefer_vdw=True)


def build_periodic_bond_graph(structure: Structure, delta: float) -> List[List[Tuple[int, Tuple[int,int,int]]]]:
    """
    TURBO VERSION: Build periodic bond graph using vectorized neighbor finding.
    Edge if d_ij < rvdw_i + rvdw_j - delta.
    """
    n = len(structure)
    adj: List[List[Tuple[int, Tuple[int,int,int]]]] = [[] for _ in range(n)]

    max_r = max(get_rvdw(s) for s in structure.sites)
    r_cut = 2 * max_r - delta + 0.5

    # TURBO: Vectorized neighbor finding - single C++ call for all sites
    all_neighbors = structure.get_all_neighbors(r=r_cut, include_index=True)

    # Track seen bonds to avoid duplicates
    seen_bonds: set = set()

    for i, neighbors in enumerate(all_neighbors):
        ri = get_rvdw(structure.sites[i])

        for nb in neighbors:
            j = int(nb.index)
            if j == i: continue

            rj = get_rvdw(structure.sites[j])
            if float(getattr(nb, "nn_distance", nb.distance)) < (ri + rj - delta):
                img = tuple(int(x) for x in nb.image)

                # Create standardized bond key to avoid duplicates
                if i <= j:
                    bond_key = (i, j, img)
                else:
                    bond_key = (j, i, tuple(-x for x in img))

                if bond_key not in seen_bonds:
                    seen_bonds.add(bond_key)
                    adj[i].append((j, img))
                    adj[j].append((i, (-img[0], -img[1], -img[2])))

    return adj


def connected_components(adj: List[List[Tuple[int, Tuple[int,int,int]]]]) -> List[List[int]]:
    """
    TURBO VERSION: Find connected components using BFS with O(1) deque operations.
    SAFETY: Hard iteration limit to prevent infinite loops.
    """
    n = len(adj)
    seen = [False] * n
    comps = []

    # SAFETY: Maximum BFS iterations per component
    MAX_BFS_ITERATIONS = 1000000

    for i in range(n):
        if seen[i]: continue

        # TURBO: Use deque for O(1) popleft
        q = deque([i])
        seen[i] = True
        comp = []

        bfs_iterations = 0
        while q:
            bfs_iterations += 1

            # SAFETY: Hard memory lock
            if bfs_iterations > MAX_BFS_ITERATIONS:
                from loguru import logger
                logger.warning(f"BFS iteration limit reached ({MAX_BFS_ITERATIONS}) in connected_components")
                break

            # TURBO: O(1) popleft instead of O(N) pop(0)
            u = q.popleft()
            comp.append(u)

            for v, _ in adj[u]:
                if not seen[v]:
                    seen[v] = True
                    q.append(v)

        comps.append(comp)

    return comps


def translation_rank(adj: List[List[Tuple[int, Tuple[int,int,int]]]], comp: List[int]) -> int:
    """
    [通用] 计算指定连通分量的平移秩 (0D/1D/2D/3D)。
    """
    S = set(comp)
    vecs = []
    for u in comp:
        for v, img in adj[u]:
            if v in S and img != (0, 0, 0):
                vecs.append(img)
    if not vecs: return 0
    uniq = list({tuple(v) for v in vecs})
    return int(np.linalg.matrix_rank(np.array(uniq, dtype=float)))


def translation_rank_of_largest_component(adj: List[List[Tuple[int, Tuple[int,int,int]]]], comps: List[List[int]]) -> int:
    """Legacy wrapper for dimensionality.py."""
    if not comps: return 0
    largest = max(comps, key=len)
    return translation_rank(adj, largest)


# =============================================================================
# PART B: 晶体几何与投影工具 (Geometry & Projection Utils)
# 用于 planar_gap.py (原 cleavage_analysis.py 核心逻辑)
# =============================================================================

def calculate_max_bond_length(structure: Structure) -> float:
    """
    [方案三] 计算结构中的最大键长。

    方案三的优势：
    - 基于实际原子距离，更准确反映结构尺度
    - 能够覆盖所有可能的解理面
    - 避免因经验公式导致的有效平面遗漏

    计算方法：
    1. 找到结构中最大的原子半径
    2. 计算最大可能的键长（考虑周期性边界）
    3. 使用晶格向量和周期性邻居查找最大距离
    """
    # 方法1：使用周期性邻居查找最大原子间距
    # 获取最大原子半径
    max_radius = max(get_rvdw(site) for site in structure.sites)

    # 设置一个足够大的截断半径（覆盖整个晶胞）
    max_lattice_dist = max(structure.lattice.abc)
    r_cut = max_lattice_dist + 2 * max_radius

    max_dist = 0.0
    n = len(structure)

    # 对每个原子，检查其周期性邻居
    for i, site in enumerate(structure.sites):
        # 获取所有周期性邻居
        neighbors = structure.get_neighbors(site, r_cut)

        for nb in neighbors:
            if nb.index >= i:  # 避免重复计数
                dist = float(getattr(nb, "nn_distance", nb.distance))
                if dist > max_dist:
                    max_dist = dist

    # 方法2：如果上面结果太小，使用晶格对角线作为上限
    lattice_diagonal = np.sqrt(np.sum(structure.lattice.matrix.T @ structure.lattice.matrix))
    max_dist = max(max_dist, lattice_diagonal)

    return max_dist


def metric_tensor(lattice_params: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    a, b, c, alpha, beta, gamma = lattice_params
    rad = np.pi / 180.0
    MatAA = np.array([
        [a*a, a*b*np.cos(gamma*rad), a*c*np.cos(beta*rad)],
        [a*b*np.cos(gamma*rad), b*b, b*c*np.cos(alpha*rad)],
        [a*c*np.cos(beta*rad), b*c*np.cos(alpha*rad), c*c]
    ])
    return MatAA, np.linalg.inv(MatAA)


def create_hkl_list(structure: Structure, dmin: float) -> Tuple[List[List[int]], List[List[int]]]:
    """
    Generate HKL planes based on dmin.

    [方案三] 使用实际结构尺度（最大键长）计算 hklmax，确保覆盖所有可能的解理面。
    """
    lat = structure.lattice
    # 使用 Pymatgen 的 get_points_in_sphere_reciprocal 或手动计算，这里保留原逻辑的简化版
    # 既然有 Pymatgen，我们可以利用它的倒易晶格生成逻辑，但为了保持算法一致性，还是用原逻辑
    lattice_params = np.array(lat.abc + lat.angles)
    _, MatBB = metric_tensor(lattice_params)

    # [方案三] 使用实际结构尺度计算 hklmax
    # 优势：基于实际原子距离，更准确反映结构尺度，避免遗漏有效平面
    max_bond_length = calculate_max_bond_length(structure)
    # 对三个晶格方向都使用相同的最大值
    hklmax_scalar = int(np.round(max_bond_length / dmin)) + 1
    hklmax = (hklmax_scalar, hklmax_scalar, hklmax_scalar)

    # 更严谨的生成：遍历倒易空间球体
    # 这里为了代码简洁，直接用 Pymatgen 的工具生成可能的 HKL 会更稳健，但原算法的 MULDIN 需要互质 HKL
    # 下面是原算法的紧凑版：
    h_rng, k_rng, l_rng = [range(-m, m+1) for m in hklmax]

    candidates = []
    for h in h_rng:
        for k in k_rng:
            for l in l_rng:
                if h==0 and k==0 and l==0: continue
                if np.gcd.reduce([abs(h), abs(k), abs(l)]) != 1: continue # 仅保留互质面
                candidates.append([h,k,l])

    candidates = np.array(candidates)
    d_spacings = 1.0 / np.sqrt(np.sum(candidates * (candidates @ MatBB.T), axis=1))
    valid_hkl = candidates[d_spacings >= dmin]

    # 去重 (hkl 和 -h-k-l 视为同一面)
    seen = set()
    unique_hkl = []
    for hkl in valid_hkl:
        t = tuple(hkl)
        inv = tuple(-hkl)
        if t not in seen and inv not in seen:
            unique_hkl.append(hkl.tolist())
            seen.add(t)

    return unique_hkl, unique_hkl # 在 P1 假设下，Full 和 Unique 是一样的


def calculate_electron_density(
    structure: Structure,
    n_grid: Tuple[int, int, int],
    gaussian_sigma_scale: float = 0.5,
) -> Dict:
    """Calculate electron density grid."""
    n1, n2, n3 = n_grid
    density = np.zeros(n_grid)
    
    # 1. 映射原子到网格
    for site in structure:
        # Z * occupancy
        weight = site.specie.Z * 1.0 
        pos = site.frac_coords
        idx = (np.round(pos * np.array([n1,n2,n3])).astype(int)) % np.array([n1,n2,n3])
        density[idx[0], idx[1], idx[2]] += weight

    # 2. 高斯平滑
    lat = structure.lattice
    avg_len = sum(lat.abc) / 3.0
    avg_grid = sum(n_grid) / 3.0
    sigma = float(gaussian_sigma_scale) * (avg_grid / avg_len)
    
    sff = ndimage.gaussian_filter(density, sigma=sigma, mode='wrap')
    
    # 构造坐标网格用于插值
    x, y, z = [np.linspace(0, 1, n, endpoint=False) for n in n_grid]
    X, Y, Z = np.meshgrid(x, y, z, indexing='ij')
    
    return {'X': X, 'Y': Y, 'Z': Z, 'SFF': sff, 'MatAA': lat.metric_tensor}


def calculate_gap_metrics(z: np.ndarray, Gamma: np.ndarray, gap_level: float) -> Dict[str, float]:
    """Analyze 1D Gamma curve to find gaps."""
    if len(z) < 2: return {'width': 0.0, 'center': 0.0, 'score': 0.0, 'depth': 0.0}
    
    dz = z[1] - z[0]
    # 扩展两倍处理周期性边界
    z_ext = np.concatenate([z, z[-1] + dz + (z - z[0])])
    g_ext = np.concatenate([Gamma, Gamma])
    
    mean_g = np.mean(g_ext)
    if mean_g <= 1e-6: return {'width': 0.0, 'center': 0.0, 'score': 0.0, 'depth': 0.0}
    
    g_norm = g_ext / mean_g
    mask = g_norm < gap_level
    if not np.any(mask): return {'width': 0.0, 'center': 0.0, 'score': 0.0, 'depth': 0.0}
    
    # 找连续段
    zg = np.sort(z_ext[np.where(mask)[0]])
    breaks = np.where(np.diff(zg, prepend=zg[0]) > 2.1 * dz)[0] # Tolerance slightly > 2*dz
    
    best = {'width': 0.0, 'center': 0.0, 'score': 0.0, 'depth': 0.0}
    
    split_indices = list(breaks) + [len(zg)]
    s = 0
    for b in split_indices:
        seg = zg[s:b]
        s = b
        if len(seg) < 2: continue
        
        start, end = seg[0], seg[-1]
        width = end - start
        
        # 计算深度分数
        seg_mask = (z_ext >= start) & (z_ext <= end)
        depth = np.mean(np.maximum(0.0, gap_level - g_norm[seg_mask]))
        score = width * depth
        
        if score > best['score']:
            best = {
                'width': width,
                'center': ((start + end) / 2.0) % 1.0,
                'depth': depth,
                'score': score
            }
            
    return best


def get_planar_gap_candidates(
    structure: Structure,
    dmin: float = 1.8,
    gap_level: float = 0.75,
    n_grid: Tuple[int, int, int] = (32, 32, 32),
    d_smooth: float = 0.1,
    timeout_seconds: float = 90.0,  # SAFETY: Hard timeout
    gaussian_sigma_scale: float = 0.5,
) -> List[Dict]:
    """
    [高层入口] 计算所有可能的解理面及其 Gap 指标。
    替代原 cleavage_analysis.analyze_cleavage。

    TURBO + SAFETY 优化:
    - 严格超时检查 (默认 90 秒)
    - 最大 HKL 迭代限制
    - 早期终止条件
    """
    import time
    from loguru import logger

    start_time = time.time()

    # SAFETY: 最大 HKL 处理数量
    MAX_HKL_ITERATIONS = 200

    def check_timeout(step_name: str = ""):
        elapsed = time.time() - start_time
        if elapsed > timeout_seconds:
            raise TimeoutError(f"Geometric route timeout after {elapsed:.1f}s during: {step_name}")

    try:
        # 1. 准备数据
        check_timeout("HKL list generation")
        _, hkl_list = create_hkl_list(structure, dmin)

        # SAFETY: 限制 HKL 数量
        if len(hkl_list) > MAX_HKL_ITERATIONS:
            logger.warning(f"Geometric route: Limiting HKL from {len(hkl_list)} to {MAX_HKL_ITERATIONS}")
            hkl_list = hkl_list[:MAX_HKL_ITERATIONS]

        check_timeout("electron density calculation")
        grid = calculate_electron_density(
            structure, n_grid, gaussian_sigma_scale=gaussian_sigma_scale
        )

        results = []

        # 2. 遍历 HKL with timeout checks
        for idx, hkl in enumerate(hkl_list):
            # SAFETY: Check timeout every 10 iterations
            if idx % 10 == 0:
                check_timeout(f"HKL iteration {idx}/{len(hkl_list)}")

            hkl_arr = np.array(hkl)

            # --- MULDIN 变换 (内联以减少函数数) ---
            # 简化版 MULDIN: 找一个矩阵使得 hkl 变为 [0,0,1]
            # 这里用更通用的 numpy 方法：构建旋转矩阵
            # 为了兼容原算法的投影逻辑，我们需要该平面法向量对齐到 Z 轴
            # 使用简化的投影方法：

            # 步骤 A: 计算 MULDIN 矩阵 (原逻辑移植)
            # (由于代码较长且不依赖其他库，建议作为内部闭包或保留独立函数，这里为简洁省略 MULDIN 实现细节，
            #  如果你需要完整功能，请把之前的 muldin 函数贴在这里，或者用 pymatgen 的 slab generator 逻辑)

            # [注] 为确保代码能跑，这里必须有 muldin 实现。
            # 为节省篇幅，假设你把之前的 muldin 函数也放在 utils 里了。
            # 下面直接调用 _muldin_transform_logic (见下文补充)
            try:
                Gamma, z = _project_density_to_hkl(grid, hkl_arr)
            except Exception as e:
                # SAFETY: Skip problematic HKL instead of crashing
                logger.debug(f"Skipping HKL {hkl} due to projection error: {e}")
                continue

            # 步骤 B: 平滑与 Gap 分析
            # 简单的卷积平滑
            w = int(d_smooth / (z[1]-z[0]))
            if w > 1:
                kernel = np.ones(w) / w
                Gamma_smooth = ndimage.convolve(Gamma, kernel, mode='wrap')
            else:
                Gamma_smooth = Gamma

            metrics = calculate_gap_metrics(z, Gamma_smooth, gap_level)
            if metrics['score'] > 0:
                metrics['hkl'] = hkl
                results.append(metrics)

        # Final timeout check
        check_timeout("final sorting")
        results.sort(key=lambda x: x['score'], reverse=True)

        elapsed = time.time() - start_time
        logger.info(f"Geometric route: Processed {len(hkl_list)} HKL planes in {elapsed:.2f}s, found {len(results)} candidates")

        return results

    except TimeoutError as e:
        elapsed = time.time() - start_time
        logger.warning(f"Geometric route TIMEOUT: {str(e)}")
        # Return partial results if any
        if results:
            results.sort(key=lambda x: x['score'], reverse=True)
            logger.info(f"Returning {len(results)} partial results after timeout")
            return results
        return []
    except Exception as e:
        elapsed = time.time() - start_time
        logger.error(f"Geometric route ERROR after {elapsed:.2f}s: {str(e)}")
        return []

# --- Helper: MULDIN (私有，仅供 get_planar_gap_candidates 使用) ---
def _muldin(hkl):
    """(将之前的 muldin 函数逻辑粘贴于此)"""
    hkl = np.array(hkl).reshape(-1)
    N = 3
    S = np.diag(np.where(hkl >= 0, 1, -1))
    if np.linalg.det(S) < 0: S[:, [0, 1]] = S[:, [1, 0]]
    X = np.linalg.inv(S) @ hkl
    I = np.eye(N)
    
    # Iterative reduction
    for _ in range(100):
        nonzero = np.where(X > 1e-9)[0] # float safe
        if len(nonzero) <= 1: break
        m_idx = nonzero[np.argmin(X[nonzero])]
        T = I.copy()
        T[:, m_idx] = 0; T[nonzero, m_idx] = 1
        S = S @ T; X = np.linalg.inv(T) @ X
        
    # Final permutation if needed (ensure non-zero at end)
    if X[-1] == 0:
        nz = np.where(X!=0)[0]
        if len(nz) > 0:
            idx = nz[0]
            # swap col idx and -1
            P = I.copy(); P[:, [idx, -1]] = P[:, [-1, idx]]
            S = S @ P
            
    return S

def _project_density_to_hkl(grid, hkl):
    X, Y, Z, SFF = grid['X'], grid['Y'], grid['Z'], grid['SFF']
    A = _muldin(hkl)
    S_mat = np.linalg.inv(A).T
    
    # Coordinate transform
    Xp = S_mat[0,0]*X + S_mat[0,1]*Y + S_mat[0,2]*Z
    Yp = S_mat[1,0]*X + S_mat[1,1]*Y + S_mat[1,2]*Z
    Zp = S_mat[2,0]*X + S_mat[2,1]*Y + S_mat[2,2]*Z
    
    # Wrap
    Xp, Yp, Zp = Xp%1, Yp%1, Zp%1
    
    # Interpolate
    coords = np.stack([Xp, Yp, Zp], axis=0) * (np.array(SFF.shape)[:,None,None,None] - 1)
    SFF_new = map_coordinates(SFF, coords, order=1, mode='wrap')
    
    Gamma = np.mean(SFF_new, axis=(0,1))
    return Gamma, np.linspace(0, 1, len(Gamma))
