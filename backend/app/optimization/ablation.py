"""Stage 6 Drift Correction Ablation & Visualization.

1. Why this file exists:
    Generates quantitative and visual proof of the impact of drift correction
    comparing DRIFT CORRECTION OFF (raw ARKit odometry) vs DRIFT CORRECTION ON
    (pose graph optimized), exporting drift_ablation.json and drift_ablation.svg.

2. Pipeline stage:
    Stage 6 — Drift Ablation Deliverable.

3. Inputs:
    Raw trajectory metrics, optimized trajectory metrics, loop closure residuals, and keyframe poses.

4. Outputs:
    Machine-readable drift_ablation.json and publication-quality vector drift_ablation.svg.

5. Coordinate conventions:
    Top-down XZ horizontal ground plane projection. Units in meters.

6. Unit assumptions:
    Distances in meters (m), percentages in %, residuals in meters.

7. Important dependencies:
    json, math, pathlib, numpy, backend.app.optimization.

8. What is most likely to break:
    Zero raw residual causing division by zero when calculating percentage improvement.

9. What a developer should inspect first:
    Verify raw_metric vs optimized_metric in drift_ablation.json.
"""

import json
import math
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import numpy as np

from backend.app.models.capture import Pose6D
from backend.app.optimization.keyframes import KeyframeNode
from backend.app.optimization.pose_graph import PoseGraphOptimizationResult


def compute_drift_ablation(
    raw_stats: Dict[str, Any],
    opt_result: PoseGraphOptimizationResult,
    raw_poses: List[Pose6D],
    opt_poses: Dict[int, Pose6D],
) -> Dict[str, Any]:
    """Assembles the quantitative before/after drift correction ablation dictionary.

    Purpose:
        Produces rigorous metric evidence comparing uncorrected vs corrected states.

    Parameters:
        raw_stats: Trajectory statistics dictionary from analyze_raw_trajectory.
        opt_result: PoseGraphOptimizationResult from optimize_pose_graph.
        raw_poses: List of raw Pose6D objects.
        opt_poses: Mapping of frame_id to optimized Pose6D objects.

    Returns:
        Dictionary structured for drift_ablation.json.

    Assumptions:
        raw_poses and opt_poses share the same frame indices.

    Failure conditions:
        Missing frames in opt_poses fall back to raw poses.

    Debugging:
        Inspect start_to_end_drift for off vs on.
    """
    first_frame = raw_poses[0].frame_index
    last_frame = raw_poses[-1].frame_index

    # Raw start and end
    p0_raw = np.array([raw_poses[0].x, raw_poses[0].y, raw_poses[0].z])
    p1_raw = np.array([raw_poses[-1].x, raw_poses[-1].y, raw_poses[-1].z])
    raw_endpoint_gap = float(np.linalg.norm(p1_raw - p0_raw))

    # Optimized start and end
    opt_p0 = opt_poses.get(first_frame, raw_poses[0])
    opt_p1 = opt_poses.get(last_frame, raw_poses[-1])
    p0_opt = np.array([opt_p0.x, opt_p0.y, opt_p0.z])
    p1_opt = np.array([opt_p1.x, opt_p1.y, opt_p1.z])
    opt_endpoint_gap = float(np.linalg.norm(p1_opt - p0_opt))

    # Calculate gap reduction
    gap_reduction_m = raw_endpoint_gap - opt_endpoint_gap
    gap_improvement_pct = (gap_reduction_m / max(raw_endpoint_gap, 1e-4)) * 100.0

    return {
        "ablation_title": "Stage 6 Trajectory Drift Correction Ablation",
        "evaluation": {
            "status": opt_result.optimization_status,
            "safety_gate_passed": opt_result.safety_gate_passed,
        },
        "metrics": {
            "drift_correction_off": {
                "description": "Raw ARKit VIO odometry without loop closure or pose graph optimization",
                "loop_closure_residual_meters": opt_result.raw_loop_residual_m,
                "start_end_displacement_meters": round(raw_endpoint_gap, 4),
                "total_path_length_meters": raw_stats.get("path_length_meters", 0.0),
            },
            "drift_correction_on": {
                "description": "Global Open3D PoseGraph optimization with ICP point-to-plane loop closures",
                "loop_closure_residual_meters": opt_result.optimized_loop_residual_m,
                "start_end_displacement_meters": round(opt_endpoint_gap, 4),
                "residual_reduction_meters": round(opt_result.raw_loop_residual_m - opt_result.optimized_loop_residual_m, 4),
                "residual_improvement_percentage": opt_result.improvement_percentage,
                "endpoint_gap_reduction_meters": round(gap_reduction_m, 4),
                "endpoint_gap_improvement_percentage": round(gap_improvement_pct, 1),
            },
        },
        "graph_statistics": {
            "keyframe_nodes": opt_result.node_count,
            "odometry_edges": opt_result.odometry_edge_count,
            "accepted_loop_edges": opt_result.loop_edge_count,
        },
    }


