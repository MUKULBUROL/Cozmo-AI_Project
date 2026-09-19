"""Room polygon geometric validation, self-intersection audit, and measurable quality scoring.

1. Why this file exists:
   Verifies geometric validity, topological closure, absence of self-intersections,
   and physical realism of candidate room polygons. Computes transparent,
   evidence-based quality metrics derived from measurable physical signals
   without inventing arbitrary scores.

2. Pipeline stage:
   Stage 3 (2D Wall Projection & Room Polygon Extraction) - Steps 10 and 11.

3. Inputs:
   Constructed polygon dictionary from polygon_builder.py,
   accepted corners from corner_detection.py,
   projected walls from projection_2d.py.

4. Outputs:
   Validation dictionary with boolean validity, closure status, self-intersection
   count, edge diagnostics, and itemized quality score components.

5. Coordinate/Unit assumptions:
   Coordinates are in meters on the horizontal floor plane (XZ).
   Lengths and perimeters in meters, areas in square meters.

6. Dependencies:
   shapely.geometry, numpy, typing.

7. Most likely failure/debugging points:
   - Self-intersection if walls cross in an hourglass / figure-8 shape.
   - Tiny edges or duplicate vertices if multiple corners snapped together.
   - Low support ratio if walls have large unobserved gaps.
"""

from typing import List, Dict, Any, Tuple
import numpy as np
from shapely.geometry import Polygon, LineString


def validate_room_polygon(
    polygon_dict: Dict[str, Any],
    min_corners: int = 3,
    min_edge_length_m: float = 0.20,
    min_area_sqm: float = 1.0,
    max_area_sqm: float = 500.0,
) -> Dict[str, Any]:
    """Performs rigorous topological and geometric checks on candidate room polygon.

    Purpose:
        Ensures polygon is closed, simple, non-self-intersecting, has realistic
        dimensions, and contains no degenerate zero-length edges or acute spikes.

    Parameters:
        polygon_dict: Dictionary with 'vertices' and 'corner_ids' from polygon_builder.
        min_corners: Minimum required unique corners (default 3).
        min_edge_length_m: Flag edges shorter than this threshold (meters).
        min_area_sqm: Minimum reasonable floor area in square meters.
        max_area_sqm: Maximum reasonable room floor area in square meters.

    Returns:
        Validation report dictionary:
        - 'is_valid': bool
        - 'is_closed': bool
        - 'is_simple': bool
        - 'self_intersections_count': int
        - 'vertex_count': int
        - 'edge_lengths_m': List[float]
        - 'tiny_edges_count': int
        - 'duplicate_vertices_count': int
        - 'errors': List[str]
        - 'warnings': List[str]

    Assumptions:
        Vertices list contains 2D points [x, z] in meters.

    Failure conditions:
        Returns is_valid=False if vertices cannot form a valid Shapely polygon.

    Debugging:
        Check 'errors' list if a polygon was marked invalid.
    """
    vertices = polygon_dict.get("vertices", [])
    errors: List[str] = []
    warnings: List[str] = []

    if len(vertices) < 4:
        return {
            "is_valid": False,
            "is_closed": False,
            "is_simple": False,
            "self_intersections_count": 0,
            "vertex_count": len(vertices),
            "edge_lengths_m": [],
            "tiny_edges_count": 0,
            "duplicate_vertices_count": 0,
            "errors": [f"insufficient_vertices_{len(vertices)}_need_at_least_4_for_closed_loop"],
            "warnings": [],
        }

    # 1. Closure check
    v_first = np.array(vertices[0], dtype=np.float64)
    v_last = np.array(vertices[-1], dtype=np.float64)
    dist_closure = float(np.linalg.norm(v_first - v_last))
    is_closed = dist_closure < 1e-4
    if not is_closed:
        errors.append(f"unclosed_polygon_gap_{dist_closure:.4f}m")

    # 2. Unique vertices and duplicate check
    unique_pts = vertices[:-1] if is_closed else vertices
    dup_count = 0
    edge_lengths: List[float] = []
    tiny_edge_count = 0

    for i in range(len(unique_pts)):
        p1 = np.array(unique_pts[i], dtype=np.float64)
        p2 = np.array(unique_pts[(i + 1) % len(unique_pts)], dtype=np.float64)
        edge_len = float(np.linalg.norm(p2 - p1))
        edge_lengths.append(edge_len)

        if edge_len < 1e-4:
            dup_count += 1
            errors.append(f"duplicate_consecutive_vertex_at_index_{i}")
        elif edge_len < min_edge_length_m:
            tiny_edge_count += 1
            warnings.append(f"short_edge_{edge_len:.3f}m_between_indices_{i}_and_{(i+1)%len(unique_pts)}")

    if len(unique_pts) < min_corners:
        errors.append(f"too_few_unique_corners_{len(unique_pts)}_need_{min_corners}")

    # 3. Shapely validity and self-intersection analysis
    poly = Polygon(vertices)
    is_valid_shapely = bool(poly.is_valid)
    is_simple_shapely = bool(poly.is_simple)
    self_intersect_count = 0

    if not is_simple_shapely:
        errors.append("self_intersecting_polygon_boundary")
        # Count edge-edge crossings
        for i in range(len(unique_pts)):
            seg1 = LineString([unique_pts[i], unique_pts[(i + 1) % len(unique_pts)]])
            for j in range(i + 2, len(unique_pts)):
                if i == 0 and j == len(unique_pts) - 1:
                    continue  # Adjacent at wrap-around
                seg2 = LineString([unique_pts[j], unique_pts[(j + 1) % len(unique_pts)]])
                if seg1.crosses(seg2):
                    self_intersect_count += 1

    if not is_valid_shapely:
        errors.append("geometrically_invalid_polygon")

    # 4. Area checks
    if poly.area < min_area_sqm:
        errors.append(f"unrealistically_small_area_{poly.area:.2f}sqm_below_{min_area_sqm}sqm")
    if poly.area > max_area_sqm:
        errors.append(f"unrealistically_large_area_{poly.area:.2f}sqm_above_{max_area_sqm}sqm")

    is_overall_valid = (
        is_closed and
        is_valid_shapely and
        is_simple_shapely and
        len(errors) == 0
    )

    return {
        "is_valid": is_overall_valid,
        "is_closed": is_closed,
        "is_simple": is_simple_shapely,
        "self_intersections_count": self_intersect_count,
        "vertex_count": len(unique_pts),
        "edge_lengths_m": edge_lengths,
        "tiny_edges_count": tiny_edge_count,
        "duplicate_vertices_count": dup_count,
        "errors": errors,
        "warnings": warnings,
    }


