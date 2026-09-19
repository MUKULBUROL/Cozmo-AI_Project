"""CLI viewer for inspecting Stage 4 room measurement deliverables.

1. Why this file exists:
   Provides formatted terminal inspection of Stage 4 measurement deliverables,
   supporting concise headless reporting for CI/CD pipelines as well as detailed
   wall-by-wall dimension tables with 95% uncertainty intervals and validity status.

2. Pipeline stage:
   Stage 4 (Metric Measurements, Room Area & Uncertainty) - CLI Inspector.

3. Inputs:
   outputs/<scan_id>/measurements/measurements.json
   outputs/<scan_id>/measurements/wall_dimensions.json
   outputs/<scan_id>/measurements/measurement_stats.json

4. Outputs:
   Formatted terminal stdout summarizing room measurements and uncertainty intervals.

5. Coordinate/Unit assumptions:
   Coordinates and lengths in meters (m).
   Areas in square meters (m2).

6. Dependencies:
   sys, json, pathlib, argparse.

7. Most likely failure/debugging points:
   - Missing measurements.json if python3 -m scripts.measure_room was not executed.
"""

import sys
import json
import argparse
from pathlib import Path

# Ensure repo root is on sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def parse_arguments() -> argparse.Namespace:
    """Parses command-line arguments for the measurement viewer.

    Purpose:
        Configures scan ID and headless flag for terminal output.

    Parameters:
        None (reads sys.argv).

    Returns:
        argparse.Namespace object.

    Assumptions:
        Standard UNIX flag conventions.

    Failure conditions:
        Exits code 2 on invalid flag syntax.

    Debugging:
        Pass --help to inspect configurable flags.
    """
    parser = argparse.ArgumentParser(
        description="View Stage 4 floor plan dimensions and uncertainty intervals."
    )
    parser.add_argument(
        "--scan",
        type=str,
        default="c00a170fe1",
        help="Scan identifier to inspect (default: c00a170fe1)",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Emit clean, concise summary suitable for CI or automated piping.",
    )
    return parser.parse_args()


def main() -> None:
    """Main execution function for measurement viewer CLI.

    Purpose:
        Loads Stage 4 JSON deliverables and prints formatted terminal report.

    Parameters:
        None.

    Returns:
        None.

    Assumptions:
        outputs/<scan_id>/measurements/ contains measurement_stats.json and measurements.json.

    Failure conditions:
        Exits with code 1 if measurement files are missing.

    Debugging:
        Verify outputs/<scan_id>/measurements/measurements.json exists.
    """
    args = parse_arguments()
    scan_id = args.scan
    measurements_dir = REPO_ROOT / "outputs" / scan_id / "measurements"

    stats_file = measurements_dir / "measurement_stats.json"
    measurements_file = measurements_dir / "measurements.json"
    wall_dim_file = measurements_dir / "wall_dimensions.json"

    if not stats_file.exists() or not measurements_file.exists():
        print(f"ERROR: Measurement deliverables not found in {measurements_dir}", file=sys.stderr)
        print(f"Run 'python3 -m scripts.measure_room --scan {scan_id}' first.", file=sys.stderr)
        sys.exit(1)

    with open(stats_file, "r", encoding="utf-8") as f:
        stats = json.load(f)
    with open(measurements_file, "r", encoding="utf-8") as f:
        master = json.load(f)

    status = stats.get("measurement_status", "unknown").upper()
    wall_count = stats.get("wall_count", 0)
    area_m2 = stats.get("floor_area_m2", 0.0)
    area_int = stats.get("floor_area_interval", [0.0, 0.0])
    perim_m = stats.get("perimeter_m", 0.0)
    perim_int = stats.get("perimeter_interval", [0.0, 0.0])
    ceil_stat = stats.get("ceiling_height_status", "not_observed")
    ceil_m = stats.get("ceiling_height_m")
    inf_corners = stats.get("inferred_corner_count", 0)

    if args.headless:
        print(f"Measurement status: {status}\n")
        print(f"Walls measured:   {wall_count}")
        print(f"Floor area:       {area_m2:.2f} m²")
        print(f"Perimeter:        {perim_m:.2f} m")
        if ceil_stat == "observed" and ceil_m is not None:
            print(f"Ceiling height:   {ceil_m:.2f} m")
        else:
            print("Ceiling height:   NOT OBSERVED")
        print(f"\nInferred corners: {inf_corners}")
        return

    # Detailed Interactive Mode
    print("=" * 70)
    print(f"STAGE 4 MEASUREMENT REPORT: {scan_id}")
    print("=" * 70)
    print(f"Validity Status:  {status}")
    if stats.get("reasons"):
        print(f"Advisory Reasons: {', '.join(stats['reasons'])}")
    print(f"Floor Area:       {area_m2:.2f} m² (95% CI: [{area_int[0]:.2f}, {area_int[1]:.2f}] m²)")
    print(f"Perimeter:        {perim_m:.2f} m  (95% CI: [{perim_int[0]:.2f}, {perim_int[1]:.2f}] m)")
    if ceil_stat == "observed" and ceil_m is not None:
        print(f"Ceiling Height:   {ceil_m:.2f} m")
    else:
        print("Ceiling Height:   NOT OBSERVED (Insufficient scan coverage)")
    print(f"Inferred Corners: {inf_corners} / {wall_count}")
    print("-" * 70)

    # Detailed wall dimension table
    if wall_dim_file.exists():
        with open(wall_dim_file, "r", encoding="utf-8") as f:
            walls = json.load(f)

        print(f"{'Wall ID':<10} {'Span Corners':<22} {'Length':<10} {'95% Interval':<16} {'Conf':<6} {'Inferred?'}")
        print("-" * 70)
        for w in walls:
            wid = w.get("wall_id", "")
            span = f"{w.get('start_corner_id', '')} -> {w.get('end_corner_id', '')}"
            l_val = f"{w.get('length_m', 0.0):.2f}m"
            int_val = f"[{w.get('interval_95_m', [0, 0])[0]:.2f} - {w.get('interval_95_m', [0, 0])[1]:.2f}]"
            conf_val = f"{w.get('confidence', 0.0):.2f}"
            inf_str = "YES [INF]" if w.get("has_inferred_corner", False) else "NO"
            print(f"{wid:<10} {span:<22} {l_val:<10} {int_val:<16} {conf_val:<6} {inf_str}")
        print("-" * 70)

    print("Notice: Engineering estimates. Calibrated physical ground truth required.")
    print("=" * 70)


if __name__ == "__main__":
    main()
