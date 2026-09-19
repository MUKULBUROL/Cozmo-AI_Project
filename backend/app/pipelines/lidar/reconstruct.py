"""Master reconstruction orchestrator for LiDAR captures."""

import os
import time
import json
from dataclasses import dataclass, asdict
from typing import Optional, Dict, Any
import numpy as np
import open3d as o3d

from .loader import LiDARScanLoader
from .fusion import fuse_scan_frames
from .filtering import voxel_downsample, remove_statistical_outliers
from .trajectory import analyze_trajectory, save_trajectory_json


@dataclass
class ReconstructionConfig:
    scan_id: str
    archive_path: str
    output_dir: str = ""
    frame_stride: int = 5
    min_confidence: int = 2
    min_depth_m: float = 0.3
    max_depth_m: float = 3.5
    voxel_size_m: float = 0.02
    remove_outliers: bool = True
    outlier_nb_neighbors: int = 20
    outlier_std_ratio: float = 2.0
    point_subsample_step: int = 1
    max_frames: Optional[int] = None
    is_loop_scan: Optional[bool] = None

    def __post_init__(self):
        if not self.output_dir:
            self.output_dir = os.path.join("outputs", self.scan_id)


def save_point_cloud(filename: str, points: np.ndarray, colors: Optional[np.ndarray] = None):
    """Saves a point cloud to PLY format using Open3D."""
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    pcd = o3d.geometry.PointCloud()
    pcd.points = o3d.utility.Vector3dVector(points.astype(np.float64))
    if colors is not None:
        c_norm = colors.astype(np.float64)
        if c_norm.max() > 1.0:
            c_norm = c_norm / 255.0
        pcd.colors = o3d.utility.Vector3dVector(c_norm)
    o3d.io.write_point_cloud(filename, pcd, write_ascii=True)


def run_lidar_reconstruction(config: ReconstructionConfig) -> Dict[str, Any]:
    """Runs complete end-to-end baseline LiDAR metric reconstruction.

    Steps:
        1. Initialize streaming loader.
        2. Unproject & fuse frames into ARKit world coordinates using raw poses.
        3. Save baseline_raw.ply.
        4. Apply voxel downsampling and outlier removal.
        5. Save baseline_filtered.ply.
        6. Compute and save trajectory.json.
        7. Compute and save reconstruction_stats.json.
    """
    start_time = time.time()
    os.makedirs(config.output_dir, exist_ok=True)

    print("=" * 60)
    print(f"LIDAR METRIC RECONSTRUCTION: {config.scan_id}")
    print(f"Archive:     {config.archive_path}")
    print(f"Output Dir:  {config.output_dir}")
    print(f"Stride:      {config.frame_stride} | Voxel Size: {config.voxel_size_m} m | Min Conf: {config.min_confidence}")
    print("=" * 60)

    # 1. Stream and fuse frames
    with LiDARScanLoader(config.archive_path, config.scan_id) as loader:
        raw_points, raw_colors, processed_poses, fusion_stats = fuse_scan_frames(
            loader=loader,
            frame_stride=config.frame_stride,
            min_confidence=config.min_confidence,
            min_depth_m=config.min_depth_m,
            max_depth_m=config.max_depth_m,
            max_frames=config.max_frames,
            point_subsample_step=config.point_subsample_step,
        )

    if len(raw_points) == 0:
        raise RuntimeError(f"Reconstruction failed: 0 points extracted from scan {config.scan_id}")

    # 2. Save baseline_raw.ply
    raw_ply_path = os.path.join(config.output_dir, "baseline_raw.ply")
    save_point_cloud(raw_ply_path, raw_points, raw_colors)
    print(f"Saved baseline raw cloud: {raw_ply_path} ({len(raw_points):,} points)")

    # 3. Voxel downsampling
    down_points, down_colors = voxel_downsample(
        points=raw_points,
        colors=raw_colors,
        voxel_size_m=config.voxel_size_m,
    )
    print(f"Voxel downsampled: {len(raw_points):,} -> {len(down_points):,} points (size={config.voxel_size_m}m)")

    # 4. Statistical outlier removal (optional)
    if config.remove_outliers:
        clean_points, clean_colors = remove_statistical_outliers(
            points=down_points,
            colors=down_colors,
            nb_neighbors=config.outlier_nb_neighbors,
            std_ratio=config.outlier_std_ratio,
        )
        print(f"Outlier removal: {len(down_points):,} -> {len(clean_points):,} points")
    else:
        clean_points, clean_colors = down_points, down_colors

    # 5. Save baseline_filtered.ply
    filtered_ply_path = os.path.join(config.output_dir, "baseline_filtered.ply")
    save_point_cloud(filtered_ply_path, clean_points, clean_colors)
    print(f"Saved baseline filtered cloud: {filtered_ply_path} ({len(clean_points):,} points)")

    # 6. Trajectory analysis & trajectory.json
    traj_stats = analyze_trajectory(processed_poses, is_loop_scan=config.is_loop_scan)
    traj_json_path = os.path.join(config.output_dir, "trajectory.json")
    save_trajectory_json(traj_stats, traj_json_path)
    print(f"Saved trajectory diagnostics: {traj_json_path}")

    # 7. Reconstruction statistics JSON
    elapsed_time = round(time.time() - start_time, 2)
    reconstruction_stats = {
        "scan_id": config.scan_id,
        "total_frames": fusion_stats["total_frames_in_scan"],
        "frames_processed": fusion_stats["frames_processed"],
        "depth_unit_input": "millimeter",
        "coordinate_unit_output": "meter",
        "points_generated": fusion_stats["total_depth_pixels_considered"],
        "points_after_confidence_filter": fusion_stats["points_passed_confidence_filter"],
        "points_after_depth_filter": fusion_stats["points_passed_depth_filter"],
        "points_raw_fused": len(raw_points),
        "points_after_downsampling": len(down_points),
        "points_final_filtered": len(clean_points),
        "voxel_size_m": config.voxel_size_m,
        "frame_stride": config.frame_stride,
        "trajectory_length_m": traj_stats.get("total_path_length_meters", 0.0),
        "start_end_displacement_m": traj_stats.get("start_end_displacement_meters", 0.0),
        "scan_duration_s": traj_stats.get("duration_seconds", 0.0),
        "processing_time_seconds": elapsed_time,
        "bounds_meters": {
            "x": [round(float(clean_points[:, 0].min()), 3), round(float(clean_points[:, 0].max()), 3)],
            "y": [round(float(clean_points[:, 1].min()), 3), round(float(clean_points[:, 1].max()), 3)],
            "z": [round(float(clean_points[:, 2].min()), 3), round(float(clean_points[:, 2].max()), 3)],
        },
        "spans_meters": {
            "width_x": round(float(clean_points[:, 0].max() - clean_points[:, 0].min()), 3),
            "height_y": round(float(clean_points[:, 1].max() - clean_points[:, 1].min()), 3),
            "depth_z": round(float(clean_points[:, 2].max() - clean_points[:, 2].min()), 3),
        },
    }

    stats_json_path = os.path.join(config.output_dir, "reconstruction_stats.json")
    with open(stats_json_path, "w", encoding="utf-8") as f:
        json.dump(reconstruction_stats, f, indent=2)
    print(f"Saved reconstruction statistics: {stats_json_path}")
    print(f"Reconstruction completed in {elapsed_time}s.")
    print("-" * 60)

    return reconstruction_stats
