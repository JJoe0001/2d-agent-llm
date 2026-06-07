from __future__ import annotations

import logging
from typing import Dict, Any, List, Optional, Tuple, Set
import numpy as np
from scipy.spatial import cKDTree
from pymatgen.core import Structure, Element
from pymatgen.analysis.local_env import CrystalNN

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 项目内部导入
from core.store import get_structure, new_structure_id, store_structure
from core.utils import get_site_element_symbol, get_element_radius


# =============================================================================
# OPTIMIZATION 1: Cached Element Objects
# =============================================================================
_ELEMENT_CACHE: Dict[str, Element] = {}

def get_cached_element(symbol: str) -> Element:
    """Get Element object with caching to avoid repeated instantiation."""
    if symbol not in _ELEMENT_CACHE:
        _ELEMENT_CACHE[symbol] = Element(symbol)
    return _ELEMENT_CACHE[symbol]


# =============================================================================
# OPTIMIZATION 2: Vectorized Topology Analysis
# =============================================================================
class TopologyCache:
    """
    Cache for topology information computed once for the entire structure.
    Replaces O(N) calls to CrystalNN.get_cn() and get_nn_info().
    """
    
    def __init__(self, structure: Structure):
        self.structure = structure
        self.crystal_nn = CrystalNN()
        
        # Compute all neighbor info ONCE
        logger.debug("Computing topology for all sites (one-time cost)...")
        self.all_nn_info = self.crystal_nn.get_all_nn_info(structure)
        
        # Precompute coordination numbers
        self.coordination_numbers = np.array([len(nn_list) for nn_list in self.all_nn_info])
        
        logger.debug(f"Topology computed: {len(structure)} sites, avg CN={self.coordination_numbers.mean():.2f}")
    
    def get_cn(self, site_index: int) -> int:
        """Get coordination number (O(1) lookup)."""
        return self.coordination_numbers[site_index]
    
    def get_nn_info(self, site_index: int) -> List[Dict]:
        """Get neighbor info (O(1) lookup)."""
        return self.all_nn_info[site_index]


# =============================================================================
# OPTIMIZATION 3: KD-Tree Based Collision Detection
# =============================================================================
# CRITICAL FIX: Reduced minimum safe distance to prevent false positives
MIN_SAFE_DISTANCE = 0.65  # Angstroms - prevents "atoms too close" errors

class CollisionDetector:
    """
    Fast collision detection using KD-tree spatial indexing.
    Replaces O(N) loop-based collision checks with O(log N) queries.
    """

    def __init__(self, structure: Structure, min_dist: float = MIN_SAFE_DISTANCE):
        self.structure = structure
        self.min_dist = min_dist
        self.lattice = structure.lattice

        # Build KD-tree for fast spatial queries
        self._rebuild_tree()
    
    def _rebuild_tree(self):
        """Build KD-tree from current structure coordinates."""
        if len(self.structure) == 0:
            self.tree = None
            return
        
        # Get fractional coordinates and build tree
        # Note: For PBC, we need to handle periodic images
        self.frac_coords = self.structure.frac_coords
        self.cart_coords = self.structure.cart_coords
        self.tree = cKDTree(self.cart_coords)
    
    def is_position_safe(self, coords: np.ndarray) -> bool:
        """
        Check if position is safe (no collision) using KD-tree.
        
        Args:
            coords: Cartesian coordinates to check
            
        Returns:
            True if safe, False if collision detected
        """
        if self.tree is None:
            return True
        
        # Query KD-tree for neighbors within min_dist
        # Note: This doesn't handle PBC perfectly, but is much faster
        # For rigorous PBC handling, use get_sites_in_sphere as fallback
        indices = self.tree.query_ball_point(coords, self.min_dist)
        
        if len(indices) == 0:
            return True
        
        # Double-check with PBC-aware distance calculation
        for idx in indices:
            dist = self.lattice.get_distance_and_image(
                self.structure.sites[idx].coords, coords
            )[0]
            if dist < self.min_dist:
                return False
        
        return True
    
    def add_site(self, coords: np.ndarray):
        """Update tree after adding a new site."""
        # For simplicity, rebuild tree (still faster than O(N) loops)
        # In production, could use incremental updates
        self._rebuild_tree()


