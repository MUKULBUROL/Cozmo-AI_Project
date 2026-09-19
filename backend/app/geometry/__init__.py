"""Geometry engine for architectural structural plane extraction and metrics."""

from .preprocessing import load_and_validate_point_cloud
from .normals import estimate_point_normals, split_horizontal_vertical_masks
from .plane_detection import fit_single_plane_ransac, extract_planes_iterative, DetectedPlane
from .plane_classification import (
    classify_floor,
    classify_ceiling,
    filter_wall_candidates,
    merge_parallel_walls,
)
from .metrics import compute_plane_residuals, compute_plane_bounds_and_spans, compute_plane_confidence
from .structural_extraction import StructuralConfig, extract_structure, write_ply
from .wall_quality import evaluate_wall_quality
from .projection_2d import (
    project_plane_to_2d_line,
    compute_finite_extents,
    project_walls_to_2d,
    merge_near_duplicate_2d_lines,
)
from .line_geometry import (
    intersect_2d_lines,
    compute_segment_extension_distance,
    point_to_segment_distance,
    angle_between_lines_deg,
)
from .corner_detection import detect_candidate_corners
from .polygon_builder import build_connectivity_graph, find_simple_cycles, extract_room_polygon
from .polygon_validation import validate_room_polygon, compute_polygon_quality_metrics
from .room_footprint import run_stage3_pipeline, render_floorplan_debug_svg

__all__ = [
    "load_and_validate_point_cloud",
    "estimate_point_normals",
    "split_horizontal_vertical_masks",
    "fit_single_plane_ransac",
    "extract_planes_iterative",
    "DetectedPlane",
    "classify_floor",
    "classify_ceiling",
    "filter_wall_candidates",
    "merge_parallel_walls",
    "compute_plane_residuals",
    "compute_plane_bounds_and_spans",
    "compute_plane_confidence",
    "StructuralConfig",
    "extract_structure",
    "write_ply",
    "evaluate_wall_quality",
    "project_plane_to_2d_line",
    "compute_finite_extents",
    "project_walls_to_2d",
    "merge_near_duplicate_2d_lines",
    "intersect_2d_lines",
    "compute_segment_extension_distance",
    "point_to_segment_distance",
    "angle_between_lines_deg",
    "detect_candidate_corners",
    "build_connectivity_graph",
    "find_simple_cycles",
    "extract_room_polygon",
    "validate_room_polygon",
    "compute_polygon_quality_metrics",
    "run_stage3_pipeline",
    "render_floorplan_debug_svg",
]
