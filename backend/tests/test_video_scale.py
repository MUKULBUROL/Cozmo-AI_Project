"""Unit tests for Stage 7 absolute metric scale recovery and scaling math.

1. Why this file exists:
   Verifies robust scale recovery against synthetic depth maps, outlier rejection via MAD,
   scale uncertainty calculation, and confirms that rotations are invariant under scale transform.

2. Pipeline stage:
   Stage 7 (Video Tier - Scale Recovery Tests).

3. Inputs:
   Simulated 3D points with known ground-truth metric scale and synthetic depth maps.

4. Outputs:
   Pytest assertion passes for scale accuracy, outlier robustness, and rotation preservation.
"""

import tempfile
from pathlib import Path
import numpy as np
import pytest

from backend.app.models.video import (
    SfmCameraPose,
    VideoCameraIntrinsics,
    MetricScaleEstimate,
)
from backend.app.pipelines.video.scale import (
    estimate_metric_scale,
    apply_metric_scale,
)


def test_estimate_metric_scale_exact_recovery():
    """Verify exact recovery of scale factor s=2.5 from simulated SfM points and metric depth."""
    true_scale = 2.5
    fx, fy, cx, cy = 1000.0, 1000.0, 500.0, 400.0
    intrinsics = VideoCameraIntrinsics(
        fx=fx, fy=fy, cx=cx, cy=cy, width=1000, height=800,
        source="test", camera_model="PINHOLE",
    )

    # 1 keyframe at origin looking along +Z
    pose = SfmCameraPose(
        keyframe_id=0,
        frame_index=0,
        timestamp=0.0,
        t_vec=[0.0, 0.0, 0.0],
        r_matrix=np.eye(3).tolist(),
        qw=1.0, qx=0.0, qy=0.0, qz=0.0,
    )

    depth_map = np.full((800, 1000), 2.5, dtype=np.float32)

    # Create 30 points at arbitrary depth z_sfm = 1.0 (so z_metric / z_sfm = 2.5)
    sparse_points = []
    for i in range(30):
        u = 200 + i * 20
        v = 200 + i * 10
        # Inverse projection into camera space at z_sfm = 1.0
        x_sfm = (u - cx) * 1.0 / fx
        y_sfm = (v - cy) * 1.0 / fy
        sparse_points.append({
            "xyz": [x_sfm, y_sfm, 1.0],
            "track": [{"image_id": 0, "point2D_idx": i}],
        })

    result = estimate_metric_scale(
        sparse_points=sparse_points,
        poses=[pose],
        depth_maps={0: depth_map},
        intrinsics=intrinsics,
    )

    assert result.status == "GOOD"
    assert np.isclose(result.scale_factor, true_scale, atol=0.01)
    assert result.supporting_points == 30
    assert result.relative_scale_uncertainty < 0.05


def test_metric_scale_robust_to_outliers():
    """Verify MAD outlier rejection suppresses 20% extreme ratio outliers."""
    true_scale = 1.8
    fx, fy, cx, cy = 800.0, 800.0, 400.0, 300.0
    intrinsics = VideoCameraIntrinsics(
        fx=fx, fy=fy, cx=cx, cy=cy, width=800, height=600,
        source="test", camera_model="PINHOLE",
    )

    pose = SfmCameraPose(
        keyframe_id=0, frame_index=0, timestamp=0.0,
        t_vec=[0.0, 0.0, 0.0], r_matrix=np.eye(3).tolist(),
        qw=1.0, qx=0.0, qy=0.0, qz=0.0,
    )

    # Depth map constant 1.8m
    depth_map = np.full((600, 800), 1.8, dtype=np.float32)

    sparse_points = []
    for i in range(50):
        u, v = 150 + i * 10, 100 + i * 8
        # 40 inlier points (z_sfm = 1.0 -> ratio 1.8)
        # 10 outlier points (z_sfm = 0.2 -> ratio 9.0)
        z_sfm = 1.0 if i < 40 else 0.2
        x_sfm = (u - cx) * z_sfm / fx
        y_sfm = (v - cy) * z_sfm / fy
        sparse_points.append({
            "xyz": [x_sfm, y_sfm, z_sfm],
            "track": [{"image_id": 0, "point2D_idx": i}],
        })

    result = estimate_metric_scale(
        sparse_points=sparse_points,
        poses=[pose],
        depth_maps={0: depth_map},
        intrinsics=intrinsics,
    )

    # Median and MAD must reject outliers and recover ~1.8
    assert np.isclose(result.scale_factor, true_scale, atol=0.05)
    assert result.inlier_ratio >= 0.75


def test_apply_metric_scale_preserves_rotations():
    """Applying metric scale multiplier must scale translations but leave rotations invariant."""
    scale = 3.14159
    orig_r = [
        [0.0, -1.0, 0.0],
        [1.0,  0.0, 0.0],
        [0.0,  0.0, 1.0],
    ]
    pose = SfmCameraPose(
        keyframe_id=0, frame_index=0, timestamp=0.0,
        t_vec=[1.0, 2.0, 3.0],
        r_matrix=orig_r,
        qw=0.7071, qx=0.0, qy=0.0, qz=0.7071,
    )
    point = {"xyz": [10.0, 20.0, 30.0], "color": [255, 0, 0]}

    scaled_poses, scaled_points = apply_metric_scale([pose], [point], scale_factor=scale)

    # Translations scaled
    assert np.isclose(scaled_poses[0].t_vec[0], 1.0 * scale)
    assert np.isclose(scaled_poses[0].t_vec[1], 2.0 * scale)
    assert np.isclose(scaled_poses[0].t_vec[2], 3.0 * scale)
    assert scaled_poses[0].is_metric is True

    # Rotations completely unchanged
    assert scaled_poses[0].r_matrix == orig_r
    assert scaled_poses[0].qw == 0.7071
    assert scaled_poses[0].qz == 0.7071

    # Points scaled
    assert np.isclose(scaled_points[0]["xyz"][0], 10.0 * scale)
    assert np.isclose(scaled_points[0]["xyz"][1], 20.0 * scale)
    assert np.isclose(scaled_points[0]["xyz"][2], 30.0 * scale)