# =============================================================================
# OPTIMIZATION 4: Vectorized Bond Vector Calculation
# =============================================================================
def compute_missing_bond_vector_vectorized(
    structure: Structure,
    site_index: int,
    nn_info: List[Dict]
) -> Optional[np.ndarray]:
    """
    Compute missing bond vector using vectorized numpy operations.
    
    Args:
        structure: Crystal structure
        site_index: Index of the site
        nn_info: Pre-computed neighbor information
        
    Returns:
        Unit vector pointing towards missing bond, or None
    """
    if not nn_info:
        return None
    
    site = structure.sites[site_index]
    element_symbol = get_site_element_symbol(site)
    
    # Guardrail: Inert surface recognition (e.g., MoS2 surface S)
    if element_symbol in {"S", "Se", "Te"} and len(nn_info) == 3:
        logger.debug(f"Chemically satisfied site {site_index} (Type: {element_symbol}, CN=3), skipping")
        return None
    
    # Extract neighbor indices and images
    neighbor_indices = np.array([nn["site_index"] for nn in nn_info], dtype=int)
    
    # Vectorized bond vector calculation
    bond_vectors = []
    for nn in nn_info:
        j = nn["site_index"]
        # Use pymatgen's PBC-aware distance calculation
        d, image = structure.lattice.get_distance_and_image(
            site.coords, structure.sites[j].coords
        )
        
        neighbor_cart = structure.sites[j].coords + np.dot(image, structure.lattice.matrix)
        vec = neighbor_cart - site.coords
        
        norm = np.linalg.norm(vec)
        if norm > 1e-3:
            bond_vectors.append(vec / norm)
    
    if not bond_vectors:
        return None
    
    # Vectorized sum and normalization
    bond_vectors_array = np.array(bond_vectors)
    sum_bonds = np.sum(bond_vectors_array, axis=0)
    norm_sum = np.linalg.norm(sum_bonds)
    
    if norm_sum < 1e-3:
        return None
    
    return -sum_bonds / norm_sum


# =============================================================================
# PERFORMANCE FIX: Distance-based Heuristic Passivation (bypasses CrystalNN)
# =============================================================================
def passivate_heuristic(structure: Structure, passivant: str = "H", cutoff: float = 2.5) -> Structure:
    """
    Fast heuristic passivation using simple distance-based coordination detection.

    CRITICAL PERFORMANCE FIX: Bypasses CrystalNN completely to avoid:
    - UserWarning spam about oxidation states
    - Voronoi tessellation failures on 2D vacuum boundaries
    - 100x+ slowdown on high-throughput screening

    Args:
        structure: Input structure
        passivant: Passivating element (default: H)
        cutoff: Distance cutoff for neighbor detection (Angstroms)

    Returns:
        Passivated structure
    """
    passivant_el = get_cached_element(passivant)
    passivated = structure.copy()

    # Initialize collision detector with safe distance
    collision_detector = CollisionDetector(passivated, min_dist=MIN_SAFE_DISTANCE)

    added_count = 0
    skipped_count = 0

    # Simple distance-based coordination detection
    for i, site in enumerate(structure.sites):
        element_symbol = get_site_element_symbol(site)

        # Get neighbors within cutoff using fast pymatgen method
        neighbors = structure.get_neighbors(site, cutoff, include_index=True)
        cn = len(neighbors)

        # Determine expected coordination based on element type
        expected_cn = 4  # Default for most elements
        if element_symbol in {"C", "N", "B"}:
            expected_cn = 3
        elif element_symbol in {"O", "S", "Se", "Te"}:
            expected_cn = 2

        # Skip if fully coordinated
        if cn >= expected_cn:
            continue

        # Calculate missing bond vector
        if not neighbors:
            # No neighbors - skip this site
            continue

        # Vectorized bond vector calculation
        bond_vectors = []
        for neighbor in neighbors:
            vec = neighbor.coords - site.coords
            norm = np.linalg.norm(vec)
            if norm > 1e-3:
                bond_vectors.append(vec / norm)

        if not bond_vectors:
            continue

        # Average direction of existing bonds
        avg_bond = np.mean(bond_vectors, axis=0)
        norm_avg = np.linalg.norm(avg_bond)

        if norm_avg < 1e-3:
            # Bonds cancel out - use perpendicular direction
            missing_vec = np.array([0.0, 0.0, 1.0])
        else:
            # Point opposite to average bond direction
            missing_vec = -avg_bond / norm_avg

        # Calculate target position
        r1 = get_element_radius(element_symbol, prefer_vdw=False)
        r2 = get_element_radius(passivant_el.symbol, prefer_vdw=False)
        target_bond_length = (r1 + r2) * 1.15

        target_pos = site.coords + missing_vec * target_bond_length

        # CRITICAL: Collision check with MIN_SAFE_DISTANCE
        if collision_detector.is_position_safe(target_pos):
            passivated.append(passivant, target_pos, coords_are_cartesian=True)
            collision_detector.add_site(target_pos)
            added_count += 1
            logger.debug(f"Added {passivant} to site {i} (CN={cn}/{expected_cn})")
        else:
            skipped_count += 1
            logger.debug(f"Skipped adding {passivant} to site {i} to prevent clash")

    logger.info(f"Heuristic passivation: added {added_count} atoms, skipped {skipped_count} due to collisions")
    return passivated


