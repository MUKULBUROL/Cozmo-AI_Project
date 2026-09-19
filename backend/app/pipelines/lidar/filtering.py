"""Point cloud filtering, confidence masking, voxel downsampling, and cleaning."""

from typing import Tuple, Dict, Any, Optional
import numpy as np


def filter_by_confidence(confidence: np.ndarray, min_confidence: int = 2) -> np.ndarray:
    """Generates a boolean mask selecting pixels with confidence >= min_confidence.

    ARKit confidence levels:
        0 = low
        1 = medium
        2 = high
    """
    return confidence >= min_confidence


def voxel_downsample(
    points: np.ndarray,
    colors: Optional[np.ndarray] = None,
    voxel_size_m: float = 0.02,
) -> Tuple[np.ndarray, Optional[np.ndarray]]:
    """Voxel downsampling using Open3D when available, with vectorized NumPy fallback.

    Args:
        points: (N, 3) float32 array of coordinates in meters.
        colors: Optional (N, 3) array of RGB colors in [0, 255] or [0, 1].
        voxel_size_m: Grid voxel cube edge length in meters.

    Returns:
        downsampled_points: (M, 3) float32 array.
        downsampled_colors: Optional (M, 3) array.
    """
    if len(points) == 0:
        return points, colors

    try:
        import open3d as o3d
        pcd = o3d.geometry.PointCloud()
        pcd.points = o3d.utility.Vector3dVector(points.astype(np.float64))
        if colors is not None:
            c_norm = colors.astype(np.float64)
            if c_norm.max() > 1.0:
                c_norm = c_norm / 255.0
            pcd.colors = o3d.utility.Vector3dVector(c_norm)

        pcd_down = pcd.voxel_down_sample(voxel_size=voxel_size_m)
        down_points = np.asarray(pcd_down.points, dtype=np.float32)
        if colors is not None and pcd_down.has_colors():
            down_colors = (np.asarray(pcd_down.colors) * 255.0).astype(np.uint8)
        else:
            down_colors = None
        return down_points, down_colors

    except ImportError:
        # Fast NumPy voxel grid binning
        voxel_indices = np.floor(points / voxel_size_m).astype(np.int64)
        # Unique voxel keys
        keys, inv_indices = np.unique(voxel_indices, axis=0, return_inverse=True)
        # Compute centroid per unique voxel
        counts = np.bincount(inv_indices)
        sum_x = np.bincount(inv_indices, weights=points[:, 0])
        sum_y = np.bincount(inv_indices, weights=points[:, 1])
        sum_z = np.bincount(inv_indices, weights=points[:, 2])

        down_points = np.stack([sum_x / counts, sum_y / counts, sum_z / counts], axis=-1).astype(np.float32)

        if colors is not None:
            sum_r = np.bincount(inv_indices, weights=colors[:, 0])
            sum_g = np.bincount(inv_indices, weights=colors[:, 1])
            sum_b = np.bincount(inv_indices, weights=colors[:, 2])
            down_colors = np.stack([sum_r / counts, sum_g / counts, sum_b / counts], axis=-1).astype(np.uint8)
        else:
            down_colors = None

        return down_points, down_colors


def remove_statistical_outliers(
    points: np.ndarray,
    colors: Optional[np.ndarray] = None,
    nb_neighbors: int = 20,
    std_ratio: float = 2.0,
) -> Tuple[np.ndarray, Optional[np.ndarray]]:
    """Removes sparse outlier points using Open3D statistical outlier filter."""
    if len(points) < nb_neighbors:
        return points, colors

    try:
        import open3d as o3d
        pcd = o3d.geometry.PointCloud()
        pcd.points = o3d.utility.Vector3dVector(points.astype(np.float64))
        if colors is not None:
            c_norm = colors.astype(np.float64)
            if c_norm.max() > 1.0:
                c_norm = c_norm / 255.0
            pcd.colors = o3d.utility.Vector3dVector(c_norm)

        cl, ind = pcd.remove_statistical_outlier(nb_neighbors=nb_neighbors, std_ratio=std_ratio)
        inlier_points = points[ind]
        inlier_colors = colors[ind] if colors is not None else None
        return inlier_points, inlier_colors
    except ImportError:
        # If open3d is not available, pass through without destructive alteration
        return points, colors
