"""
MODULE: BONDDEL Algorithm (Physics-Aware & Robust Version)
==========================================================

Overview
--------
This module implements the **Bond Deletion (BONDDEL)** algorithm, a computational 
method for discovering 2D materials from 3D bulk crystal structures. It simulates 
the physical exfoliation process by systematically breaking atomic bonds based on 
their potential energy.

Physics Principle: The XCP Potential
------------------------------------
Instead of treating all bonds purely geometrically, this algorithm uses the 
**Extended Cross-Correlation Potential (XCP)** model to estimate bond strengths.
The energy V(r) is calculated as:
    V(r) = D * (1 - exp(alpha * (r0 - r)))^2  [Morse Term: Short-range chemical bond]
         + C * exp(-gamma * r) / r            [Repulsion Term: Long-range screening]

Key Optimizations (v2.0)
------------------------
1. Energy Level Clustering : 
   In real crystals, structural distortions can create many slightly different 
   bond lengths. We cluster similar energies (tolerance=0.05 eV) to reduce 
   iterations from 50+ to just 2-3 significant cuts.

2. Timeout Circuit Breaker:
   A hard timeout (default 60s) forces the algorithm to abort and move to the 
   next material, preventing batch job failures on complex 3D networks.

3. Self-Contained Topology Check:
   Includes a built-in Breadth-First Search (BFS) with Periodic Boundary Condition 
   (PBC) image vector accumulation to detect 0D/1D/2D/3D topology.
"""

from __future__ import annotations

from typing import Dict, List, Tuple, Any, Optional, Set
import numpy as np
import networkx as nx
import time
from dataclasses import dataclass, field
from collections import Counter, deque  # TURBO: Added deque for O(1) queue operations
from loguru import logger  # Import logger at module level

from pymatgen.core import Structure, PeriodicSite
from core.utils import get_site_element_symbol, get_site_radius
from core.config import config

# [Modified] 直接导入，移除 try-except 保护。
# 如果 tools.xcp_potential 不存在，程序将在此处直接崩溃 (ImportError)。
from tools.xcp_potential import UniversalPotential, XCPParameters, compute_xcp_energy

HAS_XCP_TOOL = True


# =============================================================================
# PART 2: Graph Building & Physics Calculation
# =============================================================================

def compute_bond_weights(
    structure: Structure,
    default_params: XCPParameters,
    cutoff_radius: Optional[float] = None,
    xcp_loader: Optional[Any] = None, # UniversalPotential instance
    timeout_checker: Optional[callable] = None  # Callback for timeout checks
) -> List[Dict[str, Any]]:
    """
    TURBO VERSION: Computes all bonds using vectorized neighbor finding.
    Uses structure.get_all_neighbors() for C++ acceleration.
    """
    bonds = []

    # Auto-determine cutoff if not provided (based on max vdw radius)
    if cutoff_radius is None:
        max_r = max([get_site_radius(s, prefer_vdw=True) for s in structure.sites]) if structure.sites else 2.0
        cutoff_radius = 2.0 * max_r + 1.0 # Safety margin

    # Check timeout before heavy computation
    if timeout_checker:
        timeout_checker("compute_bond_weights start")

    # TURBO: Vectorized neighbor finding - single C++ call for all sites
    # This returns a list of lists: all_neighbors[i] = neighbors of site i
    all_neighbors = structure.get_all_neighbors(r=cutoff_radius, include_index=True)

    seen_bonds: Set[Tuple[int, int, int, int, int]] = set()

    # Iterate through the vectorized result
    for i, neighbors in enumerate(all_neighbors):
        # Check timeout every 50 sites
        if timeout_checker and i % 50 == 0:
            timeout_checker(f"compute_bond_weights site {i}/{len(structure.sites)}")

        elem_i = get_site_element_symbol(structure.sites[i])

        for neighbor in neighbors:
            j = int(neighbor.index)
            # Avoid self-loops for same atom index (unless it's a periodic image)
            if i == j and neighbor.nn_distance < 0.1:
                continue

            # Standardize edge key to avoid duplicates (undirected graph logic)
            image = tuple(int(x) for x in neighbor.image)

            if i <= j:
                u, v = i, j
                img = image
            else:
                u, v = j, i
                img = tuple(-x for x in image)

            bond_key = (u, v, img[0], img[1], img[2])
            if bond_key in seen_bonds:
                continue
            seen_bonds.add(bond_key)

            distance = float(neighbor.nn_distance)
            elem_j = get_site_element_symbol(structure.sites[j])

            # --- PHYSICS CORE: Determine Parameters ---
            current_params = default_params
            if xcp_loader is not None:
                current_params = xcp_loader.get_params(elem_i, elem_j)

            # Calculate Energy
            energy = compute_xcp_energy(distance, current_params)

            bonds.append({
                'u': u, 'v': v,
                'element_i': elem_i, 'element_j': elem_j,
                'distance': distance,
                'energy': energy,
                'image': img
            })

    return bonds

