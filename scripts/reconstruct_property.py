"""Stage 6 Multi-Room Property Reconstruction Pipeline CLI.

1. Why this file exists:
    Provides the primary command-line execution entry point for Stage 6:
    loads multi-room LiDAR captures, audits raw trajectory drift, extracts keyframes,
    detects loop closures via Point-to-Plane ICP, runs Open3D pose graph optimization,
    reconstructs drift-corrected 3D point clouds, segments global room polygons,
    builds the topological adjacency graph, and exports drift ablation and debug SVGs.

2. Pipeline stage:
    Stage 6 — Multi-Room Property Reconstruction, Loop Closure & Drift Correction.

3. Inputs:
    --scan <scan_id> (e.g. c7d28f72c6), optional --frame-stride, optional --headless.

4. Outputs:
    Directory outputs/<scan_id>/property/ containing:
    - baseline/raw_trajectory.json
    - baseline/raw_trajectory.svg
    - optimized/optimized_pointcloud.ply
    - loop_candidates.json
    - loop_closures.json
    - pose_graph.json
    - drift_ablation.json
    - drift_ablation.svg
    - property.json
    - property_debug.svg

5. Coordinate conventions:
    ARKit Y-up vertical, horizontal XZ floor plane. Units in meters.

6. Unit assumptions:
    Distances in meters (m), area in square meters (m2), angles in degrees.

7. Important dependencies:
    argparse, json, pathlib, open3d, numpy, backend.app.

8. What is most likely to break:
    Missing scan zip archive or RAM exhaustion during dense point cloud fusion.

9. What a developer should inspect first:
    Check console output for optimization status ('IMPROVED') and drift residual drop.
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Dict, Any, Optional, List
import numpy as np
import open3d as o3d

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from backend.app.pipelines.lidar.loader import LiDARScanLoader
from backend.app.pipelines.lidar.fusion import fuse_scan_frames
from backend.app.geometry.structural_extraction import extract_structure, StructuralConfig
from backend.app.optimization.trajectory_analysis import (
    analyze_raw_trajectory,
    export_raw_trajectory_json,
    render_trajectory_svg,
)
from backend.app.optimization.keyframes import select_registration_keyframes, KeyframeNode
from backend.app.optimization.odometry_edges import compute_sequential_odometry_edges
from backend.app.optimization.loop_detector import detect_loop_candidates, export_loop_candidates_json
from backend.app.optimization.registration import register_loop_candidate, RegistrationResult
from backend.app.optimization.validation import validate_loop_candidate, export_loop_closures_json, ValidationDecision
from backend.app.optimization.pose_graph import optimize_pose_graph, export_pose_graph_json
from backend.app.optimization.ablation import compute_drift_ablation, render_drift_ablation_svg
from backend.app.geometry.multiroom_segmentation import (
    cluster_trajectory_into_room_regions,
    assign_walls_to_rooms,
    build_room_polygon_in_global_frame,
)
from backend.app.geometry.property_topology import (
    validate_room_topology,
    build_room_adjacency_graph,
    assemble_property_plan_output,
    export_property_json,
)
from backend.app.geometry.property_viz import render_property_debug_svg


def find_scan_archive(scan_id: str, search_roots: List[str]) -> Optional[str]:
    """Locates the zip archive containing data for the given scan_id.

    Purpose:
        Resolves file system path to raw LiDAR scan archives automatically.

    Parameters:
        scan_id: Capture ID (e.g. 'c7d28f72c6').
        search_roots: List of directory paths to check.

    Returns:
        String path to zip archive or None if not found.

    Assumptions:
        Archive is a valid zip containing <scan_id>/odometry.csv.

    Failure conditions:
        Returns None if no matching archive is found.

    Debugging:
        Verify folder names like 'sample data' or 'data'.
    """
    for root in search_roots:
        p = Path(root)
        if not p.exists():
            continue
        for zip_file in p.glob("*.zip"):
            try:
                import zipfile
                with zipfile.ZipFile(zip_file, "r") as z:
                    if f"{scan_id}/odometry.csv" in z.namelist():
                        return str(zip_file)
            except Exception:
                continue
    return None


def run_property_reconstruction(
    scan_id: str = "c7d28f72c6",
    archive_path: Optional[str] = None,
    frame_stride: int = 5,
    headless: bool = False,
    output_dir: Optional[str] = None,
) -> Dict[str, Any]:
    """Orchestrates the entire multi-room property reconstruction and drift correction.

    Purpose:
        Executes Steps 1 through 23 of Stage 6 in end-to-end sequential order.

    Parameters:
        scan_id: Target scan identifier.
        archive_path: Optional explicit zip archive path.
        frame_stride: Downsampling stride for fusion and point cloud reconstruction.
        headless: Flag to suppress interactive displays and format concise summary.
        output_dir: Optional custom output directory for deliverables.

    Returns:
        Dictionary summarizing all reconstruction accounting metrics.

    Assumptions:
        Valid LiDAR scan data exists in archive.

    Failure conditions:
        Raises FileNotFoundError if archive is missing.

    Debugging:
        Inspect generated JSON files in outputs/<scan_id>/property/ or custom output_dir.
    """
    t_start = time.time()
    if output_dir is not None:
        out_dir = Path(output_dir)
    else:
        out_dir = Path("outputs") / scan_id / "property"
    baseline_dir = out_dir / "baseline"
    optimized_dir = out_dir / "optimized"

    out_dir.mkdir(parents=True, exist_ok=True)
    baseline_dir.mkdir(parents=True, exist_ok=True)
    optimized_dir.mkdir(parents=True, exist_ok=True)

    if archive_path is None:
        archive_path = find_scan_archive(scan_id, ["sample data", "data", "data/raw"])
        if archive_path is None:
            raise FileNotFoundError(f"Could not find scan archive for {scan_id} in 'sample data' or 'data'")

    print(f"=== STAGE 6: MULTI-ROOM PROPERTY RECONSTRUCTION ===")
    print(f"Scan ID:        {scan_id}")
    print(f"Archive:        {archive_path}")
    print(f"Frame Stride:   {frame_stride}")

    # 1. Load Odometry and Baseline Trajectory Audit
    print("\n[1/7] Auditing Raw Odometry Trajectory...")
    with LiDARScanLoader(archive_path, scan_id) as loader:
        raw_poses_list = []
        from backend.app.models.capture import Pose6D
        for r in loader.odometry_records:
            intr = loader.get_scaled_intrinsics(r)
            p = Pose6D(
                timestamp=float(r["timestamp"]),
                frame_index=int(r["frame"]),
                x=float(r["x"]),
                y=float(r["y"]),
                z=float(r["z"]),
                qx=float(r["qx"]),
                qy=float(r["qy"]),
                qz=float(r["qz"]),
                qw=float(r["qw"]),
                intrinsics=intr,
            )
            raw_poses_list.append(p)

    raw_stats = analyze_raw_trajectory(raw_poses_list)
    export_raw_trajectory_json(raw_stats, raw_poses_list, baseline_dir / "raw_trajectory.json")
    render_trajectory_svg(raw_poses_list, raw_stats.get("revisit_samples"), baseline_dir / "raw_trajectory.svg")

    print(f"  Total Poses:       {raw_stats['total_poses']}")
    print(f"  Duration:          {raw_stats['duration_seconds']}s")
    print(f"  Trajectory Length: {raw_stats['path_length_meters']}m")
    print(f"  Raw Loop Drift:    {raw_stats['start_end_displacement_meters']*100:.1f} cm")

    # 2. Keyframe Selection and Local Point Cloud Extraction
    print("\n[2/7] Selecting Registration Keyframes & Computing Local Normal Point Clouds...")
    with LiDARScanLoader(archive_path, scan_id) as loader:
        keyframes = select_registration_keyframes(
            loader,
            min_translation_m=0.80,
            min_rotation_deg=25.0,
            max_frame_gap=160,
            load_point_clouds=True,
            voxel_size_m=0.06,
        )
    print(f"  Keyframe Nodes Extracted: {len(keyframes)}")

    # 3. Odometry Edges & Loop Candidate Detection
    print("\n[3/7] Building Odometry Constraints & Detecting Revisit Candidates...")
    odometry_edges = compute_sequential_odometry_edges(keyframes)
    candidates = detect_loop_candidates(
        keyframes,
        max_proximity_m=1.6,
        min_time_gap_s=18.0,
        min_node_gap=12,
        max_candidates=25,
    )
    export_loop_candidates_json(candidates, out_dir / "loop_candidates.json")
    print(f"  Sequential Edges: {len(odometry_edges)}")
    print(f"  Loop Candidates:  {len(candidates)}")

    # 4. Geometric ICP Registration & Safety Gating
    print("\n[4/7] Performing Point-to-Plane ICP Registration & Quality Gating...")
    node_map = {k.node_id: k for k in keyframes}
    validated_loops = []
    decisions = []

    for cand in candidates:
        node_i = node_map[cand.node_i]
        node_j = node_map[cand.node_j]
        reg_res = register_loop_candidate(node_i, node_j, max_correspondence_distance_m=0.20)
        if reg_res is not None:
            dec = validate_loop_candidate(reg_res)
            decisions.append(dec)
            if dec.status in ("accepted", "uncertain"):
                validated_loops.append((reg_res, dec))

    export_loop_closures_json(decisions, out_dir / "loop_closures.json")
    accepted_count = sum(1 for d in decisions if d.status == "accepted")
    rejected_count = sum(1 for d in decisions if d.status == "rejected")
    print(f"  Accepted Closures: {accepted_count}")
    print(f"  Rejected Closures: {rejected_count}")

    # 5. Global Pose Graph Optimization
    print("\n[5/7] Running Global Pose Graph Optimization (Open3D Levenberg-Marquardt)...")
    opt_result = optimize_pose_graph(
        keyframes=keyframes,
        odometry_edges=odometry_edges,
        validated_loops=validated_loops,
        all_raw_poses=raw_poses_list,
        reference_node=0,
    )
    export_pose_graph_json(
        keyframes=keyframes,
        odometry_edges=odometry_edges,
        validated_loops=validated_loops,
        optimized_matrices=opt_result.optimized_keyframe_poses,
        output_path=out_dir / "pose_graph.json",
    )

    # 6. Drift Ablation Output
    ablation_data = compute_drift_ablation(raw_stats, opt_result, raw_poses_list, opt_result.optimized_frame_poses)
    with open(out_dir / "drift_ablation.json", "w", encoding="utf-8") as f:
        json.dump(ablation_data, f, indent=2)

    loop_pairs = [(reg.node_i, reg.node_j) for reg, dec in validated_loops if dec.status == "accepted"]
    render_drift_ablation_svg(
        keyframes=keyframes,
        opt_matrices=opt_result.optimized_keyframe_poses,
        ablation_data=ablation_data,
        loop_closures=loop_pairs,
        output_path=out_dir / "drift_ablation.svg",
    )
    print(f"  Optimization Status:    {opt_result.optimization_status.upper()}")
    print(f"  Raw Loop Residual:      {opt_result.raw_loop_residual_m:.4f} m")
    print(f"  Corrected Residual:     {opt_result.optimized_loop_residual_m:.4f} m")
    print(f"  Improvement:            {opt_result.improvement_percentage:.1f}%")

    # 7. Drift-Corrected Point Cloud Reconstruction & Multi-Room Geometry
    print("\n[6/7] Fusing Drift-Corrected Point Cloud using Optimized Poses...")
    with LiDARScanLoader(archive_path, scan_id) as loader:
        pts_opt, col_opt, _, fusion_stats = fuse_scan_frames(
            loader=loader,
            frame_stride=frame_stride,
            custom_poses=opt_result.optimized_frame_poses,
            point_subsample_step=3,
        )

    # Convert to Open3D PointCloud and Voxel Downsample
    pcd = o3d.geometry.PointCloud()
    pcd.points = o3d.utility.Vector3dVector(pts_opt.astype(np.float64))
    if len(col_opt) > 0:
        pcd.colors = o3d.utility.Vector3dVector((col_opt / 255.0).astype(np.float64))

    raw_count = len(pcd.points)
    pcd = pcd.voxel_down_sample(voxel_size=0.03)
    down_count = len(pcd.points)

    opt_ply_path = optimized_dir / "optimized_pointcloud.ply"
    o3d.io.write_point_cloud(str(opt_ply_path), pcd)
    print(f"  Corrected Cloud Saved:  {opt_ply_path} ({raw_count:,} -> {down_count:,} points)")

    # 8. Structural Extraction & Room Topology
    print("\n[7/7] Segmenting Multi-Room Geometry & Inferring Adjacency Graph...")
    struct_config = StructuralConfig(
        scan_id=scan_id,
        ply_path=str(opt_ply_path),
        output_dir=str(out_dir / "structure"),
    )
    try:
        struct_res = extract_structure(struct_config)
        struct_json_path = out_dir / "structure" / "structure.json"
        if struct_json_path.exists():
            with open(struct_json_path, "r", encoding="utf-8") as f:
                struct_data = json.load(f)
            wall_planes = struct_data.get("walls", [])
            ceiling_height = struct_data.get("ceiling", {}).get("estimated_clear_height_m") or struct_res.get("estimated_ceiling_height_m")
        else:
            wall_planes = []
            ceiling_height = struct_res.get("estimated_ceiling_height_m", 2.45)
    except Exception as e:
        print(f"  Warning: Structural extraction encountered exception: {e}; falling back to trajectory bounds")
        wall_planes = []
        ceiling_height = 2.45

    # Segment room candidates using structural free-space partitioning
    room_candidates = cluster_trajectory_into_room_regions(raw_poses_list, wall_planes=wall_planes)
    assign_walls_to_rooms(wall_planes, room_candidates)

    rooms: List[Room2D] = []
    for cand in room_candidates:
        assigned_walls = [wall_planes[idx] for idx in cand.wall_indices if idx < len(wall_planes)]
        title = "Hallway Connector" if cand.is_connector else f"Room {cand.room_id.split('_')[-1]}"
        r = build_room_polygon_in_global_frame(
            room_id=cand.room_id,
            name=title,
            associated_wall_planes=assigned_walls,
            centroid_xz=cand.centroid_xz,
            cell_polygon=cand.cell_polygon,
        )
        rooms.append(r)

    # Topological validation & Adjacency Graph
    topo_report = validate_room_topology(rooms)
    connections = build_room_adjacency_graph(rooms)

    prop_output = assemble_property_plan_output(
        scan_id=scan_id,
        rooms=rooms,
        connections=connections,
        drift_status=opt_result.optimization_status,
        residual_m=opt_result.optimized_loop_residual_m,
        ceiling_height_m=ceiling_height,
    )
    export_property_json(prop_output, out_dir / "property.json")
    render_property_debug_svg(
        rooms=rooms,
        connections=connections,
        scan_id=scan_id,
        drift_status=opt_result.optimization_status.upper(),
        output_path=out_dir / "property_debug.svg",
    )

    t_elapsed = time.time() - t_start

    # Format Headless Summary
    connectors_count = sum(1 for r in rooms if "connector" in r.room_id.lower())
    rooms_count = len(rooms) - connectors_count

    summary_text = f"""
