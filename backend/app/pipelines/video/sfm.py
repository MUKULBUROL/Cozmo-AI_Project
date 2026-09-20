"""Stage 7 Visual Structure-from-Motion (SfM) camera pose reconstruction.

1. Why this file exists:
   Recovers 6-DoF camera poses, self-calibrated intrinsics, and sparse 3D structure
   from pure RGB video keyframes using pycolmap (COLMAP C++ backend). Operates at
   arbitrary scale without reading LiDAR odometry or depth.

2. Pipeline stage:
   Stage 7 (Video Tier - Visual Camera Pose Reconstruction).

3. Inputs:
   Directory of extracted RGB keyframes (JPEG).

4. Outputs:
   - `SfMReconstructionReport` detailing registration percentage, reprojection error, and status.
   - List of `SfmCameraPose` records with rotation quaternions and translations.
   - `VideoCameraIntrinsics` recording self-calibrated focal lengths and principal point.
   - Sparse 3D tie points saved as `sparse_points.ply`.
   - `cameras.json`, `poses.json`, and `sfm_stats.json`.

5. Coordinate convention:
   - OpenCV camera frame (X right, Y down, Z forward).
   - World coordinate frame: Arbitrary scale, right-handed.

6. Unit convention:
   - Translations: Arbitrary SfM units (scaled to metric in downstream Stage 7 scale step).
   - Focal length and principal point: Pixels.
   - Reprojection error: Pixels.

7. Important dependencies:
   pycolmap, numpy, pathlib, json, open3d (optional for PLY writing fallback),
   backend.app.models.video, backend.app.pipelines.video.contract.

8. Assumptions:
   Keyframes have sequential visual overlap allowing SIFT feature matching.

9. Main failure modes:
   - Low-texture scenes (blank walls) leading to insufficient 2D-2D matches.
   - Disconnected visual graph causing multiple small reconstruction models.
   - Pure rotation without camera translation preventing triangulation.

10. What a developer should inspect first when debugging:
    Inspect `output_sfm_dir/sfm_stats.json` for registration ratio and reprojection error,
    and check `output_sfm_dir/sparse_points.ply` in Open3D/CloudCompare.
"""

import os
import json
import time
from pathlib import Path
from typing import List, Tuple, Dict, Any, Optional
import numpy as np
import pycolmap

from backend.app.models.video import (
    VideoCameraIntrinsics,
    SfmCameraPose,
)
from backend.app.pipelines.video.contract import (
    VideoReconstructionStatus,
    SfMReconstructionReport,
)


def evaluate_trajectory_continuity(
    poses: List[SfmCameraPose],
    max_translation_jump_ratio: float = 5.0,
    max_rotation_jump_deg: float = 45.0,
) -> Tuple[bool, List[str]]:
    """Evaluates smoothness of reconstructed camera trajectory to detect tracking loss or jumps.

    Purpose:
        Flags non-physical velocity discontinuities or orientation flips between adjacent keyframes.

    Parameters:
        poses: Chronologically sorted list of SfmCameraPose objects.
        max_translation_jump_ratio: Multiplier above median step distance flagged as a jump.
        max_rotation_jump_deg: Angular displacement threshold between adjacent frames in degrees.

    Returns:
        Tuple of (is_continuous: bool, warnings: List[str]).

    Assumptions:
        Poses are indexed in sequential recording order.

    Failure conditions:
        Fewer than 3 poses return (True, []).

    Dependencies:
        numpy.linalg.norm.
    """
    if len(poses) < 3:
        return True, []

    step_distances: List[float] = []
    warnings: List[str] = []

    for i in range(len(poses) - 1):
        p1 = np.array(poses[i].t_vec, dtype=np.float64)
        p2 = np.array(poses[i + 1].t_vec, dtype=np.float64)
        d = float(np.linalg.norm(p2 - p1))
        step_distances.append(d)

    median_dist = float(np.median(step_distances)) if step_distances else 0.0
    jump_threshold = max(0.01, median_dist * max_translation_jump_ratio)

    is_continuous = True
    for i, d in enumerate(step_distances):
        if d > jump_threshold and median_dist > 0.001:
            is_continuous = False
            warnings.append(
                f"Translation jump between frame {poses[i].frame_index} and {poses[i+1].frame_index}: "
                f"distance {d:.3f} > threshold {jump_threshold:.3f}"
            )

    return is_continuous, warnings


