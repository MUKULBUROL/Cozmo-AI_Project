"""Classification, heuristics, filtering, and merging of architectural planes."""

from typing import List, Tuple, Optional, Dict, Any
import numpy as np

from .plane_detection import DetectedPlane
from .metrics import compute_plane_residuals, compute_plane_bounds_and_spans


def ensure_normal_orientation(plane_model: List[float], desired_axis: int, positive: bool = True) -> List[float]:
    """Ensures normal component along desired_axis has the desired sign."""
    a, b, c, d = plane_model
    comp = [a, b, c][desired_axis]
    if (positive and comp < 0) or (not positive and comp > 0):
        return [-a, -b, -c, -d]
    return [a, b, c, d]


def classify_floor(
    horizontal_planes: List[DetectedPlane],
    vertical_axis: int = 1,
) -> Optional[DetectedPlane]:
    """Detects the floor plane: the lowest dominant horizontal structural plane."""
    if not horizontal_planes:
        return None

    # Filter planes that are truly horizontal: normal along Y > 0.85
    candidates = []
    for p in horizontal_planes:
        norm_y = abs(p.plane_model[vertical_axis])
        if norm_y >= 0.85:
            mean_y = float(np.mean(p.inlier_points[:, vertical_axis]))
            candidates.append((mean_y, p))

    if not candidates:
        return None

    # Sort by height ascending (lowest first)
    candidates.sort(key=lambda x: x[0])
    lowest_y, floor_plane = candidates[0]

    # Orient normal pointing upward (+Y)
    floor_plane.plane_model = ensure_normal_orientation(floor_plane.plane_model, desired_axis=1, positive=True)
    return floor_plane


def classify_ceiling(
    horizontal_planes: List[DetectedPlane],
    floor_plane: Optional[DetectedPlane],
    min_ceiling_height_m: float = 1.8,
    vertical_axis: int = 1,
) -> Tuple[Optional[DetectedPlane], Optional[str]]:
    """Detects the ceiling plane: dominant upper horizontal structural plane significantly above floor."""
    if floor_plane is None:
        return None, "Floor plane not detected; cannot establish ceiling height baseline"

    floor_y = float(np.mean(floor_plane.inlier_points[:, vertical_axis]))
    min_required_y = floor_y + min_ceiling_height_m

    upper_candidates = []
    for p in horizontal_planes:
        if p is floor_plane:
            continue
        norm_y = abs(p.plane_model[vertical_axis])
        if norm_y >= 0.85:
            mean_y = float(np.mean(p.inlier_points[:, vertical_axis]))
            if mean_y >= min_required_y and p.inlier_count >= 3000:
                upper_candidates.append((mean_y, p))

    if not upper_candidates:
        return None, "Insufficient upper horizontal points observed in scan (ceiling unobserved)"

    upper_candidates.sort(key=lambda x: x[0], reverse=True)
    _, ceiling_plane = upper_candidates[0]

    # Orient normal pointing downward (-Y) towards room interior
    ceiling_plane.plane_model = ensure_normal_orientation(ceiling_plane.plane_model, desired_axis=1, positive=False)
    return ceiling_plane, None


def filter_wall_candidates(
    vertical_planes: List[DetectedPlane],
    floor_y: Optional[float] = None,
    min_inliers: int = 4000,
    min_height_span_m: float = 0.70,
    min_horizontal_span_m: float = 0.70,
    max_floor_gap_m: float = 0.45,
    vertical_axis: int = 1,
) -> Tuple[List[DetectedPlane], List[Dict[str, Any]]]:
    """Applies architectural geometric heuristics to separate real walls from furniture clutter."""
    accepted = []
    rejected_log = []

    for idx, plane in enumerate(vertical_planes):
        pts = plane.inlier_points
        spans = compute_plane_bounds_and_spans(pts)["spans"]
        min_y = float(pts[:, vertical_axis].min())
        height_span = spans["height_y"]
        horiz_span = float(np.sqrt(spans["width_x"] ** 2 + spans["depth_z"] ** 2))

        # Check inliers
        if plane.inlier_count < min_inliers:
            rejected_log.append({
                "plane_index": idx,
                "reason": f"Insufficient inliers: {plane.inlier_count} < {min_inliers}",
            })
            continue

        # Check vertical height span
        if height_span < min_height_span_m:
            rejected_log.append({
                "plane_index": idx,
                "reason": f"Height span too short for wall: {height_span:.2f}m < {min_height_span_m}m (furniture/cabinet)",
            })
            continue

        # Check horizontal span
        if horiz_span < min_horizontal_span_m:
            rejected_log.append({
                "plane_index": idx,
                "reason": f"Horizontal span too narrow: {horiz_span:.2f}m < {min_horizontal_span_m}m",
            })
            continue

        # Check proximity to floor
        if floor_y is not None:
            dist_to_floor = min_y - floor_y
            if dist_to_floor > max_floor_gap_m:
                rejected_log.append({
                    "plane_index": idx,
                    "reason": f"Floating surface: bottom {dist_to_floor:.2f}m above floor (hanging cabinet or artwork)",
                })
                continue

        accepted.append(plane)

    return accepted, rejected_log


