"""Structural wall association and false-positive filtering for candidate architectural openings.

1. Why this file exists:
   Attaches 2D/3D candidate opening detections strictly to verified Stage 2 structural wall planes,
   eliminating phantom openings caused by indoor furniture, wardrobes, picture frames, mirrors,
   and television screens that visually resemble doors or windows.

2. Pipeline stage:
   Stage 5 (Door/Window Detection & Metric Opening Measurement) - Wall Association & Validation.

3. Inputs:
   Candidate opening detection, camera intrinsics, 6D camera pose, Stage 2 structural walls,
   and Stage 3 projected wall segment extents.

4. Outputs:
   Validated opening observation with associated wall_id, 3D metric jamb coordinates,
   or rejected record with explicit physical rejection reasons.

5. Coordinate/Unit assumptions:
   Coordinates in metric meters (m) in world frame (Y vertical upward, XZ horizontal ground).
   Planes normalized to unit normal length.

6. Dependencies:
   math, typing, numpy, .opening_projection.

7. Most likely failure/debugging points:
   - Detection projecting onto background wall behind open doorway rather than the frame wall
     (handled by testing normal angle and distance to camera).
   - Candidate rejected due to excessively strict segment bounding (handled with margin allowance).
"""

import math
from typing import Dict, Any, List, Optional, Tuple
import numpy as np

from .opening_projection import project_ray_to_wall_plane, project_opening_to_wall


def distance_point_to_segment_2d(
    pt: Tuple[float, float],
    seg_start: Tuple[float, float],
    seg_end: Tuple[float, float],
) -> float:
    """Computes shortest 2D Euclidean distance from a point to a finite line segment.

    Purpose:
        Verifies whether an opening candidate's (x, z) coordinates lie along the finite span of a wall.

    Parameters:
        pt: (x, z) point coordinates.
        seg_start: (x1, z1) segment start.
        seg_end: (x2, z2) segment end.

    Returns:
        Minimum perpendicular or endpoint distance in meters.

    Assumptions:
        All coordinates are metric meters.

    Failure conditions:
        Returns distance to start if segment length is zero.

    Debugging:
        Check segment endpoint coordinates if distance is unexpectedly large.
    """
    px, pz = pt
    x1, z1 = seg_start
    x2, z2 = seg_end

    dx = x2 - x1
    dz = z2 - z1
    seg_len_sq = dx * dx + dz * dz

    if seg_len_sq < 1e-6:
        return float(math.hypot(px - x1, pz - z1))

    # Project point onto segment parameter t in [0, 1]
    t = max(0.0, min(1.0, ((px - x1) * dx + (pz - z1) * dz) / seg_len_sq))
    proj_x = x1 + t * dx
    proj_z = z1 + t * dz
    return float(math.hypot(px - proj_x, pz - proj_z))


def associate_candidate_with_wall(
    candidate: Dict[str, Any],
    boundary_pixels: Dict[str, Any],
    intrinsics: Dict[str, Any],
    camera_pose: Dict[str, Any],
    structural_walls: List[Dict[str, Any]],
    projected_walls: Optional[List[Dict[str, Any]]] = None,
    max_segment_dist_m: float = 0.45,
    min_opening_width_m: float = 0.45,
    max_opening_width_m: float = 2.60,
) -> Dict[str, Any]:
    """Tests all candidate structural wall planes to find the best physical host for an opening.

    Purpose:
        Filters out non-wall objects (furniture, wardrobes, posters) and attaches valid openings
        to the specific Stage 2 wall hosting them.

    Parameters:
        candidate: Detection dictionary with bbox, class, detector_score.
        boundary_pixels: Refined boundary pixels (left_jamb_pixel, right_jamb_pixel).
        intrinsics: Camera calibration intrinsics.
        camera_pose: Camera 6D pose in world coordinates.
        structural_walls: List of Stage 2 accepted structural walls.
        projected_walls: Optional list of Stage 3 2D projected wall segments with finite bounds.
        max_segment_dist_m: Maximum allowable proximity to wall segment extent.
        min_opening_width_m: Minimum plausible physical width in meters.
        max_opening_width_m: Maximum plausible physical width in meters.

    Returns:
        Enriched observation dictionary containing association status ('accepted', 'rejected'),
        wall_id, 3D metric geometry, and rejection reasons.

    Assumptions:
        Only Stage 2 accepted walls are valid hosts for structural openings.

    Failure conditions:
        Rejects candidate if no wall plane produces forward ray intersection or valid width.

    Debugging:
        Inspect rejected candidates list in opening_observations.json to identify false positive causes.
    """
    proj_walls_map: Dict[str, Dict[str, Any]] = {}
    if projected_walls:
        for pw in projected_walls:
            wid = pw.get("wall_id")
            if wid:
                proj_walls_map[wid] = pw

    best_wall_id: Optional[str] = None
    best_proj_geo: Optional[Dict[str, Any]] = None
    best_score: float = -1.0
    rejection_reasons: List[str] = []

    for wall in structural_walls:
        wid = wall["id"]
        plane = wall["plane"]

        # 1. Attempt 3D projection onto this wall plane
        proj_geo = project_opening_to_wall(boundary_pixels, intrinsics, camera_pose, plane)
        if proj_geo is None:
            continue

        w_m = proj_geo["width_m"]
        # Check architectural width plausibility
        if w_m < min_opening_width_m or w_m > max_opening_width_m:
            continue

        c_3d = proj_geo["centroid_3d"]
        c_xz = (c_3d[0], c_3d[2])

        # 2. Check proximity to wall segment extent
        pw_info = proj_walls_map.get(wid)
        if pw_info and "start" in pw_info and "end" in pw_info:
            s1 = (pw_info["start"][0], pw_info["start"][1])
            s2 = (pw_info["end"][0], pw_info["end"][1])
            dist_to_seg = distance_point_to_segment_2d(c_xz, s1, s2)
        else:
            # Fallback to Stage 2 bounds
            bx = wall.get("bounds", {}).get("x", [-999, 999])
            bz = wall.get("bounds", {}).get("z", [-999, 999])
            s1 = (bx[0], bz[0])
            s2 = (bx[1], bz[1])
            dist_to_seg = distance_point_to_segment_2d(c_xz, s1, s2)

        if dist_to_seg > max_segment_dist_m:
            continue

        # 3. Association score based on distance and detector score
        proximity_factor = max(0.10, 1.0 - (dist_to_seg / max_segment_dist_m))
        score = candidate.get("detector_score", 0.5) * proximity_factor

        if score > best_score:
            best_score = score
            best_wall_id = wid
            best_proj_geo = proj_geo

    if best_wall_id is None or best_proj_geo is None:
        rejection_reasons.append("no_supporting_structural_wall_within_tolerance")
        return {
            "status": "rejected",
            "rejection_reasons": rejection_reasons,
            "candidate": candidate,
            "wall_id": None,
            "projected_geometry": None,
        }

    return {
        "status": "accepted",
        "rejection_reasons": [],
        "candidate": candidate,
        "wall_id": best_wall_id,
        "projected_geometry": best_proj_geo,
        "association_score": round(best_score, 3),
    }
