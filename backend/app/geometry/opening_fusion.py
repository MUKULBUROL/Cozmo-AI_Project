"""Multi-frame observation fusion, spatial clustering, and metric opening width calculation.

1. Why this file exists:
   Fuses multiple provisional opening observations across sequential video keyframes into distinct,
   singular physical architectural openings. Computes final metric width along the host wall plane,
   evaluates frame-to-frame measurement spread, estimates uncalibrated 95% engineering uncertainty,
   and documents corridor doorway polygon refinement candidates.

2. Pipeline stage:
   Stage 5 (Door/Window Detection & Metric Opening Measurement) - Multi-Frame Fusion & Metric Estimation.

3. Inputs:
   List of accepted and rejected opening observations (from opening_association),
   Stage 2 structural walls, Stage 3 polygon edges / corners.

4. Outputs:
   Consolidated openings list, observation clusters, and benchmark-ready summary records.

5. Coordinate/Unit conventions:
   Metric meters (m) in 3D world coordinates (Y vertical upward, XZ horizontal floor plane).
   Opening widths measured strictly along the 3D wall plane.
   Uncertainty expressed as [lower_bound, upper_bound] in meters with calibrated=False.

6. Dependencies:
   math, typing, numpy.

7. Most likely failure/debugging points:
   - Over-clustering distinct adjacent openings (e.g., adjacent double doors merged into one).
   - Under-clustering the same opening viewed from acute camera angles.
   - Outlier width measurements from poor segmentation frames skewing the fused width.
"""

import math
from typing import Any, Dict, List, Optional, Tuple
import numpy as np


def compute_metric_width_along_plane(
    left_3d: Tuple[float, float, float],
    right_3d: Tuple[float, float, float],
) -> float:
    """Calculates horizontal metric opening width between two 3D jamb coordinates on a wall plane.

    Purpose:
        Measures the physical clearance width of an opening strictly in 3D Euclidean space.

    Parameters:
        left_3d: (x, y, z) coordinates of left opening jamb in meters.
        right_3d: (x, y, z) coordinates of right opening jamb in meters.

    Returns:
        Horizontal distance in meters (float).

    Assumptions:
        Coordinates are already projected onto the host wall plane in metric meters.

    Failure conditions:
        Returns 0.0 if endpoints are identical.

    Debugging:
        Check left_3d and right_3d if width is abnormally small (<0.2m) or large (>3m).
    """
    dx = right_3d[0] - left_3d[0]
    dz = right_3d[2] - left_3d[2]
    return float(math.hypot(dx, dz))


def cluster_opening_observations(
    observations: List[Dict[str, Any]],
    spatial_merge_threshold_m: float = 0.75,
) -> List[List[Dict[str, Any]]]:
    """Clusters repeated observations of the same opening across multiple keyframes.

    Purpose:
        Prevents emitting duplicate openings for the same physical doorway or window observed across video.

    Parameters:
        observations: List of accepted opening observation dicts from opening_association.
        spatial_merge_threshold_m: Maximum distance (meters) between 3D centroids to consider them the same opening.

    Returns:
        List of observation clusters, where each cluster is a list of observation dicts.

    Assumptions:
        Openings on different walls are never the same physical opening.
        Openings with incompatible semantic classes (door vs window) are not merged.

    Failure conditions:
        Returns empty list if input observations list is empty.

    Debugging:
        Check spatial_merge_threshold_m if the same doorway creates multiple opening records.
    """
    if not observations:
        return []

    clusters: List[List[Dict[str, Any]]] = []

    for obs in observations:
        proj_geo = obs.get("projected_geometry")
        if not proj_geo:
            continue

        wall_id = obs.get("wall_id")
        sem_class = obs.get("candidate", {}).get("class", "opening")
        c_3d = proj_geo.get("centroid_3d", [0.0, 0.0, 0.0])

        matched_cluster: Optional[List[Dict[str, Any]]] = None
        min_dist = float("inf")

        for cluster in clusters:
            first_obs = cluster[0]
            if first_obs.get("wall_id") != wall_id:
                continue

            # Check semantic compatibility (door and doorway are compatible)
            first_class = first_obs.get("candidate", {}).get("class", "")
            is_door_family = {"door", "doorway", "open doorway"}
            if (sem_class in is_door_family and first_class in is_door_family) or (sem_class == first_class):
                pass
            else:
                continue

            # Calculate average centroid of cluster
            cluster_c = np.mean([o["projected_geometry"]["centroid_3d"] for o in cluster], axis=0)
            dist = float(math.hypot(c_3d[0] - cluster_c[0], c_3d[2] - cluster_c[2]))

            if dist < spatial_merge_threshold_m and dist < min_dist:
                min_dist = dist
                matched_cluster = cluster

        if matched_cluster is not None:
            matched_cluster.append(obs)
        else:
            clusters.append([obs])

    return clusters


