"""Iterative RANSAC plane fitting on 3D point cloud subsets."""

from dataclasses import dataclass
from typing import List, Tuple, Optional
import numpy as np
import open3d as o3d

from .metrics import compute_plane_residuals


@dataclass
class DetectedPlane:
    plane_model: List[float]  # [a, b, c, d] normalized
    inlier_indices: np.ndarray  # Indices relative to the input cloud
    inlier_points: np.ndarray  # (M, 3) point coordinates
    inlier_count: int
    mean_residual_m: float
    rmse_m: float


def fit_single_plane_ransac(
    pcd: o3d.geometry.PointCloud,
    distance_threshold_m: float = 0.03,
    ransac_n: int = 3,
    num_iterations: int = 1000,
) -> Optional[Tuple[List[float], np.ndarray]]:
    """Fits a single plane using RANSAC on Open3D PointCloud.

    Returns:
        (plane_model, inlier_indices) or None if insufficient points.
    """
    if len(pcd.points) < ransac_n:
        return None

    plane_model, inliers = pcd.segment_plane(
        distance_threshold=distance_threshold_m,
        ransac_n=ransac_n,
        num_iterations=num_iterations,
    )

    a, b, c, d = plane_model
    norm = np.sqrt(a * a + b * b + c * c)
    if norm > 0:
        a, b, c, d = a / norm, b / norm, c / norm, d / norm

    return [float(a), float(b), float(c), float(d)], np.array(inliers, dtype=np.int64)


def extract_planes_iterative(
    pcd: o3d.geometry.PointCloud,
    distance_threshold_m: float = 0.03,
    min_inliers: int = 3000,
    max_planes: int = 12,
    num_iterations: int = 1000,
) -> Tuple[List[DetectedPlane], o3d.geometry.PointCloud]:
    """Iteratively segments dominant planes from point cloud via RANSAC.

    Returns:
        detected_planes: List of DetectedPlane objects.
        remaining_pcd: PointCloud containing points not belonging to any extracted plane.
    """
    current_pcd = pcd
    all_points = np.asarray(pcd.points)
    global_indices = np.arange(len(all_points))

    detected_planes: List[DetectedPlane] = []

    for _ in range(max_planes):
        if len(current_pcd.points) < min_inliers:
            break

        res = fit_single_plane_ransac(
            pcd=current_pcd,
            distance_threshold_m=distance_threshold_m,
            ransac_n=3,
            num_iterations=num_iterations,
        )
        if res is None:
            break

        plane_model, local_inliers = res
        if len(local_inliers) < min_inliers:
            break

        # Map local inlier indices back to original cloud indices
        mapped_global_inliers = global_indices[local_inliers]
        inlier_pts = all_points[mapped_global_inliers]

        mean_res, rmse = compute_plane_residuals(plane_model, inlier_pts)

        plane = DetectedPlane(
            plane_model=plane_model,
            inlier_indices=mapped_global_inliers,
            inlier_points=inlier_pts,
            inlier_count=len(inlier_pts),
            mean_residual_m=round(mean_res, 4),
            rmse_m=round(rmse, 4),
        )
        detected_planes.append(plane)

        # Remove inliers and update remaining points
        mask_remain = np.ones(len(current_pcd.points), dtype=bool)
        mask_remain[local_inliers] = False

        global_indices = global_indices[mask_remain]
        current_pcd = current_pcd.select_by_index(local_inliers, invert=True)

    return detected_planes, current_pcd
