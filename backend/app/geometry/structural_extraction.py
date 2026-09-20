"""End-to-end structural extraction orchestrator identifying floor, ceiling, and walls.

1. Purpose:
    Segments dominant architectural surfaces (horizontal floor/ceiling planes and vertical walls)
    from a filtered metric 3D point cloud using surface normal orientation gating and iterative
    RANSAC plane fitting, with deterministic random number seeding for bit-level reproducibility.

2. Stage:
    Stage 2 (Architectural Structural Plane Extraction) & Stage 10.2 (Deterministic Baseline).

3. Inputs:
    Filtered point cloud PLY file (e.g. outputs/<scan_id>/baseline_filtered.ply),
    StructuralConfig configuration dataclass with geometric thresholds and RNG seed.

4. Outputs:
    outputs/<scan_id>/structure/
      ├── floor.ply
      ├── ceiling.ply (or placeholder text if absent)
      ├── walls.ply
      ├── unclassified.ply
      ├── structure_debug.ply
      ├── structure.json
      └── extraction_stats.json

5. Coordinate systems / units:
    Metric coordinates (meters). Standard camera/world coordinate frame:
    Y-axis represents the vertical gravity direction (upward positive).
    XZ-plane represents the horizontal ground/floor plane.

6. Dependencies:
    os, json, time, dataclasses, typing, numpy, open3d,
    backend.app.core.determinism (configure_determinism, DEFAULT_SEED),
    backend.app.geometry (preprocessing, normals, plane_detection, plane_classification, metrics).

7. Assumptions:
    Input point cloud is metric and approximately upright (Y vertical).
    Floor is planar and dominant horizontal lower surface.
    Walls are vertical planar surfaces with normals roughly orthogonal to Y axis.

8. Failure modes:
    Missing input PLY path raises FileNotFoundError or Open3D read error.
    Extremely sparse points (< min_floor_inliers or min_wall_inliers) yields empty extractions.
    Invalid normal estimation if point density is inadequate for search radius.

9. First debugging points:
    Inspect `extraction_stats.json` for inlier counts, failure reasons, and random_seed.
    Inspect `structure_debug.ply` in 3D viewer (CloudCompare/Open3D) for color-coded plane assignments.
"""

import os
import json
import time
from dataclasses import dataclass, asdict
from typing import Dict, Any, Optional, List
import numpy as np
import open3d as o3d

from backend.app.core import configure_determinism, DEFAULT_SEED
from .preprocessing import load_and_validate_point_cloud
from .normals import estimate_point_normals, split_horizontal_vertical_masks
from .plane_detection import extract_planes_iterative, DetectedPlane
from .plane_classification import (
    classify_floor,
    classify_ceiling,
    filter_wall_candidates,
    merge_parallel_walls,
)
from .metrics import compute_plane_bounds_and_spans, compute_plane_confidence


WALL_PALETTE = [
    [230, 40, 40],    # Bright Red
    [240, 140, 20],   # Amber / Orange
    [230, 210, 30],   # Warm Yellow
    [40, 200, 100],   # Emerald Green
    [210, 40, 200],   # Magenta
    [40, 200, 220],   # Cyan-Green
    [180, 80, 220],   # Purple
    [240, 80, 140],   # Coral Pink
]


@dataclass
class StructuralConfig:
    scan_id: str
    ply_path: str = ""
    output_dir: str = ""
    distance_threshold_m: float = 0.035
    normal_radius_m: float = 0.10
    normal_max_nn: int = 30
    min_floor_inliers: int = 5000
    min_wall_inliers: int = 4000
    max_horizontal_planes: int = 6
    max_vertical_planes: int = 14
    min_height_span_m: float = 0.70
    min_horizontal_span_m: float = 0.70
    wall_merge_angle_deg: float = 12.0
    wall_merge_distance_m: float = 0.18
    random_seed: int = DEFAULT_SEED
    deterministic_mode: bool = True

    def __post_init__(self):
        if not self.ply_path:
            self.ply_path = os.path.join("outputs", self.scan_id, "baseline_filtered.ply")
        if not self.output_dir:
            self.output_dir = os.path.join("outputs", self.scan_id, "structure")


