"""Stage 6 Optimization & Loop Closure Package.

1. Why this file exists:
    Initializes the backend.app.optimization package, exposing keyframe selection,
    odometry edge construction, loop closure candidate detection, point-to-plane ICP
    registration, pose graph optimization, and drift ablation analysis.

2. Pipeline stage:
    Stage 6 — Multi-Room Property Reconstruction & Drift Correction.

3. Inputs:
    Raw ARKit odometry, depth streams, and keyframe point clouds.

4. Outputs:
    Optimized 6-DoF camera poses, loop closure diagnostics, and drift metrics.

5. Coordinate conventions:
    Y-up vertical axis, XZ horizontal floor plane.
    Rigid transformations T: 4x4 homogeneous matrices in meters.

6. Unit assumptions:
    Distances in meters (m), angles in radians/degrees, timestamps in seconds (s).

7. Important dependencies:
    numpy, open3d, pydantic.

8. What is most likely to break:
    Relative transform direction inversions between camera-to-world and world-to-camera.

9. What a developer should inspect first:
    Verify transform direction against synthetic pose composition tests.
"""

from .trajectory_analysis import analyze_raw_trajectory, export_raw_trajectory_json, render_trajectory_svg
from .keyframes import select_registration_keyframes, KeyframeNode
from .odometry_edges import compute_sequential_odometry_edges, OdometryEdge
from .loop_detector import detect_loop_candidates, LoopCandidate
from .registration import register_loop_candidate, RegistrationResult
from .validation import validate_loop_candidate, ValidationDecision
from .pose_graph import build_pose_graph, optimize_pose_graph, PoseGraphOptimizationResult
from .ablation import compute_drift_ablation, render_drift_ablation_svg

__all__ = [
    "analyze_raw_trajectory",
    "export_raw_trajectory_json",
    "render_trajectory_svg",
    "select_registration_keyframes",
    "KeyframeNode",
    "compute_sequential_odometry_edges",
    "OdometryEdge",
    "detect_loop_candidates",
    "LoopCandidate",
    "register_loop_candidate",
    "RegistrationResult",
    "validate_loop_candidate",
    "ValidationDecision",
    "build_pose_graph",
    "optimize_pose_graph",
    "PoseGraphOptimizationResult",
    "compute_drift_ablation",
    "render_drift_ablation_svg",
]
