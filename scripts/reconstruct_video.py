"""CLI entry point for Stage 7 RGB Video Reconstruction.

Usage:
    python3 -m scripts.reconstruct_video --input path/to/video.mp4 --capture-id video_room_01
    python3 -m scripts.reconstruct_video --archive "sample data/single_room.zip" --scan c00a170fe1 --capture-id video_single_room
    python3 -m scripts.reconstruct_video --archive "sample data/single_scan_with_ceiling.zip" --scan c7d28f72c6 --capture-id video_multi_room --multiroom

1. Why this file exists:
   Provides high-level CLI interface for executing Stage 7 end-to-end video reconstruction.
   Accepts any .mp4 or .mov video, extracts keyframes, solves visual SfM and metric scale,
   fuses 3D point cloud, and drives downstream shared geometry extraction.

2. Pipeline stage:
   Stage 7 (Video Tier - CLI Runner).

3. Inputs:
   Path to video file or path to zip archive + scan ID.

4. Outputs:
   `outputs/<capture_id>/video/` hierarchy and diagnostic SVGs.

5. Coordinates and units:
   Keyframes use display-normalized pixel coordinates; trajectory and cloud diagnostics use
   right-handed metric world coordinates and seconds.

6. Assumptions and dependencies:
   Python stdlib, NumPy, OpenCV, and the Stage 7 backend pipeline. Archives contain
   ``<scan>/rgb.mp4``; no other member is extracted or read.

7. Failure modes and first debugging points:
   Missing inputs exit nonzero; reconstruction failures are reported by backend status. Inspect
   ``video_metadata.json``, ``sfm/sfm_stats.json``, and ``reconstruction_stats.json`` first.
"""

import sys
import os
import argparse
import tempfile
import zipfile
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
import numpy as np
import cv2

# Ensure repo root is on sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.app.pipelines.video.pipeline import run_video_pipeline