def write_ply(filename: str, points: np.ndarray, colors: Optional[np.ndarray] = None) -> None:
    """Saves 3D coordinates and optional RGB color channels to an ASCII PLY file.

    Purpose:
        Serializes raw, filtered, or classified 3D point cloud arrays into standard PLY
        files for downstream inspection and 3D visualization.

    Parameters:
        filename: str
            Destination filesystem path for output PLY.
        points: np.ndarray
            (N, 3) array of 3D point coordinates.
        colors: Optional[np.ndarray]
            (N, 3) optional RGB array in [0, 255] uint8 or [0.0, 1.0] float.

    Returns:
        None.

    Units / coordinates:
        Metric coordinates (meters). RGB color values scaled to [0.0, 1.0].

    Assumptions:
        points array is 2D with shape (N, 3).
        Parent directory is writable.

    Failure conditions:
        IOError if destination path cannot be written.
        ValueError if point coordinates contain non-finite numbers.

    Dependencies:
        os, open3d, numpy.

    Debugging clues:
        Inspect file size; check whether points array is non-empty before calling.
    """
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    pcd = o3d.geometry.PointCloud()
    pcd.points = o3d.utility.Vector3dVector(points.astype(np.float64))
    if colors is not None and len(colors) == len(points):
        c_norm = colors.astype(np.float64)
        if c_norm.max() > 1.0:
            c_norm = c_norm / 255.0
        pcd.colors = o3d.utility.Vector3dVector(c_norm)
    o3d.io.write_point_cloud(filename, pcd, write_ascii=True)


