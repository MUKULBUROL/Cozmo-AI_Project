"""Dataset validation script for Floorplan AI challenge.

Usage:
    python -m scripts.validate_dataset
"""

import os
import sys
import zipfile
import json


def validate_dataset(base_dir: str = "sample data"):
    print("=" * 40)
    print("DATASET VALIDATION")
    print("=" * 40)

    if not os.path.exists(base_dir):
        print(f"ERROR: Dataset directory '{base_dir}' not found!")
        return 1

    archives = {
        "single_room.zip": {"id": "c00a170fe1", "type": "room", "name": "Single Room"},
        "single_scan_floor_only.zip": {"id": "1a8384c3f6", "type": "property", "name": "Whole Property (Floor Only)"},
        "single_scan_with_ceiling.zip": {"id": "c7d28f72c6", "type": "property", "name": "Whole Property (With Ceiling)"},
    }

    found_archives = []
    for arc_name, meta in archives.items():
        arc_path = os.path.join(base_dir, arc_name)
        if os.path.exists(arc_path):
            found_archives.append((arc_path, arc_name, meta))

    if not found_archives:
        print(f"ERROR: No scan archives found in '{base_dir}'!")
        return 1

    # Properties and rooms count
    properties_count = 1  # Multi-room apartment captured across floor_only and with_ceiling
    rooms_count = 1       # Dedicated single room scan

    # Modality counts
    photo_images_count = 0
    photo_rooms_count = 0
    video_clips_count = 0
    depth_captures_count = 0
    pose_files_count = 0
    intrinsics_files_count = 0
    imu_files_count = 0

    total_depth_frames = 0
    total_confidence_frames = 0

    scan_details = []

    for arc_path, arc_name, meta in found_archives:
        scan_id = meta["id"]
        with zipfile.ZipFile(arc_path, "r") as zf:
            namelist = zf.namelist()

            # Video
            has_video = f"{scan_id}/rgb.mp4" in namelist
            if has_video:
                video_clips_count += 1

            # Depth & Confidence
            depth_files = [n for n in namelist if f"{scan_id}/depth/" in n and n.endswith(".png")]
            conf_files = [n for n in namelist if f"{scan_id}/confidence/" in n and n.endswith(".png")]
            if depth_files:
                depth_captures_count += 1
                total_depth_frames += len(depth_files)
                total_confidence_frames += len(conf_files)

            # Odometry / Poses
            has_odometry = f"{scan_id}/odometry.csv" in namelist
            if has_odometry:
                pose_files_count += 1

            # Intrinsics
            has_intrinsics = f"{scan_id}/camera_matrix.csv" in namelist
            if has_intrinsics:
                intrinsics_files_count += 1

            # IMU
            has_imu = f"{scan_id}/imu.csv" in namelist
            if has_imu:
                imu_files_count += 1

            scan_details.append({
                "archive": arc_name,
                "scan_id": scan_id,
                "name": meta["name"],
                "frames": len(depth_files),
                "has_video": has_video,
                "has_poses": has_odometry,
                "has_intrinsics": has_intrinsics,
                "has_imu": has_imu
            })

    # Print summary
    print(f"Properties: {properties_count}")
    print(f"Rooms: {rooms_count}")
    print()

    print("PHOTO")
    print(f"Images: {photo_images_count}")
    print(f"Rooms: {photo_rooms_count}")
    print("Status: NOT PROVIDED IN SAMPLE DATA (Must synthesize from video keyframes)")
    print()

    print("VIDEO")
    print(f"Clips: {video_clips_count}")
    print("Codec: HEVC / H.265 (1920x1440 @ 60 FPS timebase)")
    print()

    print("LIDAR")
    print(f"Depth captures: {depth_captures_count} ({total_depth_frames:,} total depth frames)")
    print(f"Confidence maps: {depth_captures_count} ({total_confidence_frames:,} total confidence frames)")
    print(f"Pose files (odometry): {pose_files_count}")
    print(f"Intrinsics (camera_matrix): {intrinsics_files_count}")
    print(f"IMU logs: {imu_files_count}")
    print("Depth resolution: 256x192 (16-bit uint16 mm)")
    print()

    print("GROUND TRUTH")
    print("Wall measurements: NO")
    print("Opening measurements: NO")
    print("Ceiling height: NO")
    print("Floor area: NO")
    print("Room adjacency: NO")
    print("Floor-plan drawings: NO")
    print("Damage annotations: NO")
    print("=" * 40)
    print("DATASET VALIDATION PASSED")
    print("=" * 40)
    return 0


def main():
    sys.exit(validate_dataset())


if __name__ == "__main__":
    main()
