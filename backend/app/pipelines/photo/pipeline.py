"""Stage 8 single-room photo reconstruction and shared geometry orchestration.

1. Why this file exists:
   Provides one auditable entry point from 2-8 standalone stills to the same metric Stage 2-5
   geometry used by LiDAR and video, without introducing photo-specific wall/measurement engines.
2. Pipeline stage:
   Stage 8 single-room orchestration from ingestion through optional opening semantics.
3. Inputs:
   A room directory containing only ordinary still images and a capture/room identifier.
4. Outputs:
   Photo/SfM/depth/cloud artifacts plus shared structure, polygon, measurements, and statistics.
5. Coordinate system:
   EXIF-normalized pixels become OpenCV cameras, then right-handed Y-up metric world geometry.
6. Units:
   Pixels for images/reprojection; meters and square meters for reconstructed geometry.
7. Dependencies:
   Stage 8 photo modules and existing Stage 2-5 implementations.
8. Assumptions:
   Input has no trusted pose/depth; pycolmap and metric depth dependencies are locally available.
9. Failure modes:
   Insufficient views, SfM failure, unstable scale, empty fusion, or unsupported shared geometry.
10. First debugging points:
   Inspect manifest, SfM quality, metric scale, filtered PLY, then shared stage JSON in that order.
"""

from __future__ import annotations

import importlib.util
import json
import time
from pathlib import Path
from typing import Any, Dict

from backend.app.geometry.room_footprint import run_stage3_pipeline
from backend.app.geometry.structural_extraction import StructuralConfig, extract_structure
from backend.app.measurements.engine import compute_room_measurements
from backend.app.pipelines.photo.fusion import fuse_photo_metric_pointcloud
from backend.app.pipelines.photo.ingestion import ingest_photo_room
from backend.app.pipelines.photo.metric import run_photo_metric_depth_and_scale
from backend.app.pipelines.photo.sfm import run_photo_sfm
from backend.app.pipelines.video.contract import VideoReconstructionStatus

DEPTH_MODEL_ID = "depth-anything/Depth-Anything-V2-Metric-Indoor-Small-hf"


def _write_opening_attempt(
    output_dir: Path,
    manifest: Any,
    polygon_valid: bool,
) -> Dict[str, Any]:
    """Record whether Stage 5 semantics can be supported without pixel-only measurements.

    Parameters:
        output_dir: Room output directory.
        manifest: Photo manifest whose normalized images would feed the shared RGB detector.
        polygon_valid: Whether shared Stage 3 produced a usable metric boundary.
    Returns:
        Opening status dictionary persisted as ``openings/openings.json``.
    Coordinates/units:
        No opening dimensions are emitted here; metric geometry is required before measurement.
    Assumptions:
        Existing YOLO-World semantics may run only from explicitly local weights.
    Failure/debugging:
        Missing geometry/dependency/weights returns NOT_EVALUABLE. Inspect reason and Stage 3.
    """
    openings_dir = output_dir / "openings"
    openings_dir.mkdir(parents=True, exist_ok=True)
    repo_root = Path(__file__).resolve().parents[4]
    candidates = [
        repo_root / "weights" / "yolov8s-worldv2.pt",
        Path("weights/yolov8s-worldv2.pt"),
        Path("yolov8s-worldv2.pt"),
    ]
    local_weights_exists = any(c.exists() for c in candidates)
    reasons = []
    if not polygon_valid:
        reasons.append("metric_room_polygon_unavailable")
    if importlib.util.find_spec("ultralytics") is None:
        reasons.append("shared_stage5_detector_dependency_unavailable")
    if not local_weights_exists:
        reasons.append("local_stage5_detector_weights_unavailable_no_download_attempted")
    report = {
        "status": "NOT_EVALUABLE" if reasons else "PROVISIONAL",
        "semantic_classes": ["door", "doorway", "window"],
        "photos_available": manifest.selected_count,
        "detections": [],
        "metric_measurements": [],
        "failure_reasons": reasons,
        "note": "Bounding-box pixels are never converted directly into metric opening dimensions.",
    }
    with open(openings_dir / "openings.json", "w", encoding="utf-8") as opening_file:
        json.dump(report, opening_file, indent=2)
    return report


