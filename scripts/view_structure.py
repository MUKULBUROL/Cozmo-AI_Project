"""Interactive visualizer and diagnostics viewer for extracted structural planes.

Usage:
    python -m scripts.view_structure --scan c00a170fe1
    python -m scripts.view_structure --scan c00a170fe1 --headless
"""

import argparse
import sys
import os
import json
import open3d as o3d
import numpy as np


def view_structure(scan_id: str, structure_dir: str = "", headless: bool = False):
    if not structure_dir:
        structure_dir = os.path.join("outputs", scan_id, "structure")

    debug_ply = os.path.join(structure_dir, "structure_debug.ply")
    stats_json = os.path.join(structure_dir, "extraction_stats.json")
    structure_json_path = os.path.join(structure_dir, "structure.json")

    if not os.path.exists(debug_ply):
        print(f"Error: Debug point cloud not found at '{debug_ply}'", file=sys.stderr)
        print("Run structural extraction first: python -m scripts.extract_structure --scan " + scan_id, file=sys.stderr)
        sys.exit(1)

    print("=" * 60)
    print(f"STRUCTURAL GEOMETRY VIEWER: {scan_id}")
    print("=" * 60)

    if os.path.exists(stats_json):
        with open(stats_json, "r", encoding="utf-8") as f:
            stats = json.load(f)
        print(f"  Input Points:          {stats.get('input_points', 0):,}")
        print(f"  Floor Detected:        {stats.get('floor_detected')} (inliers: {stats.get('floor_inliers', 0):,})")
        print(f"  Ceiling Detected:      {stats.get('ceiling_detected')} (height: {stats.get('estimated_ceiling_height_m', 'N/A')} m)")
        print(f"  Wall Planes Merged:    {stats.get('walls_final_merged', 0)}")
        print(f"  Structural Points:     {stats.get('structural_points', 0):,}")
        print(f"  Unclassified Points:   {stats.get('unclassified_points', 0):,}")

    if os.path.exists(structure_json_path):
        with open(structure_json_path, "r", encoding="utf-8") as f:
            struct = json.load(f)
        print("\n  Extracted Wall Schedule:")
        for w in struct.get("walls", []):
            spans = w.get("spans_m", {})
            print(f"    - {w['id']}: inliers={w['inlier_count']:,} | rmse={w['rmse_m']:.3f}m | "
                  f"width={spans.get('width_x', 0):.2f}m, depth={spans.get('depth_z', 0):.2f}m, height={spans.get('height_y', 0):.2f}m | conf={w['confidence']}")
    print("=" * 60)

    pcd = o3d.io.read_point_cloud(debug_ply)
    points = np.asarray(pcd.points)

    print(f"Loaded debug cloud with {len(points):,} points.")
    print("Color legend: [Blue = Floor] [Cyan = Ceiling] [Warm Colors = Walls] [Gray = Unclassified/Clutter]")

    if headless:
        print("\nHeadless mode: Diagnostics displayed successfully.")
        return

    # Check GUI display availability
    display = os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")
    if not display:
        print("\nNote: No graphical display detected in environment ($DISPLAY is unset).")
        print(f"To view visually on Windows, open '{debug_ply}' in CloudCompare, MeshLab, or VSCode 3D Viewer.")
        return

    try:
        axes = o3d.geometry.TriangleMesh.create_coordinate_frame(size=1.0, origin=[0, 0, 0])
        print("Opening Open3D viewer window...")
        o3d.visualization.draw_geometries(
            [pcd, axes],
            window_name=f"CosmoAI Structure - {scan_id}",
            width=1280,
            height=720,
        )
    except Exception as e:
        print(f"\nNote: GUI visualization could not be opened ({e}).")
        print(f"The debug cloud is saved at '{debug_ply}'. Open it in an external 3D viewer on Windows.")


def main():
    parser = argparse.ArgumentParser(description="View structural geometry planes using Open3D")
    parser.add_argument("--scan", required=True, help="Scan ID (e.g. c00a170fe1)")
    parser.add_argument("--dir", default="", help="Custom structure output directory")
    parser.add_argument("--headless", action="store_true", help="Print diagnostics only without launching GUI window")
    args = parser.parse_args()

    view_structure(args.scan, structure_dir=args.dir, headless=args.headless)


if __name__ == "__main__":
    main()
