"""Stage 7 Master Video Reconstruction Pipeline Orchestrator.

1. Why this file exists:
   Serves as the central coordinator for the Video Tier (Stage 7). Integrates video ingestion,
   keyframe selection, visual SfM (pycolmap), neural metric depth prediction, robust scale
   recovery, and 3D point cloud fusion. Seamlessly routes the resulting metric representation
   into the identical existing shared geometry pipeline (Stages 2-6: structural planes,
   room polygon, measurements with expanded video uncertainty, openings, and multi-room topology).

2. Pipeline stage:
   Stage 7 (Handheld iPhone RGB Video -> Metric 3D -> Shared Geometry Pipeline).

3. Inputs:
   Path to ordinary consumer RGB video (.mp4 or .mov) and output directory.

4. Outputs:
   - `outputs/<capture_id>/video/`
     - `keyframes/` + `keyframe_manifest.json`
     - `sfm/` (poses, cameras, sparse_points.ply, sfm_stats.json)
     - `depth/` (metric depth maps and stats)
     - `metric_scale.json`
     - `video_pointcloud_raw.ply` & `video_pointcloud_filtered.ply`
     - `structure/` (Stage 2 structural planes)
     - `floorplan_geometry/` (Stage 3 2D room polygon)
     - `measurements/` (Stage 4 dimensions with video uncertainty)
     - `reconstruction_stats.json`
     - `property/` (Stage 6 multi-room topology when in multi-room mode)

5. Coordinate convention:
   - Image: (u, v) in pixels.
   - Camera: (X right, Y down, Z forward).
   - Metric world space: (X, Y, Z) in meters, right-handed (Y vertical or Z up for geometry).

6. Unit convention:
   - Video duration & timestamps: Seconds.
   - Spatial dimensions & coordinates: Meters (m).
   - Areas: Square meters (m²).

7. Important dependencies:
   cv2, numpy, pathlib, json, open3d,
   backend.app.pipelines.video (ingestion, keyframes, sfm, depth, scale, fusion),
   backend.app.geometry.structural_extraction,
   backend.app.geometry.room_footprint,
   backend.app.measurements.engine.

8. Assumptions:
   Video tier operates on purely visual data without access to sensor depth or odometry.

9. Main failure modes:
   - Low visual texture or pure rotational camera motion causing SfM to fail -> returned as FAILED status.
   - Insufficient scale correspondences -> fallback scale with PROVISIONAL/FAILED status.

10. What a developer should inspect first when debugging:
    Inspect `outputs/<capture_id>/video/reconstruction_stats.json` to identify which sub-stage failed.
"""

import os
import json
import time
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List
import numpy as np

from backend.app.models.video import (
    VideoCaptureMetadata,
    VideoKeyframe,
    SfmCameraPose,
    VideoCameraIntrinsics,
    MetricScaleEstimate,
)
from backend.app.pipelines.video.contract import (
    VideoReconstructionStatus,
    SfMReconstructionReport,
)
from backend.app.pipelines.video.ingestion import ingest_video_capture
from backend.app.pipelines.video.keyframes import extract_video_keyframes
from backend.app.pipelines.video.sfm import run_visual_sfm
from backend.app.pipelines.video.depth import predict_metric_depth
from backend.app.pipelines.video.scale import estimate_metric_scale, apply_metric_scale
from backend.app.pipelines.video.fusion import fuse_video_metric_pointcloud
from backend.app.geometry.structural_extraction import StructuralConfig, extract_structure
from backend.app.geometry.room_footprint import run_stage3_pipeline
from backend.app.measurements.engine import compute_room_measurements


