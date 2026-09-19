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
]
