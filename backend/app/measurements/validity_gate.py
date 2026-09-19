"""Measurement validity gate for Stage 4 floor plan dimensions.

1. Why this file exists:
   Prevents uncritical propagation of geometric artifacts, doorway T-junctions,
   inferred extrapolations, and non-closed loops into user-facing dimensions by evaluating
   measurable geometric health signals to assign a calibrated validity verdict.

2. Pipeline stage:
   Stage 4 (Metric Measurements, Room Area & Uncertainty) - Quality & Validity Gate.

3. Inputs:
   Stage 3 room polygon JSON data, polygon stats, corner metrics, and wall quality metrics.

4. Outputs:
   Structured ValidityReport containing status ('valid', 'provisional', 'invalid'),
   human- and machine-readable rejection/caution reason codes, and quantitative metrics.

5. Coordinate/Unit assumptions:
   Coordinates in meters (m) in horizontal floor plane XZ.
   Areas in square meters (m2).

6. Dependencies:
   enum, typing, pydantic, numpy, shapely.

7. Most likely failure/debugging points:
   - Malformed polygon data lacking coordinates or validation blocks.
   - Overly aggressive thresholding marking valid rooms provisional.
   - Missing wall metadata when mapping polygon edges to physical plane IDs.
"""

from enum import Enum
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
import numpy as np
from shapely.geometry import Polygon


class ValidityStatus(str, Enum):
    """Categorical measurement validity state."""
    VALID = "valid"
    PROVISIONAL = "provisional"
    INVALID = "invalid"


class ValidityReport(BaseModel):
    """Machine-readable assessment of polygon measurement trustworthiness."""
    measurement_status: ValidityStatus = Field(..., description="Overall validity status")
    reasons: List[str] = Field(default_factory=list, description="Specific triggers for provisional or invalid state")
    metrics: Dict[str, Any] = Field(default_factory=dict, description="Measurable signals evaluated by gate")


