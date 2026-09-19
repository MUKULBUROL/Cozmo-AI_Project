"""Master orchestration pipeline for Stage 5 structural opening detection and metric measurement.

1. Why this file exists:
   Coordinates the end-to-end Stage 5 pipeline: RGB video keyframe selection, semantic door/window
   detection via open-vocabulary YOLO-World, depth-guided jamb boundary refinement, 3D ray projection
   onto Stage 2 structural wall planes, multi-frame observation clustering, metric clearance width
   measurement, uncalibrated engineering uncertainty estimation, and visual artifact generation.

2. Pipeline stage:
   Stage 5 (Door/Window Detection & Metric Opening Measurement) - Master Pipeline.

3. Inputs:
   Scan directory containing rgb.mp4, odometry.csv, depth/*.png, and Stage 2/3 outputs
   (structural_planes.json, room_polygon.json, room_polygon_stats.json).

4. Outputs:
   Directory outputs/<scan_id>/openings/ containing:
   - keyframes/
   - detections.json
   - opening_observations.json
   - openings.json
   - opening_stats.json
   - opening_debug.svg
   - debug_frames/

5. Coordinate/Unit conventions:
   Metric meters (m) in 3D world coordinates (Y vertical upward, XZ horizontal floor plane).
   Pixel coordinates (u, v) with origin at top-left.

6. Dependencies:
   os, json, time, typing, numpy, .keyframes, .detector, .segmentation, .opening_viz,
   backend.app.geometry.opening_association, backend.app.geometry.opening_fusion.

7. Most likely failure/debugging points:
   - Missing input Stage 2 or Stage 3 JSON artifacts (requires Stage 2/3 to be run first).
   - Missing model weights file (auto-downloaded or configured via weights_path).
   - Video file read failure or mismatched timestamp odometry.
"""

from pathlib import Path
import json
import os
import time
from typing import Any, Dict, List, Optional
import numpy as np

from .keyframes import extract_keyframes
from .detector import OpeningDetector
from .segmentation import refine_opening_boundaries_with_depth
from .opening_viz import save_annotated_frame, render_openings_floorplan_svg
from ..geometry.opening_association import associate_candidate_with_wall
from ..geometry.opening_fusion import cluster_opening_observations, fuse_openings


