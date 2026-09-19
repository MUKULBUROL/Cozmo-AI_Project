"""Stage 6 Pose Graph & Optimization Tests.

1. Why this file exists:
    Validates mathematical correctness of relative pose transforms, Open3D pose graph
    edge conventions, synthetic loop closure with known drift, ICP quality gating,
    and preservation of raw baseline poses.

2. Pipeline stage:
    Stage 6 — Pose Graph Optimization & Loop Closure Verification.

3. Inputs:
    Synthetic Pose6D fixtures, known transformation matrices, and noisy loop trajectories.

4. Outputs:
    Unit test assertions ensuring zero-regression and drift reduction.

5. Coordinate conventions:
    Y-up vertical, XZ horizontal. Metric meters.

6. Unit assumptions:
    Positions in meters, angles in radians/degrees.

7. Important dependencies:
    unittest, numpy, open3d, backend.app.optimization.

8. What is most likely to break:
    Relative transform matrix inversion (T_j^{-1} T_i vs T_i^{-1} T_j) causing divergence.

9. What a developer should inspect first:
    TestRelativePoseComposition and TestSyntheticLoopOptimization.
"""

import math
import unittest
import numpy as np
import open3d as o3d

from backend.app.models.capture import Pose6D, CameraIntrinsics
from backend.app.pipelines.lidar.transform import pose_to_matrix, quaternion_to_rotation_matrix
from backend.app.optimization.trajectory_analysis import analyze_raw_trajectory
from backend.app.optimization.keyframes import KeyframeNode
from backend.app.optimization.odometry_edges import compute_relative_transform, compute_sequential_odometry_edges, OdometryEdge
from backend.app.optimization.registration import RegistrationResult
from backend.app.optimization.validation import validate_loop_candidate, ValidationDecision
from backend.app.optimization.pose_graph import (
    build_pose_graph,
    optimize_pose_graph,
    compute_loop_residual,
    interpolate_poses_to_all_frames,
    PoseGraphOptimizationResult,
)
from backend.app.optimization.ablation import compute_drift_ablation


