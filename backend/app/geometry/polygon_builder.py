"""Connectivity graph construction and closed room polygon extraction.

1. Why this file exists:
   Constructs a topological connectivity graph where corners are nodes and
   walls are edges. Traverses the graph to discover closed non-self-intersecting
   room cycles and returns an ordered polygon boundary.

2. Pipeline stage:
   Stage 3 (2D Wall Projection & Room Polygon Extraction) - Steps 8 and 9.

3. Inputs:
   List of accepted corner dictionaries from corner_detection.py,
   list of projected wall dictionaries from projection_2d.py,
   optional reference interior point (e.g. camera centroid).

4. Outputs:
   Dictionary containing ordered polygon vertices [(x, z), ...], edge wall IDs,
   corner IDs, area, perimeter, and topological diagnostic flags.

5. Coordinate/Unit assumptions:
   Coordinates are in meters on the horizontal floor plane (XZ).
   Vertices are ordered consistently (counter-clockwise or clockwise).

6. Dependencies:
   shapely.geometry, numpy, typing.

7. Most likely failure/debugging points:
   - Graph disconnection if a corner was missed due to aggressive filtering.
   - Self-intersecting loops if wrong cycle is traversed in complex floor plans.
   - Inspect graph adjacency list if polygon fails to close.
"""

from typing import List, Dict, Any, Optional, Tuple, Set
import numpy as np
from shapely.geometry import Polygon


def build_connectivity_graph(
    corners: List[Dict[str, Any]],
    walls: List[Dict[str, Any]],
) -> Dict[str, List[Dict[str, Any]]]:
    """Constructs an adjacency graph where nodes are corners and edges are walls.

    Purpose:
        Links corners that share the same supporting wall segment into a topological graph.

    Parameters:
        corners: List of accepted corner dictionaries (each has 'id', 'x', 'z', 'wall_ids').
        walls: List of projected wall dictionaries (each has 'wall_id', 'line', 'tangent').

    Returns:
        Adjacency dictionary mapping corner_id to list of edge dicts:
        [{'neighbor_id': str, 'wall_id': str, 'length_m': float}, ...]

    Assumptions:
        Corners with the same wall_id are connected along that wall.

    Failure conditions:
        Returns empty adjacency graph if corners list is empty.

    Debugging:
        Check whether each corner has degree >= 2 to form a closed polygon.
    """
    # Group corners by wall_id
    wall_to_corners: Dict[str, List[str]] = {}
    corner_map: Dict[str, Dict[str, Any]] = {c["id"]: c for c in corners}
    wall_map: Dict[str, Dict[str, Any]] = {w["wall_id"]: w for w in walls}

    for c in corners:
        for w_id in c["wall_ids"]:
            wall_to_corners.setdefault(w_id, []).append(c["id"])

    adjacency: Dict[str, List[Dict[str, Any]]] = {c["id"]: [] for c in corners}

    for w_id, c_ids in wall_to_corners.items():
        if len(c_ids) < 2:
            continue

        w_info = wall_map.get(w_id)
        if w_info is None:
            # Sort arbitrarily by distance between first and rest
            sorted_cids = c_ids
        else:
            # Sort corners along wall tangent
            orig = np.array(w_info["origin_pt"], dtype=np.float64)
            tang = np.array(w_info["tangent"], dtype=np.float64)

            def proj_key(cid: str) -> float:
                c = corner_map[cid]
                pt = np.array([c["x"], c["z"]], dtype=np.float64)
                return float((pt - orig) @ tang)

            sorted_cids = sorted(c_ids, key=proj_key)

        # Connect consecutive corners along this wall
        for k in range(len(sorted_cids) - 1):
            c_a = sorted_cids[k]
            c_b = sorted_cids[k + 1]
            pt_a = np.array([corner_map[c_a]["x"], corner_map[c_a]["z"]])
            pt_b = np.array([corner_map[c_b]["x"], corner_map[c_b]["z"]])
            edge_len = float(np.linalg.norm(pt_b - pt_a))

            # Add bidirectional edges if not already present
            if not any(e["neighbor_id"] == c_b and e["wall_id"] == w_id for e in adjacency[c_a]):
                adjacency[c_a].append({"neighbor_id": c_b, "wall_id": w_id, "length_m": edge_len})
            if not any(e["neighbor_id"] == c_a and e["wall_id"] == w_id for e in adjacency[c_b]):
                adjacency[c_b].append({"neighbor_id": c_a, "wall_id": w_id, "length_m": edge_len})

    return adjacency