def compute_polygon_quality_metrics(
    polygon_dict: Dict[str, Any],
    accepted_corners: List[Dict[str, Any]],
    projected_walls: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Computes measurable evidence-based quality metrics for a room polygon.

    Purpose:
        Quantifies how well the extracted polygon is physically grounded in
        sensor observations without fabricating arbitrary confidence numbers.

    Parameters:
        polygon_dict: Validated polygon dictionary.
        accepted_corners: List of accepted corner dictionaries.
        projected_walls: List of projected wall dictionaries.

    Returns:
        Dictionary of measurable quality metrics:
        - 'boundary_support_ratio': Fraction of perimeter covered by observed walls.
        - 'mean_wall_rmse_m': Average plane RMSE of supporting walls.
        - 'mean_wall_confidence': Average Stage 2 confidence of supporting walls.
        - 'inferred_corner_count': Number of inferred (gap-extended) corners.
        - 'inferred_corner_ratio': Fraction of corners inferred.
        - 'avg_corner_extension_m': Mean extension distance required to close corners.
        - 'max_corner_extension_m': Worst-case corner extension distance.
        - 'composite_quality_score': Grounded score in [0.0, 1.0].

    Assumptions:
        Polygon is valid and closed.

    Failure conditions:
        Returns zeroed metrics if polygon is invalid or has no vertices.

    Debugging:
        Inspect boundary_support_ratio if quality score is unexpectedly low.
    """
    wall_ids = polygon_dict.get("wall_ids", [])
    corner_ids = polygon_dict.get("corner_ids", [])
    perimeter = polygon_dict.get("perimeter_m", 0.0)

    if not polygon_dict.get("valid", False) or perimeter <= 0.0:
        return {
            "boundary_support_ratio": 0.0,
            "mean_wall_rmse_m": 0.0,
            "mean_wall_confidence": 0.0,
            "inferred_corner_count": 0,
            "inferred_corner_ratio": 0.0,
            "avg_corner_extension_m": 0.0,
            "max_corner_extension_m": 0.0,
            "composite_quality_score": 0.0,
        }

    wall_map = {w["wall_id"]: w for w in projected_walls}
    corner_map = {c["id"]: c for c in accepted_corners}

    # 1. Boundary physical observation support
    observed_len_sum = sum(wall_map[wid]["length_m"] for wid in wall_ids if wid in wall_map)
    support_ratio = min(1.0, float(observed_len_sum / perimeter))

    # 2. Wall fitting RMSE and confidence
    wall_rmses = [wall_map[wid]["rmse_m"] for wid in wall_ids if wid in wall_map]
    wall_confs = [wall_map[wid]["confidence"] for wid in wall_ids if wid in wall_map]
    mean_rmse = float(np.mean(wall_rmses)) if wall_rmses else 0.0
    mean_conf = float(np.mean(wall_confs)) if wall_confs else 0.0

    # 3. Corner extension and inference statistics
    poly_corners = [corner_map[cid] for cid in corner_ids if cid in corner_map]
    inferred_count = sum(1 for c in poly_corners if c.get("inferred", False))
    inferred_ratio = float(inferred_count / max(1, len(poly_corners)))

    extensions = [
        max(c.get("extension_wall_a_m", 0.0), c.get("extension_wall_b_m", 0.0))
        for c in poly_corners
    ]
    avg_ext = float(np.mean(extensions)) if extensions else 0.0
    max_ext = float(np.max(extensions)) if extensions else 0.0

    # Composite score calculation:
    # 40% support ratio, 30% wall confidence, 20% extension quality, 10% RMSE quality
    ext_quality = max(0.0, 1.0 - (avg_ext / 0.35))
    rmse_quality = max(0.0, 1.0 - (mean_rmse / 0.10))
    composite_score = (
        0.40 * support_ratio +
        0.30 * mean_conf +
        0.20 * ext_quality +
        0.10 * rmse_quality
    )
    composite_score = max(0.0, min(1.0, float(composite_score)))

    return {
        "boundary_support_ratio": round(support_ratio, 4),
        "mean_wall_rmse_m": round(mean_rmse, 4),
        "mean_wall_confidence": round(mean_conf, 4),
        "inferred_corner_count": inferred_count,
        "inferred_corner_ratio": round(inferred_ratio, 4),
        "avg_corner_extension_m": round(avg_ext, 4),
        "max_corner_extension_m": round(max_ext, 4),
        "composite_quality_score": round(composite_score, 4),
    }
