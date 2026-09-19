"""Unit tests for Stage 1 LiDAR metric reconstruction mathematical components."""

import unittest
import numpy as np

from backend.app.models.capture import CameraIntrinsics, Pose6D
from backend.app.pipelines.lidar.unproject import unproject_depth
from backend.app.pipelines.lidar.transform import (
    quaternion_to_rotation_matrix,
    pose_to_matrix,
    transform_camera_to_world,
)
from backend.app.pipelines.lidar.filtering import (
    filter_by_confidence,
    voxel_downsample,
    remove_statistical_outliers,
)
from backend.app.pipelines.lidar.trajectory import analyze_trajectory
from backend.app.pipelines.lidar.reconstruct import ReconstructionConfig


class TestLiDARReconstruction(unittest.TestCase):
    def setUp(self):
        # Synthetic 4x4 camera intrinsics
        self.intrinsics = CameraIntrinsics(
            fx=100.0,
            fy=100.0,
            cx=2.0,
            cy=2.0,
            width=4,
            height=4,
        )

    def test_depth_millimeter_to_meter_conversion_and_unprojection(self):
        # 4x4 depth map where center pixel (v=2, u=2) has depth 2000 mm (2.0 m)
        depth_mm = np.zeros((4, 4), dtype=np.uint16)
        depth_mm[2, 2] = 2000  # exactly 2.0 meters

        pts_cam, indices = unproject_depth(
            depth_mm=depth_mm,
            intrinsics=self.intrinsics,
            min_depth_m=0.1,
            max_depth_m=5.0,
        )

        self.assertEqual(len(pts_cam), 1)
        # For pixel (u=2, v=2) with cx=2, cy=2, fx=100, fy=100, Z=2.0:
        # X = (2 - 2) * 2.0 / 100 = 0.0
        # Y = (2 - 2) * 2.0 / 100 = 0.0
        # Z = 2.0 m
        self.assertAlmostEqual(pts_cam[0, 0], 0.0, places=4)
        self.assertAlmostEqual(pts_cam[0, 1], 0.0, places=4)
        self.assertAlmostEqual(pts_cam[0, 2], 2.0, places=4)

        # Off-center pixel (v=2, u=3):
        # X = (3 - 2) * 2.0 / 100 = 0.02 m (2 cm)
        depth_mm[2, 3] = 2000
        pts_cam2, _ = unproject_depth(depth_mm, self.intrinsics)
        self.assertEqual(len(pts_cam2), 2)
        # Find the point with X > 0
        off_pt = pts_cam2[pts_cam2[:, 0] > 0][0]
        self.assertAlmostEqual(off_pt[0], 0.02, places=4)
        self.assertAlmostEqual(off_pt[2], 2.0, places=4)

    def test_invalid_and_range_depth_filtering(self):
        depth_mm = np.array([
            [0, 100],      # 0 mm (invalid), 100 mm (0.1 m, below min 0.3 m)
            [3000, 8000],  # 3.0 m (valid), 8.0 m (above max 5.0 m)
        ], dtype=np.uint16)

        pts, _ = unproject_depth(
            depth_mm=depth_mm,
            intrinsics=self.intrinsics,
            min_depth_m=0.3,
            max_depth_m=5.0,
        )
        # Only 3000 mm should survive
        self.assertEqual(len(pts), 1)
        self.assertAlmostEqual(pts[0, 2], 3.0, places=4)

    def test_confidence_filtering(self):
        confidence = np.array([
            [0, 1],
            [2, 2],
        ], dtype=np.uint8)

        mask_high = filter_by_confidence(confidence, min_confidence=2)
        self.assertEqual(np.count_nonzero(mask_high), 2)
        self.assertTrue(mask_high[1, 0])
        self.assertTrue(mask_high[1, 1])
        self.assertFalse(mask_high[0, 0])
        self.assertFalse(mask_high[0, 1])

        mask_med = filter_by_confidence(confidence, min_confidence=1)
        self.assertEqual(np.count_nonzero(mask_med), 3)

    def test_camera_to_world_rigid_transformation(self):
        # Test 1: Identity rotation, translation by [1, 2, 3]
        pose_ident = Pose6D(
            timestamp=0.0,
            frame_index=0,
            x=1.0, y=2.0, z=3.0,
            qx=0.0, qy=0.0, qz=0.0, qw=1.0,
        )
        pt_cam = np.array([[0.5, 0.0, 1.0]], dtype=np.float32)
        pt_world = transform_camera_to_world(pt_cam, pose_ident)
        np.testing.assert_allclose(pt_world[0], [1.5, 2.0, 4.0], rtol=1e-5, atol=1e-5)

        # Test 2: 90-degree rotation around Y axis (qx=0, qy=sin(45)=0.7071068, qz=0, qw=cos(45)=0.7071068)
        # [0, 0, 1] rotated 90 deg around Y becomes [1, 0, 0]
        qy = np.sin(np.pi / 4.0)
        qw = np.cos(np.pi / 4.0)
        pose_rot = Pose6D(
            timestamp=1.0,
            frame_index=1,
            x=0.0, y=0.0, z=0.0,
            qx=0.0, qy=float(qy), qz=0.0, qw=float(qw),
        )
        pt_cam_z = np.array([[0.0, 0.0, 1.0]], dtype=np.float32)
        pt_world_rot = transform_camera_to_world(pt_cam_z, pose_rot)
        np.testing.assert_allclose(pt_world_rot[0], [1.0, 0.0, 0.0], rtol=1e-5, atol=1e-5)

    def test_voxel_downsampling(self):
        # 100 points densely clustered inside a 1 cm cube
        np.random.seed(42)
        dense_points = np.random.uniform(low=0.0, high=0.01, size=(100, 3)).astype(np.float32)

        # Downsample with 2 cm voxel
        down_pts, _ = voxel_downsample(dense_points, voxel_size_m=0.02)
        # Should be reduced to exactly 1 centroid point
        self.assertEqual(len(down_pts), 1)
        self.assertTrue(0.0 <= down_pts[0, 0] <= 0.01)

    def test_trajectory_diagnostics(self):
        poses = [
            Pose6D(timestamp=0.0, frame_index=0, x=0.0, y=0.0, z=0.0, qx=0, qy=0, qz=0, qw=1),
            Pose6D(timestamp=1.0, frame_index=1, x=1.0, y=0.0, z=0.0, qx=0, qy=0, qz=0, qw=1),
            Pose6D(timestamp=2.0, frame_index=2, x=1.0, y=0.0, z=1.0, qx=0, qy=0, qz=0, qw=1),
            Pose6D(timestamp=3.0, frame_index=3, x=0.1, y=0.0, z=0.0, qx=0, qy=0, qz=0, qw=1),
        ]
        stats = analyze_trajectory(poses, is_loop_scan=True)
        self.assertEqual(stats["total_poses"], 4)
        self.assertEqual(stats["duration_seconds"], 3.0)
        # Path: (0->1) is 1.0, (1->1) is 1.0, (1->0.1) is sqrt(0.9^2 + 1^2) = 1.345 -> total ~ 3.345
        self.assertAlmostEqual(stats["total_path_length_meters"], 3.345, places=2)
        self.assertAlmostEqual(stats["start_end_displacement_meters"], 0.1, places=3)
        self.assertAlmostEqual(stats["estimated_loop_drift_meters"], 0.1, places=3)

    def test_reconstruction_config(self):
        cfg = ReconstructionConfig(
            scan_id="test_scan",
            archive_path="dummy.zip",
            frame_stride=3,
            voxel_size_m=0.05,
        )
        self.assertEqual(cfg.output_dir, "outputs/test_scan")
        self.assertEqual(cfg.frame_stride, 3)
        self.assertEqual(cfg.voxel_size_m, 0.05)


if __name__ == "__main__":
    unittest.main()
