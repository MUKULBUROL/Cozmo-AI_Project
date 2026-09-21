"""Stage 8 command-line entry point for single-room and property still-image reconstruction.

1. Why this file exists: gives users one command instead of requiring internal stage execution.
2. Pipeline stage: Stage 8 photo-only CLI orchestration.
3. Inputs: a room image folder or a property folder containing room/connector image folders.
4. Outputs: ``outputs/<capture-id>/photo`` artifacts and a terminal status summary.
5. Coordinate system: final outputs are right-handed Y-up metric geometry and XZ floor plans.
6. Units: pixels for image diagnostics and meters for geometry.
7. Dependencies: argparse and Stage 8 backend pipelines.
8. Assumptions: a folder with direct images is one room; subfolders indicate a property.
9. Failure modes: invalid paths/counts exit nonzero; geometric failures remain explicit reports.
10. First debugging points: inspect the printed output path and ``reconstruction_stats.json``.
"""

import argparse
import sys
import os
import json
from pathlib import Path

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from backend.app.pipelines.photo.ingestion import discover_photo_files
from backend.app.pipelines.photo.pipeline import run_photo_room_pipeline


def main() -> None:
    """Parse Stage 8 inputs and run the appropriate photo-only reconstruction mode.

    CLI values are paths/identifiers; returned artifacts use meters in a Y-up world. Property
    folders are delegated to the stitching pipeline when present. Invalid/missing directories
    raise clear errors; inspect whether direct images or child room folders were discovered.
    """
    parser = argparse.ArgumentParser(description="Stage 8 Photo-Only Reconstruction")
    parser.add_argument("--input", required=True, help="Room photo directory or property directory")
    parser.add_argument("--capture-id", required=True, help="Unique capture identifier")
    parser.add_argument("--output-dir", default=None, help="Optional output directory")
    parser.add_argument("--synthetic-development-set", action="store_true", help="Label video-derived development stills")
    args = parser.parse_args()
    input_dir = Path(args.input)
    output_dir = Path(args.output_dir) if args.output_dir else Path("outputs") / args.capture_id / "photo"
    if discover_photo_files(input_dir):
        result = run_photo_room_pipeline(input_dir, output_dir, args.capture_id, synthetic_development_set=args.synthetic_development_set)
    else:
        from backend.app.pipelines.photo.stitching import run_photo_property_pipeline
        result = run_photo_property_pipeline(input_dir, output_dir, args.capture_id, args.synthetic_development_set)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