# =============================================================================
# PART 3: Topology Check (The "Brain")
# =============================================================================

def check_dimensionality_bfs(
    graph: nx.MultiGraph,
    total_atoms: int,
    timeout_checker: Optional[callable] = None
) -> Dict[str, Any]:
    """
    TURBO VERSION: Uses collections.deque for O(1) queue operations.
    Self-contained dimensionality check using BFS and PBC image tracking.
    Returns clusters and their dimensions (0D, 1D, 2D, 3D).
    """
    visited = set()
    clusters = []
    has_2d = False
    total_bfs_iters = 0

    # Iterate through all nodes to find connected components
    for start_node in range(total_atoms):
        # Check timeout every 100 nodes
        if timeout_checker and start_node % 100 == 0:
            timeout_checker(f"check_dimensionality_bfs node {start_node}/{total_atoms}")

        if start_node in visited: continue
        if start_node not in graph: continue # Node might be isolated (0 bonds)

        # Start BFS for this component
        component_nodes = set()
        pbc_images = set()
        pbc_images.add((0,0,0))

        # TURBO: Use deque for O(1) popleft instead of list with O(N) pop(0)
        queue = deque([(start_node, (0, 0, 0))])  # (node_idx, current_cumulative_image)
        visited.add(start_node)
        component_nodes.add(start_node)

        # Optimization: Local visited set for BFS state to avoid cycles
        bfs_visited = set()
        bfs_visited.add((start_node, (0, 0, 0)))

        bfs_iterations = 0
        # 设置 BFS 迭代硬上限，防止内存溢出
        MAX_BFS_ITERATIONS = 600000

        bfs_iterations = 0
        while queue:
            # Check timeout every 100 BFS iterations
            bfs_iterations += 1
            total_bfs_iters += 1

            # ==========================================
            # 内存保护硬开关
            # ==========================================
            if bfs_iterations > MAX_BFS_ITERATIONS:
                if timeout_checker:
                    # 这里传一个特殊信息给日志，不用真报错，只是记录
                    timeout_checker(f"⚠️ 触发硬上限 ({MAX_BFS_ITERATIONS}次), 强制判定为3D")
                
                # 既然已经漫延了这么远，它肯定是无限延伸的三维网络。
                # 塞入三个线性无关的向量，确保后面的 rank 计算结果一定为 3 (3D)。
                pbc_images.add((999, 0, 0))
                pbc_images.add((0, 999, 0))
                pbc_images.add((0, 0, 999))
                break # 彻底跳出 while 循环，释放内存
            # ==========================================

            if timeout_checker and bfs_iterations % 100 == 0:
                timeout_checker(f"BFS iteration {bfs_iterations}")

            # TURBO: O(1) popleft instead of O(N) pop(0)
            curr, curr_img = queue.popleft()

            # Check neighbors
            for _, neighbor, data in graph.edges(curr, data=True):
                # Edge image points from curr -> neighbor
                edge_img = data.get('image', (0,0,0))

                # Calculate absolute position of neighbor in unfolded space
                next_img = (
                    curr_img[0] + edge_img[0],
                    curr_img[1] + edge_img[1],
                    curr_img[2] + edge_img[2]
                )

                if neighbor not in component_nodes:
                    visited.add(neighbor)
                    component_nodes.add(neighbor)

                state = (neighbor, next_img)
                if state not in bfs_visited:
                    bfs_visited.add(state)
                    pbc_images.add(next_img)
                    queue.append(state)

                    # Optimization: Limit BFS depth if component is huge
                    if len(pbc_images) > 150: 
                        break # 注意：这里的 break 只能跳出 for 循环，这就是为什么你需要上面那个 while 级的硬上限！

        # Analyze dimensionality from pbc_images
        if len(pbc_images) > 1:
            img_matrix = np.array(list(pbc_images))
            # Center the images to remove origin offset
            img_matrix = img_matrix - img_matrix[0]
            # Calculate rank
            rank = np.linalg.matrix_rank(img_matrix)
        else:
            rank = 0

        dim_str = f"{rank}D"
        if rank == 2: has_2d = True

        clusters.append({
            'atoms': list(component_nodes),
            'dimensionality': dim_str,
            'size': len(component_nodes)
        })

    return {'clusters': clusters, 'has_2d': has_2d, 'total_bfs_iters': total_bfs_iters}