def evaluate_measurement_validity(
    polygon_data: Dict[str, Any],
    polygon_stats: Optional[Dict[str, Any]] = None,
    wall_quality: Optional[Dict[str, Any]] = None,
    corners_data: Optional[List[Dict[str, Any]]] = None,
    min_boundary_support_ratio: float = 0.70,
    max_acceptable_rmse_m: float = 0.05,
    doorway_short_edge_threshold_m: float = 0.35,
    max_acceptable_extension_m: float = 0.05,
) -> ValidityReport:
    """Evaluates Stage 3 geometry to decide whether metric measurements are trustworthy.

    Purpose:
        Applies a multi-criteria gate checking topology, closure, self-intersections,
        T-junction doorway transitions, inferred gap extrapolations, and plane residuals.

    Parameters:
        polygon_data: Dictionary containing room polygon vertices, closure, and corner IDs.
        polygon_stats: Optional Stage 3 polygon_stats.json content.
        wall_quality: Optional Stage 3 wall_quality.json content.
        corners_data: Optional Stage 3 corners.json candidate/accepted list.
        min_boundary_support_ratio: Minimum fraction of boundary supported by LiDAR points.
        max_acceptable_rmse_m: Plane fitting RMSE threshold above which measurements become provisional.
        doorway_short_edge_threshold_m: Length below which an edge suggests a doorway transition / T-junction.
        max_acceptable_extension_m: Corner gap extension distance threshold.

    Returns:
        ValidityReport object with status ('valid', 'provisional', 'invalid') and reason codes.

    Assumptions:
        Vertices are 2D points [x, z] in metric meters.
        If polygon_stats is omitted, geometric validation is computed dynamically via Shapely.

    Failure conditions:
        Returns status=INVALID if polygon is unclosed, self-intersecting, has < 3 vertices, or 0 area.

    Debugging:
        Inspect report.reasons to identify exactly which physical or topological criteria were triggered.
    """
    reasons: List[str] = []
    metrics: Dict[str, Any] = {}

    poly_info = polygon_data.get("polygon", polygon_data)
    raw_vertices = poly_info.get("vertices", [])

    if len(raw_vertices) < 3:
        return ValidityReport(
            measurement_status=ValidityStatus.INVALID,
            reasons=["insufficient_vertices_under_3"],
            metrics={"vertex_count": len(raw_vertices)},
        )

    # Convert to unique vertices for Shapely analysis
    pts = [tuple(p) for p in raw_vertices]
    if len(pts) > 1 and np.allclose(pts[0], pts[-1], atol=1e-4):
        unique_pts = pts[:-1]
    else:
        unique_pts = pts

    if len(unique_pts) < 3:
        return ValidityReport(
            measurement_status=ValidityStatus.INVALID,
            reasons=["degenerate_polygon_fewer_than_3_unique_vertices"],
            metrics={"unique_vertices": len(unique_pts)},
        )

    poly = Polygon(unique_pts)
    is_valid_topology = poly.is_valid and poly.is_simple and not poly.is_empty
    area_val = float(poly.area)

    metrics["shapely_valid"] = is_valid_topology
    metrics["area_sqm"] = area_val
    metrics["vertex_count"] = len(unique_pts)

    # 1. HARD INVALIDITY CHECKS
    if not is_valid_topology:
        reasons.append("polygon_topology_invalid_or_self_intersecting")
    if area_val < 0.10:
        reasons.append("degenerate_polygon_area_below_0.10m2")

    # Check Stage 3 validation metadata if supplied
    val_meta = (polygon_stats or {}).get("validation", {})
    if val_meta:
        if not val_meta.get("is_closed", True):
            reasons.append("polygon_boundary_not_closed")
        if val_meta.get("self_intersections_count", 0) > 0:
            reasons.append("self_intersections_detected")

    # If any hard invalidity triggered, terminate immediately
    if any("invalid" in r or "self_intersecting" in r or "not_closed" in r for r in reasons):
        return ValidityReport(
            measurement_status=ValidityStatus.INVALID,
            reasons=reasons,
            metrics=metrics,
        )

    # 2. PROVISIONAL CHECKS (Measurable evidence quality)
    provisional_reasons: List[str] = []

    # Edge length analysis for short edges (door jambs, hallway transitions)
    edge_lengths: List[float] = []
    short_edges: List[float] = []
    for i in range(len(unique_pts)):
        p1 = np.array(unique_pts[i])
        p2 = np.array(unique_pts[(i + 1) % len(unique_pts)])
        edge_len = float(np.linalg.norm(p2 - p1))
        edge_lengths.append(edge_len)
        if edge_len < doorway_short_edge_threshold_m:
            short_edges.append(edge_len)

    metrics["edge_lengths_m"] = edge_lengths
    metrics["short_edges_count"] = len(short_edges)

    if len(short_edges) > 0:
        provisional_reasons.append("corridor_doorway_t_junction_detected")

    # Inferred corner analysis
    quality_meta = (polygon_stats or {}).get("quality", {})
    inferred_corner_count = quality_meta.get("inferred_corner_count", 0)
    max_extension_m = quality_meta.get("max_corner_extension_m", 0.0)

    # Inspect corners list if available
    all_corners = corners_data or polygon_data.get("corners", [])
    poly_corner_ids = set(poly_info.get("corner_ids", []))
    active_inferred_corners: List[str] = []
    for c in all_corners:
        c_id = c.get("id")
        if c_id in poly_corner_ids and c.get("inferred", False):
            active_inferred_corners.append(c_id)
            ext_a = c.get("extension_wall_a_m", 0.0)
            ext_b = c.get("extension_wall_b_m", 0.0)
            max_extension_m = max(max_extension_m, ext_a, ext_b)

    metrics["inferred_corner_count"] = len(active_inferred_corners) or inferred_corner_count
    metrics["max_corner_extension_m"] = max_extension_m

    if (len(active_inferred_corners) > 0) or (inferred_corner_count > 0):
        provisional_reasons.append("inferred_corner_present")

    if max_extension_m > max_acceptable_extension_m:
        provisional_reasons.append(f"corner_extension_{max_extension_m:.3f}m_exceeds_threshold")

    # Boundary wall support
    boundary_support = quality_meta.get("boundary_support_ratio", 1.0)
    metrics["boundary_support_ratio"] = boundary_support
    if boundary_support < min_boundary_support_ratio:
        provisional_reasons.append(f"boundary_support_{boundary_support:.2f}_below_{min_boundary_support_ratio:.2f}")

    # Wall plane fitting residuals
    accepted_walls = (wall_quality or {}).get("accepted_walls", [])
    poly_wall_ids = set(poly_info.get("wall_ids", []))
    elevated_rmse_walls: List[str] = []
    mean_rmse = quality_meta.get("mean_wall_rmse_m", 0.0)

    for w in accepted_walls:
        w_id = w.get("wall_id")
        if not poly_wall_ids or w_id in poly_wall_ids:
            rmse = w.get("rmse_m", 0.0)
            if rmse > max_acceptable_rmse_m:
                elevated_rmse_walls.append(f"{w_id}:{rmse:.3f}m")

    metrics["elevated_rmse_walls"] = elevated_rmse_walls
    metrics["mean_wall_rmse_m"] = mean_rmse

    if elevated_rmse_walls:
        provisional_reasons.append("elevated_wall_fitting_residual")

    # Multiple corners sharing same wall plane (T-junction geometry indicator)
    wall_ids_in_poly = poly_info.get("wall_ids", [])
    wall_counts: Dict[str, int] = {}
    for wid in wall_ids_in_poly:
        wall_counts[wid] = wall_counts.get(wid, 0) + 1
    multi_edge_walls = [wid for wid, count in wall_counts.items() if count > 1]
    metrics["collinear_multi_edge_walls"] = multi_edge_walls
    if len(multi_edge_walls) >= 2 and "corridor_doorway_t_junction_detected" not in provisional_reasons:
        provisional_reasons.append("multiple_t_junctions_near_doorway")

    # Final verdict assignment
    if provisional_reasons:
        return ValidityReport(
            measurement_status=ValidityStatus.PROVISIONAL,
            reasons=provisional_reasons,
            metrics=metrics,
        )

    return ValidityReport(
        measurement_status=ValidityStatus.VALID,
        reasons=[],
        metrics=metrics,
    )
