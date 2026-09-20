"""CLI entry point for Stage 3 room polygon extraction.

1. Why this file exists:
   Allows developers and batch processing scripts to trigger Stage 3
   wall quality evaluation, 2D line projection, corner detection, and closed
   room polygon extraction from command line.

2. Pipeline stage:
   Stage 3 (2D Wall Projection & Room Polygon Extraction) - CLI Pipeline Runner.

3. Inputs:
   outputs/<scan_id>/structure/structure.json
   outputs/<scan_id>/structure/walls.ply (optional)

4. Outputs:
   outputs/<scan_id>/floorplan_geometry/
     ├── wall_quality.json
     ├── projected_walls.json
     ├── corners.json
     ├── room_polygon.json
     ├── polygon_stats.json
     └── floorplan_debug.svg

5. Coordinate/Unit assumptions:
   Y is vertical (upward).
   XZ is the horizontal floor plane.
   All coordinates and metrics are in meters.

6. Dependencies:
   argparse, pathlib, sys, backend.app.geometry.room_footprint.

7. Most likely failure/debugging points:
   - Missing structure.json if Stage 2 was not executed first.
   - Run python3 -m scripts.extract_structure --scan <scan_id> if input is absent.
"""

import sys
import argparse
from pathlib import Path

# Ensure repo root is on sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.app.geometry.room_footprint import run_stage3_pipeline


def parse_arguments() -> argparse.Namespace:
    """Parses command-line arguments for the Stage 3 builder.

    Purpose:
        Configures scan ID and optional algorithm threshold overrides.

    Parameters:
        None (reads from sys.argv).

    Returns:
        argparse.Namespace object containing parsed options.

    Assumptions:
        Standard UNIX flag conventions.

    Failure conditions:
        Exits with code 2 on invalid CLI syntax.

    Debugging:
        Pass --help to inspect configurable flags.
    """
    parser = argparse.ArgumentParser(
        description="Stage 3: 2D Wall Projection, Corner Intersections & Room Polygon Extraction."
    )
    parser.add_argument(
        "--scan",
        type=str,
        default="c00a170fe1",
        help="Scan identifier to process (default: c00a170fe1)",
    )
    parser.add_argument(
        "--max-rmse",
        type=float,
        default=0.15,
        help="Maximum plane fitting RMSE threshold in meters for quality gate (default: 0.15m)",
    )
    parser.add_argument(
        "--min-confidence",
        type=float,
        default=0.40,
        help="Minimum structural confidence threshold in [0, 1] (default: 0.40)",
    )
    parser.add_argument(
        "--max-gap-extension",
        type=float,
        default=0.35,
        help="Maximum gap extension allowed at corners in meters (default: 0.35m)",
    )
    parser.add_argument(
        "--outputs-root",
        type=str,
        default="outputs",
        help="Root directory for outputs (default: outputs)",
    )
    return parser.parse_args()


def main() -> None:
    """Executes Stage 3 pipeline on the targeted scan.

    Purpose:
        Loads Stage 2 structures, runs Stage 3 processing, and prints console summary.

    Parameters:
        None.

    Returns:
        None.

    Units / coordinates:
        Metric units in meters.

    Assumptions:
        Stage 2 outputs reside in <outputs_root>/<scan_id>/structure/.

    Failure conditions:
        Prints error and exits with code 1 if Stage 2 input files are missing.

    Dependencies:
        backend.app.geometry.room_footprint.run_stage3_pipeline, Path, sys.

    Debugging clues:
        Inspect printed summary or generated JSON files in output directory.
    """
    args = parse_arguments()
    scan_id = args.scan
    outputs_root = Path(args.outputs_root)

    struct_json = outputs_root / scan_id / "structure" / "structure.json"
    walls_ply = outputs_root / scan_id / "structure" / "walls.ply"
    out_dir = outputs_root / scan_id / "floorplan_geometry"

    if not struct_json.exists():
        print(f"Error: Stage 2 structure.json not found at {struct_json}")
        print("Please run Stage 2 first: python3 -m scripts.extract_structure --scan", scan_id)
        sys.exit(1)

    print(f"============================================================")
    print(f"STAGE 3 — 2D WALL PROJECTION & ROOM POLYGON EXTRACTION")
    print(f"Scan ID: {scan_id}")
    print(f"Input:   {struct_json}")
    print(f"Output:  {out_dir}")
    print(f"============================================================")

    results = run_stage3_pipeline(
        scan_id=scan_id,
        structure_json_path=struct_json,
        walls_ply_path=walls_ply if walls_ply.exists() else None,
        output_dir=out_dir,
        max_wall_rmse_m=args.max_rmse,
        min_wall_confidence=args.min_confidence,
        max_corner_extension_m=args.max_gap_extension,
    )

    print(f"\nExecution Summary:")
    print(f"  Accepted walls:       {results['accepted_walls']}")
    print(f"  Rejected walls:       {results['rejected_walls']}")
    print(f"  Candidate corners:   {results['candidate_corners']}")
    print(f"  Accepted corners:     {results['accepted_corners']}")
    print(f"  Inferred corners:     {results['inferred_corners']}")
    print(f"  Polygon valid:       {'YES' if results['polygon_valid'] else 'NO'}")
    print(f"  Polygon closed:      {'YES' if results['polygon_closed'] else 'NO'}")
    print(f"  Self-intersections:  {results['self_intersections']}")
    print(f"  Floor area:          {results['area_sqm']:.2f} m²")
    print(f"  Perimeter:           {results['perimeter_m']:.2f} m")
    print(f"  Quality score:       {results['quality_score']:.3f} / 1.000")
    print(f"\nArtifacts saved in:    {results['output_dir']}")
    print(f"  - floorplan_debug.svg")
    print(f"  - room_polygon.json")
    print(f"  - corners.json")
    print(f"  - projected_walls.json")
    print(f"  - wall_quality.json")
    print(f"  - polygon_stats.json")
    print(f"============================================================")


if __name__ == "__main__":
    main()