def run_opening_pipeline(
    scan_id: str,
    dataset_root: str = "sample data",
    outputs_root: str = "outputs",
    model_weights_path: str = "yolov8s-worldv2.pt",
    max_keyframes: int = 45,
    min_translation_m: float = 0.20,
    min_rotation_deg: float = 12.0,
    detector_confidence_threshold: float = 0.06,
) -> Dict[str, Any]:
    """Runs the complete Stage 5 opening detection and metric measurement workflow.

    Purpose:
        Executes keyframe extraction, AI semantic detection, 3D ray-plane projection,
        wall association, multi-frame observation fusion, and disk export.

    Parameters:
        scan_id: Scan directory identifier (e.g. 'c00a170fe1').
        dataset_root: Root path containing raw scan archives.
        outputs_root: Destination directory for pipeline outputs.
        model_weights_path: Path to pretrained YOLO-World model weights.
        max_keyframes: Maximum number of sharp, motion-spaced keyframes to analyze.
        min_translation_m: Minimum camera movement (m) between candidate keyframes.
        min_rotation_deg: Minimum camera rotation (deg) between candidate keyframes.
        detector_confidence_threshold: Minimum provisional detection score.

    Returns:
        Dictionary summarizing pipeline execution results, counts, and measurements.

    Assumptions:
        Stage 1 metric depth, Stage 2 structural walls, and Stage 3 polygon exist in outputs/<scan_id>/.

    Failure conditions:
        Raises FileNotFoundError if required Stage 2/3 inputs or scan files are missing.

    Debugging:
        Check outputs/<scan_id>/openings/opening_stats.json for step-by-step diagnostic timings.
    """
    start_time = time.time()
    scan_output_dir = os.path.join(outputs_root, scan_id)
    openings_output_dir = os.path.join(scan_output_dir, "openings")
    keyframes_dir = os.path.join(openings_output_dir, "keyframes")
    debug_frames_dir = os.path.join(openings_output_dir, "debug_frames")

    os.makedirs(openings_output_dir, exist_ok=True)
    os.makedirs(debug_frames_dir, exist_ok=True)

    # 1. Load Stage 2 Structural Walls
    stage2_candidates = [
        os.path.join(scan_output_dir, "structure", "structure.json"),
        os.path.join(scan_output_dir, "structure", "structural_planes.json"),
    ]
    stage2_path = None
    for cand in stage2_candidates:
        if os.path.exists(cand):
            stage2_path = cand
            break

    if not stage2_path:
        raise FileNotFoundError(f"Required Stage 2 structural planes not found at: {stage2_candidates}")

    with open(stage2_path, "r", encoding="utf-8") as f:
        stage2_data = json.load(f)
    structural_walls = stage2_data.get("walls", [])

    # 2. Load Stage 3 Room Polygon
    stage3_path = os.path.join(scan_output_dir, "floorplan_geometry", "room_polygon.json")
    polygon_vertices: List[List[float]] = []
    polygon_edges: List[Dict[str, Any]] = []
    projected_walls: List[Dict[str, Any]] = []

    if os.path.exists(stage3_path):
        with open(stage3_path, "r", encoding="utf-8") as f:
            stage3_data = json.load(f)
            polygon_vertices = stage3_data.get("polygon", {}).get("vertices", []) or stage3_data.get("polygon_vertices_2d", [])
            polygon_edges = stage3_data.get("polygon_edges", [])
            projected_walls = stage3_data.get("walls", []) or stage3_data.get("projected_walls", [])

    # Locate raw archive
    scan_archive_map = {
        "c00a170fe1": "sample data/single_room.zip",
        "1a8384c3f6": "sample data/single_scan_floor_only.zip",
        "c7d28f72c6": "sample data/single_scan_with_ceiling.zip",
    }
    archive_candidates = [
        Path(dataset_root) if str(dataset_root).endswith(".zip") else Path(dataset_root) / f"{scan_id}.zip",
        Path(scan_archive_map.get(scan_id, "")),
        Path("sample data") / f"{scan_id}.zip",
        Path("sample data/single_room.zip"),
    ]
    archive_path: Optional[Path] = None
    for cand in archive_candidates:
        if str(cand) and cand.exists() and cand.is_file():
            archive_path = cand
            break

    if archive_path is None:
        raise FileNotFoundError(f"Could not locate zip archive for scan '{scan_id}'. Checked {archive_candidates}")

    # 3. Extract Keyframes
    print(f"[{scan_id}] Step 1/6: Extracting sharp, motion-spaced keyframes from {archive_path}...")
    keyframes = extract_keyframes(
        scan_id=scan_id,
        archive_path=archive_path,
        output_dir=Path(keyframes_dir),
        min_translation_m=min_translation_m,
        min_rotation_deg=min_rotation_deg,
        max_keyframes=max_keyframes,
    )
    print(f"[{scan_id}] Extracted {len(keyframes)} keyframes.")

    # 4. Run Semantic Detector
    print(f"[{scan_id}] Step 2/6: Running open-vocabulary detector on keyframes...")
    detector = OpeningDetector(
        weights_path=model_weights_path,
        classes=["door", "door frame", "interior door", "doorway", "window", "window glass"],
    )

    all_raw_detections: List[Dict[str, Any]] = []
    keyframe_detections_map: Dict[int, List[Dict[str, Any]]] = {}

    for kf in keyframes:
        frame_id = kf["frame_id"]
        img_path = kf["image_path"]
        dets = detector.detect(img_path, frame_id=frame_id, conf_threshold=detector_confidence_threshold)
        keyframe_detections_map[frame_id] = dets
        all_raw_detections.extend(dets)

    print(f"[{scan_id}] Detected {len(all_raw_detections)} provisional candidate opening boxes.")

    # 5. Depth Refinement, Ray Projection, and Wall Association
    print(f"[{scan_id}] Step 3/6: Depth refinement, 3D ray projection & wall association...")
    accepted_observations: List[Dict[str, Any]] = []
    rejected_observations: List[Dict[str, Any]] = []
    annotated_keyframe_records: Dict[int, List[Dict[str, Any]]] = {}

    for kf in keyframes:
        frame_id = kf["frame_id"]
        dets = keyframe_detections_map.get(frame_id, [])
        if not dets:
            continue

        depth_map = kf.get("depth_map")
        intrinsics = kf["intrinsics"]
        camera_pose = kf["camera_pose"]

        frame_annotated_dets: List[Dict[str, Any]] = []

        for det in dets:
            # Depth boundary refinement
            refined_boundary = refine_opening_boundaries_with_depth(det, depth_map)
            det["boundary_pixels"] = refined_boundary

            # Structural wall association & 3D projection
            obs = associate_candidate_with_wall(
                candidate=det,
                boundary_pixels=refined_boundary,
                intrinsics=intrinsics,
                camera_pose=camera_pose,
                structural_walls=structural_walls,
                projected_walls=projected_walls,
            )

            if obs["status"] == "accepted":
                accepted_observations.append(obs)
                # Attach projected geometry to candidate for annotation
                det_copy = dict(det)
                det_copy["projected_geometry"] = obs["projected_geometry"]
                frame_annotated_dets.append(det_copy)
            else:
                rejected_observations.append(obs)

        if frame_annotated_dets:
            annotated_keyframe_records[frame_id] = frame_annotated_dets

    print(f"[{scan_id}] Wall association: {len(accepted_observations)} accepted observations, {len(rejected_observations)} rejected candidates.")

    # 6. Multi-frame Observation Fusion
    print(f"[{scan_id}] Step 4/6: Multi-frame spatial clustering & metric width fusion...")
    clusters = cluster_opening_observations(accepted_observations)
    fusion_result = fuse_openings(
        clusters=clusters,
        rejected_observations=rejected_observations,
        structural_walls=structural_walls,
        polygon_edges=polygon_edges,
    )

    openings = fusion_result["accepted_openings"]
    uncertain = fusion_result["uncertain_openings"]
    polygon_refinements = fusion_result["polygon_refinement_candidates"]

    doors_count = sum(1 for op in openings if op.get("type") in {"door", "doorway"})
    windows_count = sum(1 for op in openings if op.get("type") == "window")

    print(f"[{scan_id}] Fused into {len(openings)} distinct openings ({doors_count} doors/doorways, {windows_count} windows).")

    # 7. Generate Debug Visualizations
    print(f"[{scan_id}] Step 5/6: Generating visual verification artifacts...")
    # Render floor plan SVG
    svg_path = os.path.join(openings_output_dir, "opening_debug.svg")
    render_openings_floorplan_svg(
        output_svg_path=svg_path,
        room_polygon_vertices=polygon_vertices,
        openings=openings,
        structural_walls=structural_walls,
        uncertain_openings=uncertain,
    )

    # Save up to 8 representative annotated debug keyframes
    annotated_count = 0
    for kf in keyframes:
        frame_id = kf["frame_id"]
        if frame_id in annotated_keyframe_records and annotated_count < 8:
            dbg_img_path = os.path.join(debug_frames_dir, f"frame_{frame_id:06d}_annotated.jpg")
            save_annotated_frame(
                image_path=kf["image_path"],
                output_path=dbg_img_path,
                detections=annotated_keyframe_records[frame_id],
            )
            annotated_count += 1

    # 8. Save JSON Outputs (Step 14 Contract)
    print(f"[{scan_id}] Step 6/6: Saving JSON contracts and statistics...")
    detections_json_path = os.path.join(openings_output_dir, "detections.json")
    with open(detections_json_path, "w", encoding="utf-8") as f:
        json.dump({
            "scan_id": scan_id,
            "keyframes_count": len(keyframes),
            "raw_detections_count": len(all_raw_detections),
            "detections": all_raw_detections,
        }, f, indent=2)

    obs_json_path = os.path.join(openings_output_dir, "opening_observations.json")
    with open(obs_json_path, "w", encoding="utf-8") as f:
        json.dump({
            "scan_id": scan_id,
            "accepted_observations_count": len(accepted_observations),
            "rejected_observations_count": len(rejected_observations),
            "accepted_observations": accepted_observations,
            "rejected_observations": rejected_observations,
        }, f, indent=2)

    openings_json_path = os.path.join(openings_output_dir, "openings.json")
    with open(openings_json_path, "w", encoding="utf-8") as f:
        json.dump({
            "scan_id": scan_id,
            "openings_count": len(openings),
            "openings": openings,
            "uncertain_openings": uncertain,
            "polygon_refinement_candidates": polygon_refinements,
            "calibration_status": "awaiting_ground_truth_benchmark",
        }, f, indent=2)

    elapsed_sec = round(time.time() - start_time, 2)
    stats_data: Dict[str, Any] = {
        "scan_id": scan_id,
        "pipeline_stage": "Stage 5 - Door/Window Detection & Metric Opening Measurement",
        "processing_time_sec": elapsed_sec,
        "keyframes_inspected": len(keyframes),
        "raw_candidate_detections": len(all_raw_detections),
        "accepted_observations": len(accepted_observations),
        "rejected_observations": len(rejected_observations),
        "accepted_openings": len(openings),
        "doors_count": doors_count,
        "windows_count": windows_count,
        "uncertain_openings": len(uncertain),
        "polygon_refinements_count": len(polygon_refinements),
        "calibration_status": "awaiting_ground_truth_benchmark",
        "uncertainty_calibrated": False,
    }

    stats_json_path = os.path.join(openings_output_dir, "opening_stats.json")
    with open(stats_json_path, "w", encoding="utf-8") as f:
        json.dump(stats_data, f, indent=2)

    return stats_data
