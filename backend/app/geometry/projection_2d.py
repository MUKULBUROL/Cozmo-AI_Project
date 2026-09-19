"""2D wall projection and finite segment extent extraction in the XZ floor plane.

1. Why this file exists:
   Converts 3D vertical wall planes (Stage 2) into 2D lines in the horizontal
   ground plane (XZ), computes finite bounding extents along each wall's tangent
   direction, and merges redundant near-duplicate coplanar wall segments.

2. Pipeline stage:
   Stage 3 (2D Wall Projection & Room Polygon Extraction) - Steps 2, 3, and 4.

3. Inputs:
   List of accepted wall plane dictionaries from Stage 2 (structure.json),
   optionally augmented with 3D inlier points from walls.ply.

4. Outputs:
   List of ProjectedWall2D objects/dictionaries containing normalized 2D line
   coefficients (A*x + B*z + C = 0), tangent vectors, endpoints, and merge logs.

5. Coordinate/Unit assumptions:
   Y is vertical (upward).
   XZ is the horizontal ground plane.
   All coordinates, lengths, and distances are metric (meters).

6. Dependencies:
   numpy, typing.

7. Most likely failure/debugging points:
   - Degenerate normal (hypot(a, c) == 0) if a horizontal plane was fed as a wall.
   - Merging opposite parallel walls if max_offset_m is set too large.
   - Empty finite extents if point cloud filtering bounding box has zero coverage.
"""

from typing import List, Dict, Any, Optional, Tuple
import numpy as np


def project_plane_to_2d_line(
    plane: Dict[str, float],
) -> Tuple[float, float, float, np.ndarray, np.ndarray]:
    """Projects a 3D vertical plane ax + by + cz + d = 0 to 2D line Ax + Bz + C = 0.

    Purpose:
        Ignores vertical dimension Y to produce a normalized 2D line equation in
        the horizontal ground floor plane (XZ).

    Parameters:
        plane: Dictionary with keys 'a', 'b', 'c', 'd' defining plane equation.

    Returns:
        (A, B, C, normal_xz, tangent_xz) where:
        - A*x + B*z + C = 0
        - sqrt(A^2 + B^2) == 1.0
        - normal_xz is np.array([A, B])
        - tangent_xz is np.array([-B, A])

    Assumptions:
        Assumes plane is vertical (|b| is small, hypot(a, c) > 0).

    Failure conditions:
        Raises ValueError if hypot(a, c) < 1e-6 (plane is purely horizontal).

    Debugging:
        Check plane coefficients in Stage 2 structure.json if normalization fails.
    """
    a = float(plane.get("a", 0.0))
    c = float(plane.get("c", 0.0))
    d = float(plane.get("d", 0.0))

    norm = float(np.hypot(a, c))
    if norm < 1e-6:
        raise ValueError(
            f"Cannot project horizontal plane (a={a}, c={c}) to vertical 2D line."
        )

    A = a / norm
    B = c / norm
    C = d / norm

    normal_xz = np.array([A, B], dtype=np.float64)
    tangent_xz = np.array([-B, A], dtype=np.float64)

    return A, B, C, normal_xz, tangent_xz


def compute_finite_extents(
    origin_pt: np.ndarray,
    tangent_xz: np.ndarray,
    bounds: Dict[str, List[float]],
    wall_points_xz: Optional[np.ndarray] = None,
) -> Tuple[float, float, np.ndarray, np.ndarray, float]:
    """Determines observed finite endpoints and length of a wall segment.

    Purpose:
        Restricts an infinite 2D line to its observed physical bounds along its
        tangent direction, preventing candidate corners from forming far away.

    Parameters:
        origin_pt: np.ndarray([x0, z0]) closest point on line to origin.
        tangent_xz: np.ndarray([tx, tz]) unit tangent vector along line.
        bounds: Dictionary with 'x': [min, max] and 'z': [min, max].
        wall_points_xz: Optional (N, 2) array of inlier (x, z) points.

    Returns:
        (s_min, s_max, p_start, p_end, observed_length_m)
        where p_start and p_end are 2D coordinates [x, z].

    Assumptions:
        tangent_xz is a normalized unit vector.

    Failure conditions:
        Falls back to bounding box projection if wall_points_xz has fewer than 10 points.

    Debugging:
        If wall length is 0.0m, verify bounding box extents in structure.json.
    """
    if wall_points_xz is not None and len(wall_points_xz) >= 10:
        # Project inlier points onto tangent
        offsets = wall_points_xz - origin_pt
        projections = offsets @ tangent_xz
        s_min = float(np.percentile(projections, 1.0))
        s_max = float(np.percentile(projections, 99.0))
    else:
        # Fallback to bounding box corners
        bx = bounds.get("x", [0.0, 0.0])
        bz = bounds.get("z", [0.0, 0.0])
        corners = np.array([
            [bx[0], bz[0]],
            [bx[0], bz[1]],
            [bx[1], bz[0]],
            [bx[1], bz[1]],
        ], dtype=np.float64)
        offsets = corners - origin_pt
        projections = offsets @ tangent_xz
        s_min = float(np.min(projections))
        s_max = float(np.max(projections))

    if s_max < s_min:
        s_min, s_max = s_max, s_min

    p_start = origin_pt + s_min * tangent_xz
    p_end = origin_pt + s_max * tangent_xz
    observed_length_m = float(s_max - s_min)

    return s_min, s_max, p_start, p_end, observed_length_m


