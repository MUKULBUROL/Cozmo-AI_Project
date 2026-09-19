"""CLI viewer and inspection utility for Stage 5 structural openings and floor plan overlays.

1. Why this file exists:
   Allows developers and operators to inspect Stage 5 opening detection results, detailed observations,
   wall associations, corridor doorway refinement recommendations, and generated visualization paths.

2. Pipeline stage:
   Stage 5 (Door/Window Detection & Metric Opening Measurement) - CLI Inspection & Viewer.

3. Inputs:
   Command-line arguments: --scan <scan_id>, optional --outputs-root, --headless.

4. Outputs:
   Terminal formatted table of openings, observations, and artifact paths.

5. Coordinate/Unit conventions:
   Metric meters (m) for widths, coordinates, and uncertainty bounds.

6. Dependencies:
   argparse, json, os, sys, typing.

7. Most likely failure/debugging points:
   - outputs/<scan_id>/openings/ does not exist (Stage 5 has not been executed yet).
   - openings.json file is corrupted or empty.
"""

import argparse
import json
import os
import sys
from typing import Any, Dict, List


def display_openings_summary(scan_id: str, outputs_root: str = "outputs", headless: bool = True) -> None:
    """Reads Stage 5 opening artifacts and displays detailed architectural inspection report.

    Purpose:
        Provides clear, human-readable inspection of opening locations, host walls, clearances,
        and uncertainty intervals.

    Parameters:
        scan_id: Identifier of target scan (e.g. 'c00a170fe1').
        outputs_root: Base outputs directory path.
        headless: Flag indicating whether graphical window display is disabled.

    Returns:
        None. Prints to standard output.

    Assumptions:
        outputs/<scan_id>/openings/openings.json exists and adheres to Stage 5 contract.

    Failure conditions:
        Exits with code 1 if openings.json cannot be found.

    Debugging:
        Run 'python3 -m scripts.detect_openings --scan <scan_id>' before viewing.
    """
    openings_dir = os.path.join(outputs_root, scan_id, "openings")
    openings_file = os.path.join(openings_dir, "openings.json")
    stats_file = os.path.join(openings_dir, "opening_stats.json")

    if not os.path.exists(openings_file):
        print(f"Error: Opening artifacts not found at {openings_file}", file=sys.stderr)
        print("Please run Stage 5 detection first: python3 -m scripts.detect_openings --scan " + scan_id, file=sys.stderr)
        sys.exit(1)

    with open(openings_file, "r", encoding="utf-8") as f:
        openings_data = json.load(f)

    stats = {}
    if os.path.exists(stats_file):
        with open(stats_file, "r", encoding="utf-8") as f:
            stats = json.load(f)

    openings = openings_data.get("openings", [])
    uncertain = openings_data.get("uncertain_openings", [])
    refinements = openings_data.get("polygon_refinement_candidates", [])

    print("=" * 75)
    print(f"STAGE 5 OPENINGS VIEWER — SCAN: {scan_id}")
    print("=" * 75)

    if stats:
        print(f"Keyframes Inspected:      {stats.get('keyframes_inspected', 'N/A')}")
        print(f"Raw Candidate Detections: {stats.get('raw_candidate_detections', 'N/A')}")
        print(f"Accepted Observations:    {stats.get('accepted_observations', 'N/A')}")
        print(f"Rejected Candidates:      {stats.get('rejected_observations', 'N/A')}")
        print(f"Processing Time:          {stats.get('processing_time_sec', 'N/A')}s")
        print("-" * 75)

    print(f"\nACCEPTED ARCHITECTURAL OPENINGS ({len(openings)}):")
    if not openings:
        print("  None detected or verified.")

    for op in openings:
        op_id = op["id"]
        op_type = op.get("type", "opening")
        wid = op.get("wall_id", "unknown")
        w_val = op.get("width", {}).get("value", 0.0)
        w_int = op.get("width", {}).get("interval", [0.0, 0.0])
        half_u = op.get("width", {}).get("half_width_uncertainty_m", 0.0)
        frames_cnt = op.get("supporting_frames", 0)
        frames_ids = op.get("supporting_frame_ids", [])
        c3d = op.get("centroid_3d", [0.0, 0.0, 0.0])

        print(f"  * {op_id.upper()}: [{op_type.upper()}] on host {wid}")
        print(f"    Clearance Width:     {w_val:.3f} m ±{half_u:.3f} m")
        print(f"    Estimated 95% CI:    [{w_int[0]:.3f} m, {w_int[1]:.3f} m] (calibrated: false)")
        print(f"    3D Centroid (m):     ({c3d[0]:.3f}, {c3d[1]:.3f}, {c3d[2]:.3f})")
        print(f"    Supporting Frames:   {frames_cnt} {frames_ids[:8]}")
        if op.get("affects_polygon"):
            print(f"    Corridor Note:       {op.get('corridor_refinement_note')}")
        print()

    if uncertain:
        print(f"\nUNCERTAIN / PROVISIONAL OPENINGS ({len(uncertain)}):")
        for uop in uncertain:
            print(f"  * {uop['id']} ({uop.get('type')}) on {uop.get('wall_id')}: width={uop['width']['value']:.3f}m")

    if refinements:
        print(f"\nPOLYGON REFINEMENT RECOMMENDATIONS ({len(refinements)}):")
        for ref in refinements:
            print(f"  * Opening: {ref['opening_id']} on {ref['wall_id']}")
            print(f"    Measured Opening Width: {ref['measured_opening_width_m']:.3f} m")
            print(f"    Historical 2D Span:     {ref['historical_polygon_edge_span_m']:.3f} m")
            print(f"    Note: {ref['notes']}")

    svg_path = os.path.join(openings_dir, "opening_debug.svg")
    dbg_dir = os.path.join(openings_dir, "debug_frames")

    print("\n" + "-" * 75)
    print("VERIFICATION ARTIFACTS:")
    print(f"  * 2D Floor Plan SVG:     {svg_path}")
    print(f"  * Annotated Keyframes:   {dbg_dir}/")
    print(f"  * Complete Contract:     {openings_file}")
    print("=" * 75)


def main() -> None:
    """CLI argument parser for view_openings."""
    parser = argparse.ArgumentParser(description="View Stage 5 opening detection and metric measurements.")
    parser.add_argument("--scan", type=str, required=True, help="Scan identifier (e.g., c00a170fe1)")
    parser.add_argument("--outputs-root", type=str, default="outputs", help="Base outputs directory")
    parser.add_argument("--headless", action="store_true", default=True, help="Run in headless mode (default)")
    args = parser.parse_args()

    display_openings_summary(scan_id=args.scan, outputs_root=args.outputs_root, headless=args.headless)


if __name__ == "__main__":
    main()
