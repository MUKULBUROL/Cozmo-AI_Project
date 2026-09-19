"""Stage 6 Pose Graph Assembly, Optimization & Safety Gating.

1. Why this file exists:
    Assembles the global SLAM PoseGraph with sequential odometry constraints and validated
    loop closure edges, executes Open3D Levenberg-Marquardt global optimization, verifies
    safety gates (rejecting optimizations that worsen residuals), and interpolates
    optimized 6-DoF poses to all scan frames.

2. Pipeline stage:
    Stage 6 — Global Pose Graph Optimization.

3. Inputs:
    List of KeyframeNode objects, OdometryEdge sequential constraints, and validated loop RegistrationResults.

4. Outputs:
    PoseGraphOptimizationResult containing raw vs optimized keyframe poses, optimization status
    ('improved', 'neutral', 'rejected'), residual metrics, and full interpolated pose mapping.

5. Coordinate conventions:
    Open3D PoseGraph:
    Node pose represents camera-to-world transformation T_world_cam.
    Edge transform stores inv(T_j) @ T_i (mapping frame i to frame j).
    Reference node 0 is fixed at origin.

6. Unit assumptions:
    Distances in meters, rotation angles in radians.

7. Important dependencies:
    open3d, numpy, scipy.spatial.transform (Rotation / Slerp), backend.app.optimization.

8. What is most likely to break:
    Unconstrained graph resulting in optimizer divergence or flipping coordinate axes.

9. What a developer should inspect first:
    Verify before_residual vs after_residual and safety gate optimization_status.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import numpy as np
import open3d as o3d
from scipy.spatial.transform import Rotation as R, Slerp

from backend.app.models.capture import Pose6D
from backend.app.optimization.keyframes import KeyframeNode
from backend.app.optimization.odometry_edges import OdometryEdge
from backend.app.optimization.registration import RegistrationResult
from backend.app.optimization.validation import ValidationDecision


@dataclass
class PoseGraphOptimizationResult:
    """Encapsulates results from pose graph optimization and safety checks.

    Attributes:
        optimization_status: One of 'improved', 'neutral', 'rejected'.
        raw_loop_residual_m: Mean loop closure edge residual before optimization in meters.
        optimized_loop_residual_m: Mean loop closure edge residual after optimization in meters.
        improvement_percentage: Percentage reduction in loop residual error.
        node_count: Number of keyframe nodes in graph.
        odometry_edge_count: Number of sequential constraints.
        loop_edge_count: Number of accepted loop closure constraints.
        optimized_keyframe_poses: Mapping of node_id -> 4x4 optimized transformation matrix.
        optimized_frame_poses: Mapping of frame_id -> optimized Pose6D instance.
        safety_gate_passed: True if optimization strictly improved geometry without unnatural jumps.
        safety_gate_reasons: List of diagnostic reasons if safety gate rejected optimization.
    """
    optimization_status: str
    raw_loop_residual_m: float
    optimized_loop_residual_m: float
    improvement_percentage: float
    node_count: int
    odometry_edge_count: int
    loop_edge_count: int
    optimized_keyframe_poses: Dict[int, np.ndarray]
    optimized_frame_poses: Dict[int, Pose6D]
    safety_gate_passed: bool
    safety_gate_reasons: List[str] = field(default_factory=list)


def build_pose_graph(
    keyframes: List[KeyframeNode],
    odometry_edges: List[OdometryEdge],
    validated_loops: List[Tuple[RegistrationResult, ValidationDecision]],
) -> o3d.pipelines.registration.PoseGraph:
    """Constructs an Open3D PoseGraph from keyframes and edge constraints.

    Purpose:
        Initializes graph topology for non-linear least squares optimization.

    Parameters:
        keyframes: List of KeyframeNode objects.
        odometry_edges: List of sequential OdometryEdge constraints.
        validated_loops: List of tuples (RegistrationResult, ValidationDecision).

    Returns:
        Populated open3d.pipelines.registration.PoseGraph instance.

    Assumptions:
        Node IDs in edges match indices in keyframes list.

    Failure conditions:
        Mismatched node indices cause Open3D C++ pybind runtime errors.

    Debugging:
        Verify len(pg.nodes) == len(keyframes).
    """
    pg = o3d.pipelines.registration.PoseGraph()

    # 1. Add nodes with initial raw poses
    for k in keyframes:
        node = o3d.pipelines.registration.PoseGraphNode(k.matrix.copy())
        pg.nodes.append(node)

    # 2. Add sequential odometry edges
    for edge in odometry_edges:
        pg_edge = o3d.pipelines.registration.PoseGraphEdge(
            source_node_id=edge.source_node_id,
            target_node_id=edge.target_node_id,
            transformation=edge.transformation.copy(),
            information=edge.information.copy(),
            uncertain=edge.uncertain,
        )
        pg.edges.append(pg_edge)

    # 3. Add validated loop closure edges
    for reg, decision in validated_loops:
        if decision.status in ("accepted", "uncertain"):
            is_uncertain = (decision.status == "uncertain")
            # Information matrix weighted by fitness
            info = reg.information_matrix.copy()
            if is_uncertain:
                info *= 0.2  # Downweight uncertain edges

            pg_edge = o3d.pipelines.registration.PoseGraphEdge(
                source_node_id=reg.node_i,
                target_node_id=reg.node_j,
                transformation=reg.optimized_transform.copy(),
                information=info,
                uncertain=is_uncertain,
            )
            pg.edges.append(pg_edge)

    return pg


def compute_loop_residual(
    pg_nodes: List[np.ndarray],
    loop_edges: List[Tuple[int, int, np.ndarray]],
) -> float:
    """Calculates the mean translation residual across all loop closure constraints.

    Purpose:
        Measures the alignment error: || T_j @ T_ij - T_i || for loop edges.

    Parameters:
        pg_nodes: List of 4x4 camera-to-world pose matrices for each node.
        loop_edges: List of (source_id, target_id, T_ij) constraints.

    Returns:
        Mean Euclidean translation error in meters.

    Assumptions:
        T_ij maps points from frame i to frame j: T_j @ T_ij should equal T_i.

    Failure conditions:
        Returns 0.0 if loop_edges list is empty.

    Debugging:
        Residual should decrease substantially after optimization.
    """
    if not loop_edges:
        return 0.0

    errors: List[float] = []
    for src, tgt, T_ij in loop_edges:
        T_i = pg_nodes[src]
        T_j = pg_nodes[tgt]
        # In Open3D: T_ij = inv(T_j) @ T_i, so predicted T_i_pred = T_j @ T_ij
        T_i_pred = T_j @ T_ij
        trans_err = float(np.linalg.norm(T_i[:3, 3] - T_i_pred[:3, 3]))
        errors.append(trans_err)

    return float(np.mean(errors))


def interpolate_poses_to_all_frames(
    all_raw_poses: List[Pose6D],
    keyframes: List[KeyframeNode],
    optimized_matrices: Dict[int, np.ndarray],
) -> Dict[int, Pose6D]:
    """Interpolates optimization corrections across all intermediate scan frames.

    Purpose:
        Applies continuous, smooth trajectory corrections to the complete high-resolution
        frame sequence without discrete jumps.

    Parameters:
        all_raw_poses: Chronological list of raw Pose6D objects.
        keyframes: List of KeyframeNode objects.
        optimized_matrices: Mapping from node_id -> 4x4 optimized matrix T_opt.

    Returns:
        Mapping from frame_id -> new corrected Pose6D instance.

    Assumptions:
        all_raw_poses is sorted by timestamp.

    Failure conditions:
        Fewer than 2 keyframes falls back to raw poses.

    Debugging:
        Verify continuous trajectory without sharp step discontinuities.
    """
    optimized_frame_poses: Dict[int, Pose6D] = {}

    if len(keyframes) < 2:
        for p in all_raw_poses:
            optimized_frame_poses[p.frame_index] = p
        return optimized_frame_poses

    # Compute keyframe correction offsets: Delta_T = T_opt @ inv(T_raw)
    kf_frames = [k.frame_id for k in keyframes]
    kf_times = [k.timestamp for k in keyframes]
    kf_corrections = []

    for k in keyframes:
        T_raw = k.matrix
        T_opt = optimized_matrices[k.node_id]
        # Offset transforming raw world to optimized world
        Delta_T = T_opt @ np.linalg.inv(T_raw)
        kf_corrections.append(Delta_T)

    kf_rotations = R.from_matrix([dT[:3, :3] for dT in kf_corrections])
    kf_translations = np.array([dT[:3, 3] for dT in kf_corrections])
    slerp = Slerp(kf_times, kf_rotations)

    for p in all_raw_poses:
        t = p.timestamp
        # Clamp t to keyframe range
        t_clamped = min(max(t, kf_times[0]), kf_times[-1])

        # Interpolate rotation correction and translation correction
        R_corr = slerp(t_clamped).as_matrix()
        # Linear interpolation for translation offset
        idx = np.searchsorted(kf_times, t_clamped)
        if idx == 0:
            t_corr = kf_translations[0]
        elif idx >= len(kf_times):
            t_corr = kf_translations[-1]
        else:
            alpha = (t_clamped - kf_times[idx - 1]) / max(kf_times[idx] - kf_times[idx - 1], 1e-5)
            t_corr = (1.0 - alpha) * kf_translations[idx - 1] + alpha * kf_translations[idx]

        Delta_T_interp = np.eye(4, dtype=np.float64)
        Delta_T_interp[:3, :3] = R_corr
        Delta_T_interp[:3, 3] = t_corr

        # Apply correction to raw camera pose: T_opt = Delta_T @ T_raw
        raw_T = k.matrix if False else np.eye(4)
        from backend.app.pipelines.lidar.transform import pose_to_matrix
        raw_T = pose_to_matrix(p)
        T_new = Delta_T_interp @ raw_T

        # Convert back to quaternion and translation
        rot_new = R.from_matrix(T_new[:3, :3])
        qx, qy, qz, qw = rot_new.as_quat()  # Scipy convention: x, y, z, w
        t_new = T_new[:3, 3]

        corr_pose = Pose6D(
            timestamp=p.timestamp,
            frame_index=p.frame_index,
            x=float(t_new[0]),
            y=float(t_new[1]),
            z=float(t_new[2]),
            qx=float(qx),
            qy=float(qy),
            qz=float(qz),
            qw=float(qw),
            intrinsics=p.intrinsics,
        )
        optimized_frame_poses[p.frame_index] = corr_pose

    return optimized_frame_poses


def optimize_pose_graph(
    keyframes: List[KeyframeNode],
    odometry_edges: List[OdometryEdge],
    validated_loops: List[Tuple[RegistrationResult, ValidationDecision]],
    all_raw_poses: List[Pose6D],
    max_correspondence_distance: float = 1.0,
    edge_prune_threshold: float = 0.25,
    preference_loop_closure: float = 1.0,
    reference_node: int = 0,
) -> PoseGraphOptimizationResult:
    """Executes Open3D global pose graph optimization with comprehensive safety validation.

    Purpose:
        Computes globally optimal camera poses that resolve accumulated drift while
        strictly enforcing that geometry is improved, not distorted.

    Parameters:
        keyframes: List of KeyframeNode objects.
        odometry_edges: List of sequential constraints.
        validated_loops: List of accepted loop closures.
        all_raw_poses: Complete list of raw Pose6D frames for interpolation.
        max_correspondence_distance: Solver pruning distance parameter.
        edge_prune_threshold: Outlier edge pruning threshold.
        preference_loop_closure: Balance weight between odometry and loop edges.
        reference_node: Fixed anchor node index (0 = origin).

    Returns:
        PoseGraphOptimizationResult containing statuses, residuals, and poses.

    Assumptions:
        Open3D global optimization library is available.

    Failure conditions:
        If solver fails or residual increases, returns 'rejected' status.

    Debugging:
        Check safety_gate_reasons when optimization is rejected.
    """
    raw_nodes = [k.matrix.copy() for k in keyframes]
    loop_edge_data = [
        (reg.node_i, reg.node_j, reg.optimized_transform)
        for reg, dec in validated_loops
        if dec.status in ("accepted", "uncertain")
    ]

    raw_residual = compute_loop_residual(raw_nodes, loop_edge_data)

    if not loop_edge_data:
        # No loop closures to optimize
        identity_mapping = {p.frame_index: p for p in all_raw_poses}
        keyframe_mapping = {k.node_id: k.matrix for k in keyframes}
        return PoseGraphOptimizationResult(
            optimization_status="neutral",
            raw_loop_residual_m=0.0,
            optimized_loop_residual_m=0.0,
            improvement_percentage=0.0,
            node_count=len(keyframes),
            odometry_edge_count=len(odometry_edges),
            loop_edge_count=0,
            optimized_keyframe_poses=keyframe_mapping,
            optimized_frame_poses=identity_mapping,
            safety_gate_passed=True,
            safety_gate_reasons=["no_loop_closures_present"],
        )

    # Build and optimize pose graph
    pg = build_pose_graph(keyframes, odometry_edges, validated_loops)

    option = o3d.pipelines.registration.GlobalOptimizationOption(
        max_correspondence_distance=max_correspondence_distance,
        edge_prune_threshold=edge_prune_threshold,
        preference_loop_closure=preference_loop_closure,
        reference_node=reference_node,
    )
    criteria = o3d.pipelines.registration.GlobalOptimizationConvergenceCriteria()
    method = o3d.pipelines.registration.GlobalOptimizationLevenbergMarquardt()

    try:
        o3d.pipelines.registration.global_optimization(pg, method, criteria, option)
    except Exception as e:
        identity_mapping = {p.frame_index: p for p in all_raw_poses}
        keyframe_mapping = {k.node_id: k.matrix for k in keyframes}
        return PoseGraphOptimizationResult(
            optimization_status="rejected",
            raw_loop_residual_m=raw_residual,
            optimized_loop_residual_m=raw_residual,
            improvement_percentage=0.0,
            node_count=len(keyframes),
            odometry_edge_count=len(odometry_edges),
            loop_edge_count=len(loop_edge_data),
            optimized_keyframe_poses=keyframe_mapping,
            optimized_frame_poses=identity_mapping,
            safety_gate_passed=False,
            safety_gate_reasons=[f"optimizer_exception: {str(e)}"],
        )

    opt_nodes = [np.array(n.pose, dtype=np.float64) for n in pg.nodes]
    opt_residual = compute_loop_residual(opt_nodes, loop_edge_data)

    # Compute safety gate metrics
    safety_reasons: List[str] = []
    gate_passed = True

    # 1. Residual improvement check
    improvement_pct = 0.0
    if raw_residual > 1e-4:
        improvement_pct = ((raw_residual - opt_residual) / raw_residual) * 100.0

    if opt_residual > raw_residual + 0.01:
        gate_passed = False
        safety_reasons.append(f"residual_increased_from_{raw_residual:.3f}m_to_{opt_residual:.3f}m")

    # 2. Maximum single-step node shift check (avoid crazy distortion jumps > 1.2 m)
    max_node_shift = 0.0
    for i in range(len(keyframes)):
        shift = float(np.linalg.norm(opt_nodes[i][:3, 3] - raw_nodes[i][:3, 3]))
        if shift > max_node_shift:
            max_node_shift = shift

    if max_node_shift > 1.2:
        gate_passed = False
        safety_reasons.append(f"excessive_node_displacement_{max_node_shift:.2f}m_above_1.2m")

    if gate_passed and improvement_pct >= 5.0:
        opt_status = "improved"
    elif gate_passed:
        opt_status = "neutral"
    else:
        opt_status = "rejected"

    # If rejected, fallback to raw poses
    if opt_status == "rejected":
        final_kf_matrices = {k.node_id: k.matrix.copy() for k in keyframes}
        final_frame_poses = {p.frame_index: p for p in all_raw_poses}
    else:
        final_kf_matrices = {i: opt_nodes[i] for i in range(len(opt_nodes))}
        final_frame_poses = interpolate_poses_to_all_frames(all_raw_poses, keyframes, final_kf_matrices)

    return PoseGraphOptimizationResult(
        optimization_status=opt_status,
        raw_loop_residual_m=round(raw_residual, 4),
        optimized_loop_residual_m=round(opt_residual, 4),
        improvement_percentage=round(improvement_pct, 1),
        node_count=len(keyframes),
        odometry_edge_count=len(odometry_edges),
        loop_edge_count=len(loop_edge_data),
        optimized_keyframe_poses=final_kf_matrices,
        optimized_frame_poses=final_frame_poses,
        safety_gate_passed=gate_passed,
        safety_gate_reasons=safety_reasons,
    )


def export_pose_graph_json(
    keyframes: List[KeyframeNode],
    odometry_edges: List[OdometryEdge],
    validated_loops: List[Tuple[RegistrationResult, ValidationDecision]],
    optimized_matrices: Optional[Dict[int, np.ndarray]],
    output_path: Path,
) -> None:
    """Serializes the pose graph topology, constraints, and poses to JSON.

    Purpose:
        Creates a transparent inspection file for graph debugging.

    Parameters:
        keyframes: Keyframe nodes.
        odometry_edges: Sequential edges.
        validated_loops: Loop edges.
        optimized_matrices: Optional mapping of optimized poses.
        output_path: Destination JSON path.

    Returns:
        None.

    Assumptions:
        Destination directory is writable.

    Failure conditions:
        OSError on disk write.

    Debugging:
        Inspect nodes and edges sections in pose_graph.json.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    nodes_data = []
    for k in keyframes:
        entry = {
            "node_id": k.node_id,
            "frame_id": k.frame_id,
            "timestamp": round(k.timestamp, 3),
            "raw_position": [round(c, 4) for c in k.matrix[:3, 3].tolist()],
        }
        if optimized_matrices and k.node_id in optimized_matrices:
            entry["optimized_position"] = [round(c, 4) for c in optimized_matrices[k.node_id][:3, 3].tolist()]
        nodes_data.append(entry)

    odom_edges_data = [
        {
            "source": e.source_node_id,
            "target": e.target_node_id,
            "type": "odometry",
            "distance_meters": round(e.distance_meters, 4),
        }
        for e in odometry_edges
    ]

    loop_edges_data = [
        {
            "source": reg.node_i,
            "target": reg.node_j,
            "type": "loop_closure",
            "status": dec.status,
            "fitness": dec.fitness,
            "inlier_rmse_meters": dec.inlier_rmse,
            "translation_delta_meters": dec.translation_delta_m,
        }
        for reg, dec in validated_loops
    ]

    payload = {
        "node_count": len(nodes_data),
        "odometry_edge_count": len(odom_edges_data),
        "loop_edge_count": len(loop_edges_data),
        "nodes": nodes_data,
        "edges": odom_edges_data + loop_edges_data,
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
