"""Stage 7 Absolute Metric Scale Recovery from Monocular Depth and Visual SfM.

1. Why this file exists:
   Visual Structure-from-Motion (SfM) produces camera trajectories and 3D tie points
   with arbitrary scale. This module estimates the global metric conversion factor (meters per unit)
   by matching SfM triangulated depths against neural metric depth predictions across keyframes.
   Strictly adheres to physics: NO hardcoded heuristics (e.g. human height, door width).

2. Pipeline stage:
   Stage 7 (Video Tier - Metric Scale Recovery).

3. Inputs:
   - Sparse 3D tie points from SfM with observation tracks.
   - Camera poses from SfM.
   - Predicted metric depth maps (meters) for registered keyframes.
   - Camera intrinsics.

4. Outputs:
   - `MetricScaleEstimate` recording scale multiplier, MAD, inliers, and uncertainty.
   - Scaled camera trajectory with translations in metric meters.
   - Scaled 3D sparse points in meters.

5. Coordinate convention:
   - Camera frame: OpenCV standard (X right, Y down, Z forward).
   - World frame: Right-handed metric coordinate system.

6. Unit convention:
   - Scale factor: Meters per arbitrary SfM unit.
   - Scale uncertainty: Standard deviation in meters.

7. Important dependencies:
   numpy, json, pathlib, backend.app.models.video.

8. Assumptions:
   - Visual SfM coordinate frame is linear and rigid.
   - Metric depth model provides approximately unbiased local metric estimates for walls and floors.

9. Main failure modes:
   - Too few valid depth correspondences (< 15 points) -> marked as FAILED status.
   - Extreme disparity between different keyframes (scale drift) -> elevated scale uncertainty.

10. What a developer should inspect first when debugging:
    Inspect `metric_scale.json` and the distribution of scale ratios across keyframes.
"""

import json
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
import numpy as np

from backend.app.models.video import (
    SfmCameraPose,
    VideoCameraIntrinsics,
    MetricScaleEstimate,
)


