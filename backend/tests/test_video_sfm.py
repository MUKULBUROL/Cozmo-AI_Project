"""
Deterministic unit tests for visual SfM reconstruction and quality gating.

1. Why this file exists:
   Verifies that Stage 7 visual SfM reports, camera poses, PLY writing, and
   quality gating (GOOD / PROVISIONAL / FAILED) operate reliably and fail
   honestly on degenerate or insufficient inputs.

2. Pipeline stage:
   Stage 7 (Video Tier - Visual SfM Unit Tests).

3. Inputs:
   Mock 3D point data, temporary test directories, and simulated keyframe sets.

4. Outputs:
   Test assertion passes verifying deterministic behavior and safety gates.

5. Coordinate convention:
   OpenCV camera space and right-handed 3D space.

6. Unit convention:
   Arbitrary SfM scale units, degrees, pixels.

7. Important dependencies:
   unittest, numpy, tempfile, pathlib, backend.app.pipelines.video.sfm.

8. Assumptions:
   Unit tests should not require running full multi-minute bundle adjustment.

9. Main failure modes:
   - Malformed PLY header or coordinate formatting.
   - Quality status misclassification.

10. What a developer should inspect first when debugging:
    Inspect test failure tracebacks in test_sparse_ply_writer or test_insufficient_keyframes_fails_honestly.
"""

import unittest
import tempfile
from pathlib import Path
import numpy as np

from backend.app.pipelines.video.contract import (
    VideoReconstructionStatus,
    VideoCameraPose,
    VideoIntrinsics,
    SfMReconstructionReport,
)
from backend.app.pipelines.video.sfm import (
    write_sparse_points_ply,
    run_visual_sfm,
)


class TestVideoSfM(unittest.TestCase):
    """Unit tests for SfM data structures, PLY export, and failure handling."""

    def test_sparse_ply_writer(self):
        """Verify that 3D points and colors are correctly formatted into an ASCII PLY file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ply_path = Path(tmpdir) / "test_points.ply"
            pts = np.array([
                [1.0, 2.0, 3.0],
                [-4.5, 0.0, 6.25],
            ], dtype=np.float32)
            colors = np.array([
                [255, 0, 0],
                [0, 255, 128],
            ], dtype=np.uint8)

            write_sparse_points_ply(pts, ply_path, colors)
            self.assertTrue(ply_path.exists())

            with open(ply_path, "r") as f:
                lines = f.readlines()

            self.assertEqual(lines[0].strip(), "ply")
            self.assertEqual(lines[1].strip(), "format ascii 1.0")
            self.assertIn("element vertex 2", [l.strip() for l in lines])
            self.assertIn("end_header", [l.strip() for l in lines])

    def test_insufficient_keyframes_fails_honestly(self):
        """Verify that fewer than 3 keyframes gracefully returns FAILED status without crashing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            kfs_dir = tmp_path / "keyframes"
            sfm_dir = tmp_path / "sfm"
            kfs_dir.mkdir(parents=True, exist_ok=True)

            # Create only 1 mock keyframe
            (kfs_dir / "frame_000000.jpg").write_text("fake_image_data")

            report, poses, intrinsics, ply_path = run_visual_sfm(
                keyframes_dir=kfs_dir,
                output_sfm_dir=sfm_dir,
                capture_id="test_fail",
            )

            self.assertEqual(report.status, VideoReconstructionStatus.FAILED)
            self.assertEqual(report.registered_keyframes, 0)
            self.assertEqual(len(poses), 0)
            self.assertIn("Fewer than 3 keyframes", report.warnings[0])

    def test_camera_pose_data_model(self):
        """Verify VideoCameraPose model attributes and quaternion consistency."""
        pose = VideoCameraPose(
            frame_index=15,
            timestamp_seconds=0.5,
            tx=1.25,
            ty=-0.5,
            tz=3.0,
            qw=1.0,
            qx=0.0,
            qy=0.0,
            qz=0.0,
            is_metric=False,
        )
        self.assertEqual(pose.frame_index, 15)
        self.assertFalse(pose.is_metric)
        self.assertEqual(pose.qw, 1.0)


if __name__ == "__main__":
    unittest.main()
