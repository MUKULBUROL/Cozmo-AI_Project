"""Stage 6 Raw Trajectory Analysis & Diagnostics.

1. Why this file exists:
    Analyzes the complete multi-room ARKit camera trajectory, calculates path statistics
    (total path length, 3D bounds, duration), computes raw start-to-end drift, detects
    spatial revisit candidate areas, and renders top-down XZ trajectory diagnostic plots.

2. Pipeline stage:
    Stage 6 — Baseline Trajectory Audit & Drift Diagnostics.

3. Inputs:
    Chronological list of Pose6D records or raw odometry records from LiDAR scan.

4. Outputs:
    Comprehensive trajectory diagnostics dictionary, raw_trajectory.json serialization,
    and vector SVG trajectory plot with start, end, and revisit hotspots.

5. Coordinate conventions:
    Y-axis is upward vertical (gravity opposite).
    XZ-plane is the horizontal building floor plane.
    Positions (x, y, z) in meters.

6. Unit assumptions:
    Distances in meters (m), timestamps in seconds (s), angles in radians/degrees.

7. Important dependencies:
    numpy, math, json, pathlib.

8. What is most likely to break:
    Zero-length trajectories or single-pose sequences causing division by zero or NaN bounds.

9. What a developer should inspect first:
    Verify start_end_displacement against dataset manifest odometry.loop_closure_drift_m.
"""

import json
import math
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import numpy as np

from backend.app.models.capture import Pose6D
from backend.app.pipelines.lidar.transform import pose_to_matrix