def render_drift_ablation_svg(
    keyframes: List[KeyframeNode],
    opt_matrices: Dict[int, np.ndarray],
    ablation_data: Dict[str, Any],
    loop_closures: Optional[List[Tuple[int, int]]] = None,
    output_path: Optional[Path] = None,
    width_px: int = 1200,
    height_px: int = 850,
    margin_px: int = 70,
) -> str:
    """Renders a comprehensive side-by-side or overlaid top-down XZ comparison SVG.

    Purpose:
        Visualizes the raw drift trajectory vs the corrected trajectory with loop closures,
        providing clear graphical proof of loop closure and gap elimination.

    Parameters:
        keyframes: List of KeyframeNode objects.
        opt_matrices: Mapping of node_id -> 4x4 optimized matrix.
        ablation_data: Dictionary produced by compute_drift_ablation.
        loop_closures: List of (node_i, node_j) accepted loop edges.
        output_path: Optional destination Path for SVG.
        width_px: Width in pixels.
        height_px: Height in pixels.
        margin_px: Margin in pixels.

    Returns:
        Complete SVG markup string.

    Assumptions:
        Coordinates are metric in meters.

    Failure conditions:
        Fewer than 2 keyframes creates minimal SVG.

    Debugging:
        Inspect overlay: Raw is orange/red dashed line, Optimized is cyan solid line.
    """
    raw_pts = [k.matrix[:3, 3] for k in keyframes]
    opt_pts = [opt_matrices.get(k.node_id, k.matrix)[:3, 3] for k in keyframes]

    all_x = [p[0] for p in raw_pts] + [p[0] for p in opt_pts]
    all_z = [p[2] for p in raw_pts] + [p[2] for p in opt_pts]

    min_x, max_x = min(all_x), max(all_x)
    min_z, max_z = min(all_z), max(all_z)

    span_x = max(max_x - min_x, 0.5)
    span_z = max(max_z - min_z, 0.5)

    usable_w = width_px - 2 * margin_px
    usable_h = height_px - 2 * margin_px - 140  # reserve space for metric header
    scale = min(usable_w / span_x, usable_h / span_z)

    offset_x = margin_px + (usable_w - span_x * scale) / 2.0
    offset_z = margin_px + 120 + (usable_h - span_z * scale) / 2.0

    def to_svg(x: float, z: float) -> Tuple[float, float]:
        return offset_x + (x - min_x) * scale, offset_z + (z - min_z) * scale

    # Build raw polyline points
    raw_svg_pts = " ".join(f"{to_svg(p[0], p[2])[0]:.1f},{to_svg(p[0], p[2])[1]:.1f}" for p in raw_pts)
    # Build opt polyline points
    opt_svg_pts = " ".join(f"{to_svg(p[0], p[2])[0]:.1f},{to_svg(p[0], p[2])[1]:.1f}" for p in opt_pts)

    m = ablation_data.get("metrics", {})
    m_off = m.get("drift_correction_off", {})
    m_on = m.get("drift_correction_on", {})

    raw_res = m_off.get("loop_closure_residual_meters", 0.0)
    opt_res = m_on.get("loop_closure_residual_meters", 0.0)
    raw_gap = m_off.get("start_end_displacement_meters", 0.0)
    opt_gap = m_on.get("start_end_displacement_meters", 0.0)
    pct_imp = m_on.get("residual_improvement_percentage", 0.0)
    status = ablation_data.get("evaluation", {}).get("status", "UNKNOWN").upper()

    svg_lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width_px} {height_px}" '
        f'width="{width_px}" height="{height_px}" style="background-color: #0b0f19; font-family: ui-sans-serif, system-ui, sans-serif;">',
        '  <defs>',
        '    <linearGradient id="rawGrad" x1="0%" y1="0%" x2="100%" y2="100%">',
        '      <stop offset="0%" stop-color="#f43f5e" stop-opacity="0.8"/>',
        '      <stop offset="100%" stop-color="#fb923c" stop-opacity="0.8"/>',
        '    </linearGradient>',
        '    <linearGradient id="optGrad" x1="0%" y1="0%" x2="100%" y2="100%">',
        '      <stop offset="0%" stop-color="#06b6d4"/>',
        '      <stop offset="100%" stop-color="#3b82f6"/>',
        '    </linearGradient>',
        '  </defs>',
        # Header banner
        f'  <rect x="24" y="20" width="{width_px - 48}" height="100" rx="10" fill="#111827" stroke="#1f2937" stroke-width="1.5"/>',
        '  <text x="44" y="52" fill="#f8fafc" font-size="20" font-weight="bold">DRIFT CORRECTION ABLATION (OFF vs ON)</text>',
        f'  <text x="44" y="76" fill="#94a3b8" font-size="13">Status: <tspan fill="#10b981" font-weight="bold">{status}</tspan> | Residual Improvement: <tspan fill="#38bdf8" font-weight="bold">{pct_imp:.1f}%</tspan> | Keyframe Nodes: {len(keyframes)}</text>',
        # Comparative summary cards inside header
        f'  <rect x="{width_px - 460}" y="32" width="200" height="74" rx="6" fill="#1f2937" stroke="#ef4444" stroke-width="1"/>',
        f'  <text x="{width_px - 448}" y="52" fill="#fca5a5" font-size="11" font-weight="bold">CORRECTION OFF (RAW)</text>',
        f'  <text x="{width_px - 448}" y="72" fill="#f8fafc" font-size="13">Loop Res: {raw_res*100:.1f} cm</text>',
        f'  <text x="{width_px - 448}" y="92" fill="#94a3b8" font-size="12">End Gap: {raw_gap*100:.1f} cm</text>',

        f'  <rect x="{width_px - 240}" y="32" width="200" height="74" rx="6" fill="#1f2937" stroke="#06b6d4" stroke-width="1.5"/>',
        f'  <text x="{width_px - 228}" y="52" fill="#67e8f9" font-size="11" font-weight="bold">CORRECTION ON (OPTIMIZED)</text>',
        f'  <text x="{width_px - 228}" y="72" fill="#f8fafc" font-size="13">Loop Res: {opt_res*100:.1f} cm</text>',
        f'  <text x="{width_px - 228}" y="92" fill="#38bdf8" font-size="12">End Gap: {opt_gap*100:.1f} cm</text>',
    ]

    # Trajectory overlay
    # Raw trajectory path (dashed orange/red)
    svg_lines.append(f'  <polyline points="{raw_svg_pts}" fill="none" stroke="url(#rawGrad)" stroke-width="2.5" stroke-dasharray="5,4" opacity="0.85"/>')

    # Optimized trajectory path (solid blue/cyan)
    svg_lines.append(f'  <polyline points="{opt_svg_pts}" fill="none" stroke="url(#optGrad)" stroke-width="3.5" stroke-linecap="round" stroke-linejoin="round"/>')

    # Draw loop closure edge links if provided
    if loop_closures:
        for i_idx, j_idx in loop_closures:
            if i_idx < len(keyframes) and j_idx < len(keyframes):
                p_i = opt_pts[i_idx]
                p_j = opt_pts[j_idx]
                sx_i, sz_i = to_svg(p_i[0], p_i[2])
                sx_j, sz_j = to_svg(p_j[0], p_j[2])
                svg_lines.append(f'  <line x1="{sx_i:.1f}" y1="{sz_i:.1f}" x2="{sx_j:.1f}" y2="{sz_j:.1f}" stroke="#eab308" stroke-width="2" stroke-dasharray="3,3"/>')
                svg_lines.append(f'  <circle cx="{sx_i:.1f}" cy="{sz_i:.1f}" r="4" fill="#eab308"/>')
                svg_lines.append(f'  <circle cx="{sx_j:.1f}" cy="{sz_j:.1f}" r="4" fill="#eab308"/>')

    # Start and End Markers
    s_raw_x, s_raw_z = to_svg(raw_pts[0][0], raw_pts[0][2])
    e_raw_x, e_raw_z = to_svg(raw_pts[-1][0], raw_pts[-1][2])
    e_opt_x, e_opt_z = to_svg(opt_pts[-1][0], opt_pts[-1][2])

    svg_lines.append(f'  <circle cx="{s_raw_x:.1f}" cy="{s_raw_z:.1f}" r="7" fill="#10b981" stroke="#ffffff" stroke-width="2"/>')
    svg_lines.append(f'  <text x="{s_raw_x + 10:.1f}" y="{s_raw_z + 4:.1f}" fill="#10b981" font-size="12" font-weight="bold">START (t=0s)</text>')

    svg_lines.append(f'  <circle cx="{e_raw_x:.1f}" cy="{e_raw_z:.1f}" r="7" fill="#ef4444" stroke="#ffffff" stroke-width="2"/>')
    svg_lines.append(f'  <text x="{e_raw_x + 10:.1f}" y="{e_raw_z + 4:.1f}" fill="#ef4444" font-size="11">RAW END (Drift: {raw_gap*100:.1f}cm)</text>')

    svg_lines.append(f'  <circle cx="{e_opt_x:.1f}" cy="{e_opt_z:.1f}" r="7" fill="#06b6d4" stroke="#ffffff" stroke-width="2"/>')
    svg_lines.append(f'  <text x="{e_opt_x + 10:.1f}" y="{e_opt_z + 18:.1f}" fill="#06b6d4" font-size="11" font-weight="bold">CORRECTED END</text>')

    # Legend
    legend_y = height_px - 35
    svg_lines.append(f'  <line x1="44" y1="{legend_y}" x2="84" y2="{legend_y}" stroke="#ef4444" stroke-width="2.5" stroke-dasharray="5,4"/>')
    svg_lines.append(f'  <text x="92" y="{legend_y + 4}" fill="#94a3b8" font-size="12">Raw Odometry (Drift OFF)</text>')

    svg_lines.append(f'  <line x1="260" y1="{legend_y}" x2="300" y2="{legend_y}" stroke="#06b6d4" stroke-width="3"/>')
    svg_lines.append(f'  <text x="308" y="{legend_y + 4}" fill="#94a3b8" font-size="12">Optimized Trajectory (Drift ON)</text>')

    svg_lines.append(f'  <line x1="510" y1="{legend_y}" x2="550" y2="{legend_y}" stroke="#eab308" stroke-width="2" stroke-dasharray="3,3"/>')
    svg_lines.append(f'  <text x="558" y="{legend_y + 4}" fill="#94a3b8" font-size="12">Accepted Loop Closure Constraint</text>')

    svg_lines.append('</svg>')
    svg_markup = "\n".join(svg_lines)

    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(svg_markup)

    return svg_markup