def project_walls_to_2d(
    accepted_walls: List[Dict[str, Any]],
    all_points_3d: Optional[np.ndarray] = None,
) -> List[Dict[str, Any]]:
    """Transforms a list of accepted 3D wall dicts into 2D projected wall records.

    Purpose:
        Prepares finite 2D wall representations for intersection calculation.

    Parameters:
        accepted_walls: List of validated wall dictionaries from wall_quality.
        all_points_3d: Optional (N, 3) point cloud array (e.g. from walls.ply).

    Returns:
        List of projected wall dicts containing:
        - wall_id, line_equation [A, B, C], normal, tangent,
        - start_pt, end_pt, length_m, s_min, s_max, inlier_count, rmse_m, confidence.

    Assumptions:
        Assumes accepted_walls contains 'plane', 'bounds', 'id'.

    Failure conditions:
        Returns empty list if accepted_walls is empty.

    Debugging:
        Check inspect_stage2_walls.py if projected lengths differ from visual model.
    """
    projected = []

    for w in accepted_walls:
        wall_id = w.get("id", "unknown_wall")
        plane = w.get("plane", {})
        bounds = w.get("bounds", {})

        A, B, C, normal_xz, tangent_xz = project_plane_to_2d_line(plane)
        origin_pt = np.array([-A * C, -B * C], dtype=np.float64)

        # Extract inlier points if available
        pts_xz = None
        if all_points_3d is not None and len(all_points_3d) > 0:
            a3, b3, c3, d3 = plane.get("a", 0.0), plane.get("b", 0.0), plane.get("c", 0.0), plane.get("d", 0.0)
            n3 = np.array([a3, b3, c3], dtype=np.float64)
            dists = np.abs(all_points_3d @ n3 + d3)
            bx = bounds.get("x", [-1e6, 1e6])
            bz = bounds.get("z", [-1e6, 1e6])
            mask = (
                (dists < 0.06) &
                (all_points_3d[:, 0] >= bx[0] - 0.15) &
                (all_points_3d[:, 0] <= bx[1] + 0.15) &
                (all_points_3d[:, 2] >= bz[0] - 0.15) &
                (all_points_3d[:, 2] <= bz[1] + 0.15)
            )
            sub_pts = all_points_3d[mask]
            if len(sub_pts) > 0:
                pts_xz = sub_pts[:, [0, 2]]

        s_min, s_max, p_start, p_end, length_m = compute_finite_extents(
            origin_pt=origin_pt,
            tangent_xz=tangent_xz,
            bounds=bounds,
            wall_points_xz=pts_xz,
        )

        projected.append({
            "wall_id": wall_id,
            "line": [float(A), float(B), float(C)],
            "normal": [float(normal_xz[0]), float(normal_xz[1])],
            "tangent": [float(tangent_xz[0]), float(tangent_xz[1])],
            "origin_pt": [float(origin_pt[0]), float(origin_pt[1])],
            "s_min": s_min,
            "s_max": s_max,
            "start": [float(p_start[0]), float(p_start[1])],
            "end": [float(p_end[0]), float(p_end[1])],
            "length_m": length_m,
            "inlier_count": int(w.get("inlier_count", 0)),
            "rmse_m": float(w.get("rmse_m", 0.0)),
            "confidence": float(w.get("confidence", 0.0)),
            "bounds": bounds,
            "merged_from": [wall_id],
        })

    return projected


