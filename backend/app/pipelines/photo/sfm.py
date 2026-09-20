"""Stage 8 unordered-photo Structure-from-Motion and geometric coverage gates.

1. Why this file exists:
   Adapts the proven Stage 7 pycolmap implementation to 2-8 unordered still photographs and
   prevents a small textured patch from being reported as a room reconstruction.
2. Pipeline stage:
   Stage 8, Steps 6-8 (feature matching, SfM poses, and minimum geometric coverage).
3. Inputs:
   A normalized photo manifest whose image directory contains only independent still images.
4. Outputs:
   pycolmap sparse artifacts, ``photo_sfm_quality.json``, and ``sfm_cameras.svg``.
5. Coordinate system:
   Camera coordinates are OpenCV X-right/Y-down/Z-forward; SfM world is arbitrary right-handed.
6. Units:
   Sparse positions and baselines are arbitrary SfM units; reprojection error is pixels.
7. Dependencies:
   NumPy and the shared Stage 7 pycolmap SfM primitive.
8. Assumptions:
   Photo filenames encode IDs only, never sequence adjacency; all pairs must be considered.
9. Failure modes:
   Two-view underconstraint, insufficient parallax, texture starvation, fragmented components,
   weak point distribution, high reprojection error, or missing pycolmap.
10. First debugging points:
   Inspect ``sfm/sfm_stats.json``, ``photo_sfm_quality.json``, and ``sfm_cameras.svg``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np

from backend.app.pipelines.photo.models import PhotoCaptureManifest, PhotoSfmQuality
from backend.app.pipelines.video.contract import (
    SfMReconstructionReport,
    VideoCameraPose,
    VideoIntrinsics,
    VideoReconstructionStatus,
)
from backend.app.pipelines.video.sfm import run_visual_sfm as _run_visual_sfm


def photo_sfm_configuration(photo_count: int) -> Dict[str, Any]:
    """Return the fixed unordered-photo matching and calibration policy.

    Parameters:
        photo_count: Number of selected room stills, constrained to 2-8 by ingestion.
    Returns:
        Serializable policy including exhaustive matching and self-calibration defaults.
    Coordinates/units:
        No geometric coordinates; count is dimensionless.
    Assumptions:
        Exhaustive O(N²) pairing is practical for at most eight images.
    Failure/debugging:
        Raises ``ValueError`` outside 2-8. Inspect the ingestion manifest count.
    """
    if not 2 <= photo_count <= 8:
        raise ValueError(f"Photo SfM requires 2-8 selected images, received {photo_count}")
    return {
        "matching_strategy": "exhaustive",
        "pair_count": photo_count * (photo_count - 1) // 2,
        "camera_model": "SIMPLE_RADIAL",
        "camera_mode": "SINGLE",
        "intrinsics_fallback": "sfm_self_calibration",
        "uses_temporal_adjacency": False,
    }


def assess_photo_geometry(
    report: SfMReconstructionReport,
    poses: List[VideoCameraPose],
    sparse_points: List[Dict[str, Any]],
    connected_components: int,
) -> PhotoSfmQuality:
    """Evaluate whether recovered cameras and tie points cover more than a tiny visual region.

    Parameters:
        report: Shared SfM registration and reprojection statistics.
        poses: Registered world-from-camera poses in arbitrary SfM coordinates.
        sparse_points: Triangulated points with arbitrary-scale XYZ and observation tracks.
        connected_components: Number of pycolmap reconstructions produced.
    Returns:
        ``PhotoSfmQuality`` with explicit status and stable failure reason codes.
    Coordinates/units:
        Camera/point coordinates are arbitrary SfM units; all reported scores are dimensionless.
    Assumptions:
        PCA's first two axes approximate the dominant visible scene spread without gravity.
    Failure/debugging:
        Degenerate arrays return FAILED scores. Inspect registration, camera centers, and tracks.
    """
    reasons: List[str] = []
    centers = np.asarray([pose.t_vec for pose in poses], dtype=np.float64)
    points = np.asarray([point.get("xyz", []) for point in sparse_points], dtype=np.float64)
    valid_points = points.ndim == 2 and points.shape[1:] == (3,) and len(points) >= 3
    baseline_spread_ratio = 0.0
    distribution_score = 0.0
    diversity_score = 0.0

    if len(centers) >= 2 and valid_points:
        baseline = float(np.linalg.norm(centers.max(axis=0) - centers.min(axis=0)))
        scene_extent = float(np.linalg.norm(np.percentile(points, 95, axis=0) - np.percentile(points, 5, axis=0)))
        baseline_spread_ratio = baseline / max(scene_extent, 1e-9)
        centered = points - np.median(points, axis=0)
        _, _, axes = np.linalg.svd(centered, full_matrices=False)
        projected = centered @ axes[:2].T
        low = np.percentile(projected, 5, axis=0)
        high = np.percentile(projected, 95, axis=0)
        normalized = np.clip((projected - low) / np.maximum(high - low, 1e-9), 0.0, 0.9999)
        cells = np.floor(normalized * 4).astype(int)
        distribution_score = min(1.0, len({tuple(cell) for cell in cells}) / 8.0)
        steps = np.linalg.norm(np.diff(centers, axis=0), axis=1)
        diversity_score = float(np.clip(np.count_nonzero(steps > max(np.median(steps) * 0.25, 1e-6)) / max(len(steps), 1), 0.0, 1.0))

    image_coverage = float(np.clip(report.registration_ratio * min(report.track_length_mean / 3.0, 1.0), 0.0, 1.0))
    if report.registered_keyframes < 2:
        reasons.append("too_few_registered_images")
    if report.total_keyframes == 2:
        reasons.append("two_view_reconstruction_poorly_constrained")
    if report.registered_keyframes >= 2 and baseline_spread_ratio < 0.02:
        reasons.append("insufficient_baseline")
    if report.sparse_point_count < 30 or distribution_score < 0.25:
        reasons.append("weak_sparse_geometry")
    if report.mean_reprojection_error > 2.0:
        reasons.append("poor_reprojection_quality")
    if connected_components > 1:
        reasons.append("disconnected_sfm")
    if report.registered_keyframes < 2 or report.sparse_point_count < 15:
        status = "FAILED"
    elif reasons or report.status != VideoReconstructionStatus.GOOD:
        status = "PROVISIONAL"
    else:
        status = "GOOD"
    return PhotoSfmQuality(
        connected_components=connected_components,
        baseline_spread_ratio=baseline_spread_ratio,
        point_distribution_score=distribution_score,
        image_coverage_score=image_coverage,
        viewpoint_diversity_score=diversity_score,
        status=status,
        failure_reasons=reasons,
    )


def render_sfm_cameras_svg(poses: List[VideoCameraPose], output_path: Path) -> None:
    """Render arbitrary-scale camera centers for fast pose-spread debugging.

    Parameters:
        poses: Registered world-frame camera centers in arbitrary SfM units.
        output_path: SVG destination.
    Returns:
        None; writes a dependency-free diagnostic SVG.
    Coordinates/units:
        Displays PCA-projected arbitrary SfM coordinates, not metric floor-plan positions.
    Assumptions:
        PCA projection is visualization-only and must not be reused as gravity alignment.
    Failure/debugging:
        Empty poses produce an annotated SVG. Check pose extraction if no points appear.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    centers = np.asarray([pose.t_vec for pose in poses], dtype=np.float64)
    projected = np.zeros((len(poses), 2), dtype=np.float64)
    if len(centers) >= 2:
        centered = centers - centers.mean(axis=0)
        _, _, axes = np.linalg.svd(centered, full_matrices=False)
        projected = centered @ axes[:2].T
        span = np.maximum(np.ptp(projected, axis=0), 1e-9)
        projected = 40.0 + 520.0 * (projected - projected.min(axis=0)) / span
    circles = "".join(
        f'<circle cx="{point[0]:.1f}" cy="{point[1]:.1f}" r="6" fill="#d35f2d"/><text x="{point[0]+8:.1f}" y="{point[1]-8:.1f}" font-size="12">{pose.keyframe_id}</text>'
        for point, pose in zip(projected, poses)
    )
    polyline = " ".join(f"{point[0]:.1f},{point[1]:.1f}" for point in projected)
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="600" height="600" viewBox="0 0 600 600">'
        '<rect width="600" height="600" fill="#faf8f2"/><text x="24" y="28" font-size="18">SfM camera centers (PCA view, arbitrary scale)</text>'
        f'<polyline points="{polyline}" fill="none" stroke="#27374d" stroke-width="2"/>{circles}</svg>'
    )
    output_path.write_text(svg, encoding="utf-8")


