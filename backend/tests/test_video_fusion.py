"""Unit tests for Stage 7 video metric point cloud unprojection, fusion, and shared geometry contracts.

1. Why this file exists:
   Verifies mathematical correctness of 2D metric depth unprojection to 3D camera space,
   point cloud fusion with camera poses, and standard ReconstructionResult contract compliance.

2. Pipeline stage:
   Stage 7 (Video Tier - Fusion Tests).

3. Inputs:
   Synthetic metric depth maps, camera intrinsics, and camera poses.

4. Outputs:
   Pytest assertions confirming geometric projection and ReconstructionResult integrity.
"""

import tempfile
from pathlib import Path
import numpy as np
import cv2
import pytest

from backend.app.models.capture import CaptureTier
from backend.app.models.reconstruction import ReconstructionResult
from backend.app.models.video import (
    SfmCameraPose,
    VideoCameraIntrinsics,
)
from backend.app.pipelines.video.fusion import (
    unproject_metric_depth_map,
    fuse_video_metric_pointcloud,
)


def test_unproject_metric_depth_map_math():
    """Verify pinhole projection math: X = (u - cx)*Z/fx, Y = (v - cy)*Z/fy."""
    fx, fy, cx, cy = 500.0, 500.0, 100.0, 100.0
    h, w = 200, 200

    # Constant 2.0m depth
    depth_m = np.full((h, w), 2.0, dtype=np.float32)

    pts_cam, uvs = unproject_metric_depth_map(depth_m, fx, fy, cx, cy, stride=1)
    assert len(pts_cam) == h * w

    # Test center pixel (u=100, v=100) -> should have X=0.0, Y=0.0, Z=2.0
    center_mask = (uvs[:, 0] == 100) & (uvs[:, 1] == 100)
    center_pt = pts_cam[center_mask][0]
    assert np.isclose(center_pt[0], 0.0, atol=1e-5)
    assert np.isclose(center_pt[1], 0.0, atol=1e-5)
    assert np.isclose(center_pt[2], 2.0, atol=1e-5)

    # Test offset pixel (u=150, v=100) -> X = (150 - 100)*2.0 / 500 = 0.2m
    offset_mask = (uvs[:, 0] == 100) & (uvs[:, 1] == 150)
    offset_pt = pts_cam[offset_mask][0]
    assert np.isclose(offset_pt[0], 0.2, atol=1e-5)
    assert np.isclose(offset_pt[1], 0.0, atol=1e-5)
    assert np.isclose(offset_pt[2], 2.0, atol=1e-5)


def test_fuse_video_metric_pointcloud_contract():
    """Verify fusion produces standard ReconstructionResult with tier=CaptureTier.VIDEO."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        out_dir = tmp_path / "fusion"

        # Create 1 synthetic image
        img_p = tmp_path / "frame_000000.jpg"
        cv2.imwrite(str(img_p), np.full((120, 160, 3), 150, dtype=np.uint8))

        intrinsics = VideoCameraIntrinsics(
            fx=200.0, fy=200.0, cx=80.0, cy=60.0, width=160, height=120,
            source="test", camera_model="PINHOLE",
        )

        pose = SfmCameraPose(
            keyframe_id=0, frame_index=0, timestamp=0.0,
            t_vec=[0.0, 0.0, 0.0], r_matrix=np.eye(3).tolist(),
            qw=1.0, qx=0.0, qy=0.0, qz=0.0,
            is_metric=True,
        )

        depth_map = np.full((120, 160), 1.5, dtype=np.float32)
        quality_mask = np.ones((120, 160), dtype=bool)

        recon_result, pcd = fuse_video_metric_pointcloud(
            keyframe_paths={0: img_p},
            depth_maps={0: depth_map},
            depth_masks={0: quality_mask},
            poses=[pose],
            intrinsics=intrinsics,
            output_dir=out_dir,
            capture_id="fusion_test",
            scale_factor_applied=1.5,
        )

        assert isinstance(recon_result, ReconstructionResult)
        assert recon_result.tier == CaptureTier.VIDEO
        assert recon_result.capture_id == "fusion_test"
        assert recon_result.point_cloud_summary.point_count > 0
        assert (out_dir / "video_pointcloud_raw.ply").exists()
        assert (out_dir / "video_pointcloud_filtered.ply").exists()
