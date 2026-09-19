"""Depth unprojection logic converting 2D depth pixels into 3D camera-space coordinates."""

from typing import Tuple, Optional
import numpy as np
from backend.app.models.capture import CameraIntrinsics


def unproject_depth(
    depth_mm: np.ndarray,
    intrinsics: CameraIntrinsics,
    min_depth_m: float = 0.2,
    max_depth_m: float = 5.0,
    valid_mask: Optional[np.ndarray] = None,
) -> Tuple[np.ndarray, np.ndarray]:
    """Unprojects depth map from millimeters into 3D metric points in camera space.

    Formula:
        Z = depth_mm / 1000.0 (meters)
        X = (u - cx) * Z / fx
        Y = (v - cy) * Z / fy

    Args:
        depth_mm: 2D uint16 array of depth values in millimeters.
        intrinsics: Scaled camera intrinsics matching depth map resolution.
        min_depth_m: Minimum allowed depth in meters (discard closer).
        max_depth_m: Maximum allowed depth in meters (discard farther).
        valid_mask: Optional boolean mask (e.g. from confidence filter) of shape (H, W).

    Returns:
        points_cam: (N, 3) float32 array of [X, Y, Z] points in camera coordinates (meters).
        valid_indices: (N, 2) int32 array of [v, u] coordinates of the selected pixels.
    """
    if depth_mm.ndim != 2:
        raise ValueError(f"Expected 2D depth array, got shape {depth_mm.shape}")

    # Explicit millimeter -> meter conversion
    depth_m = depth_mm.astype(np.float32) / 1000.0

    # Build validity mask
    range_mask = (depth_m >= min_depth_m) & (depth_m <= max_depth_m)
    if valid_mask is not None:
        total_mask = range_mask & valid_mask
    else:
        total_mask = range_mask

    if not np.any(total_mask):
        return np.empty((0, 3), dtype=np.float32), np.empty((0, 2), dtype=np.int32)

    H, W = depth_mm.shape
    u_grid, v_grid = np.meshgrid(np.arange(W, dtype=np.float32), np.arange(H, dtype=np.float32))

    u_valid = u_grid[total_mask]
    v_valid = v_grid[total_mask]
    z_valid = depth_m[total_mask]

    x_valid = (u_valid - intrinsics.cx) * z_valid / intrinsics.fx
    y_valid = (v_valid - intrinsics.cy) * z_valid / intrinsics.fy

    points_cam = np.stack([x_valid, y_valid, z_valid], axis=-1).astype(np.float32)
    v_idx = np.where(total_mask)[0].astype(np.int32)
    u_idx = np.where(total_mask)[1].astype(np.int32)
    valid_indices = np.stack([v_idx, u_idx], axis=-1)

    return points_cam, valid_indices