# =============================================================================
# Main Passivation Functions (Optimized)
# =============================================================================

class PassivatorFactory:
    """
    Factory class for surface passivation of 2D materials.
    Dispatches to the appropriate passivation method based on material type.
    """

    @staticmethod
    def passivate(structure: Structure, method: str = "auto", **kwargs) -> Structure:
        """
        Main entry point for surface passivation.

        CRITICAL PERFORMANCE FIX: "auto" mode now uses fast heuristic method
        instead of CrystalNN-based topology analysis to avoid:
        - UserWarning spam about oxidation states
        - Voronoi tessellation failures on 2D materials
        - 100x+ performance degradation in batch processing
        """
        if not isinstance(structure, Structure):
            raise TypeError("Input must be a pymatgen Structure object.")

        # PERFORMANCE FIX: Default to heuristic method for batch processing
        if method == "auto":
            logger.info("Using fast heuristic passivation (bypasses CrystalNN)")
            passivant = kwargs.get("passivant", "H")
            cutoff = kwargs.get("cutoff", 2.5)
            result = passivate_heuristic(structure, passivant=passivant, cutoff=cutoff)
        elif method == "heuristic":
            passivant = kwargs.get("passivant", "H")
            cutoff = kwargs.get("cutoff", 2.5)
            result = passivate_heuristic(structure, passivant=passivant, cutoff=cutoff)
        elif method == "covalent":
            passivant = kwargs.get("passivant", "H")
            result = passivate_covalent_surface(structure, passivant=passivant)
        elif method == "compound":
            cation_passivant = kwargs.get("cation_passivant", "F")
            anion_passivant = kwargs.get("anion_passivant", "H")
            result = passivate_compound_semiconductor(
                structure,
                cation_passivant=cation_passivant,
                anion_passivant=anion_passivant
            )
        elif method == "polar":
            result = passivate_polar_surface(structure)
        elif method == "crystalnn":
            # CrystalNN-based method available only if explicitly requested
            logger.warning("CrystalNN method is slow for 2D materials - consider using 'auto' or 'heuristic'")
            method_type = PassivatorFactory._detect_material_type(structure)
            if method_type == "covalent":
                result = passivate_covalent_surface(structure, **kwargs)
            elif method_type == "compound":
                result = passivate_compound_semiconductor(structure, **kwargs)
            elif method_type == "polar":
                result = passivate_polar_surface(structure)
            else:
                result = passivate_covalent_surface(structure, **kwargs)
        else:
            raise ValueError(f"Unknown passivation method: {method}")

        # Verify structure integrity
        if not verify_structure_integrity(result):
            logger.error("Passivated structure FAILED integrity check (atoms too close).")

        return result

    @staticmethod
    def _detect_material_type(structure: Structure) -> str:
        """
        Auto-detect material type based on composition and bonding.
        """
        comp = structure.composition
        elements = [str(el) for el in comp.elements]

        # Check for group IV materials
        group_iv = {"C", "Si", "Ge", "Sn", "Pb"}
        if len(comp.elements) == 1 and any(el in group_iv for el in elements):
            return "covalent"

        # Check for polar materials (e.g., oxides)
        if "O" in elements and len(comp.elements) > 1:
            return "polar"

        # Check for compound semiconductors (III-V, II-VI, etc.)
        if len(comp.elements) == 2:
            return "compound"

        # Default to covalent if unknown
        return "covalent"


