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
from PIL import Image

from backend.app.models.capture import CaptureTier
from backend.app.models.video import SfmCameraPose, VideoCameraIntrinsics
from backend.app.pipelines.photo.fusion import (
    compute_y_up_rotation,
    filter_cross_view_consistency,
    fuse_photo_metric_pointcloud,
)


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


def test_metric_photo_pointcloud_uses_common_reconstruction_contract(tmp_path) -> None:
    """Fuse two synthetic views and preserve PHOTO tier, meter bounds, trajectory, and PLY outputs.

    ``tmp_path`` supplies isolated image/output paths and the function returns no value. Depth is a
    one-meter fronto-parallel surface in OpenCV camera coordinates; identity poses deliberately
    overlap. The fixture assumes Open3D is available. A failure points first to key IDs, image/depth
    resolution, output PLY creation, or common ``ReconstructionResult`` provenance.
    """
    image_paths = {}
    for key, color in [(0, "red"), (1, "blue")]:
        path = tmp_path / f"photo_{key}.jpg"
        Image.new("RGB", (96, 96), color).save(path)
        image_paths[key] = path
    depth_maps = {key: np.ones((96, 96), dtype=np.float32) for key in image_paths}
    depth_masks = {key: np.ones((96, 96), dtype=bool) for key in image_paths}
    poses = [
        SfmCameraPose(
            keyframe_id=key,
            frame_index=key,
            timestamp=float(key),
            t_vec=[0.0, 0.0, 0.0],
            r_matrix=np.eye(3).tolist(),
            is_metric=True,
        )
        for key in image_paths
    ]
    intrinsics = VideoCameraIntrinsics(
        fx=80.0, fy=80.0, cx=48.0, cy=48.0, width=96, height=96
    )
    result, cloud, aligned = fuse_photo_metric_pointcloud(
        image_paths,
        depth_maps,
        depth_masks,
        poses,
        intrinsics,
        tmp_path / "output",
        "contract",
        1.0,
    )
    assert result.tier == CaptureTier.PHOTO
    assert result.metrics["unit"] == "meters"
    assert result.trajectory is not None and len(result.trajectory.poses) == 2
    assert len(cloud.points) > 0 and len(aligned) == 2
    assert (tmp_path / "output" / "photo_pointcloud_filtered.ply").exists()
