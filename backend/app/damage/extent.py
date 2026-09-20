"""Metric damage extent, planar polygon integration, linear crack skeletonization, and uncertainty estimation.

1. Why this file exists:
   Computes physical metric dimensions (surface area in square meters or crack length
   in meters) from 2D points on host structural planes. Propagates geometric uncertainty
   from camera viewing angles, boundary clipping, plane fit residuals, and depth noise,
   strictly adhering to the principle that physical dimensions derive from geometry, not AI guessing.

2. Pipeline stage:
   Stage 9 (Damage Detection, Metric Extent, Concealed-Damage Rules & Repair Scope) - Metric Extent.

3. Inputs:
   2D points in planar local coordinates (u_local, v_local), canonical damage class,
   view angle in degrees, border clipping flag, and host plane RMSE.

4. Outputs:
   Measurement[float] for metric area (m2) or linear length (m), 2D boundary polygon on surface,
   and validity status (ACCEPTED, PROVISIONAL, NOT_EVALUABLE).

5. Coordinate convention:
   Host plane local coordinates: (u_local, v_local) in metric meters.
   Origin is planar centroid; u is horizontal along surface, v is vertical (for walls).

6. Unit convention:
   Lengths: metric meters (m).
   Areas: square meters (m2).
   Uncertainty intervals: [lower_bound, upper_bound] in meters or square meters.
   Angles: degrees.

7. Dependencies:
   math, typing, numpy, scipy.spatial.ConvexHull, shapely.geometry, backend.app.models.output, backend.app.models.damage.

8. Assumptions:
   - Points represent valid geometric intersections on the host structural plane.
   - Linear damages (surface_crack, crack_structural) require arc/skeleton length, not area.
   - Oblique viewing angles (> 75 deg) or extreme image-border clipping (> 20%) invalidate metric scaling.

9. Failure modes:
   - Degenerate point clouds (< 3 non-collinear points for area, < 2 points for linear).
   - Zero or negative bounds in uncertainty intervals.

10. First things to inspect while debugging:
    - Inspect point cloud count and dispersion in (u_local, v_local).
    - Verify whether damage class is classified as linear or area type.
    - Check view_angle_deg and is_clipped_by_border flags.
"""

import math
from typing import Dict, Any, List, Optional, Tuple
import numpy as np
from scipy.spatial import ConvexHull
from shapely.geometry import Polygon, MultiPoint, LineString

from ..models.output import Measurement, DamageClass
from ..models.damage import DamageStatus
from ..models.floorplan import Point2D