def _write_failed_stats(output_dir: Path, stats: Dict[str, Any]) -> Dict[str, Any]:
    """Persist a partial reconstruction report before returning an honest failed status.

    Parameters:
        output_dir: Stage 8 room output directory.
        stats: JSON-safe partial result including a stable failure reason.
    Returns:
        The same dictionary for direct caller handling.
    Coordinates/units:
        Any included geometry retains the producing stage's declared coordinates and units.
    Assumptions:
        The caller has already created ``output_dir``.
    Failure/debugging:
        JSON I/O errors propagate; inspect directory permissions and free space.
    """
    stats["overall_status"] = "FAILED"
    with open(output_dir / "reconstruction_stats.json", "w", encoding="utf-8") as stats_file:
        json.dump(stats, stats_file, indent=2)
    return stats


def run_photo_room_pipeline(
    input_dir: Path,
    output_dir: Path,
    capture_id: str,
    room_id: str = "room_01",
    synthetic_development_set: bool = False,
) -> Dict[str, Any]:
    """Reconstruct one metric room from 2-8 standalone still photographs.

    Parameters:
        input_dir: Image-only room folder; direct child JPG/JPEG/PNG/decodable HEIC files are read.
        output_dir: Artifact destination, normally ``outputs/<capture>/photo``.
        capture_id/room_id: Stable identifiers independent of filename/folder ordering.
        synthetic_development_set: Labels video-derived development fixtures in all reports.
    Returns:
        JSON-safe reconstruction summary spanning ingestion, SfM, scale, cloud, and Stages 2-5.
    Coordinates/units:
        Final cloud/shared geometry is right-handed Y-up in meters; floor plans use XZ meters.
    Assumptions:
        Photo input supplies no ARKit, LiDAR, video, odometry, confidence, or sensor depth data.
    Failure/debugging:
        Expected geometric failures return FAILED summaries; dependency/model and unexpected shared
        stage errors propagate. Follow artifact order documented in the module header.
    """
    started = time.time()
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    timings: Dict[str, float] = {}
    step = time.time()
    manifest = ingest_photo_room(
        input_dir=input_dir,
        output_dir=output_dir,
        capture_id=capture_id,
        room_id=room_id,
        synthetic_development_set=synthetic_development_set,
    )
    timings["photo_loading_seconds"] = round(time.time() - step, 3)
    step = time.time()
    sfm_report, raw_poses, intrinsics, sparse_points, sfm_quality = run_photo_sfm(manifest, output_dir / "sfm")
    timings["sfm_seconds"] = round(time.time() - step, 3)
    base_stats: Dict[str, Any] = {
        "capture_id": capture_id,
        "room_id": room_id,
        "input_tier": "photo",
        "unit": "meters",
        "coordinate_system": "right_handed_y_up_xz_floor",
        "synthetic_development_photo_set": synthetic_development_set,
        "input_photos": manifest.selected_count,
        "registered_photos": sfm_report.registered_keyframes,
        "registration_ratio": sfm_report.registration_ratio,
        "sparse_point_count": sfm_report.sparse_point_count,
        "mean_reprojection_error_px": sfm_report.mean_reprojection_error,
        "sfm_status": sfm_quality.status,
        "sfm_failure_reasons": sfm_quality.failure_reasons,
        "intrinsics_source": intrinsics.provenance,
        "timings": timings,
    }
    if sfm_report.status == VideoReconstructionStatus.FAILED or len(raw_poses) < 2:
        base_stats["failure_reason"] = "photo_sfm_failed_or_too_few_registered_images"
        timings["total_seconds"] = round(time.time() - started, 3)
        return _write_failed_stats(output_dir, base_stats)
    step = time.time()
    depth_maps, depth_masks, image_paths, scale, metric_poses, _ = run_photo_metric_depth_and_scale(
        manifest, raw_poses, sparse_points, intrinsics, output_dir
    )
    timings["metric_depth_and_scale_seconds"] = round(time.time() - step, 3)
    base_stats.update({
        "metric_depth_model": DEPTH_MODEL_ID,
        "metric_scale_factor": scale.scale_factor,
        "metric_scale_status": scale.status,
        "metric_scale_uncertainty_rel": scale.relative_scale_uncertainty,
        "scale_correspondences": scale.total_correspondences,
        "scale_inliers": scale.inlier_count,
        "scale_mad": scale.mad,
    })
    if scale.status == "FAILED":
        base_stats["failure_reason"] = "unstable_or_insufficient_metric_scale"
        timings["total_seconds"] = round(time.time() - started, 3)
        return _write_failed_stats(output_dir, base_stats)
    step = time.time()
    reconstruction, _, aligned_poses = fuse_photo_metric_pointcloud(
        image_paths, depth_maps, depth_masks, metric_poses, intrinsics, output_dir, capture_id,
        scale.scale_factor,
    )
    with open(output_dir / "photo_trajectory.json", "w", encoding="utf-8") as trajectory_file:
        json.dump([pose.model_dump() for pose in aligned_poses], trajectory_file, indent=2)
    timings["fusion_seconds"] = round(time.time() - step, 3)
    step = time.time()
    structure_dir = output_dir / "structure"
    structure = extract_structure(StructuralConfig(
        scan_id=capture_id,
        ply_path=str(reconstruction.point_cloud_file),
        output_dir=str(structure_dir),
        distance_threshold_m=0.05,
        min_wall_inliers=300,
        min_floor_inliers=300,
    ))
    geometry_dir = output_dir / "floorplan_geometry"
    polygon = run_stage3_pipeline(
        scan_id=capture_id,
        structure_json_path=structure_dir / "structure.json",
        walls_ply_path=structure_dir / "walls.ply",
        output_dir=geometry_dir,
        max_wall_rmse_m=0.25,
        min_wall_confidence=0.06,
        min_wall_inliers=200,
        max_corner_extension_m=1.2,
        max_point_to_segment_m=1.2,
    )
    measurements = compute_room_measurements(
        scan_id=capture_id,
        stage3_geometry_dir=geometry_dir,
        stage2_structure_json_path=structure_dir / "structure.json",
        output_dir=output_dir / "measurements",
        scale_uncertainty_rel=max(scale.relative_scale_uncertainty, 0.03),
        depth_uncertainty_m=0.10,
        pose_uncertainty_m=0.08,
    )
    polygon_valid = bool(polygon.get("polygon_valid", False))
    openings = _write_opening_attempt(output_dir, manifest, polygon_valid)
    timings["geometry_seconds"] = round(time.time() - step, 3)
    timings["total_seconds"] = round(time.time() - started, 3)
    base_stats.update({
        "raw_points_count": reconstruction.metrics.get("raw_point_count", 0),
        "filtered_points_count": reconstruction.metrics.get("filtered_point_count", 0),
        "metric_bounding_box": reconstruction.metrics.get("metric_bounds", {}),
        "cross_view_consistency": reconstruction.metrics.get("cross_view_consistency", {}),
        "walls_detected": structure.get("walls_final_merged") or structure.get("walls_accepted") or len(structure.get("walls", [])),
        "plane_rmse": structure.get("mean_wall_rmse_m"),
        "polygon_valid": polygon_valid,
        "polygon_status": "VALID" if polygon_valid else ("PROVISIONAL" if polygon.get("polygon_closed") else "FAILED"),
        "floor_area_sqm": polygon.get("area_sqm") or measurements.get("room_dimensions", {}).get("area", {}).get("value", 0.0),
        "perimeter_m": polygon.get("perimeter_m") or measurements.get("room_dimensions", {}).get("perimeter", {}).get("value", 0.0),
        "measurement_status": measurements.get("status", "UNKNOWN"),
        "opening_status": openings["status"],
        "opening_count": len(openings["metric_measurements"]),
        "uncertainty_calibrated": False,
        "benchmark_accuracy": "NOT VERIFIED until laser/tape ground truth exists",
        "overall_status": "GOOD" if sfm_quality.status == "GOOD" and scale.status == "GOOD" and polygon_valid else "PROVISIONAL",
        "timings": timings,
    })
    with open(output_dir / "reconstruction_stats.json", "w", encoding="utf-8") as stats_file:
        json.dump(base_stats, stats_file, indent=2)
    return base_stats
