"""Stage 6 Registration Keyframe Selection & Local Point Cloud Extraction.

1. Why this file exists:
    Decimates the dense raw frame stream (~10,000 frames) into a well-conditioned set
    of keyframe nodes (~80-150 nodes) based on spatial and angular displacement.
    Extracts lightweight downsampled local point clouds with surface normals for
    geometric ICP registration.

2. Pipeline stage:
    Stage 6 — Registration Keyframe Selection.

3. Inputs:
    LiDARScanLoader instance, odometry poses, depth frames, confidence maps, and intrinsics.

4. Outputs:
    List of KeyframeNode instances containing node_id, frame_id, pose, transformation matrix,
    and optional Open3D local point clouds with estimated normals.

5. Coordinate conventions:
    Y-up vertical, XZ horizontal.
    Local point clouds are in Camera Coordinate Frame (Z forward, X right, Y down/up).
    Pose transformation matrix T represents T_world_camera.

6. Unit assumptions:
    Distances in meters (m), rotations in radians/degrees, timestamps in seconds (s).

7. Important dependencies:
    numpy, open3d, pydantic, backend.app.pipelines.lidar.

8. What is most likely to break:
    Too dense keyframe selection exhausting RAM, or too sparse missing loop closures.

9. What a developer should inspect first:
    Inspect selected keyframe count (target ~60-150 for a 3-minute scan) and local cloud point count.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Dict, Any
import numpy as np
import open3d as o3d

from backend.app.models.capture import Pose6D, CameraIntrinsics
from backend.app.pipelines.lidar.loader import LiDARScanLoader
from backend.app.pipelines.lidar.unproject import unproject_depth
from backend.app.pipelines.lidar.filtering import filter_by_confidence
from backend.app.pipelines.lidar.transform import pose_to_matrix


@dataclass
class KeyframeNode:
    """Represents a discrete node in the SLAM pose graph.

    Attributes:
        node_id: Zero-based sequential node index (0, 1, 2, ...).
        frame_id: Original scan frame index from ARKit odometry.
        timestamp: Capture timestamp in seconds.
        pose: Original Pose6D camera pose.
        matrix: 4x4 homogeneous transformation matrix T_world_cam.
        intrinsics: Scaled camera intrinsics for depth resolution.
        local_pcd: Downsampled Open3D point cloud in camera coordinate space (optional).
    """
    node_id: int
    frame_id: int
    timestamp: float
    pose: Pose6D
    matrix: np.ndarray
    intrinsics: CameraIntrinsics
    local_pcd: Optional[o3d.geometry.PointCloud] = None


def compute_relative_rotation_deg(q1: Tuple[float, float, float, float], q2: Tuple[float, float, float, float]) -> float:
    """Computes angular difference in degrees between two unit quaternions.

    Purpose:
        Determines angular motion for keyframe gating.

    Parameters:
        q1: Tuple (qx, qy, qz, qw) of initial orientation.
        q2: Tuple (qx, qy, qz, qw) of target orientation.

    Returns:
        Angular difference in degrees in range [0, 180].

    Assumptions:
        Quaternions are unit length.

    Failure conditions:
        Zero-norm quaternions clamped to zero rotation.

    Debugging:
        Check if dot product exceeds 1.0 due to float rounding.
    """
    dot = abs(q1[0]*q2[0] + q1[1]*q2[1] + q1[2]*q2[2] + q1[3]*q2[3])
    dot = min(1.0, max(0.0, dot))
    return float(np.degrees(2.0 * np.arccos(dot)))


def extract_local_point_cloud(
    depth_mm: np.ndarray,
    confidence: np.ndarray,
    intrinsics: CameraIntrinsics,
    min_confidence: int = 2,
    min_depth_m: float = 0.4,
    max_depth_m: float = 3.5,
    voxel_size_m: float = 0.05,
    estimate_normals: bool = True,
) -> o3d.geometry.PointCloud:
    """Unprojects a single depth frame to an Open3D point cloud in camera space.

    Purpose:
        Generates clean, downsampled local geometric observations for registration.

    Parameters:
        depth_mm: uint16 array (192, 256) of raw depths in millimeters.
        confidence: uint8 array (192, 256) of ARKit confidence flags.
        intrinsics: Scaled CameraIntrinsics object.
        min_confidence: Threshold confidence level (default 2 = high confidence).
        min_depth_m: Minimum valid depth in meters.
        max_depth_m: Maximum valid depth in meters.
        voxel_size_m: Voxel grid leaf size for downsampling (meters).
        estimate_normals: If True, computes local surface normals required for point-to-plane ICP.

    Returns:
        open3d.geometry.PointCloud in camera coordinates with normals if requested.

    Assumptions:
        Depth units in millimeters, unprojected coordinates in meters.

    Failure conditions:
        If zero points pass filtering, returns an empty PointCloud.

    Debugging:
        Inspect len(pcd.points) to ensure adequate geometry (typically 1,000-8,000 points).
    """
    conf_mask = filter_by_confidence(confidence, min_confidence=min_confidence)
    points_cam, _ = unproject_depth(
        depth_mm=depth_mm,
        intrinsics=intrinsics,
        min_depth_m=min_depth_m,
        max_depth_m=max_depth_m,
        valid_mask=conf_mask,
    )

    pcd = o3d.geometry.PointCloud()
    if len(points_cam) == 0:
        return pcd

    pcd.points = o3d.utility.Vector3dVector(points_cam.astype(np.float64))

    if voxel_size_m > 0.0 and len(pcd.points) > 10:
        pcd = pcd.voxel_down_sample(voxel_size=voxel_size_m)

    if estimate_normals and len(pcd.points) >= 10:
        pcd.estimate_normals(
            search_param=o3d.geometry.KDTreeSearchParamHybrid(radius=0.15, max_nn=30)
        )

    return pcd


def select_registration_keyframes(
    loader: LiDARScanLoader,
    min_translation_m: float = 0.45,
    min_rotation_deg: float = 18.0,
    max_frame_gap: int = 150,
    load_point_clouds: bool = True,
    voxel_size_m: float = 0.05,
) -> List[KeyframeNode]:
    """Selects discrete keyframe nodes from the continuous capture stream.

    Purpose:
        Reduces continuous ~60fps ARKit captures into informative graph nodes with
        geometric observations, preventing memory exhaustion and degenerate graphs.

    Parameters:
        loader: LiDARScanLoader instance.
        min_translation_m: Minimum Euclidean displacement in meters to trigger a new keyframe.
        min_rotation_deg: Minimum angular displacement in degrees to trigger a new keyframe.
        max_frame_gap: Maximum allowed frames between keyframes regardless of movement.
        load_point_clouds: If True, extracts and attaches local Open3D point clouds.
        voxel_size_m: Voxel downsample resolution for extracted point clouds.

    Returns:
        List of KeyframeNode objects chronologically sorted.

    Assumptions:
        Odometry records are monotonically increasing in time.

    Failure conditions:
        Raises ValueError if loader contains no odometry records.

    Debugging:
        Check len(keyframes); should scale to 60-150 nodes for multi-room scans.
    """
    total = loader.total_frames
    if total == 0:
        raise ValueError("Cannot select keyframes from an empty scan")

    keyframes: List[KeyframeNode] = []
    last_pos: Optional[np.ndarray] = None
    last_quat: Optional[Tuple[float, float, float, float]] = None
    last_frame_idx: int = -999999

    # Stream frames with stride 2 for fast evaluation
    for frame_id, ts, depth_mm, conf, pose, intrinsics in loader.stream_frames(frame_stride=2):
        current_pos = np.array([pose.x, pose.y, pose.z], dtype=np.float64)
        current_quat = (pose.qx, pose.qy, pose.qz, pose.qw)

        is_keyframe = False
        if len(keyframes) == 0:
            is_keyframe = True
        else:
            trans_dist = float(np.linalg.norm(current_pos - last_pos))
            rot_deg = compute_relative_rotation_deg(last_quat, current_quat)
            frame_gap = frame_id - last_frame_idx

            if trans_dist >= min_translation_m or rot_deg >= min_rotation_deg or frame_gap >= max_frame_gap:
                is_keyframe = True

        if is_keyframe:
            pcd = None
            if load_point_clouds:
                pcd = extract_local_point_cloud(
                    depth_mm=depth_mm,
                    confidence=conf,
                    intrinsics=intrinsics,
                    voxel_size_m=voxel_size_m,
                    estimate_normals=True,
                )

            T = pose_to_matrix(pose)
            node = KeyframeNode(
                node_id=len(keyframes),
                frame_id=frame_id,
                timestamp=ts,
                pose=pose,
                matrix=T,
                intrinsics=intrinsics,
                local_pcd=pcd,
            )
            keyframes.append(node)
            last_pos = current_pos
            last_quat = current_quat
            last_frame_idx = frame_id

    # Always ensure the final frame is a keyframe to evaluate closure
    if keyframes and keyframes[-1].frame_id != loader.odometry_records[-1]["frame"]:
        final_record = loader.odometry_records[-1]
        final_id = int(final_record["frame"])
        # Only add if sufficiently distant from last keyframe
        if final_id - keyframes[-1].frame_id > 10:
            # Load final frame data if point clouds requested
            final_pose = Pose6D(
                timestamp=float(final_record["timestamp"]),
                frame_index=final_id,
                x=float(final_record["x"]),
                y=float(final_record["y"]),
                z=float(final_record["z"]),
                qx=float(final_record["qx"]),
                qy=float(final_record["qy"]),
                qz=float(final_record["qz"]),
                qw=float(final_record["qw"]),
            )
            T = pose_to_matrix(final_pose)
            node = KeyframeNode(
                node_id=len(keyframes),
                frame_id=final_id,
                timestamp=final_pose.timestamp,
                pose=final_pose,
                matrix=T,
                intrinsics=loader.get_scaled_intrinsics(final_record),
                local_pcd=None,
            )
            keyframes.append(node)

    return keyframes