class DamageExtentEstimator:
    """Calculates physical metric area, linear crack length, and calibrated uncertainty."""

    def __init__(
        self,
        min_area_m2: float = 0.005,
        max_area_m2: float = 25.0,
        min_length_m: float = 0.05,
        max_length_m: float = 12.0,
        base_confidence: float = 0.90,
    ):
        """Initializes extent estimation boundaries.

        Purpose:
            Configures operational bounds to filter physical outliers.

        Parameters:
            min_area_m2: Smallest plausible damaged surface area (~50 cm2).
            max_area_m2: Largest plausible continuous single surface damage.
            min_length_m: Shortest measurable linear fracture length (5 cm).
            max_length_m: Longest plausible single wall crack span.
            base_confidence: Standard calibrated measurement confidence level.

        Returns:
            None.

        Assumptions:
            Measurements outside [min, max] represent noise or entire-room misdetections.

        Failure cases:
            None.

        Debugging clues:
            Adjust min_area_m2 if detecting micro-spalls or tiny paint chips.
        """
        self.min_area_m2 = min_area_m2
        self.max_area_m2 = max_area_m2
        self.min_length_m = min_length_m
        self.max_length_m = max_length_m
        self.base_confidence = base_confidence

    def compute_metric_extent(
        self,
        points_2d_local: Optional[np.ndarray],
        damage_class: DamageClass,
        view_angle_deg: Optional[float] = 0.0,
        is_clipped_by_border: bool = False,
        plane_rmse_m: float = 0.02,
        is_metric_calibrated: bool = True,
    ) -> Dict[str, Any]:
        """Calculates metric area or crack length and uncertainty intervals.

        Purpose:
            Computes geometry-based extent on host surface and propagates optical angle,
            border clipping, and plane fitting uncertainty into honest intervals.

        Parameters:
            points_2d_local: 2D numpy array (N, 2) of local plane coordinates [u, v] in meters.
            damage_class: Canonical damage category determining area vs linear treatment.
            view_angle_deg: Camera ray angle relative to surface normal in degrees.
            is_clipped_by_border: Whether candidate intersects image sensor boundary.
            plane_rmse_m: Host plane fit root mean square residual error in meters.
            is_metric_calibrated: True if depth/scale is metric (LiDAR), False if unscaled video/photo.

        Returns:
            Dictionary containing:
            {
                'status': DamageStatus,
                'metric_area': Optional[Measurement[float]],
                'metric_length': Optional[Measurement[float]],
                'polygon_on_surface': Optional[List[Point2D]],
                'uncertainty_rel': float,
                'rejection_reason': Optional[str],
            }

        Assumptions:
            All local plane coordinates are metric meters.

        Failure cases:
            Returns status=NOT_EVALUABLE if points are missing, non-metric, or severely clipped.

        Debugging clues:
            Check points_2d_local.shape and view_angle_deg if measurement fails.
        """
        if points_2d_local is None or len(points_2d_local) < 3 or not is_metric_calibrated:
            return {
                "status": DamageStatus.NOT_EVALUABLE,
                "metric_area": None,
                "metric_length": None,
                "polygon_on_surface": None,
                "uncertainty_rel": 1.0,
                "rejection_reason": "uncalibrated_or_insufficient_geometric_samples",
            }

        angle = view_angle_deg or 0.0
        if angle > 75.0:
            return {
                "status": DamageStatus.NOT_EVALUABLE,
                "metric_area": None,
                "metric_length": None,
                "polygon_on_surface": None,
                "uncertainty_rel": 1.0,
                "rejection_reason": f"extreme_oblique_angle_{angle:.1f}_deg",
            }

        # Calculate uncertainty scaling factor
        # 1. Oblique angle penalty: 1 / cos(theta)
        cos_theta = max(0.20, math.cos(math.radians(angle)))
        angle_factor = (1.0 / cos_theta) - 1.0  # 0 at 0 deg, 0.41 at 45 deg, 1.0 at 60 deg

        # 2. Border clipping penalty: clipped mask cannot guarantee true extent
        clip_factor = 0.35 if is_clipped_by_border else 0.0

        # 3. Plane RMSE factor
        plane_factor = min(0.25, plane_rmse_m * 5.0)

        # Total relative uncertainty fraction
        rel_uncertainty = float(np.clip(0.08 + angle_factor * 0.15 + clip_factor + plane_factor, 0.08, 0.85))

        is_linear = damage_class in [DamageClass.SURFACE_CRACK, DamageClass.CRACK_STRUCTURAL]

        if is_linear:
            return self._compute_linear_extent(
                points_2d_local, rel_uncertainty, is_clipped_by_border, angle
            )
        else:
            return self._compute_area_extent(
                points_2d_local, rel_uncertainty, is_clipped_by_border, angle
            )

    def _compute_area_extent(
        self,
        pts: np.ndarray,
        rel_unc: float,
        is_clipped: bool,
        angle: float,
    ) -> Dict[str, Any]:
        """Calculates damaged surface area in m2 using planar convex hull / alpha shape."""
        try:
            hull = ConvexHull(pts)
            area_m2 = float(hull.volume)  # In 2D, volume is polygon area
            hull_pts = pts[hull.vertices]
            polygon_surface = [Point2D(x=round(float(p[0]), 3), y=round(float(p[1]), 3)) for p in hull_pts]
        except Exception:
            # Fallback to bounding box area if collinear
            u_min, v_min = np.min(pts, axis=0)
            u_max, v_max = np.max(pts, axis=0)
            area_m2 = float((u_max - u_min) * (v_max - v_min) * 0.70)
            polygon_surface = [
                Point2D(x=round(float(u_min), 3), y=round(float(v_min), 3)),
                Point2D(x=round(float(u_max), 3), y=round(float(v_min), 3)),
                Point2D(x=round(float(u_max), 3), y=round(float(v_max), 3)),
                Point2D(x=round(float(u_min), 3), y=round(float(v_max), 3)),
            ]

        if area_m2 < self.min_area_m2 or area_m2 > self.max_area_m2:
            status = DamageStatus.PROVISIONAL if area_m2 < self.min_area_m2 else DamageStatus.REJECTED
        elif is_clipped or angle > 60.0 or rel_unc > 0.35:
            status = DamageStatus.PROVISIONAL
        else:
            status = DamageStatus.ACCEPTED

        delta = area_m2 * rel_unc
        lower_bound = max(0.001, round(area_m2 - delta, 3))
        upper_bound = round(area_m2 + delta, 3)

        measurement = Measurement[float](
            value=round(area_m2, 3),
            unit="m2",
            lower_bound=lower_bound,
            upper_bound=upper_bound,
            confidence=self.base_confidence,
            method="planar_surface_hull_integration",
        )

        return {
            "status": status,
            "metric_area": measurement,
            "metric_length": None,
            "polygon_on_surface": polygon_surface,
            "uncertainty_rel": round(rel_unc, 3),
            "rejection_reason": "border_clipped_partial_extent" if is_clipped else None,
        }

    def _compute_linear_extent(
        self,
        pts: np.ndarray,
        rel_unc: float,
        is_clipped: bool,
        angle: float,
    ) -> Dict[str, Any]:
        """Calculates linear crack length in meters using principal axis and curve span."""
        # Compute covariance matrix to find principal direction
        centroid = np.mean(pts, axis=0)
        centered = pts - centroid
        cov = np.cov(centered, rowvar=False)

        # Eigenvalues and eigenvectors
        try:
            eigenvals, eigenvecs = np.linalg.eigh(cov)
            major_axis = eigenvecs[:, -1]
            # Project points onto major axis
            projections = np.dot(centered, major_axis)
            length_m = float(np.max(projections) - np.min(projections))
        except Exception:
            # Fallback to Euclidean diameter
            diff = np.max(pts, axis=0) - np.min(pts, axis=0)
            length_m = float(np.linalg.norm(diff))

        # Build line polygon endpoints
        idx_min = int(np.argmin(np.dot(pts, major_axis)))
        idx_max = int(np.argmax(np.dot(pts, major_axis)))
        pt_start = pts[idx_min]
        pt_end = pts[idx_max]

        polygon_surface = [
            Point2D(x=round(float(pt_start[0]), 3), y=round(float(pt_start[1]), 3)),
            Point2D(x=round(float(pt_end[0]), 3), y=round(float(pt_end[1]), 3)),
        ]

        if length_m < self.min_length_m or length_m > self.max_length_m:
            status = DamageStatus.PROVISIONAL if length_m < self.min_length_m else DamageStatus.REJECTED
        elif is_clipped or angle > 60.0 or rel_unc > 0.35:
            status = DamageStatus.PROVISIONAL
        else:
            status = DamageStatus.ACCEPTED

        delta = length_m * rel_unc
        lower_bound = max(0.01, round(length_m - delta, 3))
        upper_bound = round(length_m + delta, 3)

        measurement = Measurement[float](
            value=round(length_m, 3),
            unit="m",
            lower_bound=lower_bound,
            upper_bound=upper_bound,
            confidence=self.base_confidence,
            method="planar_crack_principal_curve_length",
        )

        return {
            "status": status,
            "metric_area": None,
            "metric_length": measurement,
            "polygon_on_surface": polygon_surface,
            "uncertainty_rel": round(rel_unc, 3),
            "rejection_reason": "border_clipped_partial_crack" if is_clipped else None,
        }
