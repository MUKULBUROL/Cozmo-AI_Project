"""CLI entry point for LiDAR metric reconstruction.

Usage:
    python -m scripts.reconstruct_lidar --scan c00a170fe1
    python -m scripts.reconstruct_lidar --scan c7d28f72c6 --frame-stride 10 --voxel-size 0.03
"""

import argparse
import sys
import os
import json

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from backend.app.pipelines.lidar import ReconstructionConfig, run_lidar_reconstruction


SCAN_ARCHIVE_MAP = {
    "c00a170fe1": ("sample data/single_room.zip", False),
    "1a8384c3f6": ("sample data/single_scan_floor_only.zip", True),
    "c7d28f72c6": ("sample data/single_scan_with_ceiling.zip", True),
}


def main():
    parser = argparse.ArgumentParser(description="Reconstruct 3D metric point cloud from iPhone LiDAR capture")
    parser.add_argument("--scan", required=True, help="Scan ID (e.g. c00a170fe1, 1a8384c3f6, c7d28f72c6)")
    parser.add_argument("--archive", default=None, help="Path to raw zip archive (inferred from scan ID if omitted)")
    parser.add_argument("--frame-stride", type=int, default=5, help="Frame sample stride (default: 5)")
    parser.add_argument("--voxel-size", type=float, default=0.02, help="Voxel downsample size in meters (default: 0.02)")
    parser.add_argument("--min-confidence", type=int, default=2, help="Minimum ARKit confidence level (0, 1, 2; default: 2)")
    parser.add_argument("--min-depth", type=float, default=0.3, help="Minimum depth in meters (default: 0.3)")
    parser.add_argument("--max-depth", type=float, default=3.5, help="Maximum depth in meters (default: 3.5)")
    parser.add_argument("--max-frames", type=int, default=None, help="Optional max frames to process for fast testing")
    parser.add_argument("--output-dir", default=None, help="Custom output directory")
    parser.add_argument("--no-outliers", action="store_true", help="Disable statistical outlier removal")

    args = parser.parse_args()

    archive_path = args.archive
    is_loop_scan = None
    if not archive_path:
        if args.scan in SCAN_ARCHIVE_MAP:
            archive_path, is_loop_scan = SCAN_ARCHIVE_MAP[args.scan]
        else:
            print(f"Error: Unknown scan '{args.scan}'. Specify --archive explicitly.")
            sys.exit(1)

    if not os.path.exists(archive_path):
        print(f"Error: Archive not found at '{archive_path}'")
        sys.exit(1)

    config = ReconstructionConfig(
        scan_id=args.scan,
        archive_path=archive_path,
        output_dir=args.output_dir if args.output_dir else os.path.join("outputs", args.scan),
        frame_stride=args.frame_stride,
        min_confidence=args.min_confidence,
        min_depth_m=args.min_depth,
        max_depth_m=args.max_depth,
        voxel_size_m=args.voxel_size,
        remove_outliers=not args.no_outliers,
        max_frames=args.max_frames,
        is_loop_scan=is_loop_scan,
    )

    try:
        stats = run_lidar_reconstruction(config)
        print("\nReconstruction Summary:")
        print(f"  Scan ID:                  {stats['scan_id']}")
        print(f"  Frames Processed:         {stats['frames_processed']} / {stats['total_frames']}")
        print(f"  Raw Points:               {stats['points_raw_fused']:,}")
        print(f"  Voxel Downsampled Points: {stats['points_after_downsampling']:,}")
        print(f"  Final Filtered Points:    {stats['points_final_filtered']:,}")
        print(f"  Room Width X:             {stats['spans_meters']['width_x']} m")
        print(f"  Room Height Y:            {stats['spans_meters']['height_y']} m")
        print(f"  Room Depth Z:             {stats['spans_meters']['depth_z']} m")
        print(f"  Trajectory Length:        {stats['trajectory_length_m']} m")
        print(f"  Start-End Displacement:   {stats['start_end_displacement_m']} m")
        print(f"  Outputs saved in:         {config.output_dir}")
    except Exception as e:
        print(f"Reconstruction failed: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
