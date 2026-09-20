"""Stage 6 Whole-Property Floor Plan Viewer CLI.

1. Why this file exists:
    Provides a command-line viewing tool to inspect reconstructed multi-room property plans,
    room dimensions, adjacency topology, and drift ablation diagnostics.

2. Pipeline stage:
    Stage 6 — Visual Inspection & Output Verification.

3. Inputs:
    --scan <scan_id> (default: c7d28f72c6), --headless flag.

4. Outputs:
    Formatted console summary of property metrics, room areas, and file paths to SVG visualizations.

5. Coordinate conventions:
    Global XZ floor coordinates in metric units (meters).

6. Unit assumptions:
    Distances in meters (m), area in square meters (m2).

7. Important dependencies:
    argparse, json, pathlib.

8. What is most likely to break:
    Missing property.json or drift_ablation.json if pipeline hasn't been executed yet.

9. What a developer should inspect first:
    Verify file existence under outputs/<scan_id>/property/.
"""

import argparse
import json
import sys
from pathlib import Path


def view_property(scan_id: str, headless: bool = False) -> None:
    """Displays formatted whole-property reconstruction details from JSON outputs.

    Purpose:
        Enables rapid inspection of room dimensions, drift metrics, and visual asset locations.

    Parameters:
        scan_id: Capture identifier string.
        headless: Flag to suppress interactive launcher.

    Returns:
        None.

    Assumptions:
        outputs/<scan_id>/property/ contains property.json and drift_ablation.json.

    Failure conditions:
        Prints clear missing file error message if outputs directory is not found.

    Debugging:
        Ensure reconstruct_property has been run for this scan_id.
    """
    out_dir = Path("outputs") / scan_id / "property"
    prop_path = out_dir / "property.json"
    ablation_path = out_dir / "drift_ablation.json"
    svg_path = out_dir / "property_debug.svg"
    ablation_svg = out_dir / "drift_ablation.svg"

    if not prop_path.exists():
        print(f"Error: Property plan not found at {prop_path}")
        print(f"Please run reconstruction first: python3 -m scripts.reconstruct_property --scan {scan_id}")
        sys.exit(1)

    with open(prop_path, "r", encoding="utf-8") as f:
        prop_data = json.load(f)

    ablation_data = {}
    if ablation_path.exists():
        with open(ablation_path, "r", encoding="utf-8") as f:
            ablation_data = json.load(f)

    print("=" * 60)
    print(f"WHOLE PROPERTY PLAN: {scan_id}")
    print("=" * 60)

    total_area = prop_data.get("total_floor_area", {}).get("value", 0.0)
    unit = prop_data.get("total_floor_area", {}).get("unit", "m2")
    rooms = prop_data.get("rooms", [])
    conns = prop_data.get("connections", [])

    print(f"Total Floor Area:    {total_area:.2f} {unit}")
    print(f"Total Rooms/Zones:   {len(rooms)}")
    print(f"Adjacency Edges:     {len(conns)}")

    m_eval = ablation_data.get("evaluation", {})
    m_on = ablation_data.get("metrics", {}).get("drift_correction_on", {})
    print(f"Optimization Status: {m_eval.get('status', 'UNKNOWN').upper()}")
    print(f"Residual Reduction:  {m_on.get('residual_reduction_meters', 0.0):.4f} m ({m_on.get('residual_improvement_percentage', 0.0):.1f}%)")
    print(f"Endpoint Gap Clamped: {m_on.get('endpoint_gap_reduction_meters', 0.0):.4f} m")

    print("\nROOM SUMMARY:")
    print("-" * 60)
    for r in rooms:
        r_id = r.get("room_id")
        name = r.get("name")
        area = r.get("floor_area", {}).get("value", 0.0)
        perim = r.get("perimeter", {}).get("value", 0.0)
        print(f"  [{r_id}] {name:<20}: {area:6.2f} m²  (Perimeter: {perim:5.2f} m)")

    print("\nADJACENCY CONNECTIONS:")
    print("-" * 60)
    if conns:
        for c in conns:
            op_str = f"(Opening: {c.get('connecting_opening_id')})" if c.get("connecting_opening_id") else "(Shared Wall)"
            print(f"  {c.get('room_a_id')} <---> {c.get('room_b_id')}  {op_str}")
    else:
        print("  (No direct connections recorded)")

    print("\nVISUALIZATION ARTIFACTS:")
    print("-" * 60)
    print(f"  Floor Plan SVG:   {svg_path}")
    print(f"  Drift Ablation:   {ablation_svg}")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="View Reconstructed Property Plan")
    parser.add_argument("--scan", type=str, default="c7d28f72c6", help="Scan ID to view")
    parser.add_argument("--headless", action="store_true", help="Run in headless mode")
    args = parser.parse_args()

    view_property(scan_id=args.scan, headless=args.headless)


if __name__ == "__main__":
    main()