class TestPoseGraphOptimization(unittest.TestCase):
    """Verifies relative pose mathematics, optimization convergence, and quality gating."""

    def setUp(self):
        """Builds standardized synthetic pose fixtures."""
        self.intrinsics = CameraIntrinsics(
            fx=200.0, fy=200.0, cx=128.0, cy=96.0, width=256, height=192
        )

    def test_trajectory_analysis_metrics(self):
        """Verifies cumulative path length and start/end displacement calculations."""
        poses = [
            Pose6D(timestamp=0.0, frame_index=0, x=0.0, y=0.0, z=0.0, qx=0.0, qy=0.0, qz=0.0, qw=1.0, intrinsics=self.intrinsics),
            Pose6D(timestamp=10.0, frame_index=10, x=4.0, y=0.0, z=0.0, qx=0.0, qy=0.0, qz=0.0, qw=1.0, intrinsics=self.intrinsics),
            Pose6D(timestamp=20.0, frame_index=20, x=4.0, y=0.0, z=3.0, qx=0.0, qy=0.0, qz=0.0, qw=1.0, intrinsics=self.intrinsics),
            Pose6D(timestamp=30.0, frame_index=30, x=0.4, y=0.0, z=0.3, qx=0.0, qy=0.0, qz=0.0, qw=1.0, intrinsics=self.intrinsics),
        ]

        stats = analyze_raw_trajectory(poses, revisit_distance_threshold_m=1.0, revisit_min_time_gap_s=15.0)

        self.assertEqual(stats["total_poses"], 4)
        self.assertEqual(stats["duration_seconds"], 30.0)
        self.assertAlmostEqual(stats["path_length_meters"], 11.5, places=3)
        self.assertAlmostEqual(stats["start_end_displacement_meters"], 0.5, places=3)
        self.assertEqual(stats["revisit_count"], 1)

    def test_relative_pose_composition(self):
        """Verifies Open3D relative edge convention T_ij = inv(T_j) @ T_i and T_j @ T_ij = T_i."""
        # Node 0 at origin
        T_0 = np.eye(4)
        # Node 1 at [2.5, 0.0, 1.5] rotated 90 degrees around Y
        T_1 = np.eye(4)
        T_1[:3, :3] = np.array([[0, 0, 1], [0, 1, 0], [-1, 0, 0]])
        T_1[:3, 3] = [2.5, 0.0, 1.5]

        T_rel = compute_relative_transform(T_0, T_1)

        # In Open3D PoseGraph: T_rel maps points in frame 0 to frame 1
        # Therefore T_1 @ T_rel must equal T_0
        T_0_reconstructed = T_1 @ T_rel
        np.testing.assert_allclose(T_0_reconstructed, T_0, atol=1e-6)

    def test_synthetic_loop_closure_optimization(self):
        """Verifies that Open3D pose graph closes a synthetic square loop with 0.4m drift."""
        # Define 4 ground-truth square vertices in XZ plane (side length 5m)
        gt_positions = [
            np.array([0.0, 0.0, 0.0]),
            np.array([5.0, 0.0, 0.0]),
            np.array([5.0, 0.0, 5.0]),
            np.array([0.0, 0.0, 5.0]),
            np.array([0.0, 0.0, 0.0]),  # Loops back to start
        ]

        # Inject 0.40m accumulated odometry drift at the closing node (node 4)
        drift_offset = np.array([0.28, 0.0, 0.28])  # norm = 0.396 m
        noisy_positions = [
            gt_positions[0],
            gt_positions[1] + 0.25 * drift_offset,
            gt_positions[2] + 0.50 * drift_offset,
            gt_positions[3] + 0.75 * drift_offset,
            gt_positions[4] + drift_offset,  # Drifts ~0.4m from node 0
        ]

        # Build keyframe nodes
        keyframes = []
        raw_poses = []
        for i, pos in enumerate(noisy_positions):
            pose = Pose6D(
                timestamp=float(i * 10),
                frame_index=i * 50,
                x=float(pos[0]),
                y=float(pos[1]),
                z=float(pos[2]),
                qx=0.0, qy=0.0, qz=0.0, qw=1.0,
                intrinsics=self.intrinsics,
            )
            raw_poses.append(pose)
            T = np.eye(4)
            T[:3, 3] = pos
            keyframes.append(KeyframeNode(
                node_id=i,
                frame_id=i * 50,
                timestamp=pose.timestamp,
                pose=pose,
                matrix=T,
                intrinsics=self.intrinsics,
            ))

        # Initial loop gap at endpoint
        initial_loop_gap = float(np.linalg.norm(noisy_positions[-1] - noisy_positions[0]))
        self.assertAlmostEqual(initial_loop_gap, float(np.linalg.norm(drift_offset)), places=3)

        # Build sequential odometry edges
        odometry_edges = compute_sequential_odometry_edges(keyframes)
        self.assertEqual(len(odometry_edges), 4)

        # Ground truth loop closure between node 0 and node 4:
        # Since physical camera returned to same spot, relative transform between frame 0 and frame 4 is Identity!
        T_loop_ij = compute_relative_transform(keyframes[0].matrix, keyframes[0].matrix)  # Identity
        loop_reg = RegistrationResult(
            node_i=0,
            node_j=4,
            fitness=0.95,
            inlier_rmse=0.015,
            correspondence_count=500,
            initial_transform=compute_relative_transform(keyframes[0].matrix, keyframes[4].matrix),
            optimized_transform=T_loop_ij,
            information_matrix=np.eye(6) * 50.0,
            translation_delta_m=initial_loop_gap,
            rotation_delta_deg=0.0,
        )
        loop_decision = ValidationDecision(
            node_i=0,
            node_j=4,
            status="accepted",
            fitness=0.95,
            inlier_rmse=0.015,
            correspondences=500,
            translation_delta_m=initial_loop_gap,
            rotation_delta_deg=0.0,
        )

        validated_loops = [(loop_reg, loop_decision)]

        # Optimize pose graph
        opt_result = optimize_pose_graph(
            keyframes=keyframes,
            odometry_edges=odometry_edges,
            validated_loops=validated_loops,
            all_raw_poses=raw_poses,
            preference_loop_closure=1.0,
            reference_node=0,
        )

        # Verify optimization converged and closed loop
        self.assertEqual(opt_result.optimization_status, "improved")
        self.assertTrue(opt_result.safety_gate_passed)
        self.assertGreater(opt_result.improvement_percentage, 80.0)

        # Check that closing endpoint is now aligned with origin (< 0.05m)
        opt_p0 = opt_result.optimized_keyframe_poses[0][:3, 3]
        opt_p4 = opt_result.optimized_keyframe_poses[4][:3, 3]
        final_loop_gap = float(np.linalg.norm(opt_p4 - opt_p0))
        self.assertLess(final_loop_gap, 0.05)

        # Verify raw poses remain completely unchanged
        self.assertEqual(raw_poses[4].x, float(noisy_positions[4][0]))
        self.assertEqual(raw_poses[4].z, float(noisy_positions[4][2]))

        # Verify optimized poses are written separately
        self.assertIn(raw_poses[4].frame_index, opt_result.optimized_frame_poses)
        opt_pose_4 = opt_result.optimized_frame_poses[raw_poses[4].frame_index]
        self.assertNotEqual(opt_pose_4.x, raw_poses[4].x)

    def test_false_loop_constraint_rejection(self):
        """Verifies that registration results failing fitness or RMSE are rejected."""
        # Low fitness registration
        bad_reg_1 = RegistrationResult(
            node_i=2, node_j=15, fitness=0.25, inlier_rmse=0.03, correspondence_count=50,
            initial_transform=np.eye(4), optimized_transform=np.eye(4),
            information_matrix=np.eye(6), translation_delta_m=0.1, rotation_delta_deg=1.0,
        )
        dec_1 = validate_loop_candidate(bad_reg_1, min_fitness=0.55)
        self.assertEqual(dec_1.status, "rejected")
        self.assertTrue(any("low_fitness" in r for r in dec_1.rejection_reasons))

        # High RMSE registration
        bad_reg_2 = RegistrationResult(
            node_i=5, node_j=25, fitness=0.75, inlier_rmse=0.12, correspondence_count=300,
            initial_transform=np.eye(4), optimized_transform=np.eye(4),
            information_matrix=np.eye(6), translation_delta_m=0.1, rotation_delta_deg=2.0,
        )
        dec_2 = validate_loop_candidate(bad_reg_2, max_rmse_m=0.055)
        self.assertEqual(dec_2.status, "rejected")
        self.assertTrue(any("high_rmse" in r for r in dec_2.rejection_reasons))

        # Excessive translation jump (unconstrained planar slip)
        bad_reg_3 = RegistrationResult(
            node_i=10, node_j=30, fitness=0.85, inlier_rmse=0.03, correspondence_count=400,
            initial_transform=np.eye(4), optimized_transform=np.eye(4),
            information_matrix=np.eye(6), translation_delta_m=0.85, rotation_delta_deg=3.0,
        )
        dec_3 = validate_loop_candidate(bad_reg_3, max_translation_delta_m=0.50)
        self.assertEqual(dec_3.status, "rejected")
        self.assertTrue(any("excessive_translation_shift" in r for r in dec_3.rejection_reasons))

    def test_drift_ablation_metrics_computation(self):
        """Verifies compute_drift_ablation outputs complete comparative structure."""
        raw_stats = {"path_length_meters": 100.0}
        raw_poses = [
            Pose6D(timestamp=0.0, frame_index=0, x=0.0, y=0.0, z=0.0, qx=0.0, qy=0.0, qz=0.0, qw=1.0),
            Pose6D(timestamp=100.0, frame_index=100, x=0.389, y=0.0, z=0.0, qx=0.0, qy=0.0, qz=0.0, qw=1.0),
        ]
        opt_poses = {
            0: Pose6D(timestamp=0.0, frame_index=0, x=0.0, y=0.0, z=0.0, qx=0.0, qy=0.0, qz=0.0, qw=1.0),
            100: Pose6D(timestamp=100.0, frame_index=100, x=0.02, y=0.0, z=0.0, qx=0.0, qy=0.0, qz=0.0, qw=1.0),
        }
        opt_res = PoseGraphOptimizationResult(
            optimization_status="improved",
            raw_loop_residual_m=0.389,
            optimized_loop_residual_m=0.02,
            improvement_percentage=94.9,
            node_count=20,
            odometry_edge_count=19,
            loop_edge_count=2,
            optimized_keyframe_poses={},
            optimized_frame_poses=opt_poses,
            safety_gate_passed=True,
        )

        ablation = compute_drift_ablation(raw_stats, opt_res, raw_poses, opt_poses)

        self.assertIn("drift_correction_off", ablation["metrics"])
        self.assertIn("drift_correction_on", ablation["metrics"])
        m_on = ablation["metrics"]["drift_correction_on"]
        self.assertAlmostEqual(m_on["endpoint_gap_reduction_meters"], 0.369, places=3)
        self.assertGreater(m_on["residual_improvement_percentage"], 90.0)


if __name__ == "__main__":
    unittest.main()