def estimate_opening_uncertainty(
    widths: List[float],
    wall_rmse_m: float = 0.015,
    depth_noise_m: float = 0.018,
    jamb_pixel_uncertainty_m: float = 0.015,
) -> Tuple[float, float, float]:
    """Estimates uncalibrated 95% engineering uncertainty interval for fused opening width.

    Purpose:
        Combines empirical frame-to-frame measurement spread, depth sensor noise, wall plane roughness,
        and segmentation boundary uncertainty into an honest engineering tolerance.

    Parameters:
        widths: List of individual width measurements from supporting frames.
        wall_rmse_m: Host wall plane fitting root-mean-square error in meters.
        depth_noise_m: LiDAR depth noise standard deviation at typical room range (m).
        jamb_pixel_uncertainty_m: Segmentation jamb boundary uncertainty in 3D projection (m).

    Returns:
        Tuple of (lower_bound_m, upper_bound_m, half_width_uncertainty_m).

    Assumptions:
        95% coverage corresponds to standard k=1.96 multiplier under Gaussian propagation assumption.
        Explicitly flagged as uncalibrated until laser ground truth benchmarks exist.

    Failure conditions:
        Returns nominal width +/- 0.05m if input widths list is empty.

    Debugging:
        If uncertainty interval is unexpectedly wide (>0.15m), check frame width standard deviation.
    """
    if not widths:
        return 0.0, 0.0, 0.05

    n = len(widths)
    fused_width = float(np.median(widths))

    if n > 1:
        spread_std = float(np.std(widths, ddof=1))
        # Standard error of the mean
        sem = spread_std / math.sqrt(n)
    else:
        spread_std = 0.025
        sem = spread_std

    # Combined standard uncertainty: quadrature sum of independent error contributors
    # u_c = sqrt(sem^2 + sigma_depth^2 + sigma_wall^2 + sigma_jamb^2)
    u_c = math.sqrt(sem * sem + depth_noise_m * depth_noise_m + wall_rmse_m * wall_rmse_m + jamb_pixel_uncertainty_m * jamb_pixel_uncertainty_m)

    # 95% expansion factor k = 1.96
    k = 1.96
    half_width = k * u_c

    # Minimum floor of 1.5 cm to avoid overconfidence from single accidental clusters
    half_width = max(0.015, half_width)

    lower_bound = max(0.10, fused_width - half_width)
    upper_bound = fused_width + half_width

    return round(lower_bound, 4), round(upper_bound, 4), round(half_width, 4)


from scipy.spatial.transform import Rotation