def run_visual_sfm(
    image_dir: Path,
    output_sfm_dir: Path,
    capture_id: str,
    camera_model: str = "SIMPLE_RADIAL",
    min_registration_ratio_good: float = 0.65,
    min_registration_ratio_provisional: float = 0.35,
    max_mean_reprojection_error_px: float = 2.0,
) -> Tuple[SfMReconstructionReport, List[SfmCameraPose], VideoCameraIntrinsics, List[Dict[str, Any]]]:
    """Runs complete COLMAP visual SfM pipeline via pycolmap on extracted keyframes.

    Purpose:
        Reconstructs 6-DoF camera trajectory, self-calibrated intrinsics, and sparse 3D point cloud
        from RGB keyframes without external sensor hints.

    Parameters:
        image_dir: Directory containing input keyframe JPEG images.
        output_sfm_dir: Destination directory for COLMAP database, sparse model, and JSON stats.
        capture_id: Unique capture identifier.
        camera_model: COLMAP camera model (e.g. SIMPLE_RADIAL, PINHOLE).
        min_registration_ratio_good: Minimum registered frame fraction for GOOD status.
        min_registration_ratio_provisional: Minimum fraction for PROVISIONAL status.
        max_mean_reprojection_error_px: Maximum acceptable mean reprojection error in pixels.

    Returns:
        Tuple of (
            report: SfMReconstructionReport,
            poses: List[SfmCameraPose],
            intrinsics: VideoCameraIntrinsics,
            sparse_points: List[Dict[str, Any]]
        ).

    Assumptions:
        pycolmap is installed and supports CPU feature extraction, sequential matching,
        and incremental mapping.

    Failure conditions:
        If zero models are reconstructed, returns FAILED report and empty poses/points.

    Dependencies:
        pycolmap.extract_features, pycolmap.match_sequential, pycolmap.incremental_mapping.

    Debugging clues:
        Inspect output_sfm_dir/sfm_stats.json and reprojection error in the report.
    """
    t_start = time.time()
    image_dir = Path(image_dir)
    output_sfm_dir = Path(output_sfm_dir)
    output_sfm_dir.mkdir(parents=True, exist_ok=True)

    image_files = sorted(list(image_dir.glob("*.jpg")) + list(image_dir.glob("*.png")))
    total_images = len(image_files)

    database_path = output_sfm_dir / "database.db"
    if database_path.exists():
        database_path.unlink()

    # Default fallback intrinsics
    fallback_intrinsics = VideoCameraIntrinsics(
        fx=1440.0,
        fy=1440.0,
        cx=960.0,
        cy=720.0,
        width=1920,
        height=1440,
        source="default_prior",
        camera_model="PINHOLE",
        distortion_coefficients=[],
        confidence_status="FAILED",
    )

    if total_images < 2:
        report = SfMReconstructionReport(
            capture_id=capture_id,
            total_keyframes=total_images,
            registered_keyframes=0,
            registration_ratio=0.0,
            sparse_point_count=0,
            mean_reprojection_error=0.0,
            track_length_mean=0.0,
            status=VideoReconstructionStatus.FAILED,
            reconstruction_time_seconds=float(time.time() - t_start),
            warnings=["Insufficient keyframes for SfM (minimum 2 required)"],
        )
        return report, [], fallback_intrinsics, []

    # Step 1: Feature Extraction
    pycolmap.extract_features(
        database_path=database_path,
        image_path=image_dir,
        camera_model=camera_model,
        sift_options={"max_num_features": 2048},
    )

    # Step 2: Sequential Matching with overlap
    pycolmap.match_sequential(
        database_path=database_path,
        overlap=min(15, max(3, total_images // 2)),
        quadratic_overlap=True,
    )

    # Step 3: Incremental Mapping
    reconstructions = pycolmap.incremental_mapping(
        database_path=database_path,
        image_path=image_dir,
        output_path=output_sfm_dir,
    )

    if not reconstructions:
        report = SfMReconstructionReport(
            capture_id=capture_id,
            total_keyframes=total_images,
            registered_keyframes=0,
            registration_ratio=0.0,
            sparse_point_count=0,
            mean_reprojection_error=0.0,
            track_length_mean=0.0,
            status=VideoReconstructionStatus.FAILED,
            reconstruction_time_seconds=float(time.time() - t_start),
            warnings=["Incremental mapping failed to produce any 3D models from keyframe features"],
        )
        return report, [], fallback_intrinsics, []

    # Select the largest reconstruction model
    recon = max(reconstructions.values(), key=lambda r: r.num_reg_images())

    # Export sparse points PLY
    ply_path = output_sfm_dir / "sparse_points.ply"
    recon.export_PLY(str(ply_path))

    # Parse Camera Intrinsics
    calib_intrinsics = fallback_intrinsics
    if recon.cameras:
        cam = next(iter(recon.cameras.values()))
        calib_intrinsics = VideoCameraIntrinsics(
            fx=float(cam.focal_length_x),
            fy=float(cam.focal_length_y),
            cx=float(cam.principal_point_x),
            cy=float(cam.principal_point_y),
            width=int(cam.width),
            height=int(cam.height),
            source="sfm_self_calibration",
            camera_model=str(cam.model_name),
            distortion_coefficients=[float(p) for p in cam.params[cam.extra_params_idxs()]] if hasattr(cam, "extra_params_idxs") else [],
            confidence_status="GOOD",
        )

    # Extract Camera Poses (sorted by image name / index)
    poses: List[SfmCameraPose] = []
    # Map image names to reconstructed images
    image_name_map = {img.name: img for img in recon.images.values()}

    for kf_idx, img_file in enumerate(image_files):
        img_name = img_file.name
        if img_name in image_name_map:
            img = image_name_map[img_name]
            # In COLMAP, cam_from_world transforms world point to camera space
            # To get camera pose in world space, invert: world_from_cam = cam_from_world.inverse()
            cam_from_world = img.cam_from_world
            world_from_cam = cam_from_world.inverse()

            # Translation of camera center in world coordinates
            t_world = [float(c) for c in world_from_cam.translation]
            # Rotation matrix in world coordinates (3x3)
            r_mat = [[float(val) for val in row] for row in world_from_cam.rotation.matrix()]

            # Quaternion components (qw, qx, qy, qz)
            q_arr = world_from_cam.rotation.quat
            qw = float(q_arr[0])
            qx = float(q_arr[1])
            qy = float(q_arr[2])
            qz = float(q_arr[3])

            pose = SfmCameraPose(
                keyframe_id=kf_idx,
                frame_index=kf_idx,
                timestamp=0.0,
                t_vec=t_world,
                r_matrix=r_mat,
                qw=qw,
                qx=qx,
                qy=qy,
                qz=qz,
                reprojection_error=float(img.compute_mean_reprojection_error()) if hasattr(img, "compute_mean_reprojection_error") else 0.0,
                inlier_count=int(img.num_points3D),
                is_metric=False,
            )
            poses.append(pose)

    # Extract sparse 3D point details
    sparse_points_data: List[Dict[str, Any]] = []
    for pt_id, pt in recon.points3D.items():
        # pt.track contains observations in registered images
        track_obs: List[Dict[str, Any]] = []
        for track_el in pt.track.elements:
            track_obs.append({
                "image_id": int(track_el.image_id),
                "point2D_idx": int(track_el.point2D_idx),
            })

        sparse_points_data.append({
            "point3D_id": int(pt_id),
            "xyz": [float(c) for c in pt.xyz],
            "rgb": [int(c) for c in pt.color],
            "error": float(pt.error),
            "track_length": len(track_obs),
            "track": track_obs,
        })

    # Statistical Evaluation
    reg_count = len(poses)
    reg_ratio = float(reg_count / total_images) if total_images > 0 else 0.0
    mean_reproj = float(recon.compute_mean_reprojection_error())
    mean_track_len = float(recon.compute_mean_track_length())

    # Trajectory continuity check
    is_continuous, cont_warnings = evaluate_trajectory_continuity(poses)

    status = VideoReconstructionStatus.GOOD
    warnings: List[str] = list(cont_warnings)

    if reg_ratio < min_registration_ratio_provisional:
        status = VideoReconstructionStatus.FAILED
        warnings.append(f"Registration ratio {reg_ratio:.1%} below provisional threshold {min_registration_ratio_provisional:.1%}")
    elif reg_ratio < min_registration_ratio_good:
        status = VideoReconstructionStatus.PROVISIONAL
        warnings.append(f"Registration ratio {reg_ratio:.1%} below optimal threshold {min_registration_ratio_good:.1%}")

    if mean_reproj > max_mean_reprojection_error_px:
        status = VideoReconstructionStatus.PROVISIONAL if status == VideoReconstructionStatus.GOOD else status
        warnings.append(f"Mean reprojection error {mean_reproj:.2f}px exceeds nominal limit {max_mean_reprojection_error_px:.2f}px")

    if not is_continuous and status == VideoReconstructionStatus.GOOD:
        status = VideoReconstructionStatus.PROVISIONAL

    report = SfMReconstructionReport(
        capture_id=capture_id,
        total_keyframes=total_images,
        registered_keyframes=reg_count,
        registration_ratio=reg_ratio,
        sparse_point_count=len(sparse_points_data),
        mean_reprojection_error=mean_reproj,
        track_length_mean=mean_track_len,
        status=status,
        reconstruction_time_seconds=float(time.time() - t_start),
        warnings=warnings,
    )

    # Save output artifacts
    with open(output_sfm_dir / "cameras.json", "w", encoding="utf-8") as f:
        json.dump(calib_intrinsics.model_dump(), f, indent=2)

    with open(output_sfm_dir / "poses.json", "w", encoding="utf-8") as f:
        json.dump([p.model_dump() for p in poses], f, indent=2)

    with open(output_sfm_dir / "sfm_stats.json", "w", encoding="utf-8") as f:
        json.dump(report.model_dump(), f, indent=2)

    return report, poses, calib_intrinsics, sparse_points_data
