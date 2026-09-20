"""CLI entry point for Stage 4 room measurement and uncertainty computation.

1. Why this file exists:
   Allows engineers, CLI users, and automated test pipelines to execute Stage 4
   metric measurement computation, validity gating, and uncertainty estimation from the terminal.

2. Pipeline stage:
   Stage 4 (Metric Measurements, Room Area & Uncertainty) - CLI Runner.

3. Inputs:
   outputs/<scan_id>/floorplan_geometry/ (Stage 3 deliverables)
   outputs/<scan_id>/structure/structure.json (Stage 2 structural planes)

4. Outputs:
   outputs/<scan_id>/measurements/
     ├── measurements.json
     ├── wall_dimensions.json
     ├── uncertainty.json
     ├── measurement_stats.json
     └── dimensioned_debug.svg

5. Coordinate/Unit assumptions:
   Y is vertical axis (upward).
   XZ is floor plane.
   All coordinates and metrics in meters (m) and square meters (m2).

6. Dependencies:
   sys, pathlib, argparse, backend.app.measurements.

7. Most likely failure/debugging points:
   - Missing Stage 3 outputs if python3 -m scripts.build_room_polygon was not executed.
   - Missing Stage 2 structure.json if python3 -m scripts.extract_structure was not executed.
"""

import sys
import argparse
from pathlib import Path

# Ensure repo root is on sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.app.measurements.engine import compute_room_measurements


def parse_arguments() -> argparse.Namespace:
    """Parses command line arguments for the Stage 4 measurement CLI.

    Purpose:
        Configures scan ID and Monte Carlo uncertainty parameters from CLI flags.

    Parameters:
        None (reads sys.argv).

    Returns:
        argparse.Namespace with parsed options.

    Assumptions:
        Standard UNIX flag conventions.

    Failure conditions:
        Exits code 2 on invalid flag syntax.

    Debugging:
        Pass --help to inspect configurable flags.
    """
    parser = argparse.ArgumentParser(
        description="Stage 4: Metric Measurements, Room Area & Honest Uncertainty Propagation."
    )
    parser.add_argument(
        "--scan",
        type=str,
        default="c00a170fe1",
        help="Scan identifier to process (default: c00a170fe1)",
    )
    parser.add_argument(
        "--mc-samples",
        type=int,
        default=1000,
        help="Number of Monte Carlo iterations for area/perimeter uncertainty (default: 1000)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for deterministic reproducibility (default: 42)",
    )
    parser.add_argument(
        "--outputs-root",
        type=str,
        default="outputs",
        help="Root directory for outputs (default: outputs)",
    )
    return parser.parse_args()


def main() -> None:
    """Main execution function for Stage 4 room measurement runner.

    Purpose:
        Locates Stage 2 and 3 artifacts, invokes compute_room_measurements,
        and logs formatted execution summary.

    Parameters:
        None.

    Returns:
        None.

    Units / coordinates:
        Metric distances in meters, areas in square meters.

    Assumptions:
        Inputs exist in <outputs_root>/<scan_id>/.

    Failure conditions:
        Raises FileNotFoundError if prerequisites are absent.

    Dependencies:
        backend.app.measurements.engine.compute_room_measurements, Path, sys.

    Debugging clues:
        Check console logs for validity status and file output locations.
    """
    args = parse_arguments()
    scan_id = args.scan
    outputs_root = Path(args.outputs_root)

    stage3_dir = outputs_root / scan_id / "floorplan_geometry"
    stage2_file = outputs_root / scan_id / "structure" / "structure.json"
    output_dir = outputs_root / scan_id / "measurements"

    print("=" * 60)
    print(f"STAGE 4 — METRIC MEASUREMENTS & UNCERTAINTY: {scan_id}")
    print(f"Stage 3 Input: {stage3_dir}")
    print(f"Stage 2 Input: {stage2_file}")
    print(f"Output Target: {output_dir}")
    print("=" * 60)

    try:
        result = compute_room_measurements(
            scan_id=scan_id,
            stage3_geometry_dir=stage3_dir,
            stage2_structure_json_path=stage2_file,
            output_dir=output_dir,
            mc_samples=args.mc_samples,
            random_seed=args.seed,
        )

        status_str = result["validity_status"].upper()
        area = result["floor_area"]
        perim = result["perimeter"]
        ceil = result["ceiling_height"]

        print("\nMeasurement Results:")
        print(f"  Validity Status:  {status_str}")
        if result["reasons"]:
            print(f"  Advisory Reasons: {', '.join(result['reasons'])}")
        print(f"  Walls Measured:   {result['wall_count']}")
        print(f"  Floor Area:       {area['value']:.2f} m² [{area['interval'][0]:.2f} - {area['interval'][1]:.2f}] (conf: {area['confidence']:.2f})")
        print(f"  Perimeter:        {perim['value']:.2f} m [{perim['interval'][0]:.2f} - {perim['interval'][1]:.2f}] (conf: {perim['confidence']:.2f})")

        if ceil:
            print(f"  Ceiling Height:   {ceil['value']:.2f} m [{ceil['interval'][0]:.2f} - {ceil['interval'][1]:.2f}] (conf: {ceil['confidence']:.2f})")
        else:
            print("  Ceiling Height:   NOT OBSERVED (Unobserved in capture)")

        print("\nArtifacts Saved:")
        for name, path_str in result["output_files"].items():
            print(f"  - {Path(path_str).name}")

        print("=" * 60)
        print("STAGE 4 COMPLETE")
        print("=" * 60)

    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"\nERROR: Stage 4 execution failed: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
