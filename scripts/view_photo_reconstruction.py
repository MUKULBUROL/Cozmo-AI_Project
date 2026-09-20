"""Stage 8 headless photo reconstruction and cross-tier agreement reporter.

1. Why this file exists: summarizes photo evidence and compares independent tiers without tuning.
2. Pipeline stage: Stage 8 diagnostics after reconstruction.
3. Inputs: existing photo statistics and optional independent LiDAR/video statistics.
4. Outputs: terminal report and ``cross_tier_comparison.json`` when references exist.
5. Coordinate system: each tier's independently reconstructed XZ floor plan.
6. Units: meters, square meters, pixels, and dimensionless uncertainty ratios.
7. Dependencies: Python standard-library JSON/path handling.
8. Assumptions: comparison sources completed independently before this command.
9. Failure modes: absent stats are reported, never interpreted as zero geometry.
10. First debugging points: inspect each tier's reconstruction stats and polygon status.
"""

import argparse
import json
from pathlib import Path
from typing import Any, Dict, Optional


def _load_json(path: Path) -> Optional[Dict[str, Any]]:
    """Load one JSON object or return ``None`` when the artifact does not exist.

    The path is repository/output-local and values retain their recorded units. Malformed JSON
    propagates to avoid hiding corrupt reports; inspect the named artifact first.
    """
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as source:
        return json.load(source)


def report_photo(capture_id: str, lidar_scan: Optional[str] = None, video_capture: Optional[str] = None) -> None:
    """Print Stage 8 evidence and persist post-hoc cross-tier agreement metrics.

    Parameters identify existing outputs only. Area/perimeter use m2/m in each independent frame;
    return is ``None``. Missing references are omitted and failed polygons remain unavailable.
    Inspect ``reconstruction_stats.json`` when the report cannot be generated.
    """
    photo_dir = Path("outputs") / capture_id / "photo"
    stats = _load_json(photo_dir / "reconstruction_stats.json")
    if stats is None:
        print(f"Error: photo reconstruction stats not found for {capture_id}")
        return
    print("=" * 48)
    print("PHOTO RECONSTRUCTION")
    print(f"Photos: {stats.get('input_photos', 'N/A')}")
    print(f"Registered: {stats.get('registered_photos', 0)}/{stats.get('input_photos', 0)}")
    print(f"Sparse points: {stats.get('sparse_point_count', 0)}")
    print(f"Scale: {stats.get('metric_scale_factor', 'N/A')}")
    print(f"Scale uncertainty: {stats.get('metric_scale_uncertainty_rel', 'N/A')}")
    print(f"Walls: {stats.get('walls_detected', 0)}")
    print(f"Polygon: {stats.get('polygon_status', 'FAILED')}")
    photo_usable = bool(stats.get("polygon_valid"))
    if photo_usable:
        print(f"Area: {stats.get('floor_area_sqm', 0.0)} m2")
        print(f"Perimeter: {stats.get('perimeter_m', 0.0)} m")
    else:
        print("Area: NOT_EVALUABLE")
        print("Perimeter: NOT_EVALUABLE")
    print(f"Status: {stats.get('overall_status', 'FAILED')}")
    print("Benchmark accuracy: NOT VERIFIED until laser/tape ground truth exists")
    references: Dict[str, Dict[str, Any]] = {}
    if lidar_scan:
        lidar = _load_json(Path("outputs") / lidar_scan / "measurements" / "measurements.json")
        if lidar:
            references["lidar"] = {
                "area": (
                    lidar.get("floor_area", {}).get("value")
                    or lidar.get("room_dimensions", {}).get("area", {}).get("value")
                ),
                "perimeter": (
                    lidar.get("perimeter", {}).get("value")
                    or lidar.get("room_dimensions", {}).get("perimeter", {}).get("value")
                ),
            }
    if video_capture:
        video = _load_json(Path("outputs") / video_capture / "video" / "reconstruction_stats.json")
        if video:
            video_usable = bool(video.get("polygon_valid"))
            references["video"] = {
                "area": video.get("floor_area_sqm") if video_usable else None,
                "perimeter": video.get("perimeter_m") if video_usable else None,
            }
    photo_values = {
        "area": stats.get("floor_area_sqm") if photo_usable else None,
        "perimeter": stats.get("perimeter_m") if photo_usable else None,
        "polygon_status": stats.get("polygon_status"),
        "status": "available" if photo_usable else "unavailable_photo_polygon_failed",
    }
    for reference in references.values():
        reference["area_difference"] = (
            abs(photo_values["area"] - reference["area"])
            if photo_values["area"] is not None and reference.get("area") is not None
            else None
        )
        reference["perimeter_difference"] = (
            abs(photo_values["perimeter"] - reference["perimeter"])
            if photo_values["perimeter"] is not None and reference.get("perimeter") is not None
            else None
        )
    comparison = {
        "label": "CROSS-TIER AGREEMENT, NOT GROUND-TRUTH ACCURACY",
        "photo": photo_values,
        "references": references,
    }
    if references:
        with open(photo_dir / "cross_tier_comparison.json", "w", encoding="utf-8") as target:
            json.dump(comparison, target, indent=2)
        print("CROSS-TIER AGREEMENT, NOT GROUND-TRUTH ACCURACY")
        for name, ref in references.items():
            area_str = f"{ref['area']} m2" if ref.get("area") is not None else "unavailable"
            perim_str = f"{ref['perimeter']} m" if ref.get("perimeter") is not None else "unavailable"
            print(f"Reference [{name.upper()}]: area={area_str}, perimeter={perim_str}")
            if photo_usable and ref.get("area_difference") is not None:
                print(f"  Difference [{name.upper()}]: area={ref['area_difference']} m2, perimeter={ref['perimeter_difference']} m")
            else:
                print(f"  Difference [{name.upper()}]: null (PHOTO measurement unavailable)")


def main() -> None:
    """Parse output identifiers and invoke the headless Stage 8 reporter.

    Inputs name existing output folders; the function returns no value and writes only an optional
    comparison report. Missing outputs are printed clearly; verify identifiers first.
    """
    parser = argparse.ArgumentParser(description="View Stage 8 Photo Reconstruction")
    parser.add_argument("--capture-id", required=True)
    parser.add_argument("--lidar-scan", default=None)
    parser.add_argument("--video-capture", default=None)
    parser.add_argument("--headless", action="store_true")
    args = parser.parse_args()
    report_photo(args.capture_id, args.lidar_scan, args.video_capture)


if __name__ == "__main__":
    main()
