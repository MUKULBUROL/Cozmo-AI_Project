"""Interactive 3D point cloud visualizer using Open3D with headless fallback."""

import argparse
import os
import sys
import open3d as o3d
import numpy as np


def view_pointcloud(ply_path: str, show_axes: bool = True, headless: bool = False):
    if not os.path.exists(ply_path):
        print(f"File not found: {ply_path}", file=sys.stderr)
        sys.exit(1)

    print(f"Loading point cloud: {ply_path}...")
    pcd = o3d.io.read_point_cloud(ply_path)

    if pcd.is_empty():
        print("Point cloud is empty!", file=sys.stderr)
        sys.exit(1)

    points = np.asarray(pcd.points)
    x_span = float(points[:, 0].max() - points[:, 0].min())
    y_span = float(points[:, 1].max() - points[:, 1].min())
    z_span = float(points[:, 2].max() - points[:, 2].min())

    print("=" * 60)
    print(f"POINT CLOUD DIAGNOSTICS: {os.path.basename(ply_path)}")
    print("=" * 60)
    print(f"  File Path:    {ply_path}")
    print(f"  File Size:    {os.path.getsize(ply_path) / (1024*1024):.2f} MB")
    print(f"  Total Points: {len(points):,}")
    print(f"  Bounds X:     [{points[:,0].min():.3f}, {points[:,0].max():.3f}] -> span: {x_span:.3f} m")
    print(f"  Bounds Y:     [{points[:,1].min():.3f}, {points[:,1].max():.3f}] -> span: {y_span:.3f} m")
    print(f"  Bounds Z:     [{points[:,2].min():.3f}, {points[:,2].max():.3f}] -> span: {z_span:.3f} m")
    print(f"  Floor Area:   ~{x_span * z_span:.1f} m2 (bounding envelope)")
    print("=" * 60)

    if headless:
        print("Headless mode requested: Point cloud diagnostics printed above.")
        return

    # Attempt GUI visualization
    try:
        geometries = [pcd]
        if show_axes:
            axes = o3d.geometry.TriangleMesh.create_coordinate_frame(size=1.0, origin=[0, 0, 0])
            geometries.append(axes)

        print("Attempting to open Open3D visualization window...")
        o3d.visualization.draw_geometries(
            geometries,
            window_name=f"CosmoAI Floorplan - {os.path.basename(ply_path)}",
            width=1280,
            height=720,
        )
    except Exception as e:
        print(f"\nNote: GUI visualization could not be opened ({e}).")
        print(f"The point cloud was verified successfully. You can open '{ply_path}' in MeshLab, CloudCompare, or VSCode 3D Viewer on Windows.")


def main():
    parser = argparse.ArgumentParser(description="View 3D point cloud using Open3D")
    parser.add_argument("ply_path", help="Path to .ply file to view")
    parser.add_argument("--no-axes", action="store_true", help="Hide coordinate frame axes")
    parser.add_argument("--headless", action="store_true", help="Print diagnostics only without opening GUI window")
    args = parser.parse_args()

    view_pointcloud(args.ply_path, show_axes=not args.no_axes, headless=args.headless)


if __name__ == "__main__":
    main()
