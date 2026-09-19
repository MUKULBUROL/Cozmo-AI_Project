"""Rigid camera-to-world coordinate transformations for ARKit odometry."""

import numpy as np
from backend.app.models.capture import Pose6D


def quaternion_to_rotation_matrix(qx: float, qy: float, qz: float, qw: float) -> np.ndarray:
    """Converts a unit quaternion [qx, qy, qz, qw] to a 3x3 orthonormal rotation matrix.

    Follows Hamilton convention matching ARKit / iOS CoreMotion.
    """
    norm = np.sqrt(qx * qx + qy * qy + qz * qz + qw * qw)
    if norm == 0.0:
        return np.eye(3, dtype=np.float32)

    qx, qy, qz, qw = qx / norm, qy / norm, qz / norm, qw / norm

    # Precalculate products
    xx, yy, zz = qx * qx, qy * qy, qz * qz
    xy, xz, yz = qx * qy, qx * qz, qy * qz
    wx, wy, wz = qw * qx, qw * qy, qw * qz

    R = np.array([
        [1.0 - 2.0 * (yy + zz), 2.0 * (xy - wz),       2.0 * (xz + wy)],
        [2.0 * (xy + wz),       1.0 - 2.0 * (xx + zz), 2.0 * (yz - wx)],
        [2.0 * (xz - wy),       2.0 * (yz + wx),       1.0 - 2.0 * (xx + yy)],
    ], dtype=np.float32)
    return R


def pose_to_matrix(pose: Pose6D) -> np.ndarray:
    """Constructs a 4x4 homogeneous transformation matrix T_world_cam from Pose6D."""
    T = np.eye(4, dtype=np.float32)
    T[:3, :3] = quaternion_to_rotation_matrix(pose.qx, pose.qy, pose.qz, pose.qw)
    T[:3, 3] = [pose.x, pose.y, pose.z]
    return T


def transform_camera_to_world(points_cam: np.ndarray, pose: Pose6D) -> np.ndarray:
    """Transforms an (N, 3) array of camera-space points into world coordinates.

    Formula:
        P_world = R * P_cam + t
    """
    if len(points_cam) == 0:
        return np.empty((0, 3), dtype=np.float32)

    R = quaternion_to_rotation_matrix(pose.qx, pose.qy, pose.qz, pose.qw)
    t = np.array([pose.x, pose.y, pose.z], dtype=np.float32)

    points_world = (points_cam @ R.T) + t
    return points_world.astype(np.float32)