def analyze_raw_trajectory(
    poses: List[Pose6D],
    revisit_distance_threshold_m: float = 0.8,
    revisit_min_time_gap_s: float = 20.0,
) -> Dict[str, Any]:
    """Computes comprehensive metric path and drift statistics from camera poses.

    Purpose:
        Quantifies the cumulative physical distance traversed, the bounding box of the
        scanned property, start/end endpoint separation, and discovers physical locations
        revisited after significant temporal separation.

    Parameters:
        poses: Chronological list of Pose6D camera poses.
        revisit_distance_threshold_m: Maximum Euclidean distance in meters to consider two poses as revisited.
        revisit_min_time_gap_s: Minimum elapsed time in seconds between poses to qualify as a non-trivial revisit.

    Returns:
        Dictionary containing:
            total_poses: Integer count of poses.
            duration_seconds: Elapsed capture time.
            path_length_meters: Cumulative 3D path length.
            start_position: [x, y, z] of initial pose.
            end_position: [x, y, z] of final pose.
            start_end_displacement_meters: Net Euclidean distance between start and end.
            bounds_meters: Min/max coordinates across X, Y, Z.
            revisit_clusters: List of identified spatio-temporal revisit pairs.

    Coordinate/Unit assumptions:
        Y is vertical; X and Z are horizontal. Metric units in meters.

    Expected preconditions:
        poses list must contain at least 2 chronological Pose6D instances.

    Important failure cases:
        Fails with ValueError if poses list has fewer than 2 poses.
        Empty or corrupted coordinate entries yield NaN or Inf.

    Useful debugging clues:
        Inspect start_end_displacement_meters; for a closed-loop capture, this represents
        the uncorrected raw odometry loop drift.
    """
    if len(poses) < 2:
        raise ValueError(f"At least 2 poses required for trajectory analysis, received {len(poses)}")

    positions = np.array([[p.x, p.y, p.z] for p in poses], dtype=np.float64)
    timestamps = np.array([p.timestamp for p in poses], dtype=np.float64)
    frame_indices = np.array([p.frame_index for p in poses], dtype=np.int64)

    # Path length calculation via consecutive Euclidean segments
    deltas = np.diff(positions, axis=0)
    segment_lengths = np.linalg.norm(deltas, axis=1)
    total_path_length = float(np.sum(segment_lengths))

    duration_s = float(timestamps[-1] - timestamps[0])
    start_pos = positions[0].tolist()
    end_pos = positions[-1].tolist()
    start_end_displacement = float(np.linalg.norm(positions[-1] - positions[0]))

    # Compute orientation change between start and end (quaternion dot product)
    q_start = np.array([poses[0].qx, poses[0].qy, poses[0].qz, poses[0].qw])
    q_end = np.array([poses[-1].qx, poses[-1].qy, poses[-1].qz, poses[-1].qw])
    dot = np.clip(np.abs(np.dot(q_start, q_end)), 0.0, 1.0)
    angular_diff_deg = float(np.degrees(2.0 * np.arccos(dot)))

    min_bounds = np.min(positions, axis=0).tolist()
    max_bounds = np.max(positions, axis=0).tolist()

    # Revisit detection using sampled positions for computational efficiency
    sample_stride = max(1, len(poses) // 400)
    sampled_indices = np.arange(0, len(poses), sample_stride)
    sampled_pos = positions[sampled_indices]
    sampled_times = timestamps[sampled_indices]
    sampled_frames = frame_indices[sampled_indices]

    revisit_pairs: List[Dict[str, Any]] = []
    n_sampled = len(sampled_indices)
    for i in range(n_sampled):
        for j in range(i + 1, n_sampled):
            dt = sampled_times[j] - sampled_times[i]
            if dt < revisit_min_time_gap_s:
                continue
            dist = float(np.linalg.norm(sampled_pos[i] - sampled_pos[j]))
            if dist <= revisit_distance_threshold_m:
                revisit_pairs.append({
                    "frame_a": int(sampled_frames[i]),
                    "frame_b": int(sampled_frames[j]),
                    "time_a_s": round(float(sampled_times[i]), 2),
                    "time_b_s": round(float(sampled_times[j]), 2),
                    "time_delta_s": round(float(dt), 2),
                    "distance_meters": round(dist, 4),
                    "position_a": sampled_pos[i].tolist(),
                    "position_b": sampled_pos[j].tolist(),
                })

    return {
        "total_poses": len(poses),
        "duration_seconds": round(duration_s, 2),
        "path_length_meters": round(total_path_length, 4),
        "start_position": [round(c, 4) for c in start_pos],
        "end_position": [round(c, 4) for c in end_pos],
        "start_end_displacement_meters": round(start_end_displacement, 4),
        "start_end_angular_diff_degrees": round(angular_diff_deg, 2),
        "bounds_meters": {
            "min_x": round(min_bounds[0], 4),
            "max_x": round(max_bounds[0], 4),
            "min_y": round(min_bounds[1], 4),
            "max_y": round(max_bounds[1], 4),
            "min_z": round(min_bounds[2], 4),
            "max_z": round(max_bounds[2], 4),
            "span_x": round(max_bounds[0] - min_bounds[0], 4),
            "span_z": round(max_bounds[2] - min_bounds[2], 4),
        },
        "revisit_count": len(revisit_pairs),
        "revisit_samples": revisit_pairs[:30],
    }


def export_raw_trajectory_json(
    trajectory_stats: Dict[str, Any],
    poses: List[Pose6D],
    output_path: Path,
    sample_stride: int = 10,
) -> None:
    """Serializes the trajectory statistics and sampled pose coordinates to JSON.

    Purpose:
        Creates a reproducible, machine-readable artifact of the raw camera path
        prior to drift correction.

    Parameters:
        trajectory_stats: Dictionary produced by analyze_raw_trajectory.
        poses: Chronological list of Pose6D camera poses.
        output_path: File destination Path object.
        sample_stride: Stride for exporting downsampled pose coordinates.

    Returns:
        None.

    Coordinate/Unit assumptions:
        Positions in meters, timestamps in seconds.

    Expected preconditions:
        output_path directory must be writable.

    Important failure cases:
        PermissionError if output path is protected; OSError on disk failure.

    Useful debugging clues:
        Inspect the exported JSON file to confirm bounds and start/end coordinates.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    sampled_poses = []
    for i in range(0, len(poses), sample_stride):
        p = poses[i]
        sampled_poses.append({
            "frame": p.frame_index,
            "timestamp": round(p.timestamp, 3),
            "position": [round(p.x, 4), round(p.y, 4), round(p.z, 4)],
            "quaternion": [round(p.qx, 5), round(p.qy, 5), round(p.qz, 5), round(p.qw, 5)],
        })

    payload = {
        "metadata": {
            "coordinate_frame": "ARKit Y-up, right-handed (XZ horizontal)",
            "unit": "meters",
        },
        "statistics": trajectory_stats,
        "sampled_poses_stride": sample_stride,
        "sampled_poses": sampled_poses,
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def render_trajectory_svg(
    poses: List[Pose6D],
    revisits: Optional[List[Dict[str, Any]]] = None,
    output_path: Optional[Path] = None,
    width_px: int = 1000,
    height_px: int = 800,
    margin_px: int = 60,
) -> str:
    """Renders a top-down 2D horizontal floor plane (XZ) vector SVG diagram.

    Purpose:
        Provides immediate visual confirmation of the multi-room trajectory shape,
        start position, end position, loop drift gap, and revisit locations.

    Parameters:
        poses: Chronological list of Pose6D camera poses.
        revisits: Optional list of revisit candidate pairs to highlight with connection lines.
        output_path: Optional file Path to save the SVG.
        width_px: Width of output SVG in pixels.
        height_px: Height of output SVG in pixels.
        margin_px: Margin in pixels around plotted bounds.

    Returns:
        String containing the complete SVG markup.

    Coordinate/Unit assumptions:
        World X maps to SVG horizontal axis.
        World Z maps to SVG vertical axis.
        Units in meters scaled to pixels.

    Expected preconditions:
        poses list must have valid, finite x and z coordinates.

    Important failure cases:
        Zero span across X or Z results in uniform coordinate mapping.

    Useful debugging clues:
        Inspect the red dotted line connecting the start (green circle) and end (red circle);
        its length visually corresponds to accumulated odometry loop drift.
    """
    x_coords = np.array([p.x for p in poses], dtype=np.float64)
    z_coords = np.array([p.z for p in poses], dtype=np.float64)

    min_x, max_x = float(np.min(x_coords)), float(np.max(x_coords))
    min_z, max_z = float(np.min(z_coords)), float(np.max(z_coords))

    span_x = max(max_x - min_x, 0.5)
    span_z = max(max_z - min_z, 0.5)

    usable_w = width_px - 2 * margin_px
    usable_h = height_px - 2 * margin_px
    scale = min(usable_w / span_x, usable_h / span_z)

    offset_x = margin_px + (usable_w - span_x * scale) / 2.0
    offset_z = margin_px + (usable_h - span_z * scale) / 2.0

    def world_to_svg(wx: float, wz: float) -> Tuple[float, float]:
        sx = offset_x + (wx - min_x) * scale
        sz = offset_z + (wz - min_z) * scale
        return sx, sz

    # Build polyline points (subsampled for SVG size efficiency)
    step = max(1, len(poses) // 600)
    svg_points = []
    for i in range(0, len(poses), step):
        sx, sz = world_to_svg(poses[i].x, poses[i].z)
        svg_points.append(f"{sx:.1f},{sz:.1f}")
    # Always include last pose
    sx, sz = world_to_svg(poses[-1].x, poses[-1].z)
    svg_points.append(f"{sx:.1f},{sz:.1f}")
    polyline_data = " ".join(svg_points)

    start_sx, start_sz = world_to_svg(poses[0].x, poses[0].z)
    end_sx, end_sz = world_to_svg(poses[-1].x, poses[-1].z)
    drift_m = math.sqrt((poses[-1].x - poses[0].x)**2 + (poses[-1].z - poses[0].z)**2)

    svg_lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width_px} {height_px}" '
        f'width="{width_px}" height="{height_px}" style="background-color: #0f172a; font-family: sans-serif;">',
        '  <defs>',
        '    <linearGradient id="trajGrad" x1="0%" y1="0%" x2="100%" y2="100%">',
        '      <stop offset="0%" stop-color="#38bdf8"/>',
        '      <stop offset="50%" stop-color="#818cf8"/>',
        '      <stop offset="100%" stop-color="#c084fc"/>',
        '    </linearGradient>',
        '  </defs>',
        f'  <text x="24" y="38" fill="#f8fafc" font-size="18" font-weight="bold">ARKit Raw Trajectory (Top-down XZ)</text>',
        f'  <text x="24" y="60" fill="#94a3b8" font-size="13">Span: {span_x:.2f}m x {span_z:.2f}m | Total Path: {len(poses)} frames | Net Drift Gap: {drift_m*100:.1f} cm</text>',
    ]

    # Grid lines
    grid_step_m = 2.0
    g_x = math.floor(min_x / grid_step_m) * grid_step_m
    while g_x <= max_x:
        gx_pix, _ = world_to_svg(g_x, min_z)
        svg_lines.append(f'  <line x1="{gx_pix:.1f}" y1="{margin_px}" x2="{gx_pix:.1f}" y2="{height_px - margin_px}" stroke="#1e293b" stroke-width="1"/>')
        g_x += grid_step_m

    g_z = math.floor(min_z / grid_step_m) * grid_step_m
    while g_z <= max_z:
        _, gz_pix = world_to_svg(min_x, g_z)
        svg_lines.append(f'  <line x1="{margin_px}" y1="{gz_pix:.1f}" x2="{width_px - margin_px}" y2="{gz_pix:.1f}" stroke="#1e293b" stroke-width="1"/>')
        g_z += grid_step_m

    # Revisit lines if provided
    if revisits:
        for rev in revisits[:15]:
            rx1, rz1 = world_to_svg(rev["position_a"][0], rev["position_a"][2])
            rx2, rz2 = world_to_svg(rev["position_b"][0], rev["position_b"][2])
            svg_lines.append(f'  <line x1="{rx1:.1f}" y1="{rz1:.1f}" x2="{rx2:.1f}" y2="{rz2:.1f}" stroke="#fbbf24" stroke-width="1.5" stroke-dasharray="3,3" opacity="0.6"/>')

    # Trajectory path
    svg_lines.append(f'  <polyline points="{polyline_data}" fill="none" stroke="url(#trajGrad)" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>')

    # Start-to-end drift gap line
    svg_lines.append(f'  <line x1="{start_sx:.1f}" y1="{start_sz:.1f}" x2="{end_sx:.1f}" y2="{end_sz:.1f}" stroke="#f43f5e" stroke-width="2.5" stroke-dasharray="4,4"/>')

    # Start marker
    svg_lines.append(f'  <circle cx="{start_sx:.1f}" cy="{start_sz:.1f}" r="8" fill="#10b981" stroke="#ffffff" stroke-width="2"/>')
    svg_lines.append(f'  <text x="{start_sx + 12:.1f}" y="{start_sz + 4:.1f}" fill="#10b981" font-size="12" font-weight="bold">START (t=0s)</text>')

    # End marker
    svg_lines.append(f'  <circle cx="{end_sx:.1f}" cy="{end_sz:.1f}" r="8" fill="#ef4444" stroke="#ffffff" stroke-width="2"/>')
    svg_lines.append(f'  <text x="{end_sx + 12:.1f}" y="{end_sz + 4:.1f}" fill="#ef4444" font-size="12" font-weight="bold">END (drift: {drift_m*100:.1f} cm)</text>')

    svg_lines.append('</svg>')
    svg_markup = "\n".join(svg_lines)

    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(svg_markup)

    return svg_markup