PROPERTY RECONSTRUCTION
=======================

Scan: {scan_id}

Pose graph nodes:             {opt_result.node_count}
Loop candidates:              {len(candidates)}
Loop closures accepted:        {accepted_count}
Loop closures rejected:       {rejected_count}

Raw loop residual:          {opt_result.raw_loop_residual_m:.4f} m
Corrected loop residual:    {opt_result.optimized_loop_residual_m:.4f} m

Correction improvement:      {opt_result.improvement_percentage:.1f} %

Rooms detected:                 {rooms_count}
Connectors detected:            {connectors_count}
Adjacency edges:                {len(connections)}
Overlap violations:             {len(topo_report.overlap_violations)}

Optimization status:
{opt_result.optimization_status.upper()}
"""
    print(summary_text)
    print(f"Total Runtime: {t_elapsed:.1f}s")
    print(f"Deliverables exported to: {out_dir}/")

    return {
        "scan_id": scan_id,
        "runtime_s": round(t_elapsed, 2),
        "opt_result": opt_result,
        "rooms": rooms,
        "connections": connections,
        "summary": summary_text,
    }


def main():
    parser = argparse.ArgumentParser(description="Stage 6 Multi-Room Property Reconstruction Pipeline")
    parser.add_argument("--scan", type=str, default="c7d28f72c6", help="Scan ID to reconstruct")
    parser.add_argument("--archive", type=str, default=None, help="Explicit archive path")
    parser.add_argument("--frame-stride", type=int, default=5, help="Frame stride for fusion")
    parser.add_argument("--headless", action="store_true", help="Run in headless reporting mode")
    parser.add_argument("--output-dir", type=str, default=None, help="Destination directory for outputs")
    args = parser.parse_args()

    run_property_reconstruction(
        scan_id=args.scan,
        archive_path=args.archive,
        frame_stride=args.frame_stride,
        headless=args.headless,
        output_dir=args.output_dir,
    )


if __name__ == "__main__":
    main()