def generate_keyframes_contact_sheet(
    keyframes_dir: Path,
    output_path: Path,
    max_images: int = 16,
    grid_cols: int = 4,
) -> None:
    """Render a JPEG montage of extracted display-normalized RGB keyframes.

    Parameters are the keyframe directory, output JPEG path, image cap, and column count. Returns
    None; output dimensions are pixels and no world coordinates are used. Missing/undecodable
    images are skipped, and an empty directory produces no file. Inspect source JPEGs when tiles
    are blank, misoriented, or unexpectedly truncated in time.
    """
    img_files = sorted(list(keyframes_dir.glob("*.jpg")))[:max_images]
    if not img_files:
        return

    tile_w, tile_h = 320, 240
    n_tiles = len(img_files)
    n_rows = (n_tiles + grid_cols - 1) // grid_cols

    sheet = np.zeros((n_rows * tile_h, grid_cols * tile_w, 3), dtype=np.uint8)

    for idx, img_p in enumerate(img_files):
        r = idx // grid_cols
        c = idx % grid_cols
        img = cv2.imread(str(img_p))
        if img is None:
            continue
        thumb = cv2.resize(img, (tile_w, tile_h))
        # Overlay label
        label = f"KF {idx:02d}: {img_p.stem}"
        cv2.putText(thumb, label, (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

        sheet[r * tile_h : (r + 1) * tile_h, c * tile_w : (c + 1) * tile_w] = thumb

    cv2.imwrite(str(output_path), sheet, [cv2.IMWRITE_JPEG_QUALITY, 90])


def generate_trajectory_svg(
    poses_json_path: Path,
    output_svg_path: Path,
    title: str = "Reconstructed Visual Camera Trajectory",
) -> None:
    """Render a metric XZ bird's-eye trajectory SVG from scaled camera poses.

    Parameters identify the trajectory JSON, SVG destination, and title; returns None. Pose
    translations are expected in meters as ``t_vec=[x,y,z]``. Missing files or fewer than two
    usable poses produce no SVG. Inspect ``video_trajectory.json`` for malformed vectors or scale
    explosions when rendering is absent or compressed.
    """
    if not poses_json_path.exists():
        return

    with open(poses_json_path, "r", encoding="utf-8") as f:
        poses = json.load(f)

    if len(poses) < 2:
        return

    coords = [(p["t_vec"][0], p["t_vec"][2]) for p in poses if len(p.get("t_vec", [])) >= 3]
    if len(coords) < 2:
        return

    xs, zs = zip(*coords)
    min_x, max_x = min(xs), max(xs)
    min_z, max_z = min(zs), max(zs)

    span_x = max(max_x - min_x, 0.5)
    span_z = max(max_z - min_z, 0.5)

    svg_w, svg_h = 600, 600
    margin = 60

    def to_svg(x: float, z: float):
        sx = margin + (x - min_x) / span_x * (svg_w - 2 * margin)
        sz = margin + (z - min_z) / span_z * (svg_h - 2 * margin)
        return sx, sz

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {svg_w} {svg_h}" width="{svg_w}" height="{svg_h}" style="background:#0f172a;">',
        f'  <text x="{margin}" y="35" fill="#f8fafc" font-size="16" font-weight="bold">{title}</text>',
        f'  <text x="{margin}" y="55" fill="#94a3b8" font-size="12">Span: {span_x:.2f}m x {span_z:.2f}m | {len(poses)} Keyframes</text>',
    ]

    # Draw trajectory path
    path_d = []
    for i, (x, z) in enumerate(coords):
        sx, sz = to_svg(x, z)
        cmd = "M" if i == 0 else "L"
        path_d.append(f"{cmd} {sx:.1f} {sz:.1f}")

    lines.append(f'  <path d="{" ".join(path_d)}" fill="none" stroke="#38bdf8" stroke-width="3" stroke-linecap="round"/>')

    # Draw camera nodes
    for i, (x, z) in enumerate(coords):
        sx, sz = to_svg(x, z)
        color = "#22c55e" if i == 0 else ("#ef4444" if i == len(coords) - 1 else "#f59e0b")
        lines.append(f'  <circle cx="{sx:.1f}" cy="{sz:.1f}" r="5" fill="{color}" stroke="#ffffff" stroke-width="1"/>')

    lines.append('</svg>')

    with open(output_svg_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def generate_scale_consistency_svg(
    metric_scale_path: Path,
    output_svg_path: Path,
) -> None:
    """Render the SfM-to-meter scale estimate and MAD evidence as an SVG.

    Parameters identify ``metric_scale.json`` and the SVG destination; returns None. Scale uses
    meters per arbitrary SfM unit and MAD uses the same ratio units. A missing report produces no
    output. Inspect correspondence and inlier fields when status or chart fill is unexpected.
    """
    if not metric_scale_path.exists():
        return

    with open(metric_scale_path, "r", encoding="utf-8") as f:
        scale_data = json.load(f)

    scale = scale_data.get("scale_factor", 1.0)
    mad = scale_data.get("mad", 0.1)
    status = scale_data.get("status", "GOOD")
    pts = scale_data.get("supporting_points", 0)

    svg_w, svg_h = 500, 260
    status_color = "#22c55e" if status == "GOOD" else ("#f59e0b" if status == "PROVISIONAL" else "#ef4444")

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {svg_w} {svg_h}" width="{svg_w}" height="{svg_h}" style="background:#0f172a;">',
        '  <text x="30" y="35" fill="#f8fafc" font-size="16" font-weight="bold">METRIC SCALE RECOVERY</text>',
        f'  <text x="30" y="65" fill="{status_color}" font-size="14" font-weight="bold">Status: {status}</text>',
        f'  <text x="30" y="95" fill="#94a3b8" font-size="13">Scale Multiplier: <tspan fill="#38bdf8" font-weight="bold">{scale:.4f} m/unit</tspan></text>',
        f'  <text x="30" y="125" fill="#94a3b8" font-size="13">Median Absolute Deviation (MAD): <tspan fill="#f8fafc">{mad:.4f}</tspan></text>',
        f'  <text x="30" y="155" fill="#94a3b8" font-size="13">Supporting 3D-Depth Inliers: <tspan fill="#f8fafc">{pts} points</tspan></text>',
        f'  <rect x="30" y="180" width="{svg_w - 60}" height="40" rx="6" fill="#1e293b" stroke="#334155" stroke-width="1"/>',
        f'  <rect x="30" y="180" width="{int((svg_w - 60) * min(1.0, scale_data.get("inlier_ratio", 1.0)))}" height="40" rx="6" fill="{status_color}" opacity="0.35"/>',
        f'  <text x="45" y="205" fill="#f8fafc" font-size="12">Inlier Ratio: {scale_data.get("inlier_ratio", 1.0)*100:.1f}%</text>',
        '</svg>'
    ]

    with open(output_svg_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def main():
    """Parse Stage 7 CLI inputs, run reconstruction, and emit visual diagnostics.

    Input is either one standalone MP4/MOV or one archive member selected by scan ID. Output is a
    metric Stage 7 directory plus terminal summary; coordinates/units follow ``run_video_pipeline``.
    The archive path extracts only RGB video into a temporary directory. Invalid arguments and
    missing members exit nonzero; inspect the printed input/output paths and reconstruction stats.
    """
    parser = argparse.ArgumentParser(description="Stage 7 Video Reconstruction CLI")
    parser.add_argument("--input", type=str, default=None, help="Path to input .mp4 or .mov video file")
    parser.add_argument("--archive", type=str, default=None, help="Path to capture zip archive")
    parser.add_argument("--scan", type=str, default=None, help="Scan ID inside archive (e.g. c00a170fe1, c7d28f72c6)")
    parser.add_argument("--capture-id", type=str, default="video_recon_01", help="Unique capture identifier")
    parser.add_argument("--output-dir", type=str, default=None, help="Destination directory for outputs")
    parser.add_argument("--multiroom", action="store_true", help="Enable multi-room property segmentation")
    parser.add_argument("--max-keyframes", type=int, default=40, help="Maximum keyframes to extract and process")
    args = parser.parse_args()

    video_source_path = None
    temp_dir_obj = None

    if args.input:
        video_source_path = Path(args.input)
    elif args.archive and args.scan:
        arc_p = Path(args.archive)
        if not arc_p.exists():
            print(f"Error: Archive not found: {arc_p}")
            sys.exit(1)
        temp_dir_obj = tempfile.TemporaryDirectory()
        extracted_mp4 = Path(temp_dir_obj.name) / "video.mp4"
        with zipfile.ZipFile(arc_p, "r") as zf:
            video_rel = f"{args.scan}/rgb.mp4"
            if video_rel not in zf.namelist():
                print(f"Error: {video_rel} not found in {arc_p}")
                sys.exit(1)
            with open(extracted_mp4, "wb") as f:
                f.write(zf.read(video_rel))
        video_source_path = extracted_mp4
    else:
        print("Error: Must provide either --input <video.mp4> or --archive <zip> --scan <id>")
        sys.exit(1)

    out_base = Path(args.output_dir) if args.output_dir else Path("outputs") / args.capture_id / "video"

    try:
        results = run_video_pipeline(
            video_path=video_source_path,
            output_base_dir=out_base,
            capture_id=args.capture_id,
            max_keyframes=args.max_keyframes,
            run_multiroom=args.multiroom,
        )

        # Generate visual debug artifacts
        generate_keyframes_contact_sheet(
            keyframes_dir=out_base / "keyframes",
            output_path=out_base / "video_keyframes_contact_sheet.jpg",
        )
        generate_trajectory_svg(
            poses_json_path=out_base / "video_trajectory.json",
            output_svg_path=out_base / "sfm_trajectory.svg",
        )
        generate_scale_consistency_svg(
            metric_scale_path=out_base / "metric_scale.json",
            output_svg_path=out_base / "scale_consistency.svg",
        )

        st = results.get("overall_status") or results.get("status", "UNKNOWN")
        reg_k = results.get("registered_keyframes", 0)
        tot_k = results.get("extracted_keyframes", 0)
        sc_f = results.get("metric_scale_factor")
        sc_str = f"{sc_f:.4f} m/unit" if sc_f is not None else "N/A"
        sc_st = results.get("metric_scale_status", "N/A")
        pts = results.get("filtered_points_count", 0)
        walls = results.get("walls_detected", 0)
        area = results.get("floor_area_sqm", 0.0) or 0.0
        perim = results.get("perimeter_m", 0.0) or 0.0

        print("\n" + "=" * 60)
        print("STAGE 7 VIDEO RECONSTRUCTION COMPLETE")
        print("=" * 60)
        print(f"Status:             {st}")
        print(f"Registered Frames:  {reg_k} / {tot_k}")
        print(f"Metric Scale:       {sc_str} (Status: {sc_st})")
        print(f"Point Count:        {pts}")
        print(f"Walls Detected:     {walls}")
        print(f"Floor Area:         {area:.2f} m²")
        print(f"Perimeter:          {perim:.2f} m")
        print(f"Output Directory:   {out_base}")
        print("=" * 60)

    finally:
        if temp_dir_obj is not None:
            temp_dir_obj.cleanup()


if __name__ == "__main__":
    main()
