"""Inspect 3D point cloud reconstructed from depth frames, intrinsics, and odometry poses.

Usage:
    python -m scripts.inspect_pointcloud --archive "sample data/single_room.zip" --scan c00a170fe1 --frames 10
"""

import argparse
import os
import zipfile
import io
from PIL import Image
import numpy as np


def quat_to_rot(qx: float, qy: float, qz: float, qw: float) -> np.ndarray:
    n = np.sqrt(qx*qx + qy*qy + qz*qz + qw*qw)
    if n == 0:
        return np.eye(3)
    qx, qy, qz, qw = qx/n, qy/n, qz/n, qw/n
    return np.array([
        [1 - 2*qy*qy - 2*qz*qz, 2*qx*qy - 2*qz*qw, 2*qx*qz + 2*qy*qw],
        [2*qx*qy + 2*qz*qw, 1 - 2*qx*qx - 2*qz*qz, 2*qy*qz - 2*qx*qw],
        [2*qx*qz - 2*qy*qw, 2*qy*qz + 2*qx*qw, 1 - 2*qx*qx - 2*qy*qy]
    ])


def export_ply(filename: str, points: np.ndarray, colors: np.ndarray = None):
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    with open(filename, "w") as f:
        f.write("ply\n")
        f.write("format ascii 1.0\n")
        f.write(f"element vertex {len(points)}\n")
        f.write("property float x\n")
        f.write("property float y\n")
        f.write("property float z\n")
        if colors is not None:
            f.write("property uchar red\n")
            f.write("property uchar green\n")
            f.write("property uchar blue\n")
        f.write("end_header\n")
        if colors is not None:
            for p, c in zip(points, colors):
                f.write(f"{p[0]:.4f} {p[1]:.4f} {p[2]:.4f} {int(c[0])} {int(c[1])} {int(c[2])}\n")
        else:
            for p in points:
                f.write(f"{p[0]:.4f} {p[1]:.4f} {p[2]:.4f}\n")


def inspect_pointcloud(archive_path: str, scan_id: str, num_sample_frames: int = 10, output_ply: str = "outputs/sample_pointcloud.ply", min_conf: int = 2):
    if not os.path.exists(archive_path):
        print(f"Archive not found: {archive_path}")
        return

    with zipfile.ZipFile(archive_path, "r") as zf:
        odom_path = f"{scan_id}/odometry.csv"
        if odom_path not in zf.namelist():
            print(f"Odometry file {odom_path} not found.")
            return

        lines = zf.read(odom_path).decode('utf-8').splitlines()
        header = [h.strip() for h in lines[0].split(',')]
        data = [dict(zip(header, [p.strip() for p in l.split(',')])) for l in lines[1:]]

        total_frames = len(data)
        indices = np.linspace(0, total_frames - 1, num_sample_frames, dtype=int)

        sx = 256.0 / 1920.0
        sy = 192.0 / 1440.0

        all_points = []
        all_colors = []

        for idx in indices:
            row = data[idx]
            frame_id = row['frame']
            qx, qy, qz, qw = float(row['qx']), float(row['qy']), float(row['qz']), float(row['qw'])
            tx, ty, tz = float(row['x']), float(row['y']), float(row['z'])
            R = quat_to_rot(qx, qy, qz, qw)
            t = np.array([tx, ty, tz])

            fx = float(row['fx']) * sx
            fy = float(row['fy']) * sy
            cx = float(row['cx']) * sx
            cy = float(row['cy']) * sy

            depth_path = f"{scan_id}/depth/{frame_id}.png"
            conf_path = f"{scan_id}/confidence/{frame_id}.png"

            if depth_path not in zf.namelist() or conf_path not in zf.namelist():
                continue

            depth_arr = np.array(Image.open(io.BytesIO(zf.read(depth_path)))).astype(np.float32) / 1000.0
            conf_arr = np.array(Image.open(io.BytesIO(zf.read(conf_path))))

            valid = (depth_arr > 0.3) & (depth_arr < 4.5) & (conf_arr >= min_conf)
            H, W = depth_arr.shape
            u, v = np.meshgrid(np.arange(W), np.arange(H))

            z = depth_arr[valid]
            x = (u[valid] - cx) * z / fx
            y = (v[valid] - cy) * z / fy

            pts_cam = np.stack([x, y, z], axis=-1)
            pts_world = (R @ pts_cam.T).T + t

            # Downsample per frame
            step = 4
            pts_sub = pts_world[::step]
            all_points.append(pts_sub)

            # Height-based color mapping (blue floor to red ceiling)
            colors = np.zeros_like(pts_sub)
            colors[:, 0] = np.clip((pts_sub[:, 1] + 1.0) * 128, 0, 255)  # R
            colors[:, 1] = 120                                            # G
            colors[:, 2] = np.clip((1.0 - pts_sub[:, 1]) * 128, 0, 255)  # B
            all_colors.append(colors)

        if not all_points:
            print("No valid 3D points extracted.")
            return

        cloud = np.concatenate(all_points, axis=0)
        colors = np.concatenate(all_colors, axis=0)

        x_span = cloud[:, 0].max() - cloud[:, 0].min()
        y_span = cloud[:, 1].max() - cloud[:, 1].min()
        z_span = cloud[:, 2].max() - cloud[:, 2].min()

        print("=" * 60)
        print(f"POINT CLOUD INSPECTION: {scan_id}")
        print("=" * 60)
        print(f"  Frames Sampled:        {len(indices)} out of {total_frames}")
        print(f"  Total Valid Points:    {len(cloud):,}")
        print(f"  World X (Width) Span:  [{cloud[:,0].min():.3f}, {cloud[:,0].max():.3f}] -> {x_span:.3f} m")
        print(f"  World Y (Height) Span: [{cloud[:,1].min():.3f}, {cloud[:,1].max():.3f}] -> {y_span:.3f} m")
        print(f"  World Z (Depth) Span:  [{cloud[:,2].min():.3f}, {cloud[:,2].max():.3f}] -> {z_span:.3f} m")
        print(f"  Estimated Floor Area:  ~{x_span * z_span:.1f} m2 (bounding envelope)")

        export_ply(output_ply, cloud, colors)
        print(f"  Exported Sample PLY:   {output_ply}")
        print("-" * 60)

        # Attempt Open3D visualization if available
        try:
            import open3d as o3d
            pcd = o3d.geometry.PointCloud()
            pcd.points = o3d.utility.Vector3dVector(cloud)
            pcd.colors = o3d.utility.Vector3dVector(colors / 255.0)
            print("  Open3D: point cloud loaded successfully into o3d.geometry.PointCloud")
        except ImportError:
            print("  Open3D not installed in environment (PLY exported for external visualization)")


def main():
    parser = argparse.ArgumentParser(description="Inspect 3D point cloud from LiDAR scan")
    parser.add_argument("--archive", default="sample data/single_room.zip", help="Path to zip archive")
    parser.add_argument("--scan", default="c00a170fe1", help="Scan ID inside archive")
    parser.add_argument("--frames", type=int, default=10, help="Number of frames to sample")
    parser.add_argument("--output", default="outputs/sample_pointcloud.ply", help="Output PLY path")
    args = parser.parse_args()

    inspect_pointcloud(args.archive, args.scan, args.frames, args.output)


if __name__ == "__main__":
    main()
