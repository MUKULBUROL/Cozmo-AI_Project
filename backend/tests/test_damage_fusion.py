"""Unit tests for Stage 9 metric damage extent calculation and multi-view fusion.

1. Why this file exists:
   Verifies exact physical area calculation (m2), linear crack length (m),
   uncertainty propagation under oblique angles and border clipping, and spatial
   clustering / deduplication across multi-view observation frames.

2. Pipeline stage:
   Stage 9 (Damage Detection, Metric Extent, Concealed-Damage Rules & Repair Scope) - Testing.

3. Inputs:
   Synthetic planar point clouds with known ground truth dimensions and multi-frame observations.

4. Outputs:
   Pytest assertion results verifying metric accuracy, uncertainty monotonicity, and clustering.

5. Coordinate convention:
   Metric meters in plane local and 3D world frames.

6. Unit convention:
   Meters (m), square meters (m2).

7. Dependencies:
   unittest, numpy, backend.app.damage.extent, backend.app.damage.fusion.

8. Assumptions:
   - Tests execute deterministically without external model weights.

9. Failure modes:
   - Inaccurate convex hull area calculation or failure to fuse proximal centroids.

10. First things to inspect while debugging:
    - Check cluster distance threshold and input point dimensions.
"""

import unittest
import numpy as np

from backend.app.models.output import DamageClass, Measurement
from backend.app.models.damage import DamageStatus, SurfaceType
from backend.app.damage.extent import DamageExtentEstimator
from backend.app.damage.fusion import MultiViewDamageFusion


