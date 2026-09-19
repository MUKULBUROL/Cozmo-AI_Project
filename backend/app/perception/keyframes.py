"""RGB keyframe extraction and camera pose synchronization for Stage 5 opening detection.

1. Why this file exists:
   Extracts non-redundant, sharp RGB keyframes from continuous iPhone captures (rgb.mp4),
   filtering out motion blur and static camera intervals while preserving exact 1-to-1
   synchronization with 6D camera poses, timestamps, and camera intrinsics.

2. Pipeline stage:
   Stage 5 (Door/Window Detection & Metric Opening Measurement) - Keyframe Pipeline.

3. Inputs:
   Path to scan zip archive or directory containing rgb.mp4, odometry.csv, camera_matrix.csv.

4. Outputs:
   Extracted JPEG keyframes in outputs/<scan_id>/openings/keyframes/frame_{frame_id:06d}.jpg
   Structured manifest in outputs/<scan_id>/openings/keyframes/keyframe_manifest.json.

5. Coordinate/Unit assumptions:
   Camera poses: metric meters (x, y, z) and unit quaternions (qx, qy, qz, qw).
   Rotations follow ARKit convention (right-handed, Y upward, optical Z forward).
   Resolution: 1920x1440 RGB.

6. Dependencies:
   os, sys, zipfile, json, math, pathlib, typing, numpy, pillow, scipy, imageio, cv2 (optional fallback).

7. Most likely failure/debugging points:
   - Archive missing rgb.mp4 or odometry.csv.
   - Excessive motion blur causing all frames to be rejected (handled with fallback minimum frame guarantee).
   - Frame indexing mismatch between video demuxer and odometry timestamp records.
"""

import os
import io
import csv
import json
import math
import zipfile
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import numpy as np
from PIL import Image
from scipy.spatial.transform import Rotation
from scipy.ndimage import laplace
import cv2


def compute_image_sharpness(img_gray: np.ndarray) -> float:
    """Computes focus sharpness of a grayscale image using Laplacian variance.

    Purpose:
        Quantifies high-frequency edge content to detect and reject motion-blurred frames.

    Parameters:
        img_gray: 2D numpy array of grayscale pixel intensities (uint8 or float).

    Returns:
        Scalar float representing variance of the Laplacian filter response.

    Assumptions:
        Higher values indicate sharper focus; motion blur suppresses variance below ~40.

    Failure conditions:
        Returns 0.0 on flat / homogeneous images.

    Debugging:
        Downsample image before computing Laplacian to maintain high throughput.
    """
    # Downsample by factor of 4 for rapid computation
    small = img_gray[::4, ::4].astype(np.float64)
    filtered = laplace(small)
    return float(np.var(filtered))