def merge_parallel_walls(
    wall_planes: List[DetectedPlane],
    angular_thresh_deg: float = 12.0,
    distance_thresh_m: float = 0.18,
) -> List[DetectedPlane]:
    """Merges duplicate RANSAC plane fragments belonging to the same continuous wall surface."""
    if len(wall_planes) <= 1:
        return wall_planes

    merged: List[DetectedPlane] = []
    cos_thresh = np.cos(np.radians(angular_thresh_deg))

    normalized_planes = []
    for p in wall_planes:
        a, b, c, d = p.plane_model
        norm_h = np.sqrt(a * a + c * c)
        if norm_h > 0:
            a, b, c, d = a / norm_h, 0.0, c / norm_h, d / norm_h
        if a < 0 or (abs(a) < 1e-4 and c < 0):
            a, b, c, d = -a, -b, -c, -d
        p_copy = DetectedPlane(
            plane_model=[float(a), float(b), float(c), float(d)],
            inlier_indices=p.inlier_indices,
            inlier_points=p.inlier_points,
            inlier_count=p.inlier_count,
            mean_residual_m=p.mean_residual_m,
            rmse_m=p.rmse_m,
        )
        normalized_planes.append(p_copy)

    used = [False] * len(normalized_planes)

    for i in range(len(normalized_planes)):
        if used[i]:
            continue

        current = normalized_planes[i]
        used[i] = True
        merged_inliers = [current.inlier_points]
        merged_indices = [current.inlier_indices]

        n1 = np.array([current.plane_model[0], current.plane_model[2]])

        for j in range(i + 1, len(normalized_planes)):
            if used[j]:
                continue
            cand = normalized_planes[j]
            n2 = np.array([cand.plane_model[0], cand.plane_model[2]])

            dot_prod = float(np.dot(n1, n2))
            if dot_prod >= cos_thresh:
                d_diff = abs(current.plane_model[3] - cand.plane_model[3])
                if d_diff <= distance_thresh_m:
                    used[j] = True
                    merged_inliers.append(cand.inlier_points)
                    merged_indices.append(cand.inlier_indices)

        combined_pts = np.concatenate(merged_inliers, axis=0)
        combined_indices = np.concatenate(merged_indices, axis=0)
        centroid = combined_pts.mean(axis=0)

        # 3x3 covariance matrix fitting (fast and memory-free)
        centered = combined_pts - centroid
        cov = centered.T @ centered  # (3, 3) matrix
        eigvals, eigvecs = np.linalg.eigh(cov)
        normal = eigvecs[:, 0]  # Smallest eigenvalue corresponds to normal

        # Project normal to horizontal plane (wall vertical b = 0)
        norm_h = np.sqrt(normal[0] ** 2 + normal[2] ** 2)
        if norm_h > 0:
            a = float(normal[0] / norm_h)
            b = 0.0
            c = float(normal[2] / norm_h)
            d = -float(a * centroid[0] + c * centroid[2])
        else:
            a, b, c, d = current.plane_model

        mean_res, rmse = compute_plane_residuals([a, b, c, d], combined_pts)

        merged_plane = DetectedPlane(
            plane_model=[round(a, 4), round(b, 4), round(c, 4), round(d, 4)],
            inlier_indices=combined_indices,
            inlier_points=combined_pts,
            inlier_count=len(combined_pts),
            mean_residual_m=round(mean_res, 4),
            rmse_m=round(rmse, 4),
        )
        merged.append(merged_plane)

    merged.sort(key=lambda p: p.inlier_count, reverse=True)
    return merged
