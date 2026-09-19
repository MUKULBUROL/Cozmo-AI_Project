"""CLI inspection and debug viewer for Stage 3 room polygon extraction results.

1. Why this file exists:
   Inspects existing Stage 3 floorplan geometry deliverables, prints a concise
   headless diagnostic status report, and points developers to the rendered SVG.

2. Pipeline stage:
   Stage 3 (2D Wall Projection & Room Polygon Extraction) - CLI Inspection.

3. Inputs:
   outputs/<scan_id>/floorplan_geometry/
     ├── wall_quality.json
     ├── corners.json
     ├── room_polygon.json
     └── polygon_stats.json

4. Outputs:
   Terminal diagnostic summary report or SVG viewer path.

5. Coordinate/Unit assumptions:
   Coordinates and metrics are metric (meters, square meters).

6. Dependencies:
   argparse, json, pathlib, sys.

7. Most likely failure/debugging points:
   - Output files not found if build_room_polygon was not run first.
   - Run python3 -m scripts.build_room_polygon --scan <scan_id> first.
"""

import sys
import json
import argparse
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def parse_arguments() -> argparse.Namespace:
    """Parses command line arguments for the viewer.

    Purpose:
        Configures scan ID and headless mode flag.

    Parameters:
        None.

    Returns:
        argparse.Namespace with 'scan' and 'headless' attributes.

    Assumptions:
        Standard UNIX argument flags.

    Failure conditions:
        Exits on invalid arguments.

    Debugging:
        Use --help to see all options.
    """
    parser = argparse.ArgumentParser(
        description="Inspect and view Stage 3 room polygon results."
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
        help="Print concise headless diagnostic metrics to stdout without launching viewer",
    )
    return parser.parse_args()


def main() -> None:
    """Reads Stage 3 outputs and prints formatted inspection reports.

    Purpose:
        Displays validation metrics, counts of accepted/rejected components,
        closure status, and artifact locations.

    Parameters:
        None.

    Returns:
        None.

    Assumptions:
        Stage 3 deliverables exist in outputs/<scan_id>/floorplan_geometry/.

    Failure conditions:
        Exits with code 1 if room_polygon.json or wall_quality.json is missing.

    Debugging:
        Verify that scripts.build_room_polygon was executed beforehand.
    """
    args = parse_arguments()
    scan_id = args.scan
    geom_dir = REPO_ROOT / "outputs" / scan_id / "floorplan_geometry"

    poly_file = geom_dir / "room_polygon.json"
    quality_file = geom_dir / "wall_quality.json"
    corners_file = geom_dir / "corners.json"
    stats_file = geom_dir / "polygon_stats.json"
    svg_file = geom_dir / "floorplan_debug.svg"

    if not poly_file.exists() or not quality_file.exists():
        print(f"Error: Stage 3 outputs not found in {geom_dir}")
        print(f"Please run: python3 -m scripts.build_room_polygon --scan {scan_id}")
        sys.exit(1)

    with open(quality_file, "r", encoding="utf-8") as f:
        q_data = json.load(f)
    with open(poly_file, "r", encoding="utf-8") as f:
        p_data = json.load(f)
    with open(corners_file, "r", encoding="utf-8") as f:
        c_data = json.load(f)
    with open(stats_file, "r", encoding="utf-8") as f:
        s_data = json.load(f)

    accepted_walls = q_data.get("accepted_count", len(p_data.get("walls", [])))
    rejected_walls = q_data.get("rejected_count", 0)
    cand_corners = c_data.get("candidate_corners_count", len(c_data.get("accepted_corners", [])))
    acc_corners = c_data.get("accepted_corners_count", len(c_data.get("accepted_corners", [])))
    inf_corners = c_data.get("inferred_corners_count", 0)

    val_info = s_data.get("validation", {})
    poly_valid = "YES" if val_info.get("is_valid", p_data.get("polygon", {}).get("valid", False)) else "NO"
    poly_closed = "YES" if val_info.get("is_closed", p_data.get("polygon", {}).get("closed", False)) else "NO"
    self_intersections = val_info.get("self_intersections_count", 0)

    if args.headless:
        print(f"Accepted walls:       {accepted_walls}")
        print(f"Rejected walls:       {rejected_walls}")
        print(f"Candidate corners:   {cand_corners}")
        print(f"Accepted corners:     {acc_corners}")
        print(f"Inferred corners:     {inf_corners}")
        print(f"")
        print(f"Polygon valid:       {poly_valid}")
        print(f"Polygon closed:      {poly_closed}")
        print(f"Self-intersections:  {self_intersections}")
        return

    # Non-headless verbose report
    poly_info = p_data.get("polygon", {})
    area = poly_info.get("area_sqm", 0.0)
    perim = poly_info.get("perimeter_m", 0.0)
    vertices = poly_info.get("vertices", [])

    print(f"============================================================")
    print(f"STAGE 3 INSPECTION REPORT: {scan_id}")
    print(f"============================================================")
    print(f"Accepted walls:       {accepted_walls}")
    print(f"Rejected walls:       {rejected_walls}")
    print(f"Candidate corners:   {cand_corners}")
    print(f"Accepted corners:     {acc_corners}")
    print(f"Inferred corners:     {inf_corners}")
    print(f"")
    print(f"Polygon valid:       {poly_valid}")
    print(f"Polygon closed:      {poly_closed}")
    print(f"Self-intersections:  {self_intersections}")
    print(f"Area:                {area:.2f} m²")
    print(f"Perimeter:           {perim:.2f} m")
    print(f"Vertices count:      {len(vertices)}")
    print(f"")
    print(f"Ordered Polygon Vertices (XZ floor plane):")
    for idx, v in enumerate(vertices):
        print(f"  [{idx:02d}] x = {v[0]:6.3f} m,  z = {v[1]:6.3f} m")
    print(f"")
    print(f"Debug SVG visualization saved at:")
    print(f"  {svg_file}")
    print(f"============================================================")


if __name__ == "__main__":
    main()