def merge_near_duplicate_2d_lines(
    projected_walls: List[Dict[str, Any]],
    max_angle_deg: float = 8.0,
    max_offset_m: float = 0.15,
    max_gap_m: float = 0.35,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Defensively merges overlapping or nearly coplanar projected wall segments.

    Purpose:
        Consolidates fragmented wall segments belonging to the same physical
        architectural wall without merging opposite parallel room walls.

    Parameters:
        projected_walls: List of 2D projected wall dicts.
        max_angle_deg: Maximum angle difference in degrees between normals.
        max_offset_m: Maximum perpendicular distance between parallel lines.
        max_gap_m: Maximum gap along tangent to still consider segments contiguous.

    Returns:
        (merged_walls, merge_log) where merge_log details every merge action taken.

    Assumptions:
        Opposite room walls have perpendicular separation > max_offset_m (e.g. > 1.0m).

    Failure conditions:
        If max_offset_m is erroneously set > room_width (e.g. 2.5m), opposite walls
        will be incorrectly merged. Keep max_offset_m <= 0.20m.

    Debugging:
        Inspect merge_log to check why two walls were or were not merged.
    """
    merged_list: List[Dict[str, Any]] = []
    merge_log: List[Dict[str, Any]] = []

    # Sort descending by inlier count so dominant walls act as anchors
    sorted_walls = sorted(
        projected_walls, key=lambda w: w.get("inlier_count", 0), reverse=True
    )

    cos_thresh = float(np.cos(np.radians(max_angle_deg)))

    for candidate in sorted_walls:
        cand_norm = np.array(candidate["normal"], dtype=np.float64)
        cand_line = np.array(candidate["line"], dtype=np.float64)

        found_match = False
        for existing in merged_list:
            ex_norm = np.array(existing["normal"], dtype=np.float64)
            ex_line = np.array(existing["line"], dtype=np.float64)

            # Check normal alignment (accounting for potential sign flip)
            dot = float(cand_norm @ ex_norm)
            flip_sign = 1.0
            if dot < -cos_thresh:
                flip_sign = -1.0
                dot = -dot

            if dot < cos_thresh:
                continue  # Not parallel enough

            # Compute perpendicular offset between lines
            # Distance between Ax + Bz + C1 = 0 and Ax + Bz + C2 = 0 is |C1 - flip*C2|
            offset_dist = abs(ex_line[2] - flip_sign * cand_line[2])
            if offset_dist > max_offset_m:
                continue  # Too far apart (e.g. opposite room walls)

            # Check overlap or contiguity along the existing line tangent
            ex_tangent = np.array(existing["tangent"], dtype=np.float64)
            ex_origin = np.array(existing["origin_pt"], dtype=np.float64)

            # Project candidate endpoints onto existing line tangent
            cand_start = np.array(candidate["start"], dtype=np.float64)
            cand_end = np.array(candidate["end"], dtype=np.float64)
            s_cand_1 = float((cand_start - ex_origin) @ ex_tangent)
            s_cand_2 = float((cand_end - ex_origin) @ ex_tangent)
            c_smin, c_smax = min(s_cand_1, s_cand_2), max(s_cand_1, s_cand_2)

            e_smin, e_smax = existing["s_min"], existing["s_max"]

            # Overlap or close gap condition
            gap = max(0.0, max(e_smin - c_smax, c_smin - e_smax))
            if gap <= max_gap_m:
                # Merge candidate into existing
                found_match = True
                new_smin = min(e_smin, c_smin)
                new_smax = max(e_smax, c_smax)
                total_inliers = existing["inlier_count"] + candidate["inlier_count"]

                # Weighted line update
                w1 = existing["inlier_count"] / max(1, total_inliers)
                w2 = candidate["inlier_count"] / max(1, total_inliers)
                avg_A = w1 * ex_line[0] + w2 * (flip_sign * cand_line[0])
                avg_B = w1 * ex_line[1] + w2 * (flip_sign * cand_line[1])
                avg_C = w1 * ex_line[2] + w2 * (flip_sign * cand_line[2])
                norm_avg = float(np.hypot(avg_A, avg_B))
                avg_A /= norm_avg
                avg_B /= norm_avg
                avg_C /= norm_avg

                new_normal = np.array([avg_A, avg_B], dtype=np.float64)
                new_tangent = np.array([-avg_B, avg_A], dtype=np.float64)
                new_origin = np.array([-avg_A * avg_C, -avg_B * avg_C], dtype=np.float64)

                p_start = new_origin + new_smin * new_tangent
                p_end = new_origin + new_smax * new_tangent

                log_entry = {
                    "action": "merge",
                    "anchor_wall": existing["wall_id"],
                    "merged_wall": candidate["wall_id"],
                    "angle_diff_deg": float(np.degrees(np.arccos(min(1.0, dot)))),
                    "offset_dist_m": offset_dist,
                    "gap_m": gap,
                }
                merge_log.append(log_entry)

                existing["line"] = [float(avg_A), float(avg_B), float(avg_C)]
                existing["normal"] = [float(new_normal[0]), float(new_normal[1])]
                existing["tangent"] = [float(new_tangent[0]), float(new_tangent[1])]
                existing["origin_pt"] = [float(new_origin[0]), float(new_origin[1])]
                existing["s_min"] = new_smin
                existing["s_max"] = new_smax
                existing["start"] = [float(p_start[0]), float(p_start[1])]
                existing["end"] = [float(p_end[0]), float(p_end[1])]
                existing["length_m"] = float(new_smax - new_smin)
                existing["inlier_count"] = total_inliers
                existing["merged_from"].append(candidate["wall_id"])
                break

        if not found_match:
            merged_list.append(dict(candidate))

    return merged_list, merge_log
