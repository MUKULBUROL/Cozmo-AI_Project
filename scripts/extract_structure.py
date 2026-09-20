"""CLI entry point for architectural structural extraction (Floor, Ceiling, Walls).

1. Purpose:
    Provides the primary command-line interface for Stage 2 structural plane extraction,
    accepting user configuration for point cloud paths, geometric thresholds, and deterministic
    RNG seed controls. Executes surface normal estimation, horizontal/vertical filtering,
    and iterative RANSAC plane segmentation.

2. Stage:
    Stage 2 (Architectural Structural Plane Extraction) & Stage 10.2 (Deterministic Baseline).

3. Inputs:
    Command line arguments:
      --scan: Scan identifier (e.g. c00a170fe1)
      --ply-path: Optional custom path to baseline_filtered.ply
      --output-dir: Optional output directory
      --seed: Random seed for deterministic reproducibility (default: 42)
      --no-deterministic: Flag to disable deterministic RNG seeding
      Geometric threshold arguments: ransac-distance, normal-radius, min-floor-inliers,
      min-wall-inliers, max-horizontal-planes, max-vertical-planes, merge-angle-deg, merge-dist-m.

4. Outputs:
    Console summary table and populated output directory:
      outputs/<scan_id>/structure/
        ├── floor.ply
        ├── ceiling.ply
        ├── walls.ply
        ├── unclassified.ply
        ├── structure_debug.ply
        ├── structure.json
        └── extraction_stats.json

5. Coordinate systems / units:
    Metric units (meters). Angles in degrees.
    World frame: Y vertical upward, XZ horizontal floor plane.

6. Dependencies:
    argparse, sys, os, backend.app.geometry (StructuralConfig, extract_structure).

7. Assumptions:
    Stage 1 LiDAR reconstruction has completed, generating baseline_filtered.ply.
    Default seed 42 is used unless explicitly overridden.

8. Failure modes:
    Exits code 1 if baseline_filtered.ply is not found.
    Exits code 1 and prints traceback if extraction fails.

9. First debugging points:
    Verify file existence at outputs/<scan_id>/baseline_filtered.ply.
    Inspect extraction_stats.json for inlier counts and failure reasons.
"""

import argparse
import sys
import os

from backend.app.geometry import StructuralConfig, extract_structure


def main() -> None:
    """Parses CLI arguments, initializes configuration, and runs structural extraction.

    Purpose:
        Configures and executes the Stage 2 plane segmentation pipeline from CLI invocations,
        enforcing deterministic execution with seed 42 by default.

    Parameters:
        None (reads from sys.argv).

    Returns:
        None (exits 0 on success, 1 on error).

    Units / coordinates:
        Metric distances in meters, angles in degrees.

    Assumptions:
        Target scan dataset exists and contains filtered point cloud from Stage 1.

    Failure conditions:
        Exits with code 1 if input PLY does not exist or if pipeline execution raises an exception.

    Dependencies:
        argparse, backend.app.geometry.StructuralConfig, backend.app.geometry.extract_structure.

    Debugging clues:
        Pass --help to inspect configurable flags. Check printed extraction stats for zero walls.
    """
    parser = argparse.ArgumentParser(description="Extract floor, ceiling, and wall structural planes from point cloud")
    parser.add_argument("--scan", required=True, help="Scan ID (e.g. c00a170fe1)")
    parser.add_argument("--ply-path", default="", help="Path to baseline_filtered.ply (defaults to outputs/<scan_id>/baseline_filtered.ply)")
    parser.add_argument("--output-dir", default="", help="Output directory for structure artifacts")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for deterministic reproducibility (default: 42)")
    parser.add_argument("--no-deterministic", action="store_true", help="Disable deterministic RNG seeding")
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
        random_seed=args.seed,
        deterministic_mode=not args.no_deterministic,
    )

    if not os.path.exists(config.ply_path):
        print(f"Error: Input point cloud not found at '{config.ply_path}'", file=sys.stderr)
        print("Please run Stage 1 reconstruction first: python -m scripts.reconstruct_lidar --scan " + args.scan, file=sys.stderr)
        sys.exit(1)

    try:
        stats = extract_structure(config)
        print("\nStructural Extraction Summary:")
        print(f"  Scan ID:                    {stats['scan_id']}")
        print(f"  Random Seed:                {stats.get('random_seed', 'N/A')} (deterministic={stats.get('deterministic_mode', False)})")
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