class TestDamageFusion(unittest.TestCase):
    """Verifies metric extent estimation and multi-view observation fusion."""

    def setUp(self):
        self.estimator = DamageExtentEstimator()
        self.fusion = MultiViewDamageFusion(max_cluster_dist_m=0.35)

    def test_synthetic_known_metric_area(self):
        # Create a synthetic 1.0 m x 1.0 m square of points (area = 1.0 m2)
        u = np.linspace(0.0, 1.0, 20)
        v = np.linspace(0.0, 1.0, 20)
        uu, vv = np.meshgrid(u, v)
        pts = np.stack([uu.ravel(), vv.ravel()], axis=-1)

        res = self.estimator.compute_metric_extent(
            pts, DamageClass.WATER_STAIN, view_angle_deg=10.0, is_clipped_by_border=False
        )

        self.assertEqual(res["status"], DamageStatus.ACCEPTED)
        self.assertIsNotNone(res["metric_area"])
        area = res["metric_area"].value
        # Area should be very close to 1.0 m2
        self.assertAlmostEqual(area, 1.0, places=2)
        # Interval should enclose nominal value
        self.assertLessEqual(res["metric_area"].lower_bound, area)
        self.assertGreaterEqual(res["metric_area"].upper_bound, area)

    def test_synthetic_known_crack_length(self):
        # Create a synthetic straight crack of 1.50 m along u-axis
        u = np.linspace(-0.75, 0.75, 30)
        v = np.zeros_like(u) + 0.005 * np.random.randn(len(u))
        pts = np.stack([u, v], axis=-1)

        res = self.estimator.compute_metric_extent(
            pts, DamageClass.SURFACE_CRACK, view_angle_deg=15.0, is_clipped_by_border=False
        )

        self.assertEqual(res["status"], DamageStatus.ACCEPTED)
        self.assertIsNotNone(res["metric_length"])
        length = res["metric_length"].value
        self.assertAlmostEqual(length, 1.50, places=1)
        self.assertEqual(res["metric_length"].unit, "m")

    def test_uncertainty_increases_with_angle_and_clipping(self):
        pts = np.array([[0.0, 0.0], [0.5, 0.0], [0.5, 0.5], [0.0, 0.5]])

        # Baseline: 0 deg, unclipped
        res_base = self.estimator.compute_metric_extent(
            pts, DamageClass.WATER_STAIN, view_angle_deg=0.0, is_clipped_by_border=False
        )
        # Oblique angle: 55 deg
        res_oblique = self.estimator.compute_metric_extent(
            pts, DamageClass.WATER_STAIN, view_angle_deg=55.0, is_clipped_by_border=False
        )
        # Clipped by border
        res_clipped = self.estimator.compute_metric_extent(
            pts, DamageClass.WATER_STAIN, view_angle_deg=0.0, is_clipped_by_border=True
        )

        # Uncertainty interval spread should expand under adverse conditions
        spread_base = res_base["metric_area"].upper_bound - res_base["metric_area"].lower_bound
        spread_oblique = res_oblique["metric_area"].upper_bound - res_oblique["metric_area"].lower_bound
        spread_clipped = res_clipped["metric_area"].upper_bound - res_clipped["metric_area"].lower_bound

        self.assertGreater(spread_oblique, spread_base)
        self.assertGreater(spread_clipped, spread_base)

    def test_multi_view_fusion_same_damage(self):
        # Three observations of the same water stain on wall_01 from different frames
        obs1 = {
            "observation_id": "obs_f01",
            "image_id": "frame_000000.jpg",
            "host_surface_id": "wall_01",
            "host_surface_type": SurfaceType.WALL,
            "centroid_3d": [1.00, 1.50, 2.00],
            "damage_class": DamageClass.WATER_STAIN,
            "class_confidence": 0.85,
            "view_angle_deg": 15.0,
            "metric_area": Measurement[float](
                value=0.50, unit="m2", lower_bound=0.45, upper_bound=0.55, confidence=0.9, method="test"
            ),
            "status": DamageStatus.ACCEPTED,
        }
        obs2 = {
            "observation_id": "obs_f02",
            "image_id": "frame_000020.jpg",
            "host_surface_id": "wall_01",
            "host_surface_type": SurfaceType.WALL,
            "centroid_3d": [1.05, 1.48, 2.02],  # ~7 cm away
            "damage_class": DamageClass.WATER_STAIN,
            "class_confidence": 0.90,
            "view_angle_deg": 10.0,
            "metric_area": Measurement[float](
                value=0.54, unit="m2", lower_bound=0.48, upper_bound=0.60, confidence=0.9, method="test"
            ),
            "status": DamageStatus.ACCEPTED,
        }
        obs3 = {
            "observation_id": "obs_f03",
            "image_id": "frame_000040.jpg",
            "host_surface_id": "wall_01",
            "host_surface_type": SurfaceType.WALL,
            "centroid_3d": [0.98, 1.52, 1.99],  # ~5 cm away
            "damage_class": DamageClass.WATER_STAIN,
            "class_confidence": 0.80,
            "view_angle_deg": 25.0,
            "metric_area": Measurement[float](
                value=0.48, unit="m2", lower_bound=0.42, upper_bound=0.54, confidence=0.9, method="test"
            ),
            "status": DamageStatus.ACCEPTED,
        }

        fused = self.fusion.fuse_observations([obs1, obs2, obs3], capture_id="test_cap")

        # Must merge into exactly ONE fused damage region
        self.assertEqual(len(fused), 1)
        dmg = fused[0]
        self.assertEqual(dmg.host_surface_id, "wall_01")
        self.assertEqual(dmg.damage_class, DamageClass.WATER_STAIN)
        self.assertEqual(len(dmg.supporting_images), 3)
        self.assertEqual(len(dmg.supporting_observations), 3)
        # Fused area should be average ~0.506 m2
        self.assertAlmostEqual(dmg.metric_area.value, 0.51, places=1)
        # Spread should be positive and small
        self.assertIsNotNone(dmg.measurement_spread_m2)
        self.assertLess(dmg.measurement_spread_m2, 0.05)
        # Best frame should be obs2 (10 deg view angle)
        self.assertEqual(dmg.best_image_id, "frame_000020.jpg")

    def test_multi_view_fusion_distinct_damages_not_merged(self):
        # Two distinct damages far apart (1.5 m apart)
        obs_a = {
            "observation_id": "obs_a",
            "image_id": "frame_000000.jpg",
            "host_surface_id": "wall_01",
            "host_surface_type": SurfaceType.WALL,
            "centroid_3d": [0.0, 1.5, 2.0],
            "damage_class": DamageClass.WATER_STAIN,
            "class_confidence": 0.85,
            "view_angle_deg": 15.0,
            "status": DamageStatus.ACCEPTED,
        }
        obs_b = {
            "observation_id": "obs_b",
            "image_id": "frame_000020.jpg",
            "host_surface_id": "wall_01",
            "host_surface_type": SurfaceType.WALL,
            "centroid_3d": [1.5, 1.5, 2.0],  # 1.5 meters away
            "damage_class": DamageClass.HOLE_OR_MISSING_MATERIAL,
            "class_confidence": 0.88,
            "view_angle_deg": 20.0,
            "status": DamageStatus.ACCEPTED,
        }

        fused = self.fusion.fuse_observations([obs_a, obs_b], capture_id="test_cap")
        # Must retain TWO separate damage regions
        self.assertEqual(len(fused), 2)


if __name__ == "__main__":
    unittest.main()
