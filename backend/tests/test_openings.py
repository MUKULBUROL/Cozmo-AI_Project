"""Unit tests for Stage 5 opening geometry, ray projection, wall association, and multi-frame fusion.

1. Why this file exists:
   Verifies Stage 5 geometric calculations, analytical 3D ray-plane unprojections, structural wall
   associations, false-positive filtering, observation clustering, and engineering uncertainty propagation
   deterministically without requiring live model inference or GPU access.

2. Pipeline stage:
   Stage 5 (Door/Window Detection & Metric Opening Measurement) - Deterministic Test Suite.

3. Inputs:
   Synthetic walls, camera poses, pixel coordinates, observation lists, and boundary points.

4. Outputs:
   Deterministic test assertions for measurement accuracy, association correctness, and uncertainty behavior.

5. Coordinate/Unit conventions:
   Metric meters (m) in 3D world frame (Y vertical upward, XZ ground plane).
   Opening width evaluated in meters.

6. Dependencies:
   unittest, math, numpy, scipy.spatial.transform.Rotation,
   backend.app.geometry.opening_projection, backend.app.geometry.opening_association,
   backend.app.geometry.opening_fusion.

7. Most likely failure/debugging points:
   - Coordinate frame misalignment between camera optical frame (Z forward) and world frame.
   - Threshold tolerances in clustering or association distance checks.
"""

import math
import unittest
from typing import Any, Dict, List
import numpy as np
from scipy.spatial.transform import Rotation

from backend.app.geometry.opening_projection import (
    project_ray_to_wall_plane,
    project_opening_to_wall,
)
from backend.app.geometry.opening_association import (
    distance_point_to_segment_2d,
    associate_candidate_with_wall,
)
from backend.app.geometry.opening_fusion import (
    compute_metric_width_along_plane,
    cluster_opening_observations,
    estimate_opening_uncertainty,
    fuse_openings,
)


