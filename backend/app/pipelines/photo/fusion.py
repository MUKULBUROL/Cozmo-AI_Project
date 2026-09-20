"""Stage 8 photo metric cloud fusion, cross-view consistency, and Y-up alignment.

1. Why this file exists:
   Fuses registered still-image metric depth into the common reconstruction contract while
   rejecting unsupported single-view geometry and normalizing the SfM gauge for shared geometry.
2. Pipeline stage:
   Stage 8, Steps 13-15 (semi-dense cloud, consistency, and common representation).
3. Inputs:
   Metric depth/masks, normalized RGB images, metric poses, and camera intrinsics.
4. Outputs:
   ``photo_pointcloud_raw.ply``, ``photo_pointcloud_filtered.ply``, and ReconstructionResult.
5. Coordinate system:
   Input camera is OpenCV; output world is right-handed Y-up with XZ as the floor plane.
6. Units:
   All output positions, consistency residuals, and voxel sizes are meters.
7. Dependencies:
   Stage 7 unprojection, NumPy, SciPy rotations, OpenCV, and Open3D.
8. Assumptions:
   Camera image-down axes provide a usable aggregate gravity cue after EXIF normalization.
9. Failure modes:
   No valid depth, unstable up direction, too few supported voxels, or Open3D I/O failure.
10. First debugging points:
   Compare raw/filtered PLYs and inspect cross-view support counts and metric bounds.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np
import open3d as o3d
from scipy.spatial.transform import Rotation

from backend.app.models.capture import CameraIntrinsics, CaptureTier, Pose6D
from backend.app.models.reconstruction import BoundingBox3D, CameraTrajectory, PointCloudSummary, ReconstructionResult
from backend.app.models.video import SfmCameraPose, VideoCameraIntrinsics
from backend.app.pipelines.video.fusion import unproject_metric_depth_map


def compute_y_up_rotation(poses: List[SfmCameraPose]) -> np.ndarray:
    """Estimate a world-gauge rotation from normalized camera image-up directions.

    Parameters:
        poses: Registered world-from-camera rotations; camera +Y points down in images.
    Returns:
        A 3x3 rotation mapping the robust world up direction onto global ``[0, 1, 0]``.
    Coordinates/units:
        Direction vectors are unitless; no translation or metric scale is changed.
    Assumptions:
        Most photos are upright after EXIF normalization and not captured with extreme roll.
    Failure/debugging:
        Raises ``ValueError`` for no valid rotations or degenerate up vectors. Inspect pose matrices.
    """
    up_vectors = []
    for pose in poses:
        matrix = np.asarray(pose.r_matrix, dtype=np.float64)
        if matrix.shape == (3, 3) and np.all(np.isfinite(matrix)):
            up_vectors.append(matrix @ np.array([0.0, -1.0, 0.0]))
    if not up_vectors:
        raise ValueError("Cannot align photo cloud to Y-up without valid camera rotations")
    up = np.median(np.asarray(up_vectors), axis=0)
    norm = float(np.linalg.norm(up))
    if norm < 1e-8:
        raise ValueError("Camera up directions are degenerate")
    up /= norm
    target = np.array([0.0, 1.0, 0.0])
    cross = np.cross(up, target)
    dot = float(np.clip(np.dot(up, target), -1.0, 1.0))
    if np.linalg.norm(cross) < 1e-8:
        return np.eye(3) if dot > 0 else Rotation.from_rotvec(np.array([np.pi, 0.0, 0.0])).as_matrix()
    axis = cross / np.linalg.norm(cross)
    return Rotation.from_rotvec(axis * np.arccos(dot)).as_matrix()


def filter_cross_view_consistency(
    points_by_view: List[np.ndarray],
    colors_by_view: List[np.ndarray],
    voxel_size_m: float = 0.08,
    min_view_support: int = 2,
) -> Tuple[np.ndarray, np.ndarray, Dict[str, float | int | str]]:
    """Retain geometry observed by multiple views using a conservative metric voxel test.

    Parameters:
        points_by_view: World-coordinate meter points for each registered image.
        colors_by_view: Matching RGB values in 0-1 range for each view.
        voxel_size_m: Consistency voxel edge length in meters.
        min_view_support: Distinct-view count required to accept a voxel.
    Returns:
        Filtered points/colors and support/residual statistics.
    Coordinates/units:
        Points and residuals are meters in the same world frame.
    Assumptions:
        Correctly aligned overlapping surfaces fall into common 8 cm voxels.
    Failure/debugging:
        When fewer than 100 points have multi-view support, all points are retained but status is
        ``PROVISIONAL``; inspect pose/depth consistency rather than treating it as agreement.
    """
    voxel_views: Dict[Tuple[int, int, int], set[int]] = {}
    for view_id, points in enumerate(points_by_view):
        for key in np.floor(points / voxel_size_m).astype(np.int64):
            voxel_views.setdefault(tuple(key), set()).add(view_id)
    selected_points: List[np.ndarray] = []
    selected_colors: List[np.ndarray] = []
    rejected = 0
    for view_id, (points, colors) in enumerate(zip(points_by_view, colors_by_view)):
        keys = np.floor(points / voxel_size_m).astype(np.int64)
        mask = np.array([len(voxel_views[tuple(key)]) >= min_view_support for key in keys])
        selected_points.append(points[mask])
        selected_colors.append(colors[mask])
        rejected += int(np.count_nonzero(~mask))
    supported_count = sum(len(points) for points in selected_points)
    all_points = np.vstack(points_by_view)
    all_colors = np.vstack(colors_by_view)
    if supported_count < 100:
        return all_points, all_colors, {
            "status": "PROVISIONAL",
            "supported_points": supported_count,
            "rejected_points": rejected,
            "depth_consistency_residual_m": voxel_size_m,
        }
    points = np.vstack(selected_points)
    colors = np.vstack(selected_colors)
    return points, colors, {
        "status": "GOOD",
        "supported_points": len(points),
        "rejected_points": rejected,
        "depth_consistency_residual_m": voxel_size_m,
    }


def fuse_photo_metric_pointcloud(
    image_paths: Dict[int, Path],
    depth_maps: Dict[int, np.ndarray],
    depth_masks: Dict[int, np.ndarray],
    poses: List[SfmCameraPose],
    intrinsics: VideoCameraIntrinsics,
    output_dir: Path,
    capture_id: str,
    scale_factor_applied: float,
    voxel_size_m: float = 0.03,
) -> Tuple[ReconstructionResult, o3d.geometry.PointCloud, List[SfmCameraPose]]:
    """Fuse metric still depths into a filtered Y-up PHOTO reconstruction.

    Parameters:
        image_paths/depth_maps/depth_masks: Registered per-photo RGB and metric depth evidence.
        poses: Metric world-from-camera poses before gauge alignment.
        intrinsics: Processing-image pinhole parameters in pixels.
        output_dir/capture_id: Artifact destination and stable identity.
        scale_factor_applied: Meters per original SfM unit.
        voxel_size_m: Final Open3D downsample resolution in meters.
    Returns:
        Common reconstruction, filtered cloud, and Y-up metric poses.
    Coordinates/units:
        Output is right-handed Y-up meters; camera rotations and centers receive the same rigid
        gauge rotation, while metric scale is unchanged.
    Assumptions:
        Input depth resolution matches normalized RGB/intrinsics.
    Failure/debugging:
        Raises ``ValueError`` when no registered valid depth exists. Inspect keyed IDs and masks.
    """
    started = time.time()
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    alignment = compute_y_up_rotation(poses)
    points_by_view: List[np.ndarray] = []
    colors_by_view: List[np.ndarray] = []
    aligned_poses: List[SfmCameraPose] = []
    trajectory: List[Pose6D] = []
    for pose in poses:
        key = pose.keyframe_id
        if key not in image_paths or key not in depth_maps:
            continue
        points_cam, uv = unproject_metric_depth_map(
            depth_maps[key], intrinsics.fx, intrinsics.fy, intrinsics.cx, intrinsics.cy,
            valid_mask=depth_masks.get(key), stride=3,
        )
        if not len(points_cam):
            continue
        image = cv2.imread(str(image_paths[key]))
        colors = cv2.cvtColor(image, cv2.COLOR_BGR2RGB).astype(np.float32)[uv[:, 0], uv[:, 1]] / 255.0 if image is not None else np.full((len(points_cam), 3), 0.7)
        rotation = np.asarray(pose.r_matrix, dtype=np.float64)
        center = np.asarray(pose.t_vec, dtype=np.float64)
        points_world = points_cam @ rotation.T + center
        points_world = points_world @ alignment.T
        aligned_rotation = alignment @ rotation
        aligned_center = alignment @ center
        quaternion_xyzw = Rotation.from_matrix(aligned_rotation).as_quat()
        pose_data = pose.model_dump()
        pose_data.update({
            "t_vec": aligned_center.tolist(),
            "r_matrix": aligned_rotation.tolist(),
            "qx": float(quaternion_xyzw[0]), "qy": float(quaternion_xyzw[1]),
            "qz": float(quaternion_xyzw[2]), "qw": float(quaternion_xyzw[3]),
            "is_metric": True,
        })
        aligned_pose = SfmCameraPose(**pose_data)
        aligned_poses.append(aligned_pose)
        trajectory.append(Pose6D(timestamp=pose.timestamp, frame_index=pose.frame_index, x=float(aligned_center[0]), y=float(aligned_center[1]), z=float(aligned_center[2]), qx=aligned_pose.qx, qy=aligned_pose.qy, qz=aligned_pose.qz, qw=aligned_pose.qw))
        points_by_view.append(points_world)
        colors_by_view.append(colors)
    if not points_by_view:
        raise ValueError("Photo fusion produced zero valid registered depth views")
    raw_points = np.vstack(points_by_view)
    raw_colors = np.vstack(colors_by_view)
    raw_cloud = o3d.geometry.PointCloud()
    raw_cloud.points = o3d.utility.Vector3dVector(raw_points)
    raw_cloud.colors = o3d.utility.Vector3dVector(raw_colors)
    o3d.io.write_point_cloud(str(output_dir / "photo_pointcloud_raw.ply"), raw_cloud)
    consistent_points, consistent_colors, consistency = filter_cross_view_consistency(points_by_view, colors_by_view)
    cloud = o3d.geometry.PointCloud()
    cloud.points = o3d.utility.Vector3dVector(consistent_points)
    cloud.colors = o3d.utility.Vector3dVector(consistent_colors)
    cloud = cloud.voxel_down_sample(voxel_size_m)
    if len(cloud.points) >= 20:
        cloud, _ = cloud.remove_statistical_outlier(nb_neighbors=min(20, len(cloud.points) - 1), std_ratio=2.0)
        cloud.estimate_normals(search_param=o3d.geometry.KDTreeSearchParamHybrid(radius=0.15, max_nn=30))
    o3d.io.write_point_cloud(str(output_dir / "photo_pointcloud_filtered.ply"), cloud)
    points = np.asarray(cloud.points)
    if not len(points):
        raise ValueError("Photo fusion filtering removed every metric point")
    low, high = points.min(axis=0), points.max(axis=0)
    bounds = BoundingBox3D(min_x=float(low[0]), max_x=float(high[0]), min_y=float(low[1]), max_y=float(high[1]), min_z=float(low[2]), max_z=float(high[2]))
    reconstruction = ReconstructionResult(
        reconstruction_id=f"recon_{capture_id}_photo",
        capture_id=capture_id,
        tier=CaptureTier.PHOTO,
        point_cloud_summary=PointCloudSummary(point_count=len(points), has_colors=True, has_normals=len(cloud.normals) == len(points), bounds=bounds, voxel_size_meters=voxel_size_m),
        point_cloud_file=str((output_dir / "photo_pointcloud_filtered.ply").resolve()),
        trajectory=CameraTrajectory(poses=trajectory, accumulated_drift_meters=0.0, loop_closure_detected=False),
        scale_factor_applied=scale_factor_applied,
        reconstruction_method="photo_pycolmap_depth_anything_v2_metric",
        reconstruction_time_seconds=time.time() - started,
        metrics={"raw_point_count": len(raw_points), "filtered_point_count": len(points), "metric_bounds": bounds.model_dump(), "voxel_size_m": voxel_size_m, "cross_view_consistency": consistency, "coordinate_system": "right_handed_y_up_xz_floor", "unit": "meters"},
    )
    return reconstruction, cloud, aligned_poses
