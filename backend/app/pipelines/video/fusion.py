"""Stage 7 Video Metric Point Cloud Unprojection, Fusion, and Spatial Cleaning.

1. Why this file exists:
   Unprojects predicted metric depth maps into 3D camera space, transforms them into the
   scaled world coordinate frame using visual SfM poses, fuses multi-view observations,
   and applies conservative voxel downsampling and outlier removal. Outputs standard
   `ReconstructionResult` adhering to the common Stage 1-6 metric interface.

2. Pipeline stage:
   Stage 7 (Video Tier - 3D Metric Point Cloud Fusion).

3. Inputs:
   - Scaled camera poses (in meters) for registered keyframes.
   - Metric depth maps (meters) and confidence masks.
   - Keyframe images (for RGB color binding).
   - Camera intrinsics.

4. Outputs:
   - `video_pointcloud_raw.ply`
   - `video_pointcloud_filtered.ply`
   - `ReconstructionResult` object with tier=CaptureTier.VIDEO.

5. Coordinate convention:
   World coordinates in meters, right-handed (Z up or Y up matching existing geometry engine).

6. Unit convention:
   Meters for positions, distances, and voxel dimensions.

7. Important dependencies:
   numpy, open3d, cv2, pathlib, backend.app.models.capture, backend.app.models.reconstruction.

8. Assumptions:
   Camera poses have been scaled into physical meters by the scale recovery stage.

9. Main failure modes:
   - Zero valid 3D points remaining after depth masking -> raises ValueError or returns empty cloud.
   - Point cloud density too low -> flagged in summary.

10. What a developer should inspect first when debugging:
    Inspect `video_pointcloud_filtered.ply` in Open3D / CloudCompare to confirm structural alignment.
"""

import os
import time
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
import numpy as np
import cv2
import open3d as o3d

from backend.app.models.capture import (
    CaptureTier,
    CameraIntrinsics,
    Pose6D,
)
from backend.app.models.reconstruction import (
    BoundingBox3D,
    CameraTrajectory,
    PointCloudSummary,
    ReconstructionResult,
)
from backend.app.models.video import (
    SfmCameraPose,
    VideoCameraIntrinsics,
)


def unproject_metric_depth_map(
    depth_m: np.ndarray,
    fx: float,
    fy: float,
    cx: float,
    cy: float,
    valid_mask: Optional[np.ndarray] = None,
    stride: int = 2,
) -> Tuple[np.ndarray, np.ndarray]:
    """Vectorized pinhole unprojection of 2D metric depth into 3D camera coordinates.

    Formula:
        Z = depth_m (meters)
        X = (u - cx) * Z / fx
        Y = (v - cy) * Z / fy

    Parameters:
        depth_m: 2D float32 array of depth in meters.
        fx, fy, cx, cy: Camera intrinsics in pixels.
        valid_mask: Optional boolean mask selecting valid pixels.
        stride: Subsampling stride to manage memory and point density.

    Returns:
        Tuple of (points_cam: (N, 3) float32 array, valid_uv: (N, 2) int32 array).
    """
    h, w = depth_m.shape

    # Subsample grid for computational efficiency
    v_idx, u_idx = np.mgrid[0:h:stride, 0:w:stride]

    sub_depth = depth_m[v_idx, u_idx]
    if valid_mask is not None:
        sub_valid = valid_mask[v_idx, u_idx] & np.isfinite(sub_depth) & (sub_depth > 0.1)
    else:
        sub_valid = np.isfinite(sub_depth) & (sub_depth > 0.1)

    if not np.any(sub_valid):
        return np.empty((0, 3), dtype=np.float32), np.empty((0, 2), dtype=np.int32)

    u_sel = u_idx[sub_valid].astype(np.float32)
    v_sel = v_idx[sub_valid].astype(np.float32)
    z_sel = sub_depth[sub_valid].astype(np.float32)

    x_sel = (u_sel - cx) * z_sel / fx
    y_sel = (v_sel - cy) * z_sel / fy

    points_cam = np.stack([x_sel, y_sel, z_sel], axis=-1).astype(np.float32)
    uv_sel = np.stack([v_idx[sub_valid], u_idx[sub_valid]], axis=-1).astype(np.int32)

    return points_cam, uv_sel