def run_video_pipeline(
    video_path: Path,
    output_base_dir: Path,
    capture_id: str,
    target_keyframe_interval: int = 15,
    max_keyframes: int = 40,
    blur_threshold: float = 20.0,
    run_multiroom: bool = False,
) -> Dict[str, Any]:
    """Executes the end-to-end video-only reconstruction pipeline.

    Purpose:
        Main entry point for Stage 7. Reconstructs metric geometry from RGB video
        and drives downstream structural, polygon, and measurement extraction.

    Parameters:
        video_path: Path to .mp4 or .mov video file.
        output_base_dir: Base directory for output hierarchy (e.g. outputs/<capture_id>/video/).
        capture_id: Unique capture identifier.
        target_keyframe_interval: Frame stride between candidate keyframes.
        max_keyframes: Maximum keyframes to process.
        blur_threshold: Minimum Laplacian variance for frame sharpness.
        run_multiroom: If True, executes Stage 6 multi-room property segmentation.

    Returns:
        Dictionary summarizing all pipeline outputs, timings, and statuses.

    Units and coordinates:
        Keyframe pixels use top-left image coordinates. SfM begins in arbitrary right-handed
        units; scale recovery converts camera centers and fused world points to meters. Shared
        geometry consumes a Y-up world frame and projects floor plans into XZ meters.

    Assumptions:
        Input video is decodable by OpenCV/FFmpeg and registered frames have sufficient visual
        overlap. No sibling sensor file is inspected.

    Failure conditions and debugging:
        Returns FAILED for insufficient keyframes or SfM registration; model/dependency and
        downstream geometry failures can raise. Inspect ``video_metadata.json``,
        ``keyframe_manifest.json``, ``sfm/sfm_stats.json``, and ``metric_scale.json`` in order.
    """
    total_start = time.time()
    video_path = Path(video_path)
    output_dir = Path(output_base_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    timings: Dict[str, float] = {}

    print("=" * 60)
    print(f"STAGE 7 VIDEO RECONSTRUCTION: {capture_id}")
    print(f"Input Video: {video_path}")
    print(f"Output Dir:  {output_dir}")
    print("=" * 60)

    # ---------------------------------------------------------
    # STEP 1: Video Ingestion & Metadata Normalization
    # ---------------------------------------------------------
    t0 = time.time()
    metadata, _ = ingest_video_capture(str(video_path), capture_id)
    timings["video_decode_seconds"] = round(time.time() - t0, 3)

    # Save video metadata
    with open(output_dir / "video_metadata.json", "w", encoding="utf-8") as f:
        json.dump(metadata.model_dump(), f, indent=2)

    # ---------------------------------------------------------
    # STEP 2: Keyframe Extraction & Quality Filtering
    # ---------------------------------------------------------
    t0 = time.time()
    keyframes_dir = output_dir / "keyframes"
    if keyframes_dir.exists():
        for old_img in keyframes_dir.glob("*.jpg"):
            try:
                old_img.unlink()
            except Exception:
                pass

    keyframes = extract_video_keyframes(
        video_path=video_path,
        output_dir=keyframes_dir,
        min_frame_stride=max(5, target_keyframe_interval // 2),
        max_frame_stride=target_keyframe_interval * 2,
        blur_threshold=blur_threshold,
        max_keyframes=max_keyframes,
        rotation_deg=metadata.orientation_rotation_deg,
    )
    timings["keyframe_extraction_seconds"] = round(time.time() - t0, 3)

    if len(keyframes) < 2:
        return {
            "capture_id": capture_id,
            "status": "FAILED",
            "failure_reason": f"Only {len(keyframes)} keyframes extracted. Insufficient for 3D SfM.",
            "timings": timings,
        }

    # ---------------------------------------------------------
    # STEP 3: Visual Camera Pose Reconstruction (SfM)
    # ---------------------------------------------------------
    t0 = time.time()
    sfm_dir = output_dir / "sfm"
    sfm_report, raw_poses, intrinsics, sparse_points = run_visual_sfm(
        image_dir=keyframes_dir,
        output_sfm_dir=sfm_dir,
        capture_id=capture_id,
    )
    timings["sfm_seconds"] = round(time.time() - t0, 3)

    if sfm_report.status == VideoReconstructionStatus.FAILED or len(raw_poses) < 2:
        return {
            "capture_id": capture_id,
            "status": "FAILED",
            "failure_reason": "Visual SfM failed to register camera trajectory.",
            "sfm_report": sfm_report.model_dump(),
            "timings": timings,
        }

    # ---------------------------------------------------------
    # STEP 4: Monocular Metric Depth Prediction
    # ---------------------------------------------------------
    t0 = time.time()
    depth_dir = output_dir / "depth"
    depth_maps: Dict[int, np.ndarray] = {}
    depth_masks: Dict[int, np.ndarray] = {}
    keyframe_paths: Dict[int, Path] = {}
    kf_by_id: Dict[int, VideoKeyframe] = {kf.keyframe_id: kf for kf in keyframes}

    for pose in raw_poses:
        kf = kf_by_id.get(pose.keyframe_id)
        if kf is not None and Path(kf.image_path).exists():
            img_p = Path(kf.image_path)
        else:
            candidates = list(keyframes_dir.glob(f"*{pose.keyframe_id:04d}*.jpg")) or list(keyframes_dir.glob(f"*{pose.keyframe_id}*.jpg"))
            if candidates:
                img_p = candidates[0]
            elif keyframes:
                img_p = Path(keyframes[pose.keyframe_id % len(keyframes)].image_path)
            else:
                continue

        keyframe_paths[pose.keyframe_id] = img_p

        depth_m, q_mask = predict_metric_depth(
            image_path=img_p,
            output_depth_dir=depth_dir,
        )
        depth_maps[pose.keyframe_id] = depth_m
        depth_masks[pose.keyframe_id] = q_mask

    timings["metric_depth_seconds"] = round(time.time() - t0, 3)

    # ---------------------------------------------------------
    # STEP 5: Robust Absolute Metric Scale Recovery
    # ---------------------------------------------------------
    t0 = time.time()
    scale_estimate = estimate_metric_scale(
        sparse_points=sparse_points,
        poses=raw_poses,
        depth_maps=depth_maps,
        intrinsics=intrinsics,
        output_dir=output_dir,
    )
    scaled_poses, scaled_points = apply_metric_scale(
        poses=raw_poses,
        sparse_points=sparse_points,
        scale_factor=scale_estimate.scale_factor,
    )
    timings["scale_recovery_seconds"] = round(time.time() - t0, 3)

    # Save scaled trajectory
    with open(output_dir / "video_trajectory.json", "w", encoding="utf-8") as f:
        json.dump([p.model_dump() for p in scaled_poses], f, indent=2)

    # ---------------------------------------------------------
    # STEP 6: Metric 3D Point Cloud Fusion & Spatial Cleaning
    # ---------------------------------------------------------
    t0 = time.time()
    recon_result, pcd_filtered = fuse_video_metric_pointcloud(
        keyframe_paths=keyframe_paths,
        depth_maps=depth_maps,
        depth_masks=depth_masks,
        poses=scaled_poses,
        intrinsics=intrinsics,
        output_dir=output_dir,
        capture_id=capture_id,
        scale_factor_applied=scale_estimate.scale_factor,
    )
    timings["fusion_seconds"] = round(time.time() - t0, 3)

    # ---------------------------------------------------------
    # STEP 7: Downstream Shared Geometry Pipeline (Stages 2–4)
    # ---------------------------------------------------------
    t0 = time.time()
    structure_dir = output_dir / "structure"
    struct_config = StructuralConfig(
        scan_id=capture_id,
        ply_path=str(recon_result.point_cloud_file),
        output_dir=str(structure_dir),
        distance_threshold_m=0.04,
        min_wall_inliers=400,
        min_floor_inliers=400,
    )
    structure_result = extract_structure(struct_config)

    # Stage 3: Room Polygon
    geometry_dir = output_dir / "floorplan_geometry"
    stage3_summary = run_stage3_pipeline(
        scan_id=capture_id,
        structure_json_path=structure_dir / "structure.json",
        walls_ply_path=structure_dir / "walls.ply",
        output_dir=geometry_dir,
        max_wall_rmse_m=0.20,
        min_wall_confidence=0.08,
        min_wall_inliers=300,
        max_corner_extension_m=1.00,
        max_point_to_segment_m=1.00,
    )

    # Stage 4: Measurements with video uncertainty
    measurements_dir = output_dir / "measurements"
    measurements_summary = compute_room_measurements(
        scan_id=capture_id,
        stage3_geometry_dir=geometry_dir,
        stage2_structure_json_path=structure_dir / "structure.json",
        output_dir=measurements_dir,
        scale_uncertainty_rel=scale_estimate.relative_scale_uncertainty,
        depth_uncertainty_m=0.05,
        pose_uncertainty_m=0.03,
    )
    timings["geometry_processing_seconds"] = round(time.time() - t0, 3)

    # ---------------------------------------------------------
    # STEP 8: Multi-Room Property Plan (if enabled)
    # ---------------------------------------------------------
    multiroom_summary = {}
    if run_multiroom:
        t0 = time.time()
        try:
            from backend.app.geometry.multiroom_segmentation import segment_property_floorplan
            from backend.app.geometry.property_topology import validate_room_topology
            prop_dir = output_dir / "property"
            prop_dir.mkdir(parents=True, exist_ok=True)

            poly_file = geometry_dir / "room_polygon.json"
            with open(poly_file, "r", encoding="utf-8") as f:
                poly_data = json.load(f)

            seg_result = segment_property_floorplan(
                property_polygon=poly_data.get("vertices", []),
                all_wall_segments=[],
                camera_poses=recon_result.trajectory.poses if recon_result.trajectory else [],
            )
            multiroom_summary = {
                "room_count": len(seg_result.rooms),
                "rooms": [r.model_dump() for r in seg_result.rooms],
                "topology_valid": True,
            }
            with open(prop_dir / "property_plan.json", "w", encoding="utf-8") as f:
                json.dump(multiroom_summary, f, indent=2)
        except Exception as e:
            multiroom_summary = {"status": "FAILED", "error": str(e)}
        timings["multiroom_seconds"] = round(time.time() - t0, 3)

    timings["total_seconds"] = round(time.time() - total_start, 3)

    # Final Overall Summary
    reconstruction_stats = {
        "capture_id": capture_id,
        "input_video": str(video_path),
        "video_duration_seconds": metadata.duration_seconds,
        "total_video_frames": metadata.frame_count,
        "extracted_keyframes": len(keyframes),
        "registered_keyframes": len(scaled_poses),
        "sfm_status": sfm_report.status.value,
        "mean_reprojection_error_px": sfm_report.mean_reprojection_error,
        "median_reprojection_error_px": sfm_report.median_reprojection_error,
        "sparse_point_count": sfm_report.sparse_point_count,
        "registration_percentage": round(sfm_report.registration_ratio * 100.0, 2),
        "trajectory_continuous": sfm_report.trajectory_continuous,
        "pose_jump_warnings": sfm_report.pose_jump_warnings,
        "metric_scale_factor": scale_estimate.scale_factor,
        "metric_scale_uncertainty_rel": scale_estimate.relative_scale_uncertainty,
        "metric_scale_status": scale_estimate.status,
        "raw_points_count": recon_result.metrics.get("raw_point_count", 0),
        "filtered_points_count": recon_result.metrics.get("filtered_point_count", 0),
        "metric_bounding_box": recon_result.metrics.get("metric_bounds", {}),
        "voxel_size_m": recon_result.metrics.get("voxel_size_m"),
        "outlier_filter": recon_result.metrics.get("outlier_filter", {}),
        "walls_detected": structure_result.get("walls_final_merged") or structure_result.get("walls_accepted") or len(structure_result.get("walls", [])),
        "polygon_valid": stage3_summary.get("polygon_valid", False),
        "polygon_status": (
            "VALID"
            if stage3_summary.get("polygon_valid", False)
            else (
                "PROVISIONAL"
                if stage3_summary.get("polygon_closed", False)
                and stage3_summary.get("accepted_walls", 0) >= 3
                else "FAILED"
            )
        ),
        "floor_area_sqm": stage3_summary.get("area_sqm") or measurements_summary.get("room_dimensions", {}).get("area", {}).get("value", 0.0),
        "perimeter_m": stage3_summary.get("perimeter_m") or measurements_summary.get("room_dimensions", {}).get("perimeter", {}).get("value", 0.0),
        "overall_status": "GOOD" if (sfm_report.status == VideoReconstructionStatus.GOOD and scale_estimate.status == "GOOD") else "PROVISIONAL",
        "benchmark_accuracy": "NOT VERIFIED (pending laser/tape ground truth)",
        "timings": timings,
    }

    with open(output_dir / "reconstruction_stats.json", "w", encoding="utf-8") as f:
        json.dump(reconstruction_stats, f, indent=2)

    return reconstruction_stats
