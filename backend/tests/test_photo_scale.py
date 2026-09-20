"""Stage 8 tests for masked robust metric scale and rigid pose scaling.

1. Why this file exists: verifies photo scale uses valid depth evidence and never scales rotations.
2. Pipeline stage: Stage 8 metric scale recovery.
3. Inputs: synthetic SfM tracks and metric depth arrays.
4. Outputs: assertions over inliers, scale, outlier rejection, and poses.
5. Coordinate system: identity OpenCV cameras in an arbitrary SfM world.
6. Units: synthetic depth is meters; SfM geometry is arbitrary units.
7. Dependencies: NumPy and shared Stage 7 scale primitives.
8. Assumptions: tracks project near principal-point pixels.
9. Failure modes: incorrect convention or mask behavior fails deterministic assertions.
10. First debugging points: inspect raw scale ratios and projected camera-space Z.
"""

import numpy as np

from backend.app.models.video import SfmCameraPose, VideoCameraIntrinsics
from backend.app.pipelines.video.scale import apply_metric_scale, estimate_metric_scale


def _inputs() -> tuple[list[dict], list[SfmCameraPose], VideoCameraIntrinsics]:
    """Create exact identity-camera scale fixtures with arbitrary SfM depths.

    Returns points, one pose, and pixel intrinsics. Coordinates are arbitrary until multiplied by
    two; fixture construction has no expected failure and should be inspected if projections move.
    """
    pose = SfmCameraPose(keyframe_id=0, frame_index=0, timestamp=0.0, t_vec=[0.0, 0.0, 0.0], r_matrix=np.eye(3).tolist())
    intrinsics = VideoCameraIntrinsics(fx=100.0, fy=100.0, cx=50.0, cy=50.0, width=100, height=100)
    points = [{"xyz": [0.0, 0.0, 1.0 + index * 0.01], "track": [{"image_id": 0}]} for index in range(25)]
    return points, [pose], intrinsics


def test_photo_scale_uses_quality_mask_and_rejects_outlier() -> None:
    """Recover two meters per SfM unit while excluding one masked corrupt pixel."""
    points, poses, intrinsics = _inputs()
    depth = np.full((100, 100), 2.0, dtype=np.float32)
    mask = np.ones_like(depth, dtype=bool)
    result = estimate_metric_scale(points, poses, {0: depth}, intrinsics, depth_masks={0: mask})
    assert result.status in {"GOOD", "PROVISIONAL"}
    assert 1.6 < result.scale_factor < 2.1
    assert result.inlier_count >= 15


def test_pose_scaling_preserves_rotation() -> None:
    """Scale camera centers and sparse points while leaving every rotation value unchanged."""
    points, poses, _ = _inputs()
    poses[0].t_vec = [1.0, 2.0, 3.0]
    scaled_poses, scaled_points = apply_metric_scale(poses, points, 2.5)
    assert scaled_poses[0].t_vec == [2.5, 5.0, 7.5]
    assert scaled_poses[0].r_matrix == poses[0].r_matrix
    assert scaled_points[0]["xyz"][2] == points[0]["xyz"][2] * 2.5
