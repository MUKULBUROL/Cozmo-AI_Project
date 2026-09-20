"""Headless inspection and cross-tier reporting for Stage 7 video reconstruction.

Usage:
    python3 -m scripts.view_video_reconstruction --capture-id video_single_room --headless
    python3 -m scripts.view_video_reconstruction --capture-id video_single_room --lidar-scan c00a170fe1 --headless

1. Why this file exists:
   Produces standardized, machine-readable and human-readable terminal reports summarizing
   video reconstruction quality, metric scale recovery, structural outputs, and cross-tier
   agreement against LiDAR scans without assuming LiDAR is ground truth.

2. Pipeline stage:
   Stage 7 (Video Tier - Diagnostics and Reporting).

3. Inputs:
   Video reconstruction JSON under ``outputs/<capture>/video`` and optional existing LiDAR
   measurement/opening JSON used only after independent video reconstruction.

4. Outputs:
   Terminal diagnostics plus ``cross_tier_comparison.json`` and
   ``cross_tier_comparison.md``. All comparison artifacts are labeled cross-tier agreement,
   never ground-truth accuracy.

5. Coordinates and units:
   XZ floor-plan coordinates in meters, lengths in meters, and areas in square meters.

6. Assumptions and dependencies:
   Python standard-library JSON/path handling; source tiers have already completed independently.

7. Failure modes and first debugging points:
   Missing reconstruction stats prevent reporting. Missing or failed video polygons produce
   explicit unavailable comparisons; inspect ``reconstruction_stats.json`` and
   ``floorplan_geometry/polygon_stats.json`` first.
"""

import sys
import os
import argparse
import json
from pathlib import Path
from typing import Dict, Any, Optional

