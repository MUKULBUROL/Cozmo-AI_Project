"""CLI tool to execute visual damage perception, 3D metric extent, and repair scope.

1. Why this file exists:
   Provides a straightforward command-line interface to run the complete Stage 9
   damage inspection pipeline on a capture across LiDAR, Video, or Photo modalities,
   exporting structured review bundles and summary reports.

2. Pipeline stage:
   Stage 9 (Damage Detection, Metric Extent, Concealed-Damage Rules & Repair Scope) - CLI Interface.

3. Inputs:
   Command-line arguments: --capture-id (required), --tier (optional), --max-frames (optional),
   --conf-threshold (optional), --workspace-root (optional).

4. Outputs:
   - outputs/<capture>/damage/damages.json
   - outputs/<capture>/damage/concealed_flags.json
   - outputs/<capture>/damage/repair_scope.json
   - outputs/<capture>/damage/damage_summary.json
   - outputs/<capture>/damage/<damage_id>/ review bundles

5. Coordinate convention:
   N/A (CLI entry point).

6. Unit convention:
   Lengths in meters, areas in m2.

7. Dependencies:
   argparse, sys, pathlib, backend.app.damage.pipeline.

8. Assumptions:
   - Stage 1-8 reconstruction or sample keyframes exist in outputs/<capture_id> or data/.

9. Failure modes:
   - Invalid capture ID or missing inputs returns non-zero error code.

10. First things to inspect while debugging:
    - Verify outputs/<capture_id>/ existence and arguments passed.
"""

import argparse
import sys
import json
from pathlib import Path

from backend.app.damage.pipeline import DamageAssessmentPipeline


def parse_args():
    parser = argparse.ArgumentParser(
        description="Stage 9: Visual damage perception, 3D metric extent, concealed rules, and repair scope."
    )
    parser.add_argument(
        "--capture-id",
        type=str,
        required=True,
        help="Scan or capture session ID (e.g. c00a170fe1, video_single_room, photo_room_01)",
    )
    parser.add_argument(
        "--tier",
        type=str,
        default=None,
        choices=["lidar", "video", "photo"],
        help="Explicit capture modality (auto-detected if omitted)",
    )
    parser.add_argument(
        "--max-frames",
        type=int,
        default=25,
        help="Maximum keyframes to analyze (default: 25)",
    )
    parser.add_argument(
        "--conf-threshold",
        type=float,
        default=0.08,
        help="Vision detector confidence threshold (default: 0.08)",
    )
    parser.add_argument(
        "--workspace-root",
        type=str,
        default=".",
        help="Workspace root path (default: .)",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    print("=" * 60)
    print("STAGE 9: PROPERTY DAMAGE & REPAIR SCOPE ANALYSIS")
    print(f"Capture ID: {args.capture_id}")
    print(f"Tier:       {args.tier or 'AUTO-DETECT'}")
    print("=" * 60)

    pipeline = DamageAssessmentPipeline(
        workspace_root=args.workspace_root,
        conf_threshold=args.conf_threshold,
    )

    try:
        results = pipeline.run(
            capture_id=args.capture_id,
            tier=args.tier,
            max_frames=args.max_frames,
        )
    except Exception as e:
        print(f"ERROR executing damage pipeline: {e}")
        import traceback
        traceback.print_exc()
        return 1

    stats = results["summary_stats"]
    damages = results["damage_regions"]
    flags = results["concealed_flags"]
    scope = results["scope_line_items"]

    print("\nSUMMARY RESULTS:")
    print(f"  Images Inspected:        {stats['images_inspected']}")
    print(f"  Quality Gate Rejected:   {stats['quality_rejected']}")
    print(f"  Raw Candidates:          {stats['raw_candidates_detected']}")
    print(f"  Fused 3D Damage Regions: {stats['fused_damages_count']}")
    print(f"    - Accepted:            {stats['accepted_count']}")
    print(f"    - Provisional:         {stats['provisional_count']}")
    print(f"    - Not Evaluable:       {stats['not_evaluable_count']}")
    print(f"  Concealed Risk Flags:    {stats['concealed_flags_count']}")
    print(f"  Repair Scope Items:      {stats['scope_line_items_count']}")

    print("\nBENCHMARK ACCURACY:")
    print("  NOT VERIFIED (Awaiting Stage 10 staged-damage ground truth)")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