def extract_keyframes(
    scan_id: str,
    archive_path: Path,
    output_dir: Path,
    min_translation_m: float = 0.15,
    min_rotation_deg: float = 8.0,
    min_frame_stride: int = 15,
    max_frame_stride: int = 90,
    blur_threshold: float = 35.0,
    max_keyframes: int = 40,
) -> List[Dict[str, Any]]:
    """Extracts informative, non-redundant, blur-filtered RGB keyframes synchronized with 6D poses.

    Purpose:
        Selects optimal frames where camera motion provides new spatial perspectives of walls
        and openings while ensuring camera pose and intrinsics remain perfectly aligned.

    Parameters:
        scan_id: Unique capture identifier (e.g. 'c00a170fe1').
        archive_path: Path to capture zip archive.
        output_dir: Directory where extracted keyframes and manifest will be stored.
        min_translation_m: Camera movement distance threshold triggering keyframe selection.
        min_rotation_deg: Camera angular change threshold triggering keyframe selection.
        min_frame_stride: Hard lower limit on frame distance to avoid redundant bursts.
        max_frame_stride: Hard upper limit on frame distance to guarantee spatial coverage.
        blur_threshold: Minimum Laplacian variance for frame sharpness.
        max_keyframes: Maximum number of keyframes to extract.

    Returns:
        List of dictionaries containing metadata for each selected keyframe.

    Assumptions:
        rgb.mp4 and odometry.csv have 1-to-1 frame correspondence starting from frame 000000.

    Failure conditions:
        Raises FileNotFoundError if archive does not contain rgb.mp4 or odometry.csv.

    Debugging:
        Inspect keyframe_manifest.json to verify pose timestamps and selection trigger reasons.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    manifest_path = output_dir / "keyframe_manifest.json"
    if manifest_path.exists():
        with open(manifest_path, "r", encoding="utf-8") as f:
            cached = json.load(f)
            cached_kfs = cached.get("keyframes", [])
            if len(cached_kfs) >= 5:
                for kf in cached_kfs:
                    dpath = kf.get("depth_path")
                    if dpath and os.path.exists(dpath):
                        kf["depth_map"] = cv2.imread(dpath, cv2.IMREAD_UNCHANGED)
                return cached_kfs

    if not archive_path.exists():
        raise FileNotFoundError(f"Scan archive not found at: {archive_path}")

    zf = zipfile.ZipFile(archive_path, "r")
    namelist = set(zf.namelist())

    odom_rel = f"{scan_id}/odometry.csv"
    vid_rel = f"{scan_id}/rgb.mp4"
    cam_rel = f"{scan_id}/camera_matrix.csv"

    if odom_rel not in namelist:
        raise FileNotFoundError(f"Missing odometry.csv in {scan_id}")
    if vid_rel not in namelist:
        raise FileNotFoundError(f"Missing rgb.mp4 in {scan_id}")

    # Load camera matrix
    fx_default, fy_default, cx_default, cy_default = 1599.0, 1599.0, 960.0, 720.0
    if cam_rel in namelist:
        cam_lines = zf.read(cam_rel).decode("utf-8").strip().splitlines()
        mat_rows = []
        for line in cam_lines:
            parts = [float(p.strip()) for p in line.split(",") if p.strip()]
            if len(parts) == 3:
                mat_rows.append(parts)
        if len(mat_rows) == 3:
            fx_default = mat_rows[0][0]
            fy_default = mat_rows[1][1]
            cx_default = mat_rows[0][2]
            cy_default = mat_rows[1][2]

    # Load odometry
    odom_lines = zf.read(odom_rel).decode("utf-8").splitlines()
    header = [h.strip() for h in odom_lines[0].split(",")]
    records: List[Dict[str, Any]] = []
    for line in odom_lines[1:]:
        if not line.strip():
            continue
        parts = [p.strip() for p in line.split(",")]
        records.append(dict(zip(header, parts)))

    total_records = len(records)
    if total_records == 0:
        raise ValueError("Empty odometry records in capture")

    # Extract temporary mp4 to read frames with imageio
    tmp_mp4 = Path(f"/tmp/{scan_id}_rgb_temp.mp4")
    if not tmp_mp4.exists() or tmp_mp4.stat().st_size < 1000:
        with open(tmp_mp4, "wb") as f:
            f.write(zf.read(vid_rel))

    import imageio.v3 as iio

    selected_keyframes: List[Dict[str, Any]] = []
    last_pose_pos: Optional[np.ndarray] = None
    last_pose_rot: Optional[Rotation] = None
    last_selected_idx: int = -999

    # Candidate evaluation loop
    for i in range(0, total_records, min_frame_stride // 2):
        if len(selected_keyframes) >= max_keyframes:
            break

        rec = records[i]
        f_idx = int(rec.get("frame", i))
        ts = float(rec.get("timestamp", 0.0))
        pos = np.array([float(rec["x"]), float(rec["y"]), float(rec["z"])], dtype=np.float64)
        quat = [float(rec["qx"]), float(rec["qy"]), float(rec["qz"]), float(rec["qw"])]
        rot = Rotation.from_quat(quat)

        should_select = False
        trigger_reason = ""

        if last_pose_pos is None:
            should_select = True
            trigger_reason = "first_frame"
        else:
            frame_dist = i - last_selected_idx
            if frame_dist >= min_frame_stride:
                # Translation delta
                trans_delta = float(np.linalg.norm(pos - last_pose_pos))
                # Angular rotation delta
                rot_diff = rot * last_pose_rot.inv()
                rot_angle_deg = float(np.degrees(np.linalg.norm(rot_diff.as_rotvec())))

                if trans_delta >= min_translation_m:
                    should_select = True
                    trigger_reason = f"translation_{trans_delta:.2f}m"
                elif rot_angle_deg >= min_rotation_deg:
                    should_select = True
                    trigger_reason = f"rotation_{rot_angle_deg:.1f}deg"
                elif frame_dist >= max_frame_stride:
                    should_select = True
                    trigger_reason = f"max_stride_{frame_dist}_frames"

        if should_select:
            try:
                # Read specific video frame
                frame_rgb = iio.imread(tmp_mp4, index=min(i, total_records - 1))
            except Exception:
                continue

            # Convert to grayscale for sharpness evaluation
            gray = np.dot(frame_rgb[..., :3], [0.2989, 0.5870, 0.1140])
            sharpness = compute_image_sharpness(gray)

            # Skip blurry frames unless we haven't selected any frame in a long interval
            if sharpness < blur_threshold and (i - last_selected_idx) < max_frame_stride and last_pose_pos is not None:
                continue

            # Save JPEG image
            img_filename = f"frame_{f_idx:06d}.jpg"
            img_path = output_dir / img_filename
            pil_img = Image.fromarray(frame_rgb)
            pil_img.save(img_path, quality=90)

            # Retrieve frame intrinsics
            fx = float(rec.get("fx", fx_default)) if rec.get("fx") else fx_default
            fy = float(rec.get("fy", fy_default)) if rec.get("fy") else fy_default
            cx = float(rec.get("cx", cx_default)) if rec.get("cx") else cx_default
            cy = float(rec.get("cy", cy_default)) if rec.get("cy") else cy_default

            # Save depth map if present in archive
            depth_rel = f"{scan_id}/depth/{f_idx:06d}.png"
            depth_arr = None
            depth_path_str = None
            if depth_rel in namelist:
                depth_bytes = zf.read(depth_rel)
                depth_file = output_dir / f"frame_{f_idx:06d}_depth.png"
                with open(depth_file, "wb") as df:
                    df.write(depth_bytes)
                depth_path_str = str(depth_file)
                depth_arr = cv2.imdecode(np.frombuffer(depth_bytes, np.uint8), cv2.IMREAD_UNCHANGED)

            meta = {
                "keyframe_id": len(selected_keyframes),
                "frame_id": f_idx,
                "frame_index": f_idx,
                "timestamp": ts,
                "filename": img_filename,
                "image_path": str(img_path),
                "rgb_path": str(img_path),
                "depth_path": depth_path_str,
                "depth_map": depth_arr,
                "camera_pose": {
                    "position": [pos[0], pos[1], pos[2]],
                    "orientation_quaternion": quat,
                },
                "intrinsics": {
                    "fx": fx,
                    "fy": fy,
                    "cx": cx,
                    "cy": cy,
                    "width": frame_rgb.shape[1],
                    "height": frame_rgb.shape[0],
                },
                "sharpness_score": round(sharpness, 2),
                "selection_trigger": trigger_reason,
            }
            selected_keyframes.append(meta)
            last_pose_pos = pos
            last_pose_rot = rot
            last_selected_idx = i

    zf.close()

    # Save manifest (exclude non-serializable depth_map numpy array)
    manifest_keyframes = []
    for kf in selected_keyframes:
        kf_clean = dict(kf)
        kf_clean.pop("depth_map", None)
        manifest_keyframes.append(kf_clean)

    manifest_path = output_dir / "keyframe_manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "scan_id": scan_id,
                "total_keyframes": len(selected_keyframes),
                "video_total_frames": total_records,
                "keyframes": manifest_keyframes,
            },
            f,
            indent=2,
        )

    return selected_keyframes