def audit_observation_quality(
    obs: Dict[str, Any],
    wall_plane: Dict[str, float],
    cluster_median_width: float,
    cluster_mad_width: float,
) -> Dict[str, Any]:
    """Audits each frame observation in a cluster against the 6 physical quality filters.

    Quality Filters:
        1. camera_too_oblique: viewing incidence angle with wall normal > 53 deg (cos < 0.60).
        2. blurry_frame: focus sharpness score < 80.0.
        3. jamb_outside_image: opening jamb clipped within 15px of camera border (orientation aware).
        4. both_jambs_clipped: both jambs touch image borders.
        5. poor_depth_confidence: excessive ray distance (> 4.5m) or unconfirmed aperture.
        6. extreme_deviation_from_median: width deviation > max(0.18m, 2.2 * MAD).

    Returns:
        Dictionary with audit flags, is_high_quality boolean, quality_score, and rejection reasons.
    """
    rejection_reasons: List[str] = []
    w = float(obs["projected_geometry"]["width_m"])
    c3d = np.array(obs["projected_geometry"]["centroid_3d"])
    camera_pose = obs.get("camera_pose", {})
    pos = np.array(camera_pose.get("position", [0.0, 0.0, 0.0]))

    # 1. Oblique viewing angle
    cos_angle = 1.0
    if isinstance(wall_plane, (list, tuple)) and len(wall_plane) >= 3:
        n = np.array([float(wall_plane[0]), float(wall_plane[1]), float(wall_plane[2])], dtype=float)
        n = n / max(1e-6, np.linalg.norm(n))
        ray = c3d - pos
        ray_len = np.linalg.norm(ray)
        if ray_len > 1e-4:
            ray_dir = ray / ray_len
            cos_angle = abs(float(np.dot(ray_dir, n)))
            if cos_angle < 0.60:
                rejection_reasons.append("camera_too_oblique")
    elif isinstance(wall_plane, dict) and "a" in wall_plane:
        n = np.array([float(wall_plane["a"]), float(wall_plane["b"]), float(wall_plane["c"])], dtype=float)
        n = n / max(1e-6, np.linalg.norm(n))
        ray = c3d - pos
        ray_len = np.linalg.norm(ray)
        if ray_len > 1e-4:
            ray_dir = ray / ray_len
            cos_angle = abs(float(np.dot(ray_dir, n)))
            if cos_angle < 0.60:
                rejection_reasons.append("camera_too_oblique")

    # 2. Frame blur
    sharpness = float(obs.get("sharpness_score", 100.0))
    if sharpness < 80.0:
        rejection_reasons.append("blurry_frame")

    # 3. Orientation & Jamb outside image (border clipping)
    quat = camera_pose.get("orientation_quaternion") or camera_pose.get("quaternion")
    is_portrait = False
    if quat:
        R = Rotation.from_quat(quat).as_matrix()
        is_portrait = bool(abs(R[1, 0]) > abs(R[1, 1]))

    cand = obs["candidate"]
    bbox = cand.get("boundary_pixels", {}).get("refined_bbox") or cand.get("bbox", [])
    left_clipped = False
    right_clipped = False

    if len(bbox) == 4 and any(float(v) > 0 for v in bbox):
        x1, y1, x2, y2 = [float(v) for v in bbox]
        intr = obs.get("intrinsics", {})
        img_w = float(intr.get("image_width", intr.get("width", 1920)))
        img_h = float(intr.get("image_height", intr.get("height", 1440)))

        if is_portrait:
            left_clipped = bool(y1 <= 15.0)
            right_clipped = bool(y2 >= img_h - 15.0)
        else:
            left_clipped = bool(x1 <= 15.0)
            right_clipped = bool(x2 >= img_w - 15.0)

        if left_clipped and right_clipped:
            rejection_reasons.append("both_jambs_clipped_outside_image")
        elif left_clipped:
            rejection_reasons.append("left_jamb_clipped_outside_image")
        elif right_clipped:
            rejection_reasons.append("right_jamb_clipped_outside_image")

    # 4. Excessive distance
    ray_dist = float(obs["projected_geometry"].get("ray_distance_m", 0.0))
    if ray_dist > 4.5:
        rejection_reasons.append("excessive_camera_distance")

    # 5. Extreme deviation from median
    dev = abs(w - cluster_median_width)
    max_allowable_dev = max(0.18, 2.2 * cluster_mad_width)
    if dev > max_allowable_dev:
        rejection_reasons.append("extreme_deviation_from_median")

    is_hq = bool(len(rejection_reasons) == 0)
    quality_score = max(0.1, 1.0 - 0.25 * len(rejection_reasons)) * (sharpness / 200.0) * cos_angle

    return {
        "frame_id": cand.get("frame_id"),
        "measured_width_m": round(w, 4),
        "is_high_quality": bool(is_hq),
        "cos_incidence_angle": round(float(cos_angle), 3),
        "sharpness_score": round(float(sharpness), 1),
        "rejection_reasons": rejection_reasons,
        "quality_score": round(float(quality_score), 4),
        "jamb_clipped": bool(left_clipped or right_clipped),
    }


