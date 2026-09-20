"""Stage 8 metric depth inference, robust scale recovery, and scale diagnostics.

1. Why this file exists:
   Converts arbitrary-scale photo SfM into metric geometry without architectural size priors.
2. Pipeline stage:
   Stage 8, Steps 9-12 (metric depth, masking, absolute scale, and pose scaling).
3. Inputs:
   Registered normalized photos, SfM poses/points, and self-calibrated intrinsics.
4. Outputs:
   Cached metric depth maps, masks, ``metric_scale.json``, and ``scale_consistency.svg``.
5. Coordinate system:
   Depth uses OpenCV camera Z-forward; SfM world remains arbitrary orientation until fusion.
6. Units:
   Depth and scaled translations are meters; scale is meters per SfM unit.
7. Dependencies:
   Stage 7 Depth Anything, scale estimation, NumPy, and JSON/SVG output.
8. Assumptions:
   The indoor metric model is locally useful and SfM/depth projection conventions agree.
9. Failure modes:
   Model load errors, missing registered photos, too few valid correspondences, or unstable scale.
10. First debugging points:
   Inspect cached depth arrays, quality masks, ``metric_scale.json``, and ratio distribution SVG.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np

from backend.app.models.video import MetricScaleEstimate
from backend.app.pipelines.photo.models import PhotoCaptureManifest
from backend.app.pipelines.video.contract import VideoCameraPose, VideoIntrinsics
from backend.app.pipelines.video.depth import predict_metric_depth
from backend.app.pipelines.video.scale import apply_metric_scale, estimate_metric_scale


def render_scale_consistency_svg(estimate: MetricScaleEstimate, output_path: Path) -> None:
    """Render raw scale ratios and the accepted global median for debugging.

    Parameters:
        estimate: Robust metric scale result with raw meters-per-SfM-unit observations.
        output_path: SVG destination.
    Returns:
        None; writes one dependency-free diagnostic.
    Coordinates/units:
        Horizontal index is correspondence order; vertical values are meters per SfM unit.
    Assumptions:
        Raw ratios are diagnostics and may include rejected outliers.
    Failure/debugging:
        Empty observations create an annotated empty plot; inspect track/depth projection first.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    ratios = np.asarray(estimate.raw_scale_ratios, dtype=np.float64)
    points = ""
    if len(ratios):
        low, high = float(np.min(ratios)), float(np.max(ratios))
        span = max(high - low, 1e-9)
        xs = np.linspace(45.0, 755.0, len(ratios))
        ys = 330.0 - 260.0 * (ratios - low) / span
        points = "".join(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="2" fill="#355c7d"/>' for x, y in zip(xs, ys))
        median_y = 330.0 - 260.0 * (estimate.scale_factor - low) / span
        points += f'<line x1="40" y1="{median_y:.1f}" x2="760" y2="{median_y:.1f}" stroke="#c94c4c" stroke-width="2"/>'
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="800" height="380">'
        '<rect width="800" height="380" fill="#faf8f2"/>'
        f'<text x="25" y="30" font-size="18">Metric scale consistency: {estimate.status}</text>'
        f'<text x="25" y="52" font-size="13">scale={estimate.scale_factor:.6f}, MAD={estimate.mad:.6f}, inliers={estimate.inlier_count}/{estimate.total_correspondences}</text>'
        f'{points}</svg>'
    )
    output_path.write_text(svg, encoding="utf-8")


def run_photo_metric_depth_and_scale(
    manifest: PhotoCaptureManifest,
    poses: List[VideoCameraPose],
    sparse_points: List[dict],
    intrinsics: VideoIntrinsics,
    output_dir: Path,
) -> Tuple[Dict[int, np.ndarray], Dict[int, np.ndarray], Dict[int, Path], MetricScaleEstimate, List[VideoCameraPose], List[dict]]:
    """Infer per-view metric depth, estimate robust scale, and scale only translations/points.

    Parameters:
        manifest: Selected normalized photo records.
        poses: Registered arbitrary-scale SfM camera poses.
        sparse_points: Arbitrary-scale SfM tie-point records.
        intrinsics: SfM/EXIF-derived pinhole intrinsics in processing-image pixels.
        output_dir: Room photo output directory.
    Returns:
        Depth maps, masks, keyed image paths, scale estimate, metric poses, and metric sparse points.
    Coordinates/units:
        Depth/camera translation outputs are meters; rotations remain unchanged and unscaled.
    Assumptions:
        SfM keyframe IDs map to deterministic normalized ``photo_XX`` IDs.
    Failure/debugging:
        Missing image IDs are skipped; a failed scale remains explicit and callers must not claim
        metric geometry. Inspect pose IDs and manifest records when no depth is produced.
    """
    output_dir = Path(output_dir)
    depth_dir = output_dir / "depth"
    records = {record.photo_id: record for record in manifest.selected_photos}
    depth_maps: Dict[int, np.ndarray] = {}
    depth_masks: Dict[int, np.ndarray] = {}
    image_paths: Dict[int, Path] = {}
    for pose in poses:
        record = records.get(pose.keyframe_id)
        if record is None:
            continue
        image_path = Path(record.image_path)
        depth, mask = predict_metric_depth(image_path=image_path, output_depth_dir=depth_dir)
        depth_maps[pose.keyframe_id] = depth
        depth_masks[pose.keyframe_id] = mask
        image_paths[pose.keyframe_id] = image_path
    estimate = estimate_metric_scale(
        sparse_points=sparse_points,
        poses=poses,
        depth_maps=depth_maps,
        intrinsics=intrinsics,
        output_dir=output_dir,
        depth_masks=depth_masks,
    )
    metric_poses, metric_points = apply_metric_scale(poses, sparse_points, estimate.scale_factor)
    render_scale_consistency_svg(estimate, output_dir / "scale_consistency.svg")
    return depth_maps, depth_masks, image_paths, estimate, metric_poses, metric_points
