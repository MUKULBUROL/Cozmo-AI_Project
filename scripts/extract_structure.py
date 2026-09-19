"""CLI entry point for architectural structural extraction (Floor, Ceiling, Walls).

Usage:
    python -m scripts.extract_structure --scan c00a170fe1
    python -m scripts.extract_structure --scan c00a170fe1 --ransac-distance 0.04 --min-wall-inliers 3000
"""

import argparse
import sys
import os

from backend.app.geometry import StructuralConfig, extract_structure


def main():
    parser = argparse.ArgumentParser(description="Extract floor, ceiling, and wall structural planes from point cloud")
    parser.add_argument("--scan", required=True, help="Scan ID (e.g. c00a170fe1)")
    parser.add_argument("--ply-path", default="", help="Path to baseline_filtered.ply (defaults to outputs/<scan_id>/baseline_filtered.ply)")
    parser.add_argument("--output-dir", default="", help="Output directory for structure artifacts")
    parser.add_argument("--ransac-distance", type=float, default=0.035, help="RANSAC plane distance threshold in meters (default: 0.035)")
    parser.add_argument("--normal-radius", type=float, default=0.10, help="Normal estimation radius in meters (default: 0.10)")
    parser.add_argument("--min-floor-inliers", type=int, default=5000, help="Minimum inliers to accept floor (default: 5000)")
    parser.add_argument("--min-wall-inliers", type=int, default=4000, help="Minimum inliers to accept wall candidate (default: 4000)")
    parser.add_argument("--max-horizontal-planes", type=int, default=6, help="Maximum horizontal planes to extract (default: 6)")
    parser.add_argument("--max-vertical-planes", type=int, default=14, help="Maximum vertical wall candidates to extract (default: 14)")
    parser.add_argument("--merge-angle-deg", type=float, default=12.0, help="Angular threshold for merging parallel wall fragments (default: 12.0 deg)")
    parser.add_argument("--merge-dist-m", type=float, default=0.18, help="Offset distance threshold for merging parallel wall fragments (default: 0.18 m)")

    args = parser.parse_args()

    config = StructuralConfig(
        scan_id=args.scan,
        ply_path=args.ply_path,
        output_dir=args.output_dir,
        distance_threshold_m=args.ransac_distance,
        normal_radius_m=args.normal_radius,
        min_floor_inliers=args.min_floor_inliers,
        min_wall_inliers=args.min_wall_inliers,
        max_horizontal_planes=args.max_horizontal_planes,
        max_vertical_planes=args.max_vertical_planes,
        wall_merge_angle_deg=args.merge_angle_deg,
        wall_merge_distance_m=args.merge_dist_m,
    )

    if not os.path.exists(config.ply_path):
        print(f"Error: Input point cloud not found at '{config.ply_path}'", file=sys.stderr)
        print("Please run Stage 1 reconstruction first: python -m scripts.reconstruct_lidar --scan " + args.scan, file=sys.stderr)
        sys.exit(1)

    try:
        stats = extract_structure(config)
        print("\nStructural Extraction Summary:")
        print(f"  Scan ID:                    {stats['scan_id']}")
        print(f"  Input Points:               {stats['input_points']:,}")
        print(f"  Floor Detected:             {stats['floor_detected']} (inliers: {stats['floor_inliers']:,}, rmse: {stats.get('floor_rmse_m', 'N/A')} m)")
        print(f"  Ceiling Detected:           {stats['ceiling_detected']} (reason: {stats.get('ceiling_failure_reason', 'N/A')})")
        if stats['estimated_ceiling_height_m']:
            print(f"  Provisional Ceiling Height: {stats['estimated_ceiling_height_m']} m")
        print(f"  Wall Candidates Extracted:  {stats['wall_candidates']}")
        print(f"  Walls Accepted:             {stats['walls_accepted']} ({stats['walls_rejected']} rejected as furniture/clutter)")
        print(f"  Walls Final Merged:         {stats['walls_final_merged']}")
        print(f"  Structural Points:          {stats['structural_points']:,} ({stats['structural_points']/stats['input_points']*100:.1f}%)")
        print(f"  Unclassified Points:        {stats['unclassified_points']:,} ({stats['unclassified_points']/stats['input_points']*100:.1f}%)")
        print(f"  Output Artifacts:           {config.output_dir}/")
    except Exception as e:
        print(f"Extraction failed: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
