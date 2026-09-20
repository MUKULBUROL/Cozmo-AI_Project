"""Unit tests for Stage 7 Visual SfM camera pose reconstruction.

1. Why this file exists:
   Tests mathematical integrity of camera trajectory estimation, rotation orthonormality,
   continuity validation, and graceful handling of degenerate visual cases.

2. Pipeline stage:
   Stage 7 (Video Tier - Camera Pose Reconstruction Tests).

3. Inputs:
   Synthetic camera poses, simulated keyframe directories, and mock SfM outputs.

4. Outputs:
   Pytest assertions verifying mathematical consistency and quality gates.
"""

import tempfile
from pathlib import Path
import numpy as np
import pytest

from backend.app.models.video import (
    VideoCameraIntrinsics,
    SfmCameraPose,
)
from backend.app.pipelines.video.contract import (
    VideoReconstructionStatus,
    SfMReconstructionReport,
)
from backend.app.pipelines.video.sfm import (
    evaluate_trajectory_continuity,
    run_visual_sfm,
)


def test_trajectory_continuity_detects_jumps():
    """Continuity evaluator must flag abrupt translational jump between adjacent frames."""
    # Smooth linear trajectory: delta = 0.1m
    smooth_poses = [
        SfmCameraPose(
            keyframe_id=i,
            frame_index=i * 10,
            timestamp=i * 0.33,
            t_vec=[i * 0.1, 0.0, 0.0],
            r_matrix=np.eye(3).tolist(),
            qw=1.0, qx=0.0, qy=0.0, qz=0.0,
        )
        for i in range(10)
    ]

    is_continuous, warnings = evaluate_trajectory_continuity(smooth_poses)
    assert is_continuous is True
    assert len(warnings) == 0

    # Inject large jump at step 5 (1.5m jump when median is 0.1m)
    jumping_poses = [
        SfmCameraPose(
            keyframe_id=i,
            frame_index=i * 10,
            timestamp=i * 0.33,
            t_vec=[i * 0.1 if i < 5 else (i * 0.1 + 1.5), 0.0, 0.0],
            r_matrix=np.eye(3).tolist(),
            qw=1.0, qx=0.0, qy=0.0, qz=0.0,
        )
        for i in range(10)
    ]

    is_continuous_jump, warnings_jump = evaluate_trajectory_continuity(jumping_poses)
    assert is_continuous_jump is False
    assert len(warnings_jump) >= 1
    assert "Translation jump" in warnings_jump[0]


def test_sfm_handles_insufficient_frames_gracefully():
    """SfM must return FAILED report if fewer than 2 keyframes exist, without crashing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        img_dir = Path(tmpdir) / "images"
        img_dir.mkdir()
        out_sfm = Path(tmpdir) / "sfm"

        report, poses, intrinsics, points = run_visual_sfm(
            image_dir=img_dir,
            output_sfm_dir=out_sfm,
            capture_id="empty_test",
        )

        assert report.status == VideoReconstructionStatus.FAILED
        assert report.registered_keyframes == 0
        assert len(poses) == 0
        assert len(points) == 0
        assert intrinsics.confidence_status == "FAILED"


def test_rotation_matrix_orthonormality():
    """Verify camera rotation matrix is strictly orthonormal with determinant +1."""
    # Synthetic random rotation using Rodrigues / Euler angle
    theta = np.radians(35.0)
    r_z = np.array([
        [np.cos(theta), -np.sin(theta), 0.0],
        [np.sin(theta),  np.cos(theta), 0.0],
        [0.0,            0.0,           1.0],
    ])

    pose = SfmCameraPose(
        keyframe_id=0,
        frame_index=0,
        timestamp=0.0,
        t_vec=[1.0, 2.0, 3.0],
        r_matrix=r_z.tolist(),
        qw=np.cos(theta / 2.0),
        qx=0.0,
        qy=0.0,
        qz=np.sin(theta / 2.0),
    )

    r_arr = np.array(pose.r_matrix)
    # Check R * R.T = I
    identity_diff = np.max(np.abs(r_arr @ r_arr.T - np.eye(3)))
    det = np.linalg.det(r_arr)

    assert identity_diff < 1e-6
    assert np.isclose(det, 1.0, atol=1e-5)