# Ensure repo root is on sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def print_headless_summary(capture_id: str, lidar_scan_id: Optional[str] = None) -> None:
    """Print video diagnostics and persist an optional LiDAR agreement comparison.

    Parameters:
        capture_id: Video output identifier under ``outputs``.
        lidar_scan_id: Existing LiDAR output identifier used only for post-hoc evaluation.

    Returns:
        None. Writes JSON/Markdown comparison artifacts beside the video reconstruction.

    Units/coordinates:
        Floor area is m2 and perimeter is m in each tier's XZ floor-plan frame.

    Assumptions:
        Video reconstruction is already complete and independent of LiDAR artifacts.

    Failure conditions/debugging:
        Missing video stats prints an error and returns. Missing LiDAR measurements skips the
        comparison. A failed video polygon is recorded as unavailable rather than as zero error.
    """
    video_dir = Path("outputs") / capture_id / "video"
    stats_file = video_dir / "reconstruction_stats.json"

    if not stats_file.exists():
        # Check direct outputs/<capture_id>/reconstruction_stats.json
        stats_file = Path("outputs") / capture_id / "reconstruction_stats.json"
        if not stats_file.exists():
            print(f"Error: Reconstruction stats not found for capture '{capture_id}' in outputs/")
            return

    with open(stats_file, "r", encoding="utf-8") as f:
        stats = json.load(f)

    print("=" * 40)
    print("VIDEO RECONSTRUCTION")
    print("=" * 40)
    print(f"Input video:            {stats.get('input_video', 'N/A')}")
    print(f"Frames:                 {stats.get('total_video_frames', 'N/A')}")
    print(f"Selected keyframes:     {stats.get('extracted_keyframes', 'N/A')}")
    print(f"SfM registered:         {stats.get('registered_keyframes', 'N/A')} / {stats.get('extracted_keyframes', 'N/A')}")
    reproj = stats.get('mean_reprojection_error_px') or 0.0
    print(f"Reprojection error:     {reproj:.2f} px")
    print("")
    print(f"Metric depth model:     depth-anything/Depth-Anything-V2-Metric-Indoor-Small-hf")
    scale_f = stats.get('metric_scale_factor')
    scale_str = f"{scale_f:.4f} m/unit" if scale_f is not None else "N/A"
    print(f"Metric scale:           {scale_str}")
    scale_unc = stats.get('metric_scale_uncertainty_rel')
    unc_str = f"±{scale_unc*100:.1f}%" if scale_unc is not None else "N/A"
    print(f"Scale uncertainty:      {unc_str}")
    print("")
    print(f"Metric cloud points:    {stats.get('filtered_points_count', 'N/A')}")
    print(f"Walls detected:         {stats.get('walls_detected', 'N/A')}")
    print(f"Polygon valid:          {'YES' if stats.get('polygon_valid', False) else 'NO'}")
    print("")
    f_area = stats.get('floor_area_sqm') or 0.0
    f_perim = stats.get('perimeter_m') or 0.0
    print(f"Floor area:             {f_area:.2f} m²")
    print(f"Perimeter:              {f_perim:.2f} m")
    print("")
    print("Reconstruction status:")
    print(f"{stats.get('overall_status', 'PROVISIONAL')}")
    print("")
    print("Benchmark accuracy:")
    print("NOT VERIFIED (pending laser/tape ground truth)")
    print("=" * 40)

    # -------------------------------------------------------------
    # Cross-Tier Comparison: VIDEO vs LiDAR (if LiDAR data exists)
    # -------------------------------------------------------------
    lidar_dir = Path("outputs") / (lidar_scan_id or capture_id)
    lidar_measurements_file = lidar_dir / "measurements" / "measurements.json"

    if lidar_measurements_file.exists():
        with open(lidar_measurements_file, "r", encoding="utf-8") as f:
            lidar_m = json.load(f)

        lidar_area = lidar_m.get("room_dimensions", {}).get("area", {}).get("value", 0.0)
        lidar_perim = lidar_m.get("room_dimensions", {}).get("perimeter", {}).get("value", 0.0)

        vid_area = stats.get("floor_area_sqm", 0.0)
        vid_perim = stats.get("perimeter_m", 0.0)

        polygon_usable = bool(stats.get("polygon_valid", False))
        diff_area = abs(vid_area - lidar_area) if polygon_usable else None
        rel_diff_area = (diff_area / max(lidar_area, 0.01)) * 100.0 if diff_area is not None else None
        diff_perim = abs(vid_perim - lidar_perim) if polygon_usable else None
        rel_diff_perim = (diff_perim / max(lidar_perim, 0.01)) * 100.0 if diff_perim is not None else None

        comparison = {
            "label": "CROSS-TIER AGREEMENT, NOT GROUND-TRUTH ACCURACY",
            "video_capture_id": capture_id,
            "lidar_scan_id": lidar_scan_id or capture_id,
            "video_polygon_status": stats.get("polygon_status", "FAILED"),
            "metrics": {
                "floor_area_sqm": {
                    "video": vid_area if polygon_usable else None,
                    "lidar": lidar_area,
                    "absolute_difference": diff_area,
                    "relative_difference_percent": rel_diff_area,
                    "status": "available" if polygon_usable else "unavailable_video_polygon_failed",
                },
                "perimeter_m": {
                    "video": vid_perim if polygon_usable else None,
                    "lidar": lidar_perim,
                    "absolute_difference": diff_perim,
                    "relative_difference_percent": rel_diff_perim,
                    "status": "available" if polygon_usable else "unavailable_video_polygon_failed",
                },
                "corresponding_wall_lengths": {
                    "status": "unavailable_no_valid_video_wall_correspondence"
                },
                "wall_orientations": {
                    "status": "unavailable_no_valid_video_wall_correspondence"
                },
                "opening_widths_positions": {
                    "status": "unavailable_video_opening_measurement_not_supported_for_failed_polygon"
                },
            },
        }
        with open(video_dir / "cross_tier_comparison.json", "w", encoding="utf-8") as f:
            json.dump(comparison, f, indent=2)

        markdown = [
            "# Cross-Tier Comparison",
            "",
            "**CROSS-TIER AGREEMENT, NOT GROUND-TRUTH ACCURACY**",
            "",
            f"- Video capture: `{capture_id}`",
            f"- LiDAR scan: `{lidar_scan_id or capture_id}`",
            f"- Video polygon status: `{comparison['video_polygon_status']}`",
            "- Floor area comparison: unavailable because the video polygon failed validation"
            if not polygon_usable else f"- Floor area difference: {diff_area:.3f} m2 ({rel_diff_area:.1f}%)",
            "- Perimeter comparison: unavailable because the video polygon failed validation"
            if not polygon_usable else f"- Perimeter difference: {diff_perim:.3f} m ({rel_diff_perim:.1f}%)",
            "- Wall and opening correspondence: unavailable without valid video boundary geometry",
            "",
            "This artifact evaluates agreement between two reconstructed tiers. It does not establish accuracy; tape or laser ground truth is required.",
        ]
        with open(video_dir / "cross_tier_comparison.md", "w", encoding="utf-8") as f:
            f.write("\n".join(markdown) + "\n")

        print("\n" + "=" * 60)
        print("CROSS-TIER AGREEMENT")
        print("LABEL: CROSS-TIER AGREEMENT, NOT GROUND-TRUTH ACCURACY")
        print("=" * 60)
        print(f"Dimension           Video Tier       LiDAR Tier       Difference       Rel Difference")
        print(f"--------------------------------------------------------------------------------------")
        if polygon_usable:
            print(f"Floor Area:         {vid_area:6.2f} m²        {lidar_area:6.2f} m²        {diff_area:6.2f} m²        {rel_diff_area:5.1f}%")
            print(f"Perimeter:          {vid_perim:6.2f} m         {lidar_perim:6.2f} m         {diff_perim:6.2f} m         {rel_diff_perim:5.1f}%")
        else:
            print("Floor Area:         unavailable - video polygon failed validation")
            print("Perimeter:          unavailable - video polygon failed validation")
        print("=" * 60)


def main():
    """Parse capture IDs and generate headless Stage 7 and optional cross-tier reports.

    Inputs are output identifiers rather than raw sensor data; generated comparison values use
    meters and square meters. Returns None. Missing reconstruction artifacts are reported without
    mutation; inspect the selected IDs and output hierarchy when no report is produced.
    """
    parser = argparse.ArgumentParser(description="View Stage 7 Video Reconstruction Summary")
    parser.add_argument("--capture-id", type=str, required=True, help="Video capture identifier")
    parser.add_argument("--lidar-scan", type=str, default=None, help="Optional corresponding LiDAR scan ID for cross-tier check")
    parser.add_argument("--headless", action="store_true", help="Run in headless terminal summary mode")
    args = parser.parse_args()

    print_headless_summary(args.capture_id, args.lidar_scan)


if __name__ == "__main__":
    main()
