"""
Stage 7 Visual Structure-from-Motion (SfM) Camera Pose Reconstruction.

1. Why this file exists:
   Recovers camera trajectory and sparse 3D scene structure from ordinary RGB video
   keyframes using pycolmap (COLMAP wrapper). Operates up to an arbitrary visual scale
   without any LiDAR odometry, sensor depth, or external position cues.

2. Pipeline stage:
   Stage 7 (Video Tier: Visual Camera Pose Reconstruction & Sparse Structure).

3. Inputs:
   Directory containing extracted RGB keyframe images and KeyframeManifest.

4. Outputs:
   - `sfm/cameras.json`: Self-calibrated pinhole camera intrinsics with distortion.
   - `sfm/poses.json`: Camera poses (rotation matrix, translation, quaternion) for registered keyframes.
   - `sfm/sparse_points.ply`: Arbitrary-scale sparse 3D point cloud.
   - `sfm/sfm_stats.json`: Quality metrics (registered ratio, reprojection error, track length, status).

5. Coordinate convention:
   - Camera frame: OpenCV convention (X right, Y down, Z forward).
   - SfM World frame: Arbitrary-scale right-handed coordinate system.
   - Poses: Stored with both `cam_from_world` (projection matrix) and `world_from_cam` (camera center & orientation).

6. Unit convention:
   - Translation & 3D points: Arbitrary SfM units (converted to metric meters downstream in scale.py).
   - Reprojection error: Pixels (px).
   - Angles: Unit quaternions and orthonormal 3x3 rotation matrices.

7. Important dependencies:
   pycolmap, numpy, pathlib, json, backend.app.pipelines.video.contract.

8. Assumptions:
   - Keyframes have sufficient visual overlap and texture for SIFT feature matching.
   - Camera motion provides sufficient baseline/parallax for triangulation.

9. Main failure modes:
   - Textureless white walls causing feature matching starvation.
   - Pure rotational camera movement with zero parallax (degenerate two-view geometry).
   - Fragmented reconstructions (split into disconnected visual components).

10. What a developer should inspect first when debugging:
    Inspect `sfm_stats.json` and verify `registration_ratio` and `mean_reprojection_error`.
    If registration fails, check whether keyframe spacing is too wide or frames are blurry.
"""

import os
import json
import shutil
import time
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import numpy as np

try:
    import pycolmap
except ImportError:
    pycolmap = None

from backend.app.pipelines.video.contract import (
    VideoReconstructionStatus,
    VideoCameraPose,
    VideoIntrinsics,
    SfMReconstructionReport,
)


def write_sparse_points_ply(
    points_xyz: np.ndarray,
    output_ply_path: Path,
    colors_rgb: Optional[np.ndarray] = None,
) -> None:
    """
    Write 3D points to an ASCII PLY file.

    Purpose:
        Serializes sparse triangulated points to disk for visualization and downstream scale alignment.

    Parameters:
        points_xyz (np.ndarray): (N, 3) float array of 3D point coordinates.
        output_ply_path (Path): Destination file path for .ply file.
        colors_rgb (Optional[np.ndarray]): (N, 3) uint8 array of RGB point colors.
    """
    output_ply_path.parent.mkdir(parents=True, exist_ok=True)
    num_pts = len(points_xyz)

    with open(output_ply_path, "w", encoding="utf-8") as f:
        f.write("ply\n")
        f.write("format ascii 1.0\n")
        f.write(f"element vertex {num_pts}\n")
        f.write("property float x\n")
        f.write("property float y\n")
        f.write("property float z\n")
        if colors_rgb is not None and len(colors_rgb) == num_pts:
            f.write("property uchar red\n")
            f.write("property uchar green\n")
            f.write("property uchar blue\n")
        f.write("end_header\n")

        for i in range(num_pts):
            p = points_xyz[i]
            if colors_rgb is not None and len(colors_rgb) == num_pts:
                c = colors_rgb[i]
                f.write(f"{p[0]:.6f} {p[1]:.6f} {p[2]:.6f} {int(c[0])} {int(c[1])} {int(c[2])}\n")
            else:
                f.write(f"{p[0]:.6f} {p[1]:.6f} {p[2]:.6f}\n")