def passivate_covalent_surface(structure: Structure, passivant: str = "H") -> Structure:
    """
    Passivate covalent surfaces with optimized topology analysis.
    
    OPTIMIZATIONS:
    - Single topology computation using TopologyCache
    - KD-tree based collision detection
    - Cached Element objects
    """
    passivant_el = get_cached_element(passivant)
    
    # OPTIMIZATION: Compute topology once for entire structure
    topo_cache = TopologyCache(structure)
    
    # Detect 2D carbon structures
    is_2d_carbon = False
    if "C" in [str(e) for e in structure.composition.elements]:
        cart_coords = structure.cart_coords
        z_span = np.max(cart_coords[:, 2]) - np.min(cart_coords[:, 2])
        if z_span < 2.0:
            is_2d_carbon = True

    # Find under-coordinated sites using cached topology
    under_coordinated = []
    for i, site in enumerate(structure.sites):
        cn = topo_cache.get_cn(i)
        element_symbol = get_site_element_symbol(site)

        bulk_cn = 4
        if element_symbol == "C" and is_2d_carbon:
            bulk_cn = 3
        elif element_symbol not in {"Si", "Ge", "C"}:
            bulk_cn = 3

        if cn < bulk_cn:
            under_coordinated.append(i)

    logger.info(f"Found {len(under_coordinated)} under-coordinated sites")

    passivated = structure.copy()

    # OPTIMIZATION: Initialize collision detector with safe minimum distance
    collision_detector = CollisionDetector(passivated, min_dist=MIN_SAFE_DISTANCE)

    added_count = 0
    for idx in under_coordinated:
        site = structure.sites[idx]
        element_symbol = get_site_element_symbol(site)

        # Use cached neighbor info
        nn_info = topo_cache.get_nn_info(idx)
        missing_vec = compute_missing_bond_vector_vectorized(structure, idx, nn_info)
        
        if missing_vec is None:
            continue

        # Calculate target position
        r1 = get_element_radius(element_symbol, prefer_vdw=False)
        r2 = get_element_radius(passivant_el.symbol, prefer_vdw=False)
        target_bond_length = (r1 + r2)* 1.15
        
        target_pos = site.coords + missing_vec * target_bond_length

        # OPTIMIZATION: Fast collision check using KD-tree
        if collision_detector.is_position_safe(target_pos):
            passivated.append(passivant, target_pos, coords_are_cartesian=True)
            collision_detector.add_site(target_pos)  # Update tree
            added_count += 1
            logger.debug(f"Added {passivant} to site {idx}")
        else:
            logger.warning(f"Position clash detected for {passivant} at site {idx}, skipping")

    logger.info(f"Added {added_count} passivating atoms")
    return passivated


