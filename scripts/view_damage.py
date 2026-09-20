"""CLI inspection viewer for Stage 9 damage reports, metric extents, and repair scopes.

1. Why this file exists:
   Renders human-readable terminal summaries of damage analysis results for a capture,
   formatting 3D regions, confidence intervals, concealed-damage flags, and repair scope line items.

2. Pipeline stage:
   Stage 9 (Damage Detection, Metric Extent, Concealed-Damage Rules & Repair Scope) - Viewer Interface.

3. Inputs:
   Command-line arguments: --capture-id (required), --headless (flag), --workspace-root (optional).

4. Outputs:
   Formatted terminal inspection report adhering to the Challenge Stage 9 specification.

5. Coordinate convention:
   N/A (Viewer presentation).

6. Unit convention:
   Metric meters, square meters.

7. Dependencies:
   argparse, sys, json, pathlib.

8. Assumptions:
   - Analysis results exist in outputs/<capture_id>/damage/.

9. Failure modes:
   - Missing outputs/<capture_id>/damage/ directory prompts user to run analyze_damage.py first.

10. First things to inspect while debugging:
    - Check outputs/<capture_id>/damage/damages.json existence.
"""

import argparse
import sys
import json
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(
        description="View Stage 9 damage inspection and repair scope report."
    )
    parser.add_argument(
        "--capture-id",
        type=str,
        required=True,
        help="Scan or capture session ID (e.g. c00a170fe1, video_single_room)",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        default=True,
        help="Headless text output (default: True)",
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
    root = Path(args.workspace_root)
    dmg_dir = root / "outputs" / args.capture_id / "damage"

    if not dmg_dir.exists():
        print(f"\n[!] No damage analysis found for capture '{args.capture_id}' in {dmg_dir}.")
        print(f"    Please run: python3 -m scripts.analyze_damage --capture-id {args.capture_id} first.\n")
        return 1

    summary_file = dmg_dir / "damage_summary.json"
    damages_file = dmg_dir / "damages.json"
    flags_file = dmg_dir / "concealed_flags.json"
    scope_file = dmg_dir / "repair_scope.json"

    summary = {}
    if summary_file.exists():
        with open(summary_file, "r", encoding="utf-8") as f:
            summary = json.load(f)

    damages = []
    if damages_file.exists():
        with open(damages_file, "r", encoding="utf-8") as f:
            damages = json.load(f)

    flags = []
    if flags_file.exists():
        with open(flags_file, "r", encoding="utf-8") as f:
            flags = json.load(f)

    scope = []
    if scope_file.exists():
        with open(scope_file, "r", encoding="utf-8") as f:
            scope = json.load(f)

    print("\nDAMAGE ANALYSIS")
    print("=" * 40)
    print(f"Capture:           {args.capture_id}")
    print(f"Images inspected:  {summary.get('images_inspected', 'N/A')}")
    print(f"Damage candidates: {summary.get('raw_candidates_detected', len(damages))}")
    print(f"Accepted:          {summary.get('accepted_count', 0)}")
    print(f"Provisional:       {summary.get('provisional_count', 0)}")
    print(f"Not Evaluable:     {summary.get('not_evaluable_count', 0)}")
    print("=" * 40)

    if not damages:
        print("\nNo visible property damage regions detected on structural surfaces.\n")
    else:
        for idx, d in enumerate(damages, 1):
            print(f"\nDamage {idx:02d} ({d.get('damage_id')})")
            print(f"Class:     {d.get('damage_class')}")
            print(f"Surface:   {d.get('host_surface_id')} ({d.get('host_surface_type')})")
            print(f"Status:    {d.get('status')}")

            if d.get("metric_area"):
                m = d["metric_area"]
                print(f"Area:      {m.get('value')} {m.get('unit')}")
                print(f"Interval:  [{m.get('lower_bound')}, {m.get('upper_bound')}] {m.get('unit')} (conf: {m.get('confidence')})")
            elif d.get("metric_length"):
                m = d["metric_length"]
                print(f"Length:    {m.get('value')} {m.get('unit')}")
                print(f"Interval:  [{m.get('lower_bound')}, {m.get('upper_bound')}] {m.get('unit')}")
            else:
                print("Extent:    NOT_EVALUABLE (insufficient metric geometry)")

            imgs = d.get("supporting_images", [])
            print(f"Support:   {len(imgs)} images ({', '.join(imgs[:3])}{'...' if len(imgs) > 3 else ''})")
            if d.get("measurement_spread_m2") is not None:
                print(f"Spread:    ±{d.get('measurement_spread_m2'):.4f} m²")

            # Concealed flags for this damage
            d_flags = [f for f in flags if f.get("damage_id") == d.get("damage_id")]
            if d_flags:
                print("\n  Concealed Risk Flags:")
                for fl in d_flags:
                    print(f"    - {fl.get('suspected_issue')}")
                    print(f"      requires inspection: {'yes' if fl.get('requires_inspection') else 'no'}")
                    print(f"      protocol: {fl.get('inspection_recommendation')}")

            # Scope items for this damage
            d_scope = [sc for sc in scope if sc.get("damage_id") == d.get("damage_id")]
            if d_scope:
                print("\n  Remediation Scope:")
                for sc in d_scope:
                    q_str = f"{sc.get('quantity')} {sc.get('unit')}" if sc.get("quantity") is not None else "TBD on inspection"
                    print(f"    - {sc.get('action')} (quantity: {q_str})")

            print("-" * 40)

    print("\nBENCHMARK ACCURACY:")
    print("NOT VERIFIED (Awaiting Stage 10 staged-damage ground truth)\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