# =============================================================================
# PART 4: Main Algorithm Class
# =============================================================================

@dataclass
class BondDelResult:
    success: bool
    final_clusters: List[Set[int]]
    deleted_bonds: List[Dict[str, Any]]
    steps_taken: int
    message: str = ""

class BondDelAlgorithm:
    def __init__(
        self,
        structure: Structure,
        universal_potential: Optional[Any] = None, # The UniversalPotential object
        timeout_seconds: int = 60,
        max_atoms: int = 600  # Fail-fast limit
    ):
        self.structure = structure
        self.xcp_loader = universal_potential
        self.default_params = XCPParameters(
            D=2.0,
            alpha=1.5,
            r0=2.5,
            C=0.0,
            gamma=1.0
        )

        self.timeout_seconds = timeout_seconds
        self.max_atoms = max_atoms
        self.graph = None
        self.bonds = []
        self.start_time = 0

    def _check_timeout(self, step_name: str = "") -> None:
        """
        Internal timeout check. Raises TimeoutError if exceeded.
        Call this frequently inside heavy loops.
        """
        elapsed = time.time() - self.start_time
        if elapsed > self.timeout_seconds:
            raise TimeoutError(
                f"BONDDEL timeout after {elapsed:.1f}s during: {step_name}"
            )

    def _cluster_energies(self, tolerance: float = 0.05) -> List[float]:
        """
        Groups similar bond energies to avoid redundant steps.
        Returns a sorted list of energy thresholds (weakest to strongest).
        """
        if not self.bonds: return []
        
        # Filter: We only care about 'cutting' bonds.
        # XCP energy: negative = attraction, positive = repulsion.
        # We typically cut from closest to 0 (weakest attraction) down to deep negative (strong).
        # Or, if we strictly follow the paper, we cut bonds where V > E_cut.
        # Let's sort all bond energies.
        energies = sorted([b['energy'] for b in self.bonds], reverse=True) # Max (weakest/repulsive) first
        
        clustered = []
        if not energies: return []
        
        curr = energies[0]
        clustered.append(curr)
        
        for e in energies[1:]:
            # If difference is significant, add new level
            if abs(e - curr) > tolerance:
                clustered.append(e)
                curr = e
                
        return clustered

    def run(self, verbose: bool = False) -> BondDelResult:
        """
        Run the BONDDEL algorithm with internal timeout checks and fail-fast constraints.
        """
        self.start_time = time.time()

        try:
            # FAIL-FAST: Check structure size
            n_atoms = len(self.structure)
            if n_atoms > self.max_atoms:
                msg = (
                    f"Structure too large ({n_atoms} atoms > {self.max_atoms} limit). "
                    f"Skipping BONDDEL to prevent timeout."
                )
                if verbose:
                    print(msg)
                logger.warning(f"BONDDEL skipped: {msg}")
                return BondDelResult(
                    success=False,
                    final_clusters=[],
                    deleted_bonds=[],
                    steps_taken=0,
                    message=f"SKIPPED: Too many atoms ({n_atoms} > {self.max_atoms})"
                )

            if verbose:
                print(f"BONDDEL: Processing structure with {n_atoms} atoms")

            # 1. Build Graph
            # 如果 compute_bond_weights 内部出错（如 XCP 参数问题），直接抛出异常
            self.bonds = compute_bond_weights(
                self.structure,
                self.default_params,
                xcp_loader=self.xcp_loader,
                timeout_checker=self._check_timeout
            )

            # Check timeout after bond computation
            self._check_timeout("after compute_bond_weights")

            # TURBO: Batch graph construction
            # Initial Graph (Full)
            self.graph = nx.MultiGraph()

            # TURBO: Add all nodes at once (already optimized)
            self.graph.add_nodes_from(range(len(self.structure)))

            # TURBO: Build edge list for batch addition
            # Format: list of (u, v, key, {attributes})
            edge_list = [
                (b['u'], b['v'], i, {'energy': b['energy'], 'image': b['image']})
                for i, b in enumerate(self.bonds)
            ]

            # Check timeout before batch edge addition
            self._check_timeout(f"before adding {len(edge_list)} edges")

            # TURBO: Add all edges at once - much faster than loop
            self.graph.add_edges_from(edge_list)

            # Check timeout after graph building
            self._check_timeout("after building graph")

            # 2. Get Energy Levels (Clusters)
            # We scan from high energy (weak/unstable) down to low energy (strong).
            # We look for a gap where the structure becomes 2D.
            energy_levels = self._cluster_energies(
                tolerance=config.ENERGY_CLUSTER_TOLERANCE_EV
            )  # 30 meV tolerance

            # Filter levels: We generally only cut bonds that are "weak".
            # If energy is deeply negative (e.g. -5 eV), cutting it is unrealistic physics-wise
            # unless we are melting the crystal.
            # Heuristic: Only scan energies > -2.0 eV (adjustable).
            energy_levels = [
                e for e in energy_levels
                if e > config.ENERGY_CUTOFF_THRESHOLD_EV
            ]

            if verbose:
                print(f"BONDDEL: Found {len(energy_levels)} energy levels to scan.")

            # 3. Iterative Cutting
            initial_edges = self.graph.number_of_edges()

            for step, e_cut in enumerate(energy_levels):
                # Check Timeout
                self._check_timeout(f"energy level {step}/{len(energy_levels)}")

                # Cut Condition: Remove bonds strictly weaker (higher energy) than e_cut
                # Or, following the logic: We simulate an exfoliation energy.
                # Any bond with Binding Energy < E_exfoliation breaks.
                # Here, e_cut acts as the threshold.

                # Identify edges to remove
                # We remove edges where energy >= e_cut (assuming e_cut is decreasing)
                # Actually, standard BONDDEL removes weakest first.
                # e_cut is the current energy level we are "testing" to break.

                edges_to_remove = []
                edge_count = 0
                for u, v, k, data in list(self.graph.edges(data=True, keys=True)):
                    # Check timeout every 1000 edges
                    edge_count += 1
                    if edge_count % 1000 == 0:
                        self._check_timeout(f"checking edge {edge_count} for removal")

                    # If bond energy is higher (more positive/closer to zero) than current level
                    # it means it's weaker than the current "strength test".
                    if data['energy'] >= e_cut:
                        edges_to_remove.append((u, v, k))

                if not edges_to_remove: continue

                # Apply Cut
                self.graph.remove_edges_from(edges_to_remove)

                # If nothing changed from previous step (due to clustering), skip check
                if self.graph.number_of_edges() == initial_edges:
                    continue
                initial_edges = self.graph.number_of_edges()

                # 4. Topology Check
                topo = check_dimensionality_bfs(
                    self.graph,
                    len(self.structure),
                    timeout_checker=self._check_timeout
                )

                iters = topo.get('total_bfs_iters', 0)

                if topo['has_2d']:
                    # Found it!
                    # Extract the 2D clusters
                    clusters_2d = [set(c['atoms']) for c in topo['clusters'] if c['dimensionality'] == '2D']

                    logger.info(f"🎉 2D layer found in {iters} BFS iterations at cut {e_cut:.3f} eV")

                    return BondDelResult(
                        success=True,
                        final_clusters=clusters_2d,
                        deleted_bonds=[{'energy_threshold': e_cut}],
                        steps_taken=step,
                        message=f"Success: 2D Found at cut {e_cut:.3f} eV (BFS iters: {iters})"
                    )

                # Stop condition: If everything is 0D (gas), we went too far
                is_all_0d = all(c['dimensionality'] == '0D' for c in topo['clusters'])
                if is_all_0d:
                    logger.info(f"Structure disintegrated to 0D in {iters} BFS iterations at cut {e_cut:.3f} eV")
                    return BondDelResult(
                        success=False,
                        final_clusters=[],
                        deleted_bonds=[],
                        steps_taken=step,
                        message=f"Failed: Structure disintegrated to 0D (BFS iters: {iters})"
                    )

            return BondDelResult(
                success=False,
                final_clusters=[],
                deleted_bonds=[],
                steps_taken=len(energy_levels),
                message="Failed: No 2D layers found after all cuts"
            )

        except TimeoutError as e:
            # Graceful timeout handling
            elapsed = time.time() - self.start_time
            msg = f"TIMEOUT after {elapsed:.1f}s: {str(e)}"
            if verbose:
                print(msg)
            logger.warning(f"BONDDEL timeout: {msg}")
            return BondDelResult(
                success=False,
                final_clusters=[],
                deleted_bonds=[],
                steps_taken=0,
                message=msg
            )

        except Exception as e:
            # Catch any other errors gracefully
            elapsed = time.time() - self.start_time
            msg = f"ERROR after {elapsed:.1f}s: {type(e).__name__}: {str(e)}"
            if verbose:
                print(msg)
            logger.error(f"BONDDEL error: {msg}")
            logger.debug("BONDDEL stack trace:", exc_info=True)
            return BondDelResult(
                success=False,
                final_clusters=[],
                deleted_bonds=[],
                steps_taken=0,
                message=msg
            )