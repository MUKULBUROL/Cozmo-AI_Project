"""Point cloud preprocessing and validation for structural geometry extraction."""

import os
from typing import Tuple, Optional
import numpy as np
import open3d as o3d


def load_and_validate_point_cloud(
    ply_path: str,
    voxel_size_m: Optional[float] = None,
    min_points: int = 1000,
) -> o3d.geometry.PointCloud:
    """Loads a metric point cloud and validates coordinates and dimensions.

    Args:
        ply_path: Path to the Stage 1 PLY file.
        voxel_size_m: Optional additional voxel downsampling in meters.
        min_points: Minimum expected points for a valid architectural scan.

    Returns:
        pcd: Validated Open3D PointCloud.
    """
    if not os.path.exists(ply_path):
        raise FileNotFoundError(f"Point cloud file not found: {ply_path}")

    pcd = o3d.io.read_point_cloud(ply_path)
    if pcd.is_empty():
        raise ValueError(f"Point cloud in {ply_path} is empty")

    points = np.asarray(pcd.points)
    if len(points) < min_points:
        raise ValueError(f"Insufficient points: {len(points)}, expected at least {min_points}")

    # Verify finite numbers
    if not np.all(np.isfinite(points)):
        raise ValueError("Point cloud contains NaN or Inf coordinates")

    # Verify realistic metric room bounds (between -50m and +50m)
    min_b = points.min(axis=0)
    max_b = points.max(axis=0)
    spans = max_b - min_b

    if np.any(spans > 50.0):
        raise ValueError(f"Point cloud bounds exceed realistic building scale: spans={spans} meters")

    if voxel_size_m is not None and voxel_size_m > 0:
        pcd = pcd.voxel_down_sample(voxel_size=voxel_size_m)

    return pcd