def extract_structure(config: StructuralConfig) -> Dict[str, Any]:
    """Runs complete structural plane segmentation pipeline.

    Purpose:
        Executes end-to-end extraction of architectural planes (floor, ceiling, and vertical walls)
        from a preprocessed metric 3D point cloud, applying deterministic random seeding, surface
        normal gating, iterative RANSAC plane fitting, quality classification, and parallel wall merging.

    Parameters:
        config: StructuralConfig
            Configuration dataclass defining scan identity, input/output paths, geometric distance
            and normal thresholds, minimum inlier criteria, and random seed parameters.

    Returns:
        Dict[str, Any]:
            Dictionary containing comprehensive summary statistics of the extraction run, including
            input point counts, floor/ceiling detection status and metrics, wall candidate counts,
            inlier counts, execution duration, and deterministic seed metadata.

    Units / coordinates:
        Distances and residuals in meters (m). Angles in degrees. Coordinates in meters.
        World coordinate system with Y vertical upward, XZ ground plane.

    Assumptions:
        Input point cloud is metric and approximately oriented with Y upward.
        Point density is adequate for normal estimation within normal_radius_m.

    Failure conditions:
        Raises FileNotFoundError if input point cloud does not exist.
        Raises ValueError if point cloud contains NaN or invalid vertex coordinates.

    Dependencies:
        backend.app.core.determinism.configure_determinism,
        backend.app.geometry (preprocessing, normals, plane_detection, plane_classification, metrics),
        open3d, numpy.

    Debugging clues:
        Inspect console logs for normal split percentages and RANSAC candidate counts.
        Verify extraction_stats.json has floor_detected=True and wall counts >= 4.
        Inspect structure_debug.ply in CloudCompare to visually verify classified planes.
    """
    start_time = time.time()
    os.makedirs(config.output_dir, exist_ok=True)

    # 0. Initialize centralized determinism before any RANSAC or sampling occurs
    if config.deterministic_mode and config.random_seed is not None:
        configure_determinism(config.random_seed)

    print("=" * 60)
    print(f"STRUCTURAL EXTRACTION: {config.scan_id}")
    print(f"Input PLY:   {config.ply_path}")
    print(f"Output Dir:  {config.output_dir}")
    print(f"Seed:        {config.random_seed} (deterministic={config.deterministic_mode})")
    print("=" * 60)

    # 1. Load point cloud
    pcd = load_and_validate_point_cloud(config.ply_path)
    points = np.asarray(pcd.points)
    total_input_points = len(points)
    print(f"Loaded {total_input_points:,} metric points.")

    # 2. Normal estimation
    print("Estimating surface normals...")
    normals = estimate_point_normals(pcd, radius_m=config.normal_radius_m, max_nn=config.normal_max_nn)

    # 3. Normal orientation split
    is_horiz, is_vert, is_oblique = split_horizontal_vertical_masks(normals, vertical_axis=1)
    print(f"Points split: {np.count_nonzero(is_horiz):,} horizontal | {np.count_nonzero(is_vert):,} vertical | {np.count_nonzero(is_oblique):,} oblique")

    # 4. Detect horizontal planes (floor & ceiling)
    horiz_indices = np.where(is_horiz)[0]
    pcd_horiz = pcd.select_by_index(horiz_indices)
    horiz_planes, _ = extract_planes_iterative(
        pcd=pcd_horiz,
        distance_threshold_m=config.distance_threshold_m,
        min_inliers=config.min_floor_inliers,
        max_planes=config.max_horizontal_planes,
    )

    floor_plane = classify_floor(horiz_planes, vertical_axis=1)
    ceiling_plane, ceiling_reason = classify_ceiling(horiz_planes, floor_plane, vertical_axis=1)

    floor_detected = floor_plane is not None
    ceiling_detected = ceiling_plane is not None
    floor_y = float(np.mean(floor_plane.inlier_points[:, 1])) if floor_detected else None
    ceiling_y = float(np.mean(ceiling_plane.inlier_points[:, 1])) if ceiling_detected else None

    ceiling_height_m = round(ceiling_y - floor_y, 3) if (floor_detected and ceiling_detected) else None

    if floor_detected:
        print(f"Floor detected: Y={floor_y:.3f} m | inliers={floor_plane.inlier_count:,} | rmse={floor_plane.rmse_m:.3f} m")
    else:
        print("Floor: NOT DETECTED")

    if ceiling_detected:
        print(f"Ceiling detected: Y={ceiling_y:.3f} m | inliers={ceiling_plane.inlier_count:,} | height={ceiling_height_m:.3f} m")
    else:
        print(f"Ceiling: NOT DETECTED ({ceiling_reason})")

    # 5. Detect vertical wall candidates
    # Exclude points already assigned to floor or ceiling
    used_indices = set()
    if floor_detected:
        used_indices.update(horiz_indices[floor_plane.inlier_indices])
    if ceiling_detected:
        used_indices.update(horiz_indices[ceiling_plane.inlier_indices])

    vert_indices = np.where(is_vert)[0]
    vert_available = [idx for idx in vert_indices if idx not in used_indices]
    pcd_vert = pcd.select_by_index(vert_available)

    vert_planes, _ = extract_planes_iterative(
        pcd=pcd_vert,
        distance_threshold_m=config.distance_threshold_m,
        min_inliers=config.min_wall_inliers,
        max_planes=config.max_vertical_planes,
    )
    print(f"Extracted {len(vert_planes)} raw vertical plane candidates.")

    # 6. Filter non-wall planes & merge duplicate wall fragments
    accepted_walls, rejected_log = filter_wall_candidates(
        vertical_planes=vert_planes,
        floor_y=floor_y,
        min_inliers=config.min_wall_inliers,
        min_height_span_m=config.min_height_span_m,
        min_horizontal_span_m=config.min_horizontal_span_m,
    )
    print(f"Heuristics accepted {len(accepted_walls)} walls ({len(rejected_log)} rejected as furniture/clutter).")

    merged_walls = merge_parallel_walls(
        wall_planes=accepted_walls,
        angular_thresh_deg=config.wall_merge_angle_deg,
        distance_thresh_m=config.wall_merge_distance_m,
    )
    print(f"Consolidated into {len(merged_walls)} dominant room walls after merging fragments.")

    # 7. Color assignment for debug visualization
    # Color palette: Floor = Blue, Ceiling = Cyan, Walls = Red/Orange/Yellow/Green/Magenta, Clutter = Gray
    debug_colors = np.full((total_input_points, 3), 160, dtype=np.uint8)  # default neutral gray
    classified_mask = np.zeros(total_input_points, dtype=bool)

    # Floor coloring
    if floor_detected:
        floor_global_idx = horiz_indices[floor_plane.inlier_indices]
        debug_colors[floor_global_idx] = [30, 110, 240]  # Royal Blue
        classified_mask[floor_global_idx] = True

    # Ceiling coloring
    if ceiling_detected:
        ceil_global_idx = horiz_indices[ceiling_plane.inlier_indices]
        debug_colors[ceil_global_idx] = [40, 220, 240]   # Cyan
        classified_mask[ceil_global_idx] = True

    # Walls coloring
    all_wall_points = []
    walls_json_list = []
    for w_idx, wall in enumerate(merged_walls):
        w_color = WALL_PALETTE[w_idx % len(WALL_PALETTE)]
        # Select inliers in global coordinate indices
        wall_pts = wall.inlier_points
        all_wall_points.append(wall_pts)

        bounds_info = compute_plane_bounds_and_spans(wall_pts)
        conf = compute_plane_confidence(wall.inlier_count, wall.rmse_m)

        wall_entry = {
            "id": f"wall_{w_idx + 1:02d}",
            "type": "wall",
            "plane": {
                "a": wall.plane_model[0],
                "b": wall.plane_model[1],
                "c": wall.plane_model[2],
                "d": wall.plane_model[3],
            },
            "normal": [wall.plane_model[0], wall.plane_model[1], wall.plane_model[2]],
            "centroid": bounds_info["centroid"],
            "bounds": bounds_info["bounds"],
            "spans_m": bounds_info["spans"],
            "inlier_count": wall.inlier_count,
            "mean_residual_m": wall.mean_residual_m,
            "rmse_m": wall.rmse_m,
            "confidence": conf,
        }
        walls_json_list.append(wall_entry)

        # Color inliers if indices map directly
        # Distance-based coloring for merged points to ensure full debug coverage
        a, b, c, d = wall.plane_model
        dists = np.abs(points[:, 0] * a + points[:, 1] * b + points[:, 2] * c + d)
        w_inliers = (dists <= config.distance_threshold_m) & is_vert & (~classified_mask)
        debug_colors[w_inliers] = w_color
        classified_mask[w_inliers] = True

    unclassified_count = int(np.count_nonzero(~classified_mask))
    classified_count = int(np.count_nonzero(classified_mask))

    # 8. Export PLY files
    # Floor PLY
    if floor_detected:
        write_ply(
            os.path.join(config.output_dir, "floor.ply"),
            floor_plane.inlier_points,
            np.tile([30, 110, 240], (len(floor_plane.inlier_points), 1)).astype(np.uint8),
        )

    # Ceiling PLY
    if ceiling_detected:
        write_ply(
            os.path.join(config.output_dir, "ceiling.ply"),
            ceiling_plane.inlier_points,
            np.tile([40, 220, 240], (len(ceiling_plane.inlier_points), 1)).astype(np.uint8),
        )
    else:
        # Write empty placeholder file explaining absence
        with open(os.path.join(config.output_dir, "ceiling.ply"), "w") as f:
            f.write(f"ply\ncomment ceiling not detected: {ceiling_reason}\nelement vertex 0\nend_header\n")

    # Walls PLY
    if all_wall_points:
        merged_wall_pts = np.concatenate(all_wall_points, axis=0)
        write_ply(os.path.join(config.output_dir, "walls.ply"), merged_wall_pts)

    # Unclassified PLY
    unclassified_pts = points[~classified_mask]
    write_ply(os.path.join(config.output_dir, "unclassified.ply"), unclassified_pts)

    # Debug PLY
    debug_ply_path = os.path.join(config.output_dir, "structure_debug.ply")
    write_ply(debug_ply_path, points, debug_colors)
    print(f"Saved color-coded debug point cloud: {debug_ply_path}")

    # 9. Structure JSON
    structure_json = {
        "scan_id": config.scan_id,
        "random_seed": config.random_seed,
        "deterministic_mode": config.deterministic_mode,
        "floor": {
            "detected": floor_detected,
            "plane": {
                "a": floor_plane.plane_model[0],
                "b": floor_plane.plane_model[1],
                "c": floor_plane.plane_model[2],
                "d": floor_plane.plane_model[3],
            } if floor_detected else None,
            "mean_y": floor_y,
            "inlier_count": floor_plane.inlier_count if floor_detected else 0,
            "rmse_m": floor_plane.rmse_m if floor_detected else None,
            "confidence": compute_plane_confidence(floor_plane.inlier_count, floor_plane.rmse_m) if floor_detected else 0.0,
        },
        "ceiling": {
            "detected": ceiling_detected,
            "failure_reason": ceiling_reason,
            "plane": {
                "a": ceiling_plane.plane_model[0],
                "b": ceiling_plane.plane_model[1],
                "c": ceiling_plane.plane_model[2],
                "d": ceiling_plane.plane_model[3],
            } if ceiling_detected else None,
            "mean_y": ceiling_y,
            "estimated_clear_height_m": ceiling_height_m,
            "inlier_count": ceiling_plane.inlier_count if ceiling_detected else 0,
            "rmse_m": ceiling_plane.rmse_m if ceiling_detected else None,
        },
        "walls": walls_json_list,
        "rejected_candidates": rejected_log,
    }

    structure_json_path = os.path.join(config.output_dir, "structure.json")
    with open(structure_json_path, "w", encoding="utf-8") as f:
        json.dump(structure_json, f, indent=2)
    print(f"Saved structural geometry JSON: {structure_json_path}")

    # 10. Extraction stats JSON
    elapsed_time = round(time.time() - start_time, 2)
    stats_json = {
        "scan_id": config.scan_id,
        "random_seed": config.random_seed,
        "deterministic_mode": config.deterministic_mode,
        "input_points": total_input_points,
        "floor_detected": floor_detected,
        "floor_inliers": floor_plane.inlier_count if floor_detected else 0,
        "mean_floor_residual_m": floor_plane.mean_residual_m if floor_detected else None,
        "floor_rmse_m": floor_plane.rmse_m if floor_detected else None,
        "ceiling_detected": ceiling_detected,
        "ceiling_inliers": ceiling_plane.inlier_count if ceiling_detected else 0,
        "ceiling_failure_reason": ceiling_reason,
        "estimated_ceiling_height_m": ceiling_height_m,
        "mean_ceiling_residual_m": ceiling_plane.mean_residual_m if ceiling_detected else None,
        "wall_candidates": len(vert_planes),
        "walls_accepted": len(accepted_walls),
        "walls_rejected": len(rejected_log),
        "walls_final_merged": len(merged_walls),
        "structural_points": classified_count,
        "unclassified_points": unclassified_count,
        "processing_time_seconds": elapsed_time,
    }

    stats_json_path = os.path.join(config.output_dir, "extraction_stats.json")
    with open(stats_json_path, "w", encoding="utf-8") as f:
        json.dump(stats_json, f, indent=2)
    print(f"Saved extraction statistics: {stats_json_path}")
    print(f"Structural extraction finished in {elapsed_time}s.")
    print("-" * 60)

    return stats_json