def run_photo_sfm(
    manifest: PhotoCaptureManifest,
    output_sfm_dir: Path,
) -> Tuple[SfMReconstructionReport, List[VideoCameraPose], VideoIntrinsics, List[Dict[str, Any]], PhotoSfmQuality]:
    """Run exhaustive pycolmap reconstruction and photo-specific coverage validation.

    Parameters:
        manifest: Validated room manifest containing exactly 2-8 normalized stills.
        output_sfm_dir: Destination for COLMAP and diagnostic artifacts.
    Returns:
        Shared SfM report, poses, intrinsics, sparse points, and ``PhotoSfmQuality``.
    Coordinates/units:
        Outputs remain in arbitrary SfM world units with OpenCV camera convention.
    Assumptions:
        Every normalized image is in one directory and Stage 7 uses exhaustive matching for <=80.
    Failure/debugging:
        A two-photo set returns the shared honest failure rather than fabricating geometry. Missing
        pycolmap or mapping errors propagate; inspect configuration and SfM artifacts.
    """
    config = photo_sfm_configuration(manifest.selected_count)
    image_dirs = {Path(record.image_path).parent.resolve() for record in manifest.selected_photos}
    if len(image_dirs) != 1:
        raise ValueError(f"Normalized photo records must share one directory, found {image_dirs}")
    output_sfm_dir = Path(output_sfm_dir)
    report, poses, intrinsics, sparse_points = _run_visual_sfm(
        image_dir=image_dirs.pop(),
        output_sfm_dir=output_sfm_dir,
        capture_id=manifest.capture_id,
        camera_model=config["camera_model"],
    )
    components = len([path for path in output_sfm_dir.iterdir() if path.is_dir() and path.name.isdigit()]) if output_sfm_dir.exists() else 0
    quality = assess_photo_geometry(report, poses, sparse_points, components)
    with open(output_sfm_dir / "photo_sfm_quality.json", "w", encoding="utf-8") as quality_file:
        json.dump({"configuration": config, **quality.model_dump()}, quality_file, indent=2)
    render_sfm_cameras_svg(poses, output_sfm_dir.parent / "sfm_cameras.svg")
    return report, poses, intrinsics, sparse_points, quality