def fuse_video_metric_pointcloud(
    keyframe_paths: Dict[int, Path],
    depth_maps: Dict[int, np.ndarray],
    depth_masks: Dict[int, np.ndarray],
    poses: List[SfmCameraPose],
    intrinsics: VideoCameraIntrinsics,
    output_dir: Path,
    capture_id: str,
    scale_factor_applied: float = 1.0,
    voxel_size_m: float = 0.03,
    nb_neighbors: int = 20,
    std_ratio: float = 2.0,
) -> Tuple[ReconstructionResult, o3d.geometry.PointCloud]:
    """Unprojects and fuses multi-view metric depth into a clean metric 3D point cloud.

    Purpose:
        Produces the authoritative metric point cloud required by the downstream shared
        structural extraction pipeline (Stage 2-6).

    Parameters:
        keyframe_paths: Dict mapping keyframe_id to RGB image file.
        depth_maps: Dict mapping keyframe_id to 2D metric depth in meters.
        depth_masks: Dict mapping keyframe_id to 2D boolean quality mask.
        poses: Scaled camera poses in physical meters.
        intrinsics: Camera intrinsics.
        output_dir: Directory where point cloud PLYs and summaries will be written.
        capture_id: Unique capture ID.
        scale_factor_applied: Multiplier applied to SfM units to achieve meters.
        voxel_size_m: Voxel grid resolution in meters for downsampling.
        nb_neighbors: Neighborhood size for statistical outlier removal.
        std_ratio: Standard deviation multiplier for statistical outlier removal.

    Returns:
        Tuple of (ReconstructionResult, o3d.geometry.PointCloud).

    Assumptions:
        Poses are scaled in physical meters and camera coordinate frame matches pinhole unprojection.
    """
    t_start = time.time()
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    fx, fy = intrinsics.fx, intrinsics.fy
    cx, cy = intrinsics.cx, intrinsics.cy

    all_points: List[np.ndarray] = []
    all_colors: List[np.ndarray] = []
    trajectory_poses: List[Pose6D] = []

    for pose in poses:
        kf_id = pose.keyframe_id
        if kf_id not in depth_maps or kf_id not in keyframe_paths:
            continue

        depth = depth_maps[kf_id]
        mask = depth_masks.get(kf_id, None)

        pts_cam, uvs = unproject_metric_depth_map(depth, fx, fy, cx, cy, valid_mask=mask, stride=3)
        if len(pts_cam) == 0:
            continue

        # Load RGB image for color binding
        img_bgr = cv2.imread(str(keyframe_paths[kf_id]))
        if img_bgr is not None:
            # OpenCV BGR -> RGB normalized [0, 1]
            img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
            colors = img_rgb[uvs[:, 0], uvs[:, 1]]
        else:
            colors = np.ones((len(pts_cam), 3), dtype=np.float32) * 0.7

        # Transform from camera to world coordinates:
        # X_world = R_wc * X_cam + C_world
        r_wc = np.array(pose.r_matrix, dtype=np.float32)
        c_wc = np.array(pose.t_vec, dtype=np.float32)

        pts_world = (pts_cam @ r_wc.T) + c_wc

        all_points.append(pts_world)
        all_colors.append(colors)

        # Record trajectory pose
        trajectory_poses.append(Pose6D(
            timestamp=pose.timestamp,
            frame_index=pose.frame_index,
            x=float(c_wc[0]),
            y=float(c_wc[1]),
            z=float(c_wc[2]),
            qw=float(pose.qw),
            qx=float(pose.qx),
            qy=float(pose.qy),
            qz=float(pose.qz),
        ))

    if not all_points:
        raise ValueError(f"Fusion failed: zero valid 3D points generated from {len(poses)} poses")

    fused_points = np.vstack(all_points)
    fused_colors = np.vstack(all_colors)

    # Build Open3D point cloud
    raw_pcd = o3d.geometry.PointCloud()
    raw_pcd.points = o3d.utility.Vector3dVector(fused_points.astype(np.float64))
    raw_pcd.colors = o3d.utility.Vector3dVector(fused_colors.astype(np.float64))

    raw_ply_path = output_dir / "video_pointcloud_raw.ply"
    o3d.io.write_point_cloud(str(raw_ply_path), raw_pcd)

    # Voxel Downsampling
    pcd_down = raw_pcd.voxel_down_sample(voxel_size=voxel_size_m)

    # Statistical Outlier Removal
    pcd_filtered, _ = pcd_down.remove_statistical_outlier(
        nb_neighbors=nb_neighbors,
        std_ratio=std_ratio,
    )

    # Estimate surface normals
    pcd_filtered.estimate_normals(
        search_param=o3d.geometry.KDTreeSearchParamHybrid(radius=0.15, max_nn=30)
    )

    filtered_ply_path = output_dir / "video_pointcloud_filtered.ply"
    o3d.io.write_point_cloud(str(filtered_ply_path), pcd_filtered)

    # Compute bounding box and summary
    pts_arr = np.asarray(pcd_filtered.points)
    min_b = pts_arr.min(axis=0)
    max_b = pts_arr.max(axis=0)

    bounds = BoundingBox3D(
        min_x=float(min_b[0]), max_x=float(max_b[0]),
        min_y=float(min_b[1]), max_y=float(max_b[1]),
        min_z=float(min_b[2]), max_z=float(max_b[2]),
    )

    summary = PointCloudSummary(
        point_count=len(pts_arr),
        has_colors=True,
        has_normals=True,
        bounds=bounds,
        voxel_size_meters=voxel_size_m,
    )

    trajectory = CameraTrajectory(
        poses=trajectory_poses,
        accumulated_drift_meters=0.0,
        loop_closure_detected=False,
    )

    recon_result = ReconstructionResult(
        reconstruction_id=f"recon_{capture_id}_video",
        capture_id=capture_id,
        tier=CaptureTier.VIDEO,
        point_cloud_summary=summary,
        point_cloud_file=str(filtered_ply_path.resolve()),
        trajectory=trajectory,
        scale_factor_applied=float(scale_factor_applied),
        reconstruction_method="PyCOLMAP_DepthAnythingV2_Metric",
        reconstruction_time_seconds=float(time.time() - t_start),
        metrics={
            "raw_point_count": len(fused_points),
            "filtered_point_count": len(pts_arr),
            "keyframes_fused": len(trajectory_poses),
            "voxel_size_m": voxel_size_m,
        },
    )

    return recon_result, pcd_filtered