def passivate_compound_semiconductor(
    structure: Structure,
    cation_passivant: str = "F",
    anion_passivant: str = "H"
) -> Structure:
    """
    Passivate compound semiconductor surfaces with optimized topology analysis.
    """
    comp = structure.composition
    elements = list(comp.elements)
    elecs = [el.X for el in elements]
    avg_elec = np.mean(elecs)
    cations = {el for el in elements if el.X < avg_elec}

    # OPTIMIZATION: Compute topology once
    topo_cache = TopologyCache(structure)

    passivated = structure.copy()
    collision_detector = CollisionDetector(passivated, min_dist=MIN_SAFE_DISTANCE)

    added_count = 0
    for i, site in enumerate(structure.sites):
        cn = topo_cache.get_cn(i)
        if cn >= 4:
            continue

        element_symbol = get_site_element_symbol(site)
        if hasattr(site, 'is_ordered') and site.is_ordered:
            element_obj = site.specie
        else:
            element_obj = max(site.species, key=site.species.get)

        if element_obj in cations:
            p_el = get_cached_element(cation_passivant)
        else:
            p_el = get_cached_element(anion_passivant)

        nn_info = topo_cache.get_nn_info(i)
        missing_vec = compute_missing_bond_vector_vectorized(structure, i, nn_info)
        
        if missing_vec is None:
            continue

        r1 = get_element_radius(element_symbol, prefer_vdw=False)
        r2 = get_element_radius(p_el.symbol, prefer_vdw=False)
        target_bond_length = (r1 + r2) * 1.15
        
        target_pos = site.coords + missing_vec * target_bond_length

        if collision_detector.is_position_safe(target_pos):
            passivated.append(p_el.symbol, target_pos, coords_are_cartesian=True)
            collision_detector.add_site(target_pos)
            added_count += 1
            logger.debug(f"Added {p_el.symbol} to site {i}")
        else:
            logger.warning(f"Position clash detected for {p_el.symbol} at site {i}, skipping")

    logger.info(f"Added {added_count} passivating atoms")
    return passivated


def passivate_polar_surface(structure: Structure) -> Structure:
    """
    Passivate polar surfaces using hydroxylation with optimized topology analysis.
    """
    # OPTIMIZATION: Compute topology once
    topo_cache = TopologyCache(structure)

    passivated = structure.copy()
    collision_detector = CollisionDetector(passivated, min_dist=MIN_SAFE_DISTANCE)

    added_count = 0
    for i, site in enumerate(structure.sites):
        cn = topo_cache.get_cn(i)
        element_symbol = get_site_element_symbol(site)

        is_anion = element_symbol in {"O", "S", "Se"}
        bulk_cn = 6 if is_anion else 4

        if cn >= bulk_cn:
            continue

        nn_info = topo_cache.get_nn_info(i)
        missing_vec = compute_missing_bond_vector_vectorized(structure, i, nn_info)
        
        if missing_vec is None:
            continue

        if is_anion:
            # Case: Anion -> Add H
            passivant = get_cached_element("H")
            r1 = get_element_radius(element_symbol, prefer_vdw=False)
            r2 = get_element_radius(passivant.symbol, prefer_vdw=False)
            target_len = (r1 + r2) * 1.15
            
            target_pos = site.coords + missing_vec * target_len

            if collision_detector.is_position_safe(target_pos):
                passivated.append("H", target_pos, coords_are_cartesian=True)
                collision_detector.add_site(target_pos)
                added_count += 1
                logger.debug(f"Added H to O/S site {i}")
            else:
                logger.warning(f"Position clash detected for H at site {i}, skipping")
        else:
            # Case: Cation -> Add OH
            o_el = get_cached_element("O")
            r1 = get_element_radius(element_symbol, prefer_vdw=False)
            r2 = get_element_radius(o_el.symbol, prefer_vdw=False)
            len_o = (r1 + r2) * 1.15
            
            o_pos = site.coords + missing_vec * len_o

            if not collision_detector.is_position_safe(o_pos):
                logger.warning(f"Position clash detected for O at site {i}, skipping OH group")
                continue

            passivated.append("O", o_pos, coords_are_cartesian=True)
            collision_detector.add_site(o_pos)
            o_site_index = len(passivated) - 1
            logger.debug(f"Added O to cation site {i}")

            h_el = get_cached_element("H")
            r_o = get_element_radius(o_el.symbol, prefer_vdw=False)
            r_h = get_element_radius(h_el.symbol, prefer_vdw=False)
            len_h = r_o + r_h

            # Construct perpendicular vector for rotation
            if abs(missing_vec[2]) > 0.9:
                ref_vec = np.array([1.0, 0.0, 0.0])
            else:
                ref_vec = np.array([0.0, 0.0, 1.0])

            perp_vec = np.cross(missing_vec, ref_vec)
            perp_vec /= np.linalg.norm(perp_vec)

            h_added = False
            # Wiggle check: Try rotating around the bond axis
            for angle_deg in range(0, 360, 15):
                angle_rad = np.radians(angle_deg)
                
                axis_component = missing_vec * np.cos(np.radians(60))
                perp_component = perp_vec * np.sin(np.radians(60))
                
                cross_term = np.cross(missing_vec, perp_vec)
                rotated_perp = perp_component * np.cos(angle_rad) + \
                               cross_term * np.sin(np.radians(60)) * np.sin(angle_rad)
                
                h_vec_dir = axis_component + rotated_perp
                h_vec_dir /= np.linalg.norm(h_vec_dir)

                h_pos = o_pos + h_vec_dir * len_h

                if collision_detector.is_position_safe(h_pos):
                    passivated.append("H", h_pos, coords_are_cartesian=True)
                    collision_detector.add_site(h_pos)
                    added_count += 2  # O + H
                    logger.debug(f"Added H to O at site {i} (rotated {angle_deg}°)")
                    h_added = True
                    break

            if not h_added:
                logger.warning(f"Could not find safe position for H on O at site {i}, removing O")
                passivated.remove_sites([o_site_index])
                collision_detector._rebuild_tree()  # Rebuild after removal

    logger.info(f"Added {added_count} passivating atoms")
    return passivated