class TestOpeningGeometry(unittest.TestCase):
    """Deterministic geometric test suite for opening unprojection, association, and fusion."""

    def test_01_known_wall_and_known_doorway(self) -> None:
        """Verifies metric width calculation along a known 4m wall with doorway from x=1.2 to x=2.1.

        Purpose:
            Confirms that two known 3D jamb coordinates on a wall plane produce exactly 0.9m width.
        Assumptions:
            Wall along X axis at z = 3.0.
        Debugging:
            Check compute_metric_width_along_plane Euclidean delta.
        """
        left_jamb = (1.20, 0.0, 3.0)
        right_jamb = (2.10, 0.0, 3.0)
        width = compute_metric_width_along_plane(left_jamb, right_jamb)
        self.assertAlmostEqual(width, 0.90, places=3, msg="Expected exact 0.9m doorway clearance width")

    def test_02_camera_ray_projection_synthetic(self) -> None:
        """Verifies synthetic camera unprojection onto a wall plane at known depth.

        Purpose:
            Confirms ray passing through camera center (principal point) hits the wall at the expected depth.
        Assumptions:
            Camera at (0, 1.5, 0) looking along +Z axis with identity rotation. Wall plane z = 3.0.
        Debugging:
            Check camera rotation matrix identity and ray direction sign.
        """
        intrinsics = {
            "fx": 1000.0,
            "fy": 1000.0,
            "cx": 500.0,
            "cy": 500.0,
            "image_width": 1000,
            "image_height": 1000,
        }
        # Identity rotation: camera axes align with world axes (Z forward)
        q = [0.0, 0.0, 0.0, 1.0]
        camera_pose = {
            "position": [0.0, 1.5, 0.0],
            "quaternion": q,
        }
        # Wall plane equation: 0*x + 0*y + 1*z - 3.0 = 0 (plane at z = 3.0)
        plane = [0.0, 0.0, 1.0, -3.0]

        # Cast ray through optical center (cx, cy)
        pt_hit = project_ray_to_wall_plane((500.0, 500.0), intrinsics, camera_pose, plane)
        self.assertIsNotNone(pt_hit, "Ray through principal point must intersect plane in front of camera")
        if pt_hit is not None:
            self.assertAlmostEqual(pt_hit[0], 0.0, places=2)
            self.assertAlmostEqual(pt_hit[1], 1.5, places=2)
            self.assertAlmostEqual(pt_hit[2], 3.0, places=2)

    def test_03_wall_association_correctness(self) -> None:
        """Verifies that an opening candidate near Wall A associates with Wall A and rejects Wall B.

        Purpose:
            Prevents openings from attaching to unrelated parallel or orthogonal walls.
        Assumptions:
            Wall A at z = 3.0, Wall B at x = 5.0 (orthogonal).
        Debugging:
            Check association score and distance_point_to_segment_2d.
        """
        intrinsics = {"fx": 1000.0, "fy": 1000.0, "cx": 500.0, "cy": 500.0}
        q = [0.0, 0.0, 0.0, 1.0]
        camera_pose = {"position": [0.0, 1.5, 0.0], "quaternion": q}

        # Wall A at z = 3.0 from x=-2 to x=2
        wall_a = {
            "id": "wall_A",
            "plane": [0.0, 0.0, 1.0, -3.0],
            "bounds": {"x": [-2.0, 2.0], "z": [2.9, 3.1]},
        }
        # Wall B at x = 5.0 (orthogonal)
        wall_b = {
            "id": "wall_B",
            "plane": [1.0, 0.0, 0.0, -5.0],
            "bounds": {"x": [4.9, 5.1], "z": [-2.0, 2.0]},
        }

        # Bounding box roughly corresponding to 0.9m width at z=3.0 (u from 350 to 650 -> delta_u = 300, W = 300 * 3.0 / 1000 = 0.9m)
        candidate = {"class": "doorway", "detector_score": 0.85, "frame_id": 1, "bbox": [350, 200, 650, 900]}
        boundary = {"left_jamb_pixel": [350.0, 500.0], "right_jamb_pixel": [650.0, 500.0]}

        obs = associate_candidate_with_wall(
            candidate=candidate,
            boundary_pixels=boundary,
            intrinsics=intrinsics,
            camera_pose=camera_pose,
            structural_walls=[wall_a, wall_b],
        )

        self.assertEqual(obs["status"], "accepted")
        self.assertEqual(obs["wall_id"], "wall_A", "Opening must attach to wall_A, not wall_B")
        self.assertAlmostEqual(obs["projected_geometry"]["width_m"], 0.90, places=2)

    def test_04_multi_frame_fusion_deduplication(self) -> None:
        """Verifies that multiple observations of the same opening across different frames fuse into one.

        Purpose:
            Prevents duplicating openings across video frames.
        Debugging:
            Check cluster_opening_observations spatial threshold.
        """
        obs1 = {
            "status": "accepted",
            "wall_id": "wall_01",
            "candidate": {"class": "doorway", "detector_score": 0.80, "frame_id": 10},
            "projected_geometry": {
                "width_m": 0.89,
                "centroid_3d": [1.50, 1.2, 3.0],
                "left_jamb_3d": [1.055, 1.2, 3.0],
                "right_jamb_3d": [1.945, 1.2, 3.0],
            },
        }
        obs2 = {
            "status": "accepted",
            "wall_id": "wall_01",
            "candidate": {"class": "door", "detector_score": 0.84, "frame_id": 25},
            "projected_geometry": {
                "width_m": 0.91,
                "centroid_3d": [1.52, 1.2, 3.0],
                "left_jamb_3d": [1.065, 1.2, 3.0],
                "right_jamb_3d": [1.975, 1.2, 3.0],
            },
        }
        obs3 = {
            "status": "accepted",
            "wall_id": "wall_01",
            "candidate": {"class": "doorway", "detector_score": 0.88, "frame_id": 40},
            "projected_geometry": {
                "width_m": 0.90,
                "centroid_3d": [1.51, 1.2, 3.0],
                "left_jamb_3d": [1.060, 1.2, 3.0],
                "right_jamb_3d": [1.960, 1.2, 3.0],
            },
        }

        clusters = cluster_opening_observations([obs1, obs2, obs3])
        self.assertEqual(len(clusters), 1, "Three observations of the same door must cluster into exactly one cluster")

        structural_walls = [{"id": "wall_01", "plane": [0, 0, 1, -3], "fit_quality": {"rmse_m": 0.012}}]
        fused = fuse_openings(clusters, rejected_observations=[], structural_walls=structural_walls)
        self.assertEqual(len(fused["accepted_openings"]), 1)
        door = fused["accepted_openings"][0]
        self.assertEqual(door["supporting_frames"], 3)
        self.assertAlmostEqual(door["width"]["value"], 0.90, places=2)

    def test_05_duplicate_detections_in_same_frame(self) -> None:
        """Verifies that two overlapping candidate boxes on the same frame cluster into one opening.

        Purpose:
            Prevents dual detections (e.g. 'door' and 'doorway' on the same physical door) from creating duplicate openings.
        Debugging:
            Check centroid distance in cluster_opening_observations.
        """
        obs_a = {
            "status": "accepted",
            "wall_id": "wall_02",
            "candidate": {"class": "door", "detector_score": 0.75, "frame_id": 100},
            "projected_geometry": {
                "width_m": 0.88,
                "centroid_3d": [-1.0, 1.1, 2.5],
                "left_jamb_3d": [-1.44, 1.1, 2.5],
                "right_jamb_3d": [-0.56, 1.1, 2.5],
            },
        }
        obs_b = {
            "status": "accepted",
            "wall_id": "wall_02",
            "candidate": {"class": "doorway", "detector_score": 0.79, "frame_id": 100},
            "projected_geometry": {
                "width_m": 0.90,
                "centroid_3d": [-1.02, 1.1, 2.5],
                "left_jamb_3d": [-1.47, 1.1, 2.5],
                "right_jamb_3d": [-0.57, 1.1, 2.5],
            },
        }
        clusters = cluster_opening_observations([obs_a, obs_b])
        self.assertEqual(len(clusters), 1, "Duplicate detections in same frame must be clustered together")

    def test_06_phantom_detection_rejection(self) -> None:
        """Verifies that a phantom candidate (e.g. wardrobe in the middle of the room) is rejected.

        Purpose:
            Eliminates false positive detections without structural wall support.
        Debugging:
            Check max_segment_dist_m and rejection_reasons in opening_association.
        """
        intrinsics = {"fx": 1000.0, "fy": 1000.0, "cx": 500.0, "cy": 500.0}
        q = [0.0, 0.0, 0.0, 1.0]
        camera_pose = {"position": [0.0, 1.5, 0.0], "quaternion": q}

        # Wall far away at z = 10.0
        wall = {
            "id": "wall_far",
            "plane": [0.0, 0.0, 1.0, -10.0],
            "bounds": {"x": [-2.0, 2.0], "z": [9.9, 10.1]},
        }
        # A candidate box that would project to 3m width at z=10m (unplausible for single door)
        candidate = {"class": "door", "detector_score": 0.60, "frame_id": 5, "bbox": [100, 100, 900, 900]}
        boundary = {"left_jamb_pixel": [100.0, 500.0], "right_jamb_pixel": [900.0, 500.0]}

        obs = associate_candidate_with_wall(
            candidate=candidate,
            boundary_pixels=boundary,
            intrinsics=intrinsics,
            camera_pose=camera_pose,
            structural_walls=[wall],
            max_opening_width_m=2.60,
        )
        self.assertEqual(obs["status"], "rejected", "Phantom candidate exceeding max width must be rejected")
        self.assertIn("no_supporting_structural_wall_within_tolerance", obs["rejection_reasons"])

    def test_07_closed_door_surface_support(self) -> None:
        """Verifies that a closed planar door surface is supported when semantic and boundary geometry align.

        Purpose:
            Ensures closed doors are not discarded simply because they lack an empty depth void behind them.
        Debugging:
            Verify associate_candidate_with_wall accepts valid planar width even with continuous depth.
        """
        intrinsics = {"fx": 1000.0, "fy": 1000.0, "cx": 500.0, "cy": 500.0}
        q = [0.0, 0.0, 0.0, 1.0]
        camera_pose = {"position": [0.0, 1.5, 0.0], "quaternion": q}

        wall = {
            "id": "wall_closed_door",
            "plane": [0.0, 0.0, 1.0, -2.5],
            "bounds": {"x": [-1.5, 1.5], "z": [2.4, 2.6]},
        }
        # Width: 320 pixels at z=2.5m, fx=1000 -> 320 * 2.5 / 1000 = 0.80m
        candidate = {"class": "door", "detector_score": 0.92, "frame_id": 50, "bbox": [340, 200, 660, 900]}
        boundary = {"left_jamb_pixel": [340.0, 500.0], "right_jamb_pixel": [660.0, 500.0]}

        obs = associate_candidate_with_wall(
            candidate=candidate,
            boundary_pixels=boundary,
            intrinsics=intrinsics,
            camera_pose=camera_pose,
            structural_walls=[wall],
        )
        self.assertEqual(obs["status"], "accepted", "Closed planar door must be accepted if geometry is consistent")
        self.assertAlmostEqual(obs["projected_geometry"]["width_m"], 0.80, places=2)

    def test_08_uncertainty_interval_widening(self) -> None:
        """Verifies that higher frame measurement spread and higher wall RMSE widen the uncertainty interval.

        Purpose:
            Ensures honest uncalibrated engineering uncertainty reflects empirical measurement noise.
        Debugging:
            Check estimate_opening_uncertainty error propagation formula.
        """
        # Low noise case: consistent observations and low wall RMSE
        widths_consistent = [0.90, 0.905, 0.895, 0.90]
        _, _, half_u_low = estimate_opening_uncertainty(widths_consistent, wall_rmse_m=0.008, depth_noise_m=0.010)

        # High noise case: erratic observations and high wall RMSE
        widths_erratic = [0.82, 0.98, 0.85, 0.95]
        _, _, half_u_high = estimate_opening_uncertainty(widths_erratic, wall_rmse_m=0.040, depth_noise_m=0.030)

        self.assertGreater(
            half_u_high,
            half_u_low,
            f"High-noise uncertainty ({half_u_high}m) must be wider than low-noise ({half_u_low}m)",
        )


if __name__ == "__main__":
    unittest.main()