def estimate_metric_scale(
    sparse_points: List[Dict[str, Any]],
    poses: List[SfmCameraPose],
    depth_maps: Dict[int, np.ndarray],
    intrinsics: VideoCameraIntrinsics,
    output_dir: Optional[Path] = None,
    min_correspondences: int = 15,
) -> MetricScaleEstimate:
    """Robustly recovers the global metric scale factor relating arbitrary SfM to meters.

    Purpose:
        Compares triangulated SfM camera-space depths against predicted metric depths across
        all registered viewpoints using median and MAD outlier rejection.

    Parameters:
        sparse_points: List of 3D point records with observation tracks.
        poses: Chronologically indexed SfmCameraPose records.
        depth_maps: Dict mapping keyframe_id to 2D float32 metric depth map (meters).
        intrinsics: Camera intrinsic parameters (fx, fy, cx, cy).
        output_dir: Target directory to save `metric_scale.json`.
        min_correspondences: Minimum inlier matches required to declare scale valid.

    Returns:
        MetricScaleEstimate with global scale factor and scale uncertainty.

    Assumptions:
        Camera poses represent world-from-camera (or cam-from-world) consistently.

    Failure conditions:
        If fewer than `min_correspondences` are found, returns default scale with FAILED status.

    Dependencies:
        numpy.median, numpy.abs.
    """
    scale_ratios: List[float] = []
    per_frame_ratios: Dict[int, List[float]] = {}

    pose_map = {p.keyframe_id: p for p in poses}

    fx, fy = intrinsics.fx, intrinsics.fy
    cx, cy = intrinsics.cx, intrinsics.cy
    img_w, img_h = intrinsics.width, intrinsics.height

    for pt in sparse_points:
        xyz_w = np.array(pt["xyz"], dtype=np.float64)  # 3D position in world coords
        track = pt.get("track", [])

        for obs in track:
            kf_id = obs.get("image_id", obs.get("keyframe_id"))
            if kf_id not in pose_map or kf_id not in depth_maps:
                continue

            pose = pose_map[kf_id]
            depth_map = depth_maps[kf_id]

            # Pose stores world_from_cam translation and rotation
            # Transform world point to camera space:
            # X_world = R_wc * X_cam + C_world  ==>  X_cam = R_wc.T * (X_world - C_world)
            r_wc = np.array(pose.r_matrix, dtype=np.float64)
            c_world = np.array(pose.t_vec, dtype=np.float64)

            x_cam = r_wc.T @ (xyz_w - c_world)
            z_sfm = float(x_cam[2])

            # Must be in front of camera
            if z_sfm <= 0.05:
                continue

            # Project to 2D pixel coordinates
            u = int(round(fx * (x_cam[0] / z_sfm) + cx))
            v = int(round(fy * (x_cam[1] / z_sfm) + cy))

            # Bounds check
            if 0 <= u < depth_map.shape[1] and 0 <= v < depth_map.shape[0]:
                z_metric = float(depth_map[v, u])
                if 0.20 <= z_metric <= 6.50 and np.isfinite(z_metric):
                    ratio = z_metric / z_sfm
                    if 0.01 < ratio < 100.0:  # Physically plausible ratio bounds
                        scale_ratios.append(ratio)
                        if kf_id not in per_frame_ratios:
                            per_frame_ratios[kf_id] = []
                        per_frame_ratios[kf_id].append(ratio)

    if len(scale_ratios) < min_correspondences:
        result = MetricScaleEstimate(
            scale_factor=1.0,
            supporting_frames=len(per_frame_ratios),
            supporting_points=len(scale_ratios),
            median_ratio=1.0,
            mad=1.0,
            relative_scale_uncertainty=1.0,
            status="FAILED",
            inlier_ratio=0.0,
            total_correspondences=len(scale_ratios),
            inlier_count=0,
            rejected_count=len(scale_ratios),
            raw_scale_ratios=[float(value) for value in scale_ratios],
        )
        if output_dir:
            with open(Path(output_dir) / "metric_scale.json", "w", encoding="utf-8") as f:
                json.dump(result.model_dump(), f, indent=2)
        return result

    ratios_arr = np.array(scale_ratios, dtype=np.float64)

    # Initial median and MAD
    raw_median = float(np.median(ratios_arr))
    abs_deviations = np.abs(ratios_arr - raw_median)
    mad = float(np.median(abs_deviations))

    # MAD outlier rejection (2.5 * 1.4826 * MAD)
    consistency_factor = 1.4826
    sigma_est = max(1e-5, consistency_factor * mad)
    inlier_mask = abs_deviations <= (2.5 * sigma_est)

    inlier_ratios = ratios_arr[inlier_mask]
    if len(inlier_ratios) < min_correspondences:
        inlier_ratios = ratios_arr  # Fallback to all if filtering is too strict

    final_scale = float(np.median(inlier_ratios))
    inlier_mad = float(np.median(np.abs(inlier_ratios - final_scale)))
    inlier_sigma = consistency_factor * inlier_mad

    # Scale uncertainty: standard error of the median estimate
    n_inliers = len(inlier_ratios)
    scale_uncertainty = float(inlier_sigma / np.sqrt(max(1, n_inliers)))
    rel_uncertainty = float(scale_uncertainty / final_scale) if final_scale > 0 else 1.0

    inlier_ratio = float(n_inliers / len(ratios_arr))

    # Quality Gate
    status = "GOOD"
    if rel_uncertainty > 0.25 or inlier_ratio < 0.50:
        status = "FAILED"
    elif rel_uncertainty > 0.10 or inlier_ratio < 0.70:
        status = "PROVISIONAL"

    result = MetricScaleEstimate(
        scale_factor=final_scale,
        supporting_frames=len(per_frame_ratios),
        supporting_points=n_inliers,
        median_ratio=final_scale,
        mad=inlier_mad,
        relative_scale_uncertainty=rel_uncertainty,
        status=status,
        inlier_ratio=inlier_ratio,
        total_correspondences=len(ratios_arr),
        inlier_count=n_inliers,
        rejected_count=len(ratios_arr) - n_inliers,
        raw_scale_ratios=[float(value) for value in ratios_arr],
    )

    if output_dir:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        with open(output_dir / "metric_scale.json", "w", encoding="utf-8") as f:
            json.dump(result.model_dump(), f, indent=2)

    return result


def apply_metric_scale(
    poses: List[SfmCameraPose],
    sparse_points: List[Dict[str, Any]],
    scale_factor: float,
) -> Tuple[List[SfmCameraPose], List[Dict[str, Any]]]:
    """Applies global metric scale factor to camera translations and sparse 3D structure.

    Purpose:
        Converts arbitrary-scale SfM geometry into physical meters.
        CRITICAL: Rotations remain strictly invariant and are NOT scaled.

    Parameters:
        poses: Camera poses with arbitrary translation coordinates.
        sparse_points: Sparse 3D tie points with arbitrary coordinates.
        scale_factor: Metric scale multiplier (meters per arbitrary unit).

    Returns:
        Tuple of (scaled_poses: List[SfmCameraPose], scaled_points: List[Dict[str, Any]]).

    Assumptions:
        Scale multiplier applies homogeneously across world translation coordinates.
    """
    scaled_poses: List[SfmCameraPose] = []
    for p in poses:
        p_dict = p.model_dump()
        # Scale translations by scale_factor
        p_dict["t_vec"] = [float(c * scale_factor) for c in p.t_vec]
        # Rotations remain strictly unchanged
        p_dict["is_metric"] = True
        scaled_poses.append(SfmCameraPose(**p_dict))

    scaled_points: List[Dict[str, Any]] = []
    for pt in sparse_points:
        pt_copy = dict(pt)
        pt_copy["xyz"] = [float(c * scale_factor) for c in pt["xyz"]]
        scaled_points.append(pt_copy)

    return scaled_poses, scaled_points