def verify_structure_integrity(structure: Structure, min_dist: float = 0.7) -> bool:
    """
    Verify that the structure has no extremely close atoms (<0.7 Å).
    
    OPTIMIZATION: Uses get_all_neighbors once instead of per-atom queries.
    """
    if len(structure) < 2:
        return True

    try:
        all_neighbors = structure.get_all_neighbors(min_dist, include_index=True)
        
        for i, neighbors in enumerate(all_neighbors):
            for neighbor in neighbors:
                j = neighbor.index
                dist = neighbor.nn_distance
                
                if i < j:
                    el_i = get_site_element_symbol(structure.sites[i])
                    el_j = get_site_element_symbol(structure.sites[j])
                    logger.error(f"INTEGRITY FAIL: Atom {i} ({el_i}) and Atom {j} ({el_j}) are too close: {dist:.3f} Å")
                    return False
        return True
        
    except Exception as e:
        logger.error(f"Error during integrity check: {e}")
        return False


# =============================================================================
# MCP Tool Implementations (Keep existing signatures)
# =============================================================================

def passivate_covalent_surface_impl(structure_id: str, passivant: str = "H") -> Dict[str, Any]:
    struct = get_structure(structure_id)
    passivated_struct = passivate_covalent_surface(struct, passivant=passivant)
    new_sid = new_structure_id()
    store_structure(new_sid, passivated_struct, meta={"parent": structure_id, "method": "covalent_passivation"})
    return {
        "original_id": structure_id,
        "passivated_id": new_sid,
        "method": "covalent",
        "nsites_passivated": len(passivated_struct)
    }

def passivate_compound_semiconductor_impl(structure_id: str) -> Dict[str, Any]:
    struct = get_structure(structure_id)
    passivated_struct = passivate_compound_semiconductor(struct)
    new_sid = new_structure_id()
    store_structure(new_sid, passivated_struct, meta={"parent": structure_id, "method": "compound_passivation"})
    return {
        "original_id": structure_id,
        "passivated_id": new_sid,
        "method": "compound",
        "nsites_passivated": len(passivated_struct)
    }

def passivate_polar_surface_impl(structure_id: str) -> Dict[str, Any]:
    struct = get_structure(structure_id)
    passivated_struct = passivate_polar_surface(struct)
    new_sid = new_structure_id()
    store_structure(new_sid, passivated_struct, meta={"parent": structure_id, "method": "polar_passivation"})
    return {
        "original_id": structure_id,
        "passivated_id": new_sid,
        "method": "polar",
        "nsites_passivated": len(passivated_struct)
    }

def auto_passivate_surface_impl(structure_id: str, method: str = "auto", **kwargs) -> Dict[str, Any]:
    struct = get_structure(structure_id)
    passivated_struct = PassivatorFactory.passivate(struct, method=method, **kwargs)
    new_sid = new_structure_id()
    store_structure(new_sid, passivated_struct, meta={"parent": structure_id, "method": f"{method}_passivation"})
    return {
        "original_id": structure_id,
        "passivated_id": new_sid,
        "method": method,
        "nsites_passivated": len(passivated_struct)
    }