def find_simple_cycles(
    adjacency: Dict[str, List[Dict[str, Any]]],
    min_cycle_length: int = 3,
    max_cycle_length: int = 8,
) -> List[List[Tuple[str, str]]]:
    """Finds all simple cycles in the corner-wall graph.

    Purpose:
        Enumerates candidate closed loops that could form room boundaries.

    Parameters:
        adjacency: Adjacency dictionary from build_connectivity_graph.
        min_cycle_length: Minimum number of vertices (e.g. 3 for triangle, 4 for quad).
        max_cycle_length: Maximum number of vertices to explore.

    Returns:
        List of cycles, where each cycle is a list of (corner_id, wall_id) tuples.

    Assumptions:
        Nodes are identified by unique corner IDs.

    Failure conditions:
        Returns empty list if graph is acyclic or disconnected.

    Debugging:
        Inspect graph connectivity if expected 4-cycle is not detected.
    """
    cycles: List[List[Tuple[str, str]]] = []
    visited_cycles: Set[Tuple[str, ...]] = set()

    nodes = sorted(list(adjacency.keys()))

    def dfs(
        current_node: str,
        start_node: str,
        path: List[Tuple[str, str]],
        visited_nodes: Set[str],
    ) -> None:
        if len(path) >= max_cycle_length:
            return

        for edge in adjacency.get(current_node, []):
            nxt = edge["neighbor_id"]
            w_id = edge["wall_id"]

            if nxt == start_node and len(path) >= min_cycle_length:
                # Cycle found!
                cycle_nodes = tuple(c for c, _ in path)
                # Canonical representation: min rotation and direction
                min_idx = cycle_nodes.index(min(cycle_nodes))
                canon1 = cycle_nodes[min_idx:] + cycle_nodes[:min_idx]
                rev = tuple(reversed(cycle_nodes))
                min_rev_idx = rev.index(min(rev))
                canon2 = rev[min_rev_idx:] + rev[:min_rev_idx]
                canonical = min(canon1, canon2)

                if canonical not in visited_cycles:
                    visited_cycles.add(canonical)
                    # Complete cycle with final edge
                    full_cycle = list(path) + [(start_node, w_id)]
                    cycles.append(full_cycle)
                continue

            if nxt not in visited_nodes:
                # Prevent traversing back along the same wall immediately
                if path and path[-1][1] == w_id:
                    continue
                visited_nodes.add(nxt)
                dfs(nxt, start_node, path + [(nxt, w_id)], visited_nodes)
                visited_nodes.remove(nxt)

    for node in nodes:
        visited_nodes = {node}
        for first_edge in adjacency.get(node, []):
            nbr = first_edge["neighbor_id"]
            w_id = first_edge["wall_id"]
            visited_nodes.add(nbr)
            dfs(nbr, node, [(node, ""), (nbr, w_id)], visited_nodes)
            visited_nodes.remove(nbr)

    return cycles


