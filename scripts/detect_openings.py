"""CLI runner for Stage 5 structural opening detection and metric width measurement.

1. Why this file exists:
   Serves as the primary command-line entry point to execute Stage 5: extracting RGB keyframes,
   detecting door and window openings via open-vocabulary AI, projecting jambs into 3D metric coordinates,
   associating with Stage 2 structural walls, fusing multi-frame observations, and writing benchmark records.

2. Pipeline stage:
   Stage 5 (Door/Window Detection & Metric Opening Measurement) - CLI Entry Point.

3. Inputs:
   Command-line arguments: --scan <scan_id>, optional --dataset-root, --outputs-root, --weights.

4. Outputs:
   Populated outputs/<scan_id>/openings/ directory with JSON, SVG, and debug image artifacts.
   Standard console summary table.

5. Coordinate/Unit conventions:
   Metric meters (m) for width, positions, and uncertainty bounds.

6. Dependencies:
   argparse, sys, json, os, backend.app.perception.pipeline.

7. Most likely failure/debugging points:
   - User provides invalid or non-existent scan ID.
   - Stage 2 structural planes or Stage 3 room polygon not yet computed.
   - Pretrained model weights not downloaded.
"""

import argparse
import json
import os
import sys

from backend.app.perception.pipeline import run_opening_pipeline


def main() -> None:
    """Parses CLI arguments, executes Stage 5 opening pipeline, and outputs human-readable summary.

    Purpose:
        Coordinates standalone execution of door/window detection and metric measurement.

    Parameters:
        None (uses sys.argv).

    Returns:
        None. Exits 0 on success, non-zero on failure.

    Assumptions:
        Target scan dataset exists and Stages 1-3 have been computed.

    Failure conditions:
        Exits with code 1 if execution fails or input files are missing.

    Debugging:
        Check exception stack trace or inspect outputs/<scan_id>/openings/opening_stats.json.
    """
    parser = argparse.ArgumentParser(
        description="Stage 5 — Detect architectural openings and measure clearance width geometrically."
    )
    parser.add_argument("--scan", type=str, required=True, help="Scan identifier (e.g., c00a170fe1)")
    parser.add_argument("--dataset-root", type=str, default="sample data/single_room", help="Root directory of scan data")
    parser.add_argument("--outputs-root", type=str, default="outputs", help="Root directory for outputs")
    parser.add_argument("--weights", type=str, default="yolov8s-worldv2.pt", help="Path to YOLO-World weights")
    parser.add_argument("--max-keyframes", type=int, default=45, help="Maximum keyframes to extract")
    parser.add_argument("--headless", action="store_true", help="Run without graphical display (default)")

    args = parser.parse_args()

    print("=" * 70)
    print(f"COSMO AI — STAGE 5: DOOR / WINDOW DETECTION & METRIC MEASUREMENT")
    print(f"Scan ID: {args.scan}")
    print("=" * 70)

    try:
        stats = run_opening_pipeline(
            scan_id=args.scan,
            dataset_root=args.dataset_root,
            outputs_root=args.outputs_root,
            model_weights_path=args.weights,
            max_keyframes=args.max_keyframes,
        )

        openings_json_path = os.path.join(args.outputs_root, args.scan, "openings", "openings.json")
        openings_data = {}
        if os.path.exists(openings_json_path):
            with open(openings_json_path, "r", encoding="utf-8") as f:
                openings_data = json.load(f)

        openings_list = openings_data.get("openings", [])

        print("\n" + "-" * 70)
        print("STAGE 5 SUMMARY RESULTS")
        print("-" * 70)
        print(f"Frames inspected:      {stats['keyframes_inspected']}")
        print(f"Candidate openings:    {stats['raw_candidate_detections']}")
        print(f"Accepted openings:     {stats['accepted_openings']}")
        print(f"Rejected candidates:   {stats['rejected_observations']}")
        print()
        print(f"Doors:                 {stats['doors_count']}")
        print(f"Windows:               {stats['windows_count']}")
        print("-" * 70)

        for op in openings_list:
            op_id = op["id"]
            wid = op["wall_id"]
            w_val = op["width"]["value"]
            w_int = op["width"]["interval"]
            half_u = op["width"]["half_width_uncertainty_m"]
            frames_cnt = op["supporting_frames"]
            status = op["status"].upper()
            op_type = op["type"]

            print(f"{op_id.capitalize()} ({op_type}):")
            print(f"  wall:              {wid}")
            print(f"  width:             {w_val:.3f} m ±{half_u:.3f} m (95% CI: [{w_int[0]:.3f}, {w_int[1]:.3f}] m)")
            print(f"  supporting frames: {frames_cnt}")
            print(f"  status:            {status}")
            if op.get("affects_polygon"):
                print(f"  corridor note:     {op.get('corridor_refinement_note', 'Affects room polygon')}")
            print()

        print("-" * 70)
        print(f"Artifacts exported to: {os.path.join(args.outputs_root, args.scan, 'openings')}/")
        print(f"Processing time:       {stats['processing_time_sec']}s")
        print("=" * 70)

    except Exception as e:
        print(f"ERROR: Stage 5 pipeline failed: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
