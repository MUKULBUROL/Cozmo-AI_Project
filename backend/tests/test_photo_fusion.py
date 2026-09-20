"""Stage 8 tests for photo cloud consistency, Y-up alignment, and common contracts.

1. Why this file exists: protects shared unprojection reuse and PHOTO reconstruction provenance.
2. Pipeline stage: Stage 8 semi-dense metric fusion.
3. Inputs: synthetic point arrays and camera rotations.
4. Outputs: assertions over support filtering and alignment matrices.
5. Coordinate system: OpenCV camera inputs and Y-up output world.
6. Units: meters for points and voxels.
7. Dependencies: NumPy and the Stage 8 fusion module.
8. Assumptions: camera image-up directions are consistent across views.
9. Failure modes: invalid rotations/support accounting fail assertions.
10. First debugging points: inspect transformed up vectors and voxel keys.
"""

import numpy as np

from backend.app.models.video import SfmCameraPose
from backend.app.pipelines.photo.fusion import compute_y_up_rotation, filter_cross_view_consistency


def test_y_up_alignment_maps_camera_up_to_global_y() -> None:
    """Map the world camera-up estimate to positive global Y without altering scale."""
    pose = SfmCameraPose(keyframe_id=0, frame_index=0, timestamp=0.0, t_vec=[0.0, 0.0, 0.0], r_matrix=np.eye(3).tolist())
    alignment = compute_y_up_rotation([pose])
    transformed = alignment @ np.array([0.0, -1.0, 0.0])
    assert np.allclose(transformed, [0.0, 1.0, 0.0], atol=1e-7)
    assert np.isclose(np.linalg.det(alignment), 1.0)


def test_cross_view_filter_counts_supported_and_rejected_points() -> None:
    """Keep points in shared metric voxels and account for unsupported observations."""
    first = np.array([[0.01, 0.0, 0.01], [2.0, 0.0, 2.0]])
    second = np.array([[0.02, 0.0, 0.02], [3.0, 0.0, 3.0]])
    colors = [np.ones((2, 3)), np.ones((2, 3)) * 0.5]
    points, _, report = filter_cross_view_consistency([first, second], colors, voxel_size_m=0.08)
    assert report["supported_points"] == 2
    assert report["rejected_points"] == 2
    assert len(points) == 4  # Fallback retains all because this tiny unit fixture has <100 support.
    assert report["status"] == "PROVISIONAL"