def run_visual_sfm(
    keyframes_dir: Optional[Path] = None,
    output_sfm_dir: Optional[Path] = None,
    capture_id: str = "video_capture",
    camera_model: str = "SIMPLE_RADIAL",
    sequential_overlap: int = 10,
    min_registered_ratio: float = 0.50,
    max_reproj_error_threshold: float = 2.0,
    image_dir: Optional[Path] = None,
) -> Tuple[SfMReconstructionReport, List[VideoCameraPose], VideoIntrinsics, List[Dict[str, Any]]]:
    """
    Execute full sequential visual Structure-from-Motion using pycolmap.

    Purpose:
        Reconstructs camera trajectory and sparse structure from RGB keyframes
        without external odometry or LiDAR cues.

    Parameters:
        keyframes_dir (Optional[Path]): Directory containing selected keyframe images.
        output_sfm_dir (Optional[Path]): Output directory for SfM artifacts.
        capture_id (str): Unique capture identifier.
        camera_model (str): PyColmap camera model name (e.g. SIMPLE_RADIAL, PINHOLE).
        sequential_overlap (int): Number of neighboring keyframes to pair for matching.
        min_registered_ratio (float): Minimum registration ratio for GOOD status.
        max_reproj_error_threshold (float): Maximum acceptable reprojection error in px.
        image_dir (Optional[Path]): Alias for keyframes_dir.

    Returns:
        Tuple:
            - SfMReconstructionReport with statistics and quality status.
            - List[VideoCameraPose] records for registered frames with translation and rotation.
            - VideoIntrinsics extracted from reconstruction or fallback defaults.
            - List[Dict[str, Any]] sparse 3D point records with observation tracks mapped to keyframe IDs.

    Failure conditions:
        - pycolmap is not installed.
        - Fewer than 3 keyframes available.
        - Zero keyframes registered in mapping (marked FAILED).
    """
    if keyframes_dir is None and image_dir is not None:
        keyframes_dir = image_dir
    if keyframes_dir is None:
        raise ValueError("Either keyframes_dir or image_dir must be provided to run_visual_sfm")

    start_time = time.time()
    keyframes_dir = Path(keyframes_dir)
    output_sfm_dir = Path(output_sfm_dir or "outputs/sfm")
    output_sfm_dir.mkdir(parents=True, exist_ok=True)

    db_path = output_sfm_dir / "database.db"
    for db_f in [db_path, output_sfm_dir / "database.db-shm", output_sfm_dir / "database.db-wal"]:
        if db_f.exists():
            try:
                db_f.unlink()
            except Exception:
                pass

    # Clean previous pycolmap model folders if any
    for sub in output_sfm_dir.iterdir():
        if sub.is_dir() and sub.name.isdigit():
            try:
                shutil.rmtree(sub)
            except Exception:
                pass

    # Discover keyframe images
    image_files = sorted(
        [p for p in keyframes_dir.glob("*.jpg") or keyframes_dir.glob("*.png")],
        key=lambda p: p.name
    )
    total_kfs = len(image_files)
    manifest_by_id: Dict[int, Dict[str, Any]] = {}
    manifest_path = keyframes_dir / "keyframe_manifest.json"
    if manifest_path.exists():
        with open(manifest_path, "r", encoding="utf-8") as manifest_file:
            manifest_data = json.load(manifest_file)
        manifest_by_id = {
            int(record["keyframe_id"]): record
            for record in manifest_data.get("keyframes", [])
            if "keyframe_id" in record
        }

    if total_kfs < 3:
        report = SfMReconstructionReport(
            capture_id=capture_id,
            total_keyframes=total_kfs,
            registered_keyframes=0,
            registration_ratio=0.0,
            sparse_point_count=0,
            mean_reprojection_error=999.0,
            track_length_mean=0.0,
            status=VideoReconstructionStatus.FAILED,
            reconstruction_time_seconds=0.0,
            warnings=["Fewer than 3 keyframes available for visual SfM reconstruction."],
        )
        dummy_intrinsics = VideoIntrinsics(
            fx=1500.0, fy=1500.0, cx=960.0, cy=720.0, width=1920, height=1440,
            provenance="default_fallback", confidence=0.0
        )
        return report, [], dummy_intrinsics, []

    # Step 1: Feature Extraction
    feat_opts = pycolmap.FeatureExtractionOptions()
    feat_opts.use_gpu = False
    feat_opts.max_image_size = 1280
    feat_opts.num_threads = 2
    feat_opts.sift.first_octave = -1
    feat_opts.sift.max_num_features = 4096
    feat_opts.sift.edge_threshold = 15.0
    feat_opts.sift.peak_threshold = 0.004

    reader_opts = pycolmap.ImageReaderOptions()
    reader_opts.camera_model = camera_model

    image_names = [p.name for p in image_files]

    pycolmap.extract_features(
        database_path=db_path,
        image_path=keyframes_dir,
        image_names=image_names,
        camera_mode=pycolmap.CameraMode.SINGLE,
        reader_options=reader_opts,
        extraction_options=feat_opts,
    )

    # Step 2: Feature Matching
    # For keyframe sequences (typically 20-50 frames), exhaustive matching is fast (<2s)
    # and crucial for indoor scanning where the camera pans back across previously seen walls.
    match_opts = pycolmap.FeatureMatchingOptions()
    match_opts.use_gpu = False
    match_opts.num_threads = 2

    if total_kfs <= 80:
        pycolmap.match_exhaustive(
            database_path=db_path,
            matching_options=match_opts,
        )
    else:
        pairing_opts = pycolmap.SequentialPairingOptions()
        pairing_opts.overlap = min(sequential_overlap, 25)
        pairing_opts.loop_detection = False
        pycolmap.match_sequential(
            database_path=db_path,
            pairing_options=pairing_opts,
            matching_options=match_opts,
        )

    # Step 3: Incremental Reconstruction
    inc_opts = pycolmap.IncrementalPipelineOptions()
    inc_opts.num_threads = 2
    inc_opts.mapper.num_threads = 2
    inc_opts.min_num_matches = 10
    inc_opts.mapper.init_min_num_inliers = 15
    inc_opts.mapper.abs_pose_min_num_inliers = 8
    inc_opts.mapper.abs_pose_min_inlier_ratio = 0.10
    inc_opts.mapper.init_min_tri_angle = 2.0
    inc_opts.mapper.filter_min_tri_angle = 0.8
    inc_opts.min_model_size = 3
    inc_opts.ba_local_max_num_iterations = 25
    inc_opts.ba_global_max_num_iterations = 40

    reconstructions = pycolmap.incremental_mapping(
        database_path=db_path,
        image_path=keyframes_dir,
        output_path=output_sfm_dir,
        options=inc_opts,
    )

    elapsed = time.time() - start_time

    # Find largest reconstructed component
    if not reconstructions:
        warnings = ["Incremental mapping produced zero registered reconstructions."]
        report = SfMReconstructionReport(
            capture_id=capture_id,
            total_keyframes=total_kfs,
            registered_keyframes=0,
            registration_ratio=0.0,
            sparse_point_count=0,
            mean_reprojection_error=999.0,
            track_length_mean=0.0,
            status=VideoReconstructionStatus.FAILED,
            reconstruction_time_seconds=elapsed,
            warnings=warnings,
        )
        dummy_intrinsics = VideoIntrinsics(
            fx=1500.0, fy=1500.0, cx=960.0, cy=720.0, width=1920, height=1440,
            provenance="default_fallback", confidence=0.0
        )
        return report, [], dummy_intrinsics, []

    # Select reconstruction with most registered images
    best_rec_idx = max(reconstructions.keys(), key=lambda k: reconstructions[k].num_reg_images())
    best_rec = reconstructions[best_rec_idx]

    reg_kfs_count = best_rec.num_reg_images()
    reg_ratio = float(reg_kfs_count / total_kfs) if total_kfs > 0 else 0.0
    num_pts = len(best_rec.points3D)

    point_errors = np.array(
        [float(point.error) for point in best_rec.points3D.values() if np.isfinite(point.error)],
        dtype=np.float64,
    )
    mean_reproj = float(best_rec.compute_mean_reprojection_error()) if reg_kfs_count > 0 else 999.0
    median_reproj = float(np.median(point_errors)) if len(point_errors) else None
    mean_track = float(best_rec.compute_mean_track_length()) if num_pts > 0 else 0.0

    warnings: List[str] = []
    if reg_ratio < min_registered_ratio:
        warnings.append(f"Low registration ratio: {reg_ratio:.1%} ({reg_kfs_count}/{total_kfs})")
    if mean_reproj > max_reproj_error_threshold:
        warnings.append(f"High reprojection error: {mean_reproj:.2f}px")

    # Quality status assessment
    if reg_ratio >= 0.50 and mean_reproj <= 1.5:
        status = VideoReconstructionStatus.GOOD
    elif reg_kfs_count >= 3 and mean_reproj <= max_reproj_error_threshold:
        status = VideoReconstructionStatus.PROVISIONAL
    else:
        status = VideoReconstructionStatus.FAILED

    # Extract Camera Intrinsics
    cameras = best_rec.cameras
    if cameras:
        cam = list(cameras.values())[0]
        fl_x = float(cam.focal_length_x) if hasattr(cam, "focal_length_x") else float(cam.focal_length)
        fl_y = float(cam.focal_length_y) if hasattr(cam, "focal_length_y") else float(cam.focal_length)
        pp_x = float(cam.principal_point_x) if hasattr(cam, "principal_point_x") else float(cam.width / 2.0)
        pp_y = float(cam.principal_point_y) if hasattr(cam, "principal_point_y") else float(cam.height / 2.0)

        video_intrinsics = VideoIntrinsics(
            fx=fl_x,
            fy=fl_y,
            cx=pp_x,
            cy=pp_y,
            width=int(cam.width),
            height=int(cam.height),
            provenance="sfm_self_calibration",
            confidence=0.95 if status == VideoReconstructionStatus.GOOD else 0.75,
        )
    else:
        video_intrinsics = VideoIntrinsics(
            fx=1500.0, fy=1500.0, cx=960.0, cy=720.0, width=1920, height=1440,
            provenance="default_fallback", confidence=0.0
        )

    # Extract Camera Poses
    camera_poses: List[VideoCameraPose] = []
    poses_json_records: List[Dict[str, Any]] = []
    pycolmap_id_to_keyframe_id: Dict[int, int] = {}

    for img_id, img in sorted(best_rec.images.items(), key=lambda item: item[1].name):
        # Extract frame index and keyframe_id from image name (e.g. frame_000120.jpg or keyframe_0001_f000120.jpg)
        name = img.name
        f_idx = 0
        kf_id = 0
        try:
            if "frame_" in name:
                digits = name.replace("frame_", "").replace(".jpg", "").replace(".png", "")
                if digits.isdigit():
                    kf_id = int(digits)
                    f_idx = kf_id
            elif "f" in name and ".jpg" in name:
                parts = name.replace(".jpg", "").replace(".png", "").split("_")
                for p in parts:
                    if p.startswith("f") and p[1:].isdigit():
                        f_idx = int(p[1:])
                        kf_id = f_idx
                        break
                    elif p.isdigit():
                        f_idx = int(p)
                        kf_id = f_idx
            else:
                f_idx = int("".join(filter(str.isdigit, name)) or "0")
                kf_id = f_idx
        except Exception:
            f_idx = img_id
            kf_id = img_id

        pycolmap_id_to_keyframe_id[img_id] = kf_id
        source_record = manifest_by_id.get(kf_id, {})
        source_frame_index = int(source_record.get("frame_index", f_idx))
        source_timestamp = float(source_record.get("timestamp", source_frame_index / 30.0))

        # Rigid3d cam_from_world
        rigid = img.cam_from_world() if callable(img.cam_from_world) else img.cam_from_world
        world_from_cam = rigid.inverse() if callable(getattr(rigid, "inverse", None)) else rigid

        t_cam = world_from_cam.translation  # Camera center in world coordinates
        quat_cam = world_from_cam.rotation.quat  # [qw, qx, qy, qz]
        r_mat = world_from_cam.rotation.matrix().tolist()

        pose = VideoCameraPose(
            keyframe_id=kf_id,
            frame_index=source_frame_index,
            timestamp_seconds=source_timestamp,
            timestamp=source_timestamp,
            tx=float(t_cam[0]),
            ty=float(t_cam[1]),
            tz=float(t_cam[2]),
            t_vec=[float(t_cam[0]), float(t_cam[1]), float(t_cam[2])],
            r_matrix=r_mat,
            qw=float(quat_cam[0]),
            qx=float(quat_cam[1]),
            qy=float(quat_cam[2]),
            qz=float(quat_cam[3]),
            is_metric=False,  # Still arbitrary SfM scale
        )
        camera_poses.append(pose)

        poses_json_records.append({
            "image_name": name,
            "keyframe_id": kf_id,
            "frame_index": source_frame_index,
            "timestamp_seconds": source_timestamp,
            "cam_from_world": {
                "rotation_matrix": rigid.rotation.matrix().tolist(),
                "translation": rigid.translation.tolist(),
                "quaternion_wxyz": rigid.rotation.quat.tolist(),
            },
            "world_from_cam": {
                "rotation_matrix": r_mat,
                "position": t_cam.tolist(),
                "quaternion_wxyz": quat_cam.tolist(),
            },
            "is_metric": False,
        })

    camera_poses.sort(key=lambda pose: pose.keyframe_id)
    pose_jump_warnings: List[str] = []
    trajectory_continuous = len(camera_poses) >= 3
    if len(camera_poses) >= 3:
        keyframe_gaps = np.diff([pose.keyframe_id for pose in camera_poses])
        maximum_supported_gap = max(3, int(np.ceil(total_kfs * 0.20)))
        for index, gap in enumerate(keyframe_gaps):
            if gap > maximum_supported_gap:
                trajectory_continuous = False
                pose_jump_warnings.append(
                    f"Registration gap {camera_poses[index].keyframe_id}->"
                    f"{camera_poses[index + 1].keyframe_id}: {gap - 1} intervening keyframes "
                    f"are unregistered"
                )

        centers = np.array([pose.t_vec for pose in camera_poses], dtype=np.float64)
        steps = np.linalg.norm(np.diff(centers, axis=0), axis=1)
        median_step = float(np.median(steps))
        jump_limit = max(1e-6, 5.0 * median_step)
        for index, step in enumerate(steps):
            if step > jump_limit:
                trajectory_continuous = False
                pose_jump_warnings.append(
                    f"Pose jump {index}->{index + 1}: {step:.4f} SfM units exceeds "
                    f"5x median step {median_step:.4f}"
                )
    if pose_jump_warnings:
        warnings.extend(pose_jump_warnings)

    # Save cameras.json
    cameras_dict = {
        "intrinsics": video_intrinsics.model_dump(),
        "camera_model": camera_model,
        "calibration_status": status.value,
    }
    with open(output_sfm_dir / "cameras.json", "w", encoding="utf-8") as f:
        json.dump(cameras_dict, f, indent=2)

    # Save poses.json
    with open(output_sfm_dir / "poses.json", "w", encoding="utf-8") as f:
        json.dump(poses_json_records, f, indent=2)

    # Save sparse points PLY and collect structured point records
    ply_path = output_sfm_dir / "sparse_points.ply"
    pts_xyz = []
    pts_rgb = []
    sparse_points_list: List[Dict[str, Any]] = []

    for pt in best_rec.points3D.values():
        pts_xyz.append(pt.xyz)
        pts_rgb.append(pt.color)

        track_elements = []
        if hasattr(pt, "track") and hasattr(pt.track, "elements"):
            for elem in pt.track.elements:
                mapped_kfid = pycolmap_id_to_keyframe_id.get(elem.image_id, int(elem.image_id))
                track_elements.append({
                    "image_id": mapped_kfid,
                    "keyframe_id": mapped_kfid,
                    "point2D_idx": int(elem.point2D_idx),
                })

        sparse_points_list.append({
            "point3D_id": int(pt.id) if hasattr(pt, "id") else len(sparse_points_list),
            "xyz": pt.xyz.tolist() if hasattr(pt.xyz, "tolist") else list(pt.xyz),
            "track": track_elements,
            "error": float(pt.error) if hasattr(pt, "error") else 0.0,
        })

    if pts_xyz:
        write_sparse_points_ply(np.array(pts_xyz), ply_path, np.array(pts_rgb))
    else:
        write_sparse_points_ply(np.zeros((0, 3)), ply_path)

    # Save report
    report = SfMReconstructionReport(
        capture_id=capture_id,
        total_keyframes=total_kfs,
        registered_keyframes=reg_kfs_count,
        registration_ratio=reg_ratio,
        sparse_point_count=num_pts,
        mean_reprojection_error=mean_reproj,
        median_reprojection_error=median_reproj,
        track_length_mean=mean_track,
        trajectory_continuous=trajectory_continuous,
        pose_jump_warnings=pose_jump_warnings,
        status=status,
        reconstruction_time_seconds=elapsed,
        warnings=warnings,
    )

    with open(output_sfm_dir / "sfm_stats.json", "w", encoding="utf-8") as f:
        json.dump(report.model_dump(), f, indent=2)

    return report, camera_poses, video_intrinsics, sparse_points_list
