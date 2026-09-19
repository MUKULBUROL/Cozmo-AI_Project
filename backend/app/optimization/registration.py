"""Stage 6 Geometric ICP Registration.

1. Why this file exists:
    Estimates metric relative alignment between two keyframe point clouds using
    Point-to-Plane Iterative Closest Point (ICP), computing fitness, inlier RMSE,
    and the 6x6 information matrix for pose graph optimization.

2. Pipeline stage:
    Stage 6 — Geometric Registration.

3. Inputs:
    Source keyframe node i, target keyframe node j, and coarse initial transform.

4. Outputs:
    RegistrationResult containing optimized relative transform, fitness score,
    RMSE in meters, inlier count, and Hessian information matrix.

5. Coordinate conventions:
    Open3D PoseGraph convention:
    Transformation maps source point cloud (frame i) into target frame j: P_j = T_ij @ P_i.
    Units in meters (m).

6. Unit assumptions:
    Distances in meters, angles in radians.

7. Important dependencies:
    open3d, numpy, backend.app.optimization.keyframes, backend.app.optimization.odometry_edges.

8. What is most likely to break:
    Target point cloud missing surface normals causing Point-to-Plane ICP to abort.

9. What a developer should inspect first:
    Inspect registration fitness (> 0.5) and inlier_rmse (< 0.05m).
"""

from dataclasses import dataclass
from typing import Optional, Tuple
import numpy as np
import open3d as o3d

from backend.app.optimization.keyframes import KeyframeNode
from backend.app.optimization.odometry_edges import compute_relative_transform


@dataclass
class RegistrationResult:
    """Stores quantitative metrics and matrices resulting from ICP registration.

    Attributes:
        node_i: Source node ID.
        node_j: Target node ID.
        fitness: Fraction of source points having correspondences within distance threshold (0.0 to 1.0).
        inlier_rmse: Root Mean Square Error of inlier point-to-plane residual distances in meters.
        correspondence_count: Total number of valid point correspondences.
        initial_transform: 4x4 coarse transformation matrix (from odometry).
        optimized_transform: 4x4 refined transformation matrix from ICP.
        information_matrix: 6x6 information matrix for the pose graph constraint.
        translation_delta_m: Magnitude of translation shift induced by ICP relative to odometry.
        rotation_delta_deg: Angular shift induced by ICP relative to odometry.
    """
    node_i: int
    node_j: int
    fitness: float
    inlier_rmse: float
    correspondence_count: int
    initial_transform: np.ndarray
    optimized_transform: np.ndarray
    information_matrix: np.ndarray
    translation_delta_m: float
    rotation_delta_deg: float


def compute_transformation_delta(T_init: np.ndarray, T_opt: np.ndarray) -> Tuple[float, float]:
    """Calculates translation distance and rotation angle between initial and refined transforms.

    Purpose:
        Quantifies how far ICP drifted from the odometry prior to detect unconstrained slips.

    Parameters:
        T_init: Initial 4x4 transformation matrix.
        T_opt: Refined 4x4 transformation matrix.

    Returns:
        Tuple of (translation_delta_m, rotation_delta_deg).

    Assumptions:
        Homogeneous 4x4 matrices.

    Failure conditions:
        Numerical instability in arccos clamped safely.

    Debugging:
        Translation delta > 0.6 m usually signifies an erroneous slip along planar features.
    """
    t_init = T_init[:3, 3]
    t_opt = T_opt[:3, 3]
    trans_delta = float(np.linalg.norm(t_opt - t_init))

    R_init = T_init[:3, :3]
    R_opt = T_opt[:3, :3]
    R_diff = R_opt @ R_init.T
    trace = np.trace(R_diff)
    cos_val = np.clip((trace - 1.0) / 2.0, -1.0, 1.0)
    rot_delta_deg = float(np.degrees(np.arccos(cos_val)))

    return trans_delta, rot_delta_deg


def register_loop_candidate(
    node_i: KeyframeNode,
    node_j: KeyframeNode,
    max_correspondence_distance_m: float = 0.20,
    max_icp_iterations: int = 40,
) -> Optional[RegistrationResult]:
    """Performs Point-to-Plane ICP registration between keyframe point clouds.

    Purpose:
        Refines the relative pose between two candidate loop keyframes using physical geometry.

    Parameters:
        node_i: Source KeyframeNode.
        node_j: Target KeyframeNode.
        max_correspondence_distance_m: Maximum point pairing distance in meters.
        max_icp_iterations: Maximum solver iterations.

    Returns:
        RegistrationResult object if clouds are valid, or None if point clouds are missing.

    Assumptions:
        node_i.local_pcd and node_j.local_pcd contain points in their respective camera frames.

    Failure conditions:
        Returns None if point clouds have fewer than 20 points.

    Debugging:
        Check target cloud normals; if missing, falls back to Point-to-Point ICP.
    """
    if node_i.local_pcd is None or node_j.local_pcd is None:
        return None

    pcd_source = node_i.local_pcd
    pcd_target = node_j.local_pcd

    if len(pcd_source.points) < 20 or len(pcd_target.points) < 20:
        return None

    # Initial transform from odometry: T_ij = inv(T_j) @ T_i
    T_init = compute_relative_transform(node_i.matrix, node_j.matrix)

    # Ensure target has normals for point-to-plane
    if not pcd_target.has_normals():
        pcd_target.estimate_normals(
            search_param=o3d.geometry.KDTreeSearchParamHybrid(radius=0.2, max_nn=30)
        )

    # Configure Point-to-Plane estimation
    estimation_method = o3d.pipelines.registration.TransformationEstimationPointToPlane()
    criteria = o3d.pipelines.registration.ICPConvergenceCriteria(
        max_iteration=max_icp_iterations,
        relative_fitness=1e-6,
        relative_rmse=1e-6,
    )

    reg = o3d.pipelines.registration.registration_icp(
        source=pcd_source,
        target=pcd_target,
        max_correspondence_distance=max_correspondence_distance_m,
        init=T_init,
        estimation_method=estimation_method,
        criteria=criteria,
    )

    # Compute 6x6 information matrix
    info_matrix = o3d.pipelines.registration.get_information_matrix_from_point_clouds(
        source=pcd_source,
        target=pcd_target,
        max_correspondence_distance=max_correspondence_distance_m,
        transformation=reg.transformation,
    )

    # If information matrix is degenerate or singular, use regularized identity
    if np.any(np.isnan(info_matrix)) or np.linalg.cond(info_matrix + 1e-4 * np.eye(6)) > 1e7:
        info_matrix = np.eye(6, dtype=np.float64) * (reg.fitness * 100.0)

    trans_delta, rot_delta = compute_transformation_delta(T_init, reg.transformation)

    return RegistrationResult(
        node_i=node_i.node_id,
        node_j=node_j.node_id,
        fitness=float(reg.fitness),
        inlier_rmse=float(reg.inlier_rmse),
        correspondence_count=len(reg.correspondence_set),
        initial_transform=T_init,
        optimized_transform=np.array(reg.transformation, dtype=np.float64),
        information_matrix=np.array(info_matrix, dtype=np.float64),
        translation_delta_m=round(trans_delta, 4),
        rotation_delta_deg=round(rot_delta, 2),
    )
