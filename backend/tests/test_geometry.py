"""Deterministic synthetic tests for Stage 2 structural plane extraction."""

import unittest
import numpy as np

from backend.app.geometry.normals import split_horizontal_vertical_masks
from backend.app.geometry.metrics import compute_plane_residuals, compute_plane_confidence
from backend.app.geometry.plane_detection import DetectedPlane
from backend.app.geometry.plane_classification import (
    classify_floor,
    classify_ceiling,
    filter_wall_candidates,
    merge_parallel_walls,
)


class TestGeometryExtraction(unittest.TestCase):
    def setUp(self):
        np.random.seed(42)

    def test_plane_residual_computation(self):
        # Plane: y = 2.0 -> 0*x + 1*y + 0*z - 2.0 = 0
        plane = [0.0, 1.0, 0.0, -2.0]
        pts = np.array([
            [1.0, 2.0, 3.0],   # On plane (dist = 0)
            [0.0, 2.02, 0.0],  # 0.02 m off plane
            [-1.0, 1.98, 1.0], # 0.02 m off plane
        ])
        mean_res, rmse = compute_plane_residuals(plane, pts)
        self.assertAlmostEqual(mean_res, 4.0 / 300.0, places=4)
        self.assertAlmostEqual(rmse, np.sqrt((0 + 0.02**2 + 0.02**2) / 3.0), places=4)

    def test_normal_orientation_split(self):
        normals = np.array([
            [0.0, 0.99, 0.05],   # Horizontal surface (normal ~ Y)
            [0.0, -0.98, 0.01],  # Horizontal surface (normal ~ -Y)
            [0.99, 0.05, 0.02],  # Vertical surface (wall, normal ~ X)
            [0.02, 0.01, 0.99],  # Vertical surface (wall, normal ~ Z)
            [0.707, 0.707, 0.0], # 45-degree slope (oblique)
        ])
        is_h, is_v, is_o = split_horizontal_vertical_masks(normals, vertical_axis=1, horizontal_thresh=0.8, vertical_thresh=0.25)
        self.assertTrue(is_h[0])
        self.assertTrue(is_h[1])
        self.assertTrue(is_v[2])
        self.assertTrue(is_v[3])
        self.assertTrue(is_o[4])

    def test_floor_and_ceiling_classification(self):
        # Create synthetic floor at Y = -1.5 with 5,000 points
        pts_floor = np.random.uniform(low=[-2, -1.51, -3], high=[2, -1.49, 3], size=(5000, 3))
        plane_floor = DetectedPlane(
            plane_model=[0.0, 1.0, 0.0, 1.50],
            inlier_indices=np.arange(5000),
            inlier_points=pts_floor,
            inlier_count=5000,
            mean_residual_m=0.005,
            rmse_m=0.006,
        )

        # Create synthetic ceiling at Y = +1.2 with 4,000 points
        pts_ceil = np.random.uniform(low=[-2, 1.19, -3], high=[2, 1.21, 3], size=(4000, 3))
        plane_ceil = DetectedPlane(
            plane_model=[0.0, 1.0, 0.0, -1.20],
            inlier_indices=np.arange(4000),
            inlier_points=pts_ceil,
            inlier_count=4000,
            mean_residual_m=0.005,
            rmse_m=0.006,
        )

        # Create synthetic table surface at Y = -0.7 with 1,500 points
        pts_table = np.random.uniform(low=[-0.5, -0.71, -0.5], high=[0.5, -0.69, 0.5], size=(1500, 3))
        plane_table = DetectedPlane(
            plane_model=[0.0, 1.0, 0.0, 0.70],
            inlier_indices=np.arange(1500),
            inlier_points=pts_table,
            inlier_count=1500,
            mean_residual_m=0.005,
            rmse_m=0.006,
        )

        planes = [plane_table, plane_floor, plane_ceil]

        # 1. Floor detection should accurately select plane_floor (lowest)
        detected_floor = classify_floor(planes)
        self.assertIsNotNone(detected_floor)
        self.assertAlmostEqual(float(np.mean(detected_floor.inlier_points[:, 1])), -1.5, places=1)

        # 2. Ceiling detection should select plane_ceil (significantly above floor)
        detected_ceil, reason = classify_ceiling(planes, detected_floor, min_ceiling_height_m=1.8)
        self.assertIsNotNone(detected_ceil)
        self.assertAlmostEqual(float(np.mean(detected_ceil.inlier_points[:, 1])), 1.2, places=1)

        # 3. Test missing ceiling handling
        planes_without_ceil = [plane_table, plane_floor]
        detected_ceil_none, reason_none = classify_ceiling(planes_without_ceil, detected_floor, min_ceiling_height_m=1.8)
        self.assertIsNone(detected_ceil_none)
        self.assertIn("Insufficient upper horizontal points", reason_none)

    def test_wall_rejection_heuristics(self):
        # Candidate 1: Real wall: spans 2m high, 3m wide, reaches floor (Y from -1.5 to 0.5)
        pts_real_wall = np.random.uniform(low=[-1.5, -1.5, 2.99], high=[1.5, 0.5, 3.01], size=(6000, 3))
        plane_real = DetectedPlane(
            plane_model=[0.0, 0.0, 1.0, -3.0],
            inlier_indices=np.arange(6000),
            inlier_points=pts_real_wall,
            inlier_count=6000,
            mean_residual_m=0.006,
            rmse_m=0.007,
        )

        # Candidate 2: Small cabinet door: only 0.4m high, 0.4m wide
        pts_cabinet = np.random.uniform(low=[-0.2, -1.0, 1.99], high=[0.2, -0.6, 2.01], size=(4500, 3))
        plane_cabinet = DetectedPlane(
            plane_model=[0.0, 0.0, 1.0, -2.0],
            inlier_indices=np.arange(4500),
            inlier_points=pts_cabinet,
            inlier_count=4500,
            mean_residual_m=0.005,
            rmse_m=0.006,
        )

        # Candidate 3: Floating picture frame: bottom is 1.0m above floor
        pts_frame = np.random.uniform(low=[-0.5, -0.2, -1.99], high=[0.5, 0.6, -2.01], size=(5000, 3))
        plane_frame = DetectedPlane(
            plane_model=[0.0, 0.0, 1.0, 2.0],
            inlier_indices=np.arange(5000),
            inlier_points=pts_frame,
            inlier_count=5000,
            mean_residual_m=0.005,
            rmse_m=0.006,
        )

        accepted, rejected = filter_wall_candidates(
            vertical_planes=[plane_real, plane_cabinet, plane_frame],
            floor_y=-1.5,
            min_inliers=3000,
            min_height_span_m=0.7,
            min_horizontal_span_m=0.7,
            max_floor_gap_m=0.3,
        )

        self.assertEqual(len(accepted), 1)
        self.assertEqual(accepted[0], plane_real)
        self.assertEqual(len(rejected), 2)

    def test_parallel_wall_merging(self):
        # Fragment 1 of Wall X: x = 2.00 (from z=-2 to 0)
        pts1 = np.random.uniform(low=[1.99, -1.5, -2], high=[2.01, 0.5, 0], size=(3000, 3))
        p1 = DetectedPlane(
            plane_model=[1.0, 0.0, 0.0, -2.00],
            inlier_indices=np.arange(3000),
            inlier_points=pts1,
            inlier_count=3000,
            mean_residual_m=0.005,
            rmse_m=0.006,
        )

        # Fragment 2 of Wall X: x = 2.02 (from z=0 to 2) (same wall, slight offset due to noise)
        pts2 = np.random.uniform(low=[2.01, -1.5, 0], high=[2.03, 0.5, 2], size=(3000, 3))
        p2 = DetectedPlane(
            plane_model=[1.0, 0.0, 0.0, -2.02],
            inlier_indices=np.arange(3000),
            inlier_points=pts2,
            inlier_count=3000,
            mean_residual_m=0.005,
            rmse_m=0.006,
        )

        # Opposite Wall X: x = -2.00 (should NOT be merged!)
        pts_opp = np.random.uniform(low=[-2.01, -1.5, -2], high=[-1.99, 0.5, 2], size=(4000, 3))
        p_opp = DetectedPlane(
            plane_model=[-1.0, 0.0, 0.0, -2.00],
            inlier_indices=np.arange(4000),
            inlier_points=pts_opp,
            inlier_count=4000,
            mean_residual_m=0.005,
            rmse_m=0.006,
        )

        merged = merge_parallel_walls([p1, p2, p_opp], angular_thresh_deg=10.0, distance_thresh_m=0.15)
        # Should be merged into 2 distinct walls (one at x ~ 2.01, one at x ~ -2.00)
        self.assertEqual(len(merged), 2)
        # The merged wall at x ~ 2.01 should have 6,000 inliers
        wall_plus = [w for w in merged if abs(w.plane_model[3]) > 0][0]
        self.assertEqual(wall_plus.inlier_count, 6000)

    def test_plane_confidence_score(self):
        conf_high = compute_plane_confidence(inlier_count=20000, rmse_m=0.01)
        conf_low = compute_plane_confidence(inlier_count=2000, rmse_m=0.035)
        self.assertGreater(conf_high, 0.8)
        self.assertLess(conf_low, 0.5)


if __name__ == "__main__":
    unittest.main()
