"""Metrics and quality estimation for detected structural planes."""

from typing import Tuple, Dict, Any, List
import numpy as np


def compute_plane_residuals(plane: List[float], points: np.ndarray) -> Tuple[float, float]:
    """Computes mean residual and RMSE of points to plane ax + by + cz + d = 0.

    Returns:
        mean_residual_m: Average absolute distance in meters.
        rmse_m: Root-mean-squared error in meters.
    """
    if len(points) == 0:
        return 0.0, 0.0

    a, b, c, d = plane
    norm = np.sqrt(a * a + b * b + c * c)
    if norm == 0.0:
        return 0.0, 0.0

    distances = np.abs(points[:, 0] * a + points[:, 1] * b + points[:, 2] * c + d) / norm
    mean_residual = float(np.mean(distances))
    rmse = float(np.sqrt(np.mean(distances ** 2)))
    return mean_residual, rmse


def compute_plane_bounds_and_spans(points: np.ndarray) -> Dict[str, Any]:
    """Computes 3D centroid, bounding box, and metric spans."""
    if len(points) == 0:
        return {
            "centroid": [0.0, 0.0, 0.0],
            "bounds": {"x": [0.0, 0.0], "y": [0.0, 0.0], "z": [0.0, 0.0]},
            "spans": {"width_x": 0.0, "height_y": 0.0, "depth_z": 0.0},
        }

    min_b = points.min(axis=0)
    max_b = points.max(axis=0)
    spans = max_b - min_b
    centroid = points.mean(axis=0)

    return {
        "centroid": [round(float(x), 4) for x in centroid],
        "bounds": {
            "x": [round(float(min_b[0]), 3), round(float(max_b[0]), 3)],
            "y": [round(float(min_b[1]), 3), round(float(max_b[1]), 3)],
            "z": [round(float(min_b[2]), 3), round(float(max_b[2]), 3)],
        },
        "spans": {
            "width_x": round(float(spans[0]), 3),
            "height_y": round(float(spans[1]), 3),
            "depth_z": round(float(spans[2]), 3),
        },
    }


def compute_plane_confidence(
    inlier_count: int,
    rmse_m: float,
    expected_inliers: int = 15000,
    max_rmse_thresh: float = 0.03,
) -> float:
    """Calculates an empirical quality confidence score in [0.1, 1.0].

    Formulation:
        confidence = support_factor * residual_factor
    """
    support_score = np.clip(inlier_count / expected_inliers, 0.1, 1.0)
    residual_score = np.clip(1.0 - (rmse_m / max_rmse_thresh), 0.1, 1.0)
    confidence = float(np.clip(0.6 * support_score + 0.4 * residual_score, 0.10, 0.99))
    return round(confidence, 3)
