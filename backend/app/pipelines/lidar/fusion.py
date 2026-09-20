"""Incremental multi-frame point cloud fusion for full-scan LiDAR reconstruction."""

import sys
from typing import Tuple, List, Dict, Any, Optional, Callable
import numpy as np

from backend.app.models.capture import Pose6D
from .loader import LiDARScanLoader
from .unproject import unproject_depth
from .transform import transform_camera_to_world
from .filtering import filter_by_confidence


def fuse_scan_frames(
    loader: LiDARScanLoader,
    frame_stride: int = 1,
    min_confidence: int = 2,
    min_depth_m: float = 0.3,
    max_depth_m: float = 3.5,
    max_frames: Optional[int] = None,
    point_subsample_step: int = 1,
    progress_callback: Optional[Callable[[int, int, int], None]] = None,
    custom_poses: Optional[Dict[int, Pose6D]] = None,
) -> Tuple[np.ndarray, np.ndarray, List[Pose6D], Dict[str, Any]]:
    """Streams and fuses multi-frame depth maps into a shared world-coordinate point cloud.

    Args:
        loader: LiDARScanLoader instance.
        frame_stride: Process every N-th frame (e.g. 1 for all, 5 for faster).
        min_confidence: Minimum ARKit confidence (0=low, 1=medium, 2=high).
        min_depth_m: Discard points closer than this in meters.
        max_depth_m: Discard points farther than this in meters.
        max_frames: Optional limit on processed frames.
        point_subsample_step: Intra-frame point stride (e.g. 1 = all valid pixels, 2 = 1/4th).
        progress_callback: Callback(processed_count, total_frames, current_points).
        custom_poses: Optional mapping of frame_id -> Pose6D (used by Stage 6 drift-corrected reconstruction).

    Returns:
        fused_points: (N, 3) float32 array in metric world coordinates.
        fused_colors: (N, 3) uint8 array of RGB colors.
        poses: Chronological list of processed Pose6D objects.
        stats: Dictionary of fusion accounting metrics.
    """
    all_points: List[np.ndarray] = []
    all_colors: List[np.ndarray] = []
    processed_poses: List[Pose6D] = []

    total_depth_pixels_considered = 0
    points_passed_confidence = 0
    points_passed_depth_range = 0
    frames_processed = 0

    total_available_frames = loader.total_frames
    expected_frames = (total_available_frames + frame_stride - 1) // frame_stride
    if max_frames:
        expected_frames = min(expected_frames, max_frames)

    for frame_id, ts, depth_mm, confidence, pose, intrinsics in loader.stream_frames(
        frame_stride=frame_stride, max_frames=max_frames
    ):
        if custom_poses and frame_id in custom_poses:
            pose = custom_poses[frame_id]

        frames_processed += 1
        H, W = depth_mm.shape
        total_depth_pixels_considered += H * W

        # 1. Confidence mask
        conf_mask = filter_by_confidence(confidence, min_confidence=min_confidence)
        conf_pass_count = int(np.count_nonzero(conf_mask))
        points_passed_confidence += conf_pass_count

        # 2. Depth unprojection in camera space (mm -> m inside)
        points_cam, valid_indices = unproject_depth(
            depth_mm=depth_mm,
            intrinsics=intrinsics,
            min_depth_m=min_depth_m,
            max_depth_m=max_depth_m,
            valid_mask=conf_mask,
        )
        depth_pass_count = len(points_cam)
        points_passed_depth_range += depth_pass_count

        if depth_pass_count == 0:
            continue

        # 3. Optional intra-frame subsampling for memory management
        if point_subsample_step > 1:
            points_cam = points_cam[::point_subsample_step]

        # 4. Transform from camera coordinate frame to world coordinate frame
        points_world = transform_camera_to_world(points_cam, pose)
        all_points.append(points_world)
        processed_poses.append(pose)

        # 5. Generate height-based palette coloring (World Y is vertical)
        # ARKit world coordinate: Y is up. Colors: Blue (floor) to Red (ceiling)
        colors = np.zeros_like(points_world, dtype=np.uint8)
        # Map Y in [-1.5, 1.5] to [0, 255]
        norm_y = np.clip((points_world[:, 1] + 1.2) / 2.5, 0.0, 1.0)
        colors[:, 0] = (norm_y * 240).astype(np.uint8)          # Red
        colors[:, 1] = ((1.0 - np.abs(norm_y - 0.5) * 2) * 180).astype(np.uint8) # Green
        colors[:, 2] = ((1.0 - norm_y) * 240).astype(np.uint8)  # Blue
        all_colors.append(colors)

        if frames_processed % 50 == 0 or frames_processed == expected_frames:
            current_count = sum(len(p) for p in all_points)
            if progress_callback:
                progress_callback(frames_processed, expected_frames, current_count)
            else:
                print(f"Processed {frames_processed}/{expected_frames} frames ({current_count:,} points)")

    if all_points:
        fused_points = np.concatenate(all_points, axis=0)
        fused_colors = np.concatenate(all_colors, axis=0)
    else:
        fused_points = np.empty((0, 3), dtype=np.float32)
        fused_colors = np.empty((0, 3), dtype=np.uint8)

    stats = {
        "total_frames_in_scan": total_available_frames,
        "frames_processed": frames_processed,
        "frame_stride": frame_stride,
        "total_depth_pixels_considered": total_depth_pixels_considered,
        "points_passed_confidence_filter": points_passed_confidence,
        "points_passed_depth_filter": points_passed_depth_range,
        "points_fused_raw": len(fused_points),
        "point_subsample_step": point_subsample_step,
    }
    return fused_points, fused_colors, processed_poses, stats
