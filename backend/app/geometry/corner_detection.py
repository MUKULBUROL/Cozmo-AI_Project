"""Candidate corner detection, geometric gap inference, and corner validation.

1. Why this file exists:
   Intersects pairs of 2D projected wall lines to identify candidate room corners.
   Filters out wild or mathematically unstable intersections, handles physical
   scan gaps at corners with controlled geometric extension, flags inferred
   closures, and preserves non-orthogonal/angled room geometry.

2. Pipeline stage:
   Stage 3 (2D Wall Projection & Room Polygon Extraction) - Steps 5, 6, and 7.

3. Inputs:
   List of 2D projected wall dictionaries from projection_2d.py.

4. Outputs:
   List of accepted and rejected corner dictionaries with coordinates, supporting
   wall IDs, extension distances, inference flags, and detailed diagnostics.

5. Coordinate/Unit assumptions:
   Coordinates (x, z) are in meters on the horizontal floor plane.
   All distances (extensions, segment distances) are metric (meters).
   Angles are in degrees.

6. Dependencies:
   numpy, typing, .line_geometry.

7. Most likely failure/debugging points:
   - Rejecting genuine corners if max_extension_m is set too tight for a sparse scan.
   - Creating false corners if max_extension_m is set too high across distant rooms.
   - Inspect corners.json for rejected pairwise intersections and reasons.
"""

from typing import List, Dict, Any, Tuple
import numpy as np
from .line_geometry import (
    intersect_2d_lines,
    compute_segment_extension_distance,
    point_to_segment_distance,
    angle_between_lines_deg,
)


def detect_candidate_corners(
    projected_walls: List[Dict[str, Any]],
    max_extension_m: float = 0.35,
    max_point_to_segment_m: float = 0.40,
    min_angle_deg: float = 12.0,
    orthogonality_tolerance_deg: float = 15.0,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Computes and validates pairwise 2D wall intersections as candidate corners.

    Purpose:
        Identifies plausible room boundary corners while discarding parallel
        walls, distant infinite-line projections, and unclamped extensions.

    Parameters:
        projected_walls: List of 2D projected wall dicts.
        max_extension_m: Maximum allowable extension beyond observed wall extents (meters).
        max_point_to_segment_m: Maximum Euclidean distance from corner to finite segment.
        min_angle_deg: Minimum intersection angle in degrees to prevent numerical instability.
        orthogonality_tolerance_deg: Angular tolerance from 90 degrees to flag near-orthogonality.

    Returns:
        (accepted_corners, rejected_corners)
        Accepted corners include:
        - id, x, z, wall_ids, distance_to_wall_a_extent_m, distance_to_wall_b_extent_m,
        - angle_deg, is_near_orthogonal, inferred, status='accepted'.

    Assumptions:
        Wall lines are normalized in Ax + Bz + C = 0 form.

    Failure conditions:
        Returns empty accepted list if no walls intersect within distance thresholds.

    Debugging:
        Check rejected_corners for pairs that were rejected due to 'exceeds_max_extension'.
    """
    accepted_corners: List[Dict[str, Any]] = []
    rejected_corners: List[Dict[str, Any]] = []

    n_walls = len(projected_walls)
    corner_counter = 1

    for i in range(n_walls):
        w_a = projected_walls[i]
        line_a = np.array(w_a["line"], dtype=np.float64)
        orig_a = np.array(w_a["origin_pt"], dtype=np.float64)
        tang_a = np.array(w_a["tangent"], dtype=np.float64)
        s_min_a, s_max_a = w_a["s_min"], w_a["s_max"]
        p_start_a = np.array(w_a["start"], dtype=np.float64)
        p_end_a = np.array(w_a["end"], dtype=np.float64)

        for j in range(i + 1, n_walls):
            w_b = projected_walls[j]
            line_b = np.array(w_b["line"], dtype=np.float64)
            orig_b = np.array(w_b["origin_pt"], dtype=np.float64)
            tang_b = np.array(w_b["tangent"], dtype=np.float64)
            s_min_b, s_max_b = w_b["s_min"], w_b["s_max"]
            p_start_b = np.array(w_b["start"], dtype=np.float64)
            p_end_b = np.array(w_b["end"], dtype=np.float64)

            # 1. Mathematical line intersection
            pt = intersect_2d_lines(line_a, line_b, min_angle_deg=min_angle_deg)
            if pt is None:
                rejected_corners.append({
                    "wall_ids": [w_a["wall_id"], w_b["wall_id"]],
                    "status": "rejected",
                    "rejection_reason": "near_parallel_lines",
                })
                continue

            # 2. Angular relationship (non-destructive; does not enforce 90 deg)
            angle_deg = angle_between_lines_deg(line_a, line_b)
            is_near_ortho = abs(angle_deg - 90.0) <= orthogonality_tolerance_deg

            # 3. Extension distances along tangent extents
            ext_a = compute_segment_extension_distance(pt, orig_a, tang_a, s_min_a, s_max_a)
            ext_b = compute_segment_extension_distance(pt, orig_b, tang_b, s_min_b, s_max_b)

            # 4. Euclidean distance to finite segments
            dist_seg_a = point_to_segment_distance(pt, p_start_a, p_end_a)
            dist_seg_b = point_to_segment_distance(pt, p_start_b, p_end_b)

            rejection_reasons = []
            if ext_a > max_extension_m:
                rejection_reasons.append(
                    f"wall_a_extension_{ext_a:.3f}m_exceeds_{max_extension_m:.3f}m"
                )
            if ext_b > max_extension_m:
                rejection_reasons.append(
                    f"wall_b_extension_{ext_b:.3f}m_exceeds_{max_extension_m:.3f}m"
                )
            if dist_seg_a > max_point_to_segment_m:
                rejection_reasons.append(
                    f"wall_a_segment_dist_{dist_seg_a:.3f}m_exceeds_{max_point_to_segment_m:.3f}m"
                )
            if dist_seg_b > max_point_to_segment_m:
                rejection_reasons.append(
                    f"wall_b_segment_dist_{dist_seg_b:.3f}m_exceeds_{max_point_to_segment_m:.3f}m"
                )

            corner_record = {
                "id": f"corner_{corner_counter:02d}",
                "x": float(pt[0]),
                "z": float(pt[1]),
                "wall_ids": [w_a["wall_id"], w_b["wall_id"]],
                "distance_to_wall_a_extent_m": float(ext_a),
                "distance_to_wall_b_extent_m": float(ext_b),
                "distance_to_segment_a_m": float(dist_seg_a),
                "distance_to_segment_b_m": float(dist_seg_b),
                "angle_deg": float(angle_deg),
                "is_near_orthogonal": bool(is_near_ortho),
                "inferred": bool(ext_a > 0.01 or ext_b > 0.01),
                "extension_wall_a_m": float(ext_a),
                "extension_wall_b_m": float(ext_b),
            }

            if rejection_reasons:
                corner_record["status"] = "rejected"
                corner_record["rejection_reasons"] = rejection_reasons
                rejected_corners.append(corner_record)
            else:
                corner_record["status"] = "accepted"
                corner_record["rejection_reasons"] = []
                accepted_corners.append(corner_record)
                corner_counter += 1

    return accepted_corners, rejected_corners
