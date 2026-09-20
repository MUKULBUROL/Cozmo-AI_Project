"""Iterative RANSAC plane fitting on 3D point cloud subsets.

1. Purpose:
    Extracts dominant geometric planes from 3D point clouds via iterative RANSAC
    segmentation. Supports deterministic random seeding to guarantee identical plane
    equations and inlier indices across repeated runs.

2. Stage:
    Stage 2 (Architectural Structural Plane Extraction) & Stage 10.2 (Deterministic Baseline).

3. Inputs:
    Open3D PointCloud object, distance threshold in meters, minimum inlier count,
    maximum plane iterations, RANSAC sampling size, and optional deterministic seed.

4. Outputs:
    DetectedPlane dataclasses containing normalized plane models [a, b, c, d],
    inlier indices mapped to original point cloud coordinates, inlier point arrays,
    and residual statistics (mean residual and RMSE).

5. Coordinate systems / units:
    Metric units (meters). Normalized plane equation: a*x + b*y + c*z + d = 0, with ||(a, b, c)|| = 1.

6. Dependencies:
    dataclasses, typing, numpy, open3d, backend.app.core.determinism.configure_determinism,
    backend.app.geometry.metrics.compute_plane_residuals.

7. Assumptions:
    Input point cloud points are in metric Cartesian coordinates.
    Norm of plane normal [a, b, c] is strictly non-zero.

8. Failure modes:
    Insufficient points (< ransac_n) returns None or empty plane list.
    Collinear or degenerate points fail to form a valid 3D plane.

9. First debugging points:
    Verify len(pcd.points) >= ransac_n. Inspect distance_threshold_m relative to point cloud noise.
"""

from dataclasses import dataclass
from typing import List, Tuple, Optional
import numpy as np
import open3d as o3d

from backend.app.core import configure_determinism
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
    seed: Optional[int] = None,
) -> Optional[Tuple[List[float], np.ndarray]]:
    """Fits a single plane using RANSAC on Open3D PointCloud.

    Purpose:
        Executes Open3D segment_plane with optional deterministic RNG configuration,
        normalizing the resulting plane model coefficients.

    Parameters:
        pcd: o3d.geometry.PointCloud
            Input point cloud to segment.
        distance_threshold_m: float
            Maximum distance (in meters) from plane for a point to be considered an inlier.
        ransac_n: int
            Number of initial sample points to fit a candidate plane (default: 3).
        num_iterations: int
            Number of RANSAC random sample iterations (default: 1000).
        seed: Optional[int]
            Optional random seed to initialize Open3D and NumPy RNG before RANSAC.

    Returns:
        Optional[Tuple[List[float], np.ndarray]]:
            Tuple of ([a, b, c, d] normalized plane equation, array of inlier indices),
            or None if input point cloud contains fewer than ransac_n points.

    Units / coordinates:
        Metric coordinates (meters). Plane normal is normalized to unit length.

    Assumptions:
        Input point cloud is non-empty and contains 3D coordinates.

    Failure conditions:
        Returns None if len(pcd.points) < ransac_n.

    Dependencies:
        open3d.geometry.PointCloud.segment_plane, backend.app.core.configure_determinism, numpy.

    Debugging clues:
        Check len(pcd.points); inspect distance_threshold_m if 0 inliers are returned.
    """
    if len(pcd.points) < ransac_n:
        return None

    if seed is not None:
        configure_determinism(seed)

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
    seed: Optional[int] = None,
) -> Tuple[List[DetectedPlane], o3d.geometry.PointCloud]:
    """Iteratively segments dominant planes from point cloud via RANSAC.

    Purpose:
        Iteratively fits candidate planes, records quality metrics, strips inlier points,
        and repeats until minimum inlier threshold or maximum plane count is reached.

    Parameters:
        pcd: o3d.geometry.PointCloud
            Input metric point cloud.
        distance_threshold_m: float
            Maximum distance threshold in meters for inlier classification.
        min_inliers: int
            Minimum number of inliers required to accept a plane candidate.
        max_planes: int
            Maximum number of sequential planes to extract.
        num_iterations: int
            RANSAC iteration count per plane search.
        seed: Optional[int]
            Optional seed to initialize RNG before starting iterative extraction.

    Returns:
        Tuple[List[DetectedPlane], o3d.geometry.PointCloud]:
            List of accepted DetectedPlane objects and remaining unclassified point cloud.

    Units / coordinates:
        Metric units (meters). Residuals in meters.

    Assumptions:
        Input point cloud coordinates are metric meters.

    Failure conditions:
        Returns empty list if input has fewer points than min_inliers.

    Dependencies:
        fit_single_plane_ransac, compute_plane_residuals, open3d, numpy.

    Debugging clues:
        Inspect min_inliers; verify that remaining point cloud is properly reduced after each step.
    """
    if seed is not None:
        configure_determinism(seed)
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