def extract_room_polygon(
    corners: List[Dict[str, Any]],
    walls: List[Dict[str, Any]],
    reference_interior_pt: Optional[Tuple[float, float]] = None,
) -> Dict[str, Any]:
    """Constructs the best closed room polygon from accepted corners and walls.

    Purpose:
        Selects the topologically valid, non-self-intersecting closed polygon
        that best represents the primary room space.

    Parameters:
        corners: List of accepted corner dictionaries.
        walls: List of projected wall dictionaries.
        reference_interior_pt: Optional (x, z) point inside room (e.g. camera centroid).

    Returns:
        Dictionary with:
        - 'valid': bool
        - 'closed': bool
        - 'vertices': List[[x, z], ...] (closed loop: first == last)
        - 'corner_ids': List[str]
        - 'wall_ids': List[str]
        - 'area_sqm': float
        - 'perimeter_m': float
        - 'diagnostics': Dict with failure reasons or selection metrics.

    Assumptions:
        A valid room has at least 3 non-collinear corners and positive area.

    Failure conditions:
        Returns valid=False if no simple closed polygon can be formed.
        Does not fabricate polygons.

    Debugging:
        Check 'diagnostics' field if valid=False.
    """
    corner_map = {c["id"]: c for c in corners}
    wall_map = {w["wall_id"]: w for w in walls}

    if len(corners) < 3 or len(walls) < 3:
        return {
            "valid": False,
            "closed": False,
            "vertices": [],
            "corner_ids": [],
            "wall_ids": [],
            "area_sqm": 0.0,
            "perimeter_m": 0.0,
            "diagnostics": {
                "reason": "insufficient_geometry",
                "corner_count": len(corners),
                "wall_count": len(walls),
            },
        }

    adjacency = build_connectivity_graph(corners, walls)
    candidate_cycles = find_simple_cycles(adjacency, min_cycle_length=3, max_cycle_length=10)

    best_poly: Optional[Polygon] = None
    best_cycle_info: Optional[Dict[str, Any]] = None
    best_score = -1e9

    for cycle in candidate_cycles:
        # Extract ordered vertices (cycle is list of (corner_id, wall_id))
        c_ids = [cid for cid, _ in cycle[:-1]]  # Unique corners
        w_ids = [wid for _, wid in cycle[1:]]   # Walls traversed
        coords = [[corner_map[cid]["x"], corner_map[cid]["z"]] for cid in c_ids]
        closed_coords = coords + [coords[0]]

        poly = Polygon(closed_coords)

        # Topological validity checks
        if not poly.is_valid or not poly.is_simple:
            continue
        if poly.area < 1.0:  # Ignore tiny slivers/artifacts
            continue

        # Score this candidate polygon
        # 1. Total wall inlier support
        inlier_sum = sum(wall_map[wid].get("inlier_count", 0) for wid in w_ids if wid in wall_map)
        # 2. Average corner extension penalty
        total_ext = sum(
            corner_map[cid].get("distance_to_wall_a_extent_m", 0.0) +
            corner_map[cid].get("distance_to_wall_b_extent_m", 0.0)
            for cid in c_ids
        )
        avg_ext = total_ext / max(1, len(c_ids))

        # 3. Reference interior point bonus
        contains_ref = False
        if reference_interior_pt is not None:
            from shapely.geometry import Point
            ref_pt = Point(reference_interior_pt[0], reference_interior_pt[1])
            contains_ref = poly.contains(ref_pt)

        # Scoring function favoring high inliers, reference point containment, and low extension
        score = inlier_sum * (2.0 if contains_ref else 1.0) - avg_ext * 10000.0 + poly.area * 500.0

        if score > best_score:
            best_score = score
            best_poly = poly
            best_cycle_info = {
                "corner_ids": c_ids,
                "wall_ids": w_ids,
                "vertices": closed_coords,
                "area_sqm": float(poly.area),
                "perimeter_m": float(poly.length),
                "contains_reference": contains_ref,
                "avg_corner_extension_m": float(avg_ext),
                "total_inliers": inlier_sum,
            }

    if best_poly is None or best_cycle_info is None:
        return {
            "valid": False,
            "closed": False,
            "vertices": [],
            "corner_ids": [],
            "wall_ids": [],
            "area_sqm": 0.0,
            "perimeter_m": 0.0,
            "diagnostics": {
                "reason": "no_valid_closed_simple_cycle_found",
                "candidate_cycles_evaluated": len(candidate_cycles),
            },
        }

    return {
        "valid": True,
        "closed": True,
        "vertices": best_cycle_info["vertices"],
        "corner_ids": best_cycle_info["corner_ids"],
        "wall_ids": best_cycle_info["wall_ids"],
        "area_sqm": best_cycle_info["area_sqm"],
        "perimeter_m": best_cycle_info["perimeter_m"],
        "diagnostics": {
            "status": "success",
            "contains_reference": best_cycle_info["contains_reference"],
            "avg_corner_extension_m": best_cycle_info["avg_corner_extension_m"],
            "total_inliers": best_cycle_info["total_inliers"],
            "candidate_cycles_evaluated": len(candidate_cycles),
        },
    }
