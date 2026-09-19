"""Surface normal estimation and orientation analysis for structural segmentation."""

from typing import Tuple
import numpy as np
import open3d as o3d


def estimate_point_normals(
    pcd: o3d.geometry.PointCloud,
    radius_m: float = 0.10,
    max_nn: int = 30,
) -> np.ndarray:
    """Estimates surface normals for each point using a local KDTree hybrid neighborhood.

    Args:
        pcd: Open3D PointCloud.
        radius_m: Neighborhood search radius in meters.
        max_nn: Maximum number of nearest neighbors.

    Returns:
        normals: (N, 3) float64 array of unit normals.
    """
    search_param = o3d.geometry.KDTreeSearchParamHybrid(radius=radius_m, max_nn=max_nn)
    pcd.estimate_normals(search_param=search_param)
    normals = np.asarray(pcd.normals)
    return normals


def split_horizontal_vertical_masks(
    normals: np.ndarray,
    vertical_axis: int = 1,
    horizontal_thresh: float = 0.80,
    vertical_thresh: float = 0.25,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Splits points into horizontal, vertical, and oblique categories based on normal alignment.

    In ARKit coordinates (Y-up):
        vertical_axis = 1 (Y).
        Horizontal plane (floor/ceiling): normal aligns with Y -> |n_y| > horizontal_thresh.
        Vertical plane (walls): normal perpendicular to Y -> |n_y| < vertical_thresh.

    Returns:
        is_horizontal: Boolean mask of horizontal surface points.
        is_vertical: Boolean mask of vertical surface points.
        is_oblique: Boolean mask of remaining points.
    """
    ny = np.abs(normals[:, vertical_axis])
    is_horizontal = ny >= horizontal_thresh
    is_vertical = ny <= vertical_thresh
    is_oblique = ~(is_horizontal | is_vertical)
    return is_horizontal, is_vertical, is_oblique