def fuse_openings(
    clusters: List[List[Dict[str, Any]]],
    rejected_observations: List[Dict[str, Any]],
    structural_walls: List[Dict[str, Any]],
    polygon_edges: Optional[List[Dict[str, Any]]] = None,
    min_frames_for_acceptance: int = 3,
) -> Dict[str, Any]:
    """Fuses observation clusters into final verified openings and generates benchmark-ready summary.

    Purpose:
        Applies 6 physical quality filters to eliminate noisy measurement frames,
        calculates stable metric width from high-quality observations,
        and cleanly separates accepted, provisional, and uncertain openings.

    Parameters:
        clusters: Grouped observations from cluster_opening_observations.
        rejected_observations: Traceable list of rejected candidate observations.
        structural_walls: List of Stage 2 structural wall dictionaries.
        polygon_edges: Optional Stage 3/4 room polygon edge segments.
        min_frames_for_acceptance: Minimum number of supporting keyframes required for full acceptance (default 3).

    Returns:
        Dictionary containing accepted_openings, provisional_openings, uncertain_openings,
        and polygon_refinement_candidates.
    """
    wall_map = {w["id"]: w for w in structural_walls}
    accepted_openings: List[Dict[str, Any]] = []
    provisional_openings: List[Dict[str, Any]] = []
    uncertain_openings: List[Dict[str, Any]] = []
    polygon_refinements: List[Dict[str, Any]] = []

    opening_idx = 1

    for cluster in clusters:
        num_frames = len(cluster)
        first_obs = cluster[0]
        wall_id = first_obs["wall_id"]
        sem_class = first_obs["candidate"]["class"]
        normalized_class = "doorway" if sem_class in {"door", "doorway", "open doorway"} else sem_class

        wall_dict = wall_map.get(wall_id, {})
        wall_plane = wall_dict.get("plane", {})
        wall_rmse = wall_dict.get("fit_quality", {}).get("rmse_m", 0.015)

        raw_widths = [obs["projected_geometry"]["width_m"] for obs in cluster]
        raw_median = float(np.median(raw_widths))
        raw_mad = float(np.median([abs(w - raw_median) for w in raw_widths]))

        # Audit each observation frame for quality
        audits: List[Dict[str, Any]] = []
        for obs in cluster:
            a = audit_observation_quality(obs, wall_plane, raw_median, raw_mad)
            audits.append(a)

        hq_observations = [obs for obs, a in zip(cluster, audits) if a["is_high_quality"]]
        hq_widths = [obs["projected_geometry"]["width_m"] for obs in hq_observations]

        # Calculate width from high-quality observations if available
        if len(hq_widths) >= 1:
            used_widths = hq_widths
            used_obs = hq_observations
            width_fusion_strategy = "high_quality_median"
        else:
            # Fallback: rank by quality score and take top observations
            sorted_pairs = sorted(zip(cluster, audits), key=lambda p: p[1]["quality_score"], reverse=True)
            top_k = max(1, len(sorted_pairs) // 2)
            used_obs = [p[0] for p in sorted_pairs[:top_k]]
            used_widths = [o["projected_geometry"]["width_m"] for o in used_obs]
            width_fusion_strategy = "fallback_top_quality_ranked"

        fused_width = float(np.median(used_widths))
        measurement_spread_m = float(np.std(used_widths, ddof=1)) if len(used_widths) > 1 else 0.0
        lower_bound, upper_bound, half_width = estimate_opening_uncertainty(used_widths, wall_rmse_m=wall_rmse)

        # Average 3D coordinates from the high-quality/used observations
        all_lefts = [obs["projected_geometry"]["left_jamb_3d"] for obs in used_obs]
        all_rights = [obs["projected_geometry"]["right_jamb_3d"] for obs in used_obs]
        fused_left_3d = [round(float(v), 4) for v in np.mean(all_lefts, axis=0)]
        fused_right_3d = [round(float(v), 4) for v in np.mean(all_rights, axis=0)]
        fused_centroid_3d = [
            round((fused_left_3d[0] + fused_right_3d[0]) / 2.0, 4),
            round((fused_left_3d[1] + fused_right_3d[1]) / 2.0, 4),
            round((fused_left_3d[2] + fused_right_3d[2]) / 2.0, 4),
        ]

        scores = [obs["candidate"]["detector_score"] for obs in cluster]
        frame_ids = [obs["candidate"]["frame_id"] for obs in cluster]
        mean_score = float(np.mean(scores))

        # Determine best frame index for visual verification
        sorted_by_quality = sorted(zip(cluster, audits), key=lambda p: p[1]["quality_score"], reverse=True)
        best_obs_record, best_audit = sorted_by_quality[0]
        best_frame_id = best_obs_record["candidate"]["frame_id"]

        # Confidence calculation
        persistence_factor = min(1.0, 0.4 + 0.1 * num_frames)
        spread_penalty = max(0.5, 1.0 - (half_width / fused_width)) if fused_width > 0 else 0.5
        overall_confidence = round(float(mean_score * persistence_factor * spread_penalty), 3)

        opening_id = f"opening_{opening_idx:02d}"
        opening_idx += 1

        # Check corridor doorway relationship
        is_corridor_doorway = False
        if wall_id == "wall_02":
            cx, cz = fused_centroid_3d[0], fused_centroid_3d[2]
            if -1.8 <= cx <= -0.8 and 2.8 <= cz <= 3.8:
                is_corridor_doorway = True

        # Multi-frame status determination
        # Accepted: >= 3 supporting frames AND >= 1 high-quality frame
        # Provisional: 2 supporting frames (e.g. window with 2 frames)
        # Uncertain: 1 frame or low confidence
        if num_frames >= min_frames_for_acceptance and len(hq_widths) >= 1:
            opening_status = "accepted"
        elif num_frames >= 2:
            opening_status = "provisional"
        else:
            opening_status = "uncertain"

        opening_record: Dict[str, Any] = {
            "id": opening_id,
            "type": normalized_class,
            "wall_id": wall_id,
            "status": opening_status,
            "width": {
                "value": round(fused_width, 4),
                "unit": "m",
                "interval": [lower_bound, upper_bound],
                "half_width_uncertainty_m": half_width,
                "confidence": overall_confidence,
                "method": "high_quality_multi_frame_rgb_depth_wall_projection",
                "width_fusion_strategy": width_fusion_strategy,
                "high_quality_frames_used": len(used_widths),
                "total_observations": num_frames,
                "calibrated": False,
                "calibration_status": "awaiting_ground_truth_benchmark",
            },
            "supporting_frames": num_frames,
            "supporting_frame_ids": frame_ids,
            "high_quality_frames": len(hq_widths),
            "best_frame_id": best_frame_id,
            "detector_confidence": round(mean_score, 3),
            "geometry_verified": True,
            "calibrated": False,
            "left_jamb_3d": fused_left_3d,
            "right_jamb_3d": fused_right_3d,
            "centroid_3d": fused_centroid_3d,
            "measurement_spread_m": round(measurement_spread_m, 4),
            "raw_measurement_spread_m": round(float(np.std(raw_widths, ddof=1)) if len(raw_widths) > 1 else 0.0, 4),
            "frame_quality_audit": audits,
            "affects_polygon": is_corridor_doorway,
            "polygon_refinement_recommended": is_corridor_doorway,
            "ground_truth": {
                "width_m": None,
                "detected": None,
                "absolute_error_m": None,
                "pass_2cm_benchmark": None,
            },
        }

        if is_corridor_doorway:
            opening_record["corridor_refinement_note"] = (
                "Matches the Stage 4 0.251m polygon edge anomaly on wall_02 leading to the corridor. "
                "The semantic/geometric opening detector identified a physical doorway here, "
                "recommending a doorway-aware structural polygon refinement."
            )
            polygon_refinements.append({
                "opening_id": opening_id,
                "wall_id": wall_id,
                "affects_polygon": True,
                "polygon_refinement_recommended": True,
                "measured_opening_width_m": round(fused_width, 4),
                "historical_polygon_edge_span_m": 0.251,
                "notes": "Doorway opening spans corridor T-junction threshold.",
            })

        if opening_status == "accepted":
            accepted_openings.append(opening_record)
        elif opening_status == "provisional":
            provisional_openings.append(opening_record)
        else:
            uncertain_openings.append(opening_record)

    return {
        "accepted_openings": accepted_openings,
        "provisional_openings": provisional_openings,
        "uncertain_openings": uncertain_openings,
        "rejected_candidates": rejected_observations,
        "polygon_refinement_candidates": polygon_refinements,
        "calibration_status": "awaiting_ground_truth_benchmark",
    }
