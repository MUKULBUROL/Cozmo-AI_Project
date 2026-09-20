"""Unified cross-tier RGB frame observation adapter for damage inspection.

1. Why this file exists:
   Normalizes RGB image ingestion across LiDAR, Video, and Photo capture tiers into
   a uniform DamageFrame representation, decoupling downstream damage perception,
   geometric back-projection, and multi-view fusion from tier-specific storage formats.

2. Pipeline stage:
   Stage 9 (Damage Detection, Metric Extent, Concealed-Damage Rules & Repair Scope) - Ingestion Adapter.

3. Inputs:
   Capture directory paths or scan IDs for LiDAR, Video, or Photo modalities,
   including keyframe manifests, camera poses, depth maps, and intrinsics.

4. Outputs:
   List of standardized DamageFrame Pydantic objects containing image paths,
   depth references, camera intrinsics, and 6D world poses.

5. Coordinate convention:
   Camera frame: Optical frame (X right, Y down, Z forward).
   World frame: Right-handed metric coordinates (Y vertical upward, XZ ground plane).
   Quaternions: [qx, qy, qz, qw].

6. Unit convention:
   Metric meters for camera translations and depth measurements.
   Focal lengths and principal points in pixels.
   Timestamps in seconds.

7. Dependencies:
   os, json, pathlib, typing, numpy, backend.app.models.damage.

8. Assumptions:
   - Keyframes have been extracted by prior stages (Stage 5 LiDAR keyframes, Stage 7 Video keyframes,
     or Stage 8 Photo normalized images).
   - Video and Photo tiers may have provisional or self-calibrated intrinsics/poses.

9. Failure modes:
   - Missing keyframe directories or empty image collections.
   - Missing camera poses in uncalibrated or failed SfM frames (falls back to pose=None).
   - File read errors if relative paths do not resolve against workspace root.

10. First things to inspect while debugging:
    - Check whether outputs/<capture_id>/ contains the expected tier subfolders.
    - Inspect camera_pose dictionary keys (position, orientation_quaternion).
    - Verify depth_path existence when running on LiDAR captures.
"""

import os
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
import numpy as np
from scipy.spatial.transform import Rotation

from ..models.damage import DamageFrame


class DamageInputAdapter:
    """Unified observation adapter extracting standardized DamageFrame objects."""

    def __init__(self, workspace_root: str = "."):
        """Initializes the adapter with a workspace base path.

        Purpose:
            Sets root path context for relative directory discovery.

        Parameters:
            workspace_root: Filesystem directory path of repository root.

        Returns:
            None.

        Assumptions:
            Relative paths from manifest files resolve against workspace_root.

        Failure cases:
            None.

        Debugging clues:
            Verify workspace_root matches current execution working directory.
        """
        self.workspace_root = Path(workspace_root)

    def load_frames(
        self,
        capture_id: str,
        tier: Optional[str] = None,
        max_frames: Optional[int] = None,
    ) -> List[DamageFrame]:
        """Loads and standardizes RGB observation frames for a given capture.

        Purpose:
            Discovers keyframes, camera poses, intrinsics, and depth references across
            LiDAR, Video, or Photo tiers without code duplication in perception.

        Parameters:
            capture_id: Scan or session identifier (e.g. 'c00a170fe1', 'video_single_room').
            tier: Optional explicit tier ('lidar', 'video', 'photo'). Auto-detected if None.
            max_frames: Optional cap on the number of returned frames for performance.

        Returns:
            List of DamageFrame objects sorted by timestamp or image identifier.

        Assumptions:
            At least one valid modality folder exists in outputs/<capture_id> or data/.

        Failure cases:
            Returns empty list if no compatible keyframes or images are discovered.

        Debugging clues:
            Inspect detected modality string and search paths logged during discovery.
        """
        detected_tier = tier.lower() if tier else self._detect_tier(capture_id)
        if not detected_tier:
            return []

        if detected_tier == "lidar":
            return self._load_lidar_frames(capture_id, max_frames)
        elif detected_tier == "video":
            return self._load_video_frames(capture_id, max_frames)
        elif detected_tier == "photo":
            return self._load_photo_frames(capture_id, max_frames)
        else:
            return []

    def _detect_tier(self, capture_id: str) -> Optional[str]:
        """Auto-detects the capture tier from directory layout.

        Purpose:
            Determines whether the capture represents LiDAR, Video, or Photo artifacts.

        Parameters:
            capture_id: Identifier of the capture.

        Returns:
            Tier string ('lidar', 'video', 'photo') or None if unknown.

        Assumptions:
            Directory structure follows standardized outputs/ layout.

        Failure cases:
            Returns None if no recognized directories exist.

        Debugging clues:
            Check whether outputs/<capture_id> exists.
        """
        base_out = self.workspace_root / "outputs" / capture_id
        if (base_out / "openings" / "keyframes").exists():
            return "lidar"
        if (base_out / "video" / "keyframes").exists() or (base_out / "video").exists():
            return "video"
        if (base_out / "photo" / "normalized").exists() or (base_out / "photo").exists():
            return "photo"
        if "video" in capture_id.lower():
            return "video"
        if "photo" in capture_id.lower():
            return "photo"
        return "lidar"

    def _load_lidar_frames(
        self, capture_id: str, max_frames: Optional[int] = None
    ) -> List[DamageFrame]:
        """Extracts damage frames from LiDAR keyframes and manifest.

        Purpose:
            Loads synchronized 1920x1440 RGB keyframes with 256x192 metric depth,
            ARKit 6D poses, and calibrated intrinsics.

        Parameters:
            capture_id: LiDAR scan ID.
            max_frames: Optional frame limit.

        Returns:
            List of standardized DamageFrame instances.

        Assumptions:
            outputs/<capture_id>/openings/keyframes/keyframe_manifest.json exists.

        Failure cases:
            Falls back to raw file search if manifest is missing.

        Debugging clues:
            Check keyframe_manifest.json formatting and image paths.
        """
        kf_dir = self.workspace_root / "outputs" / capture_id / "openings" / "keyframes"
        manifest_path = kf_dir / "keyframe_manifest.json"
        frames: List[DamageFrame] = []

        if manifest_path.exists():
            try:
                with open(manifest_path, "r", encoding="utf-8") as f:
                    manifest = json.load(f)
                for item in manifest.get("keyframes", []):
                    img_path = str(self.workspace_root / item["image_path"])
                    depth_path = (
                        str(self.workspace_root / item["depth_path"])
                        if item.get("depth_path")
                        else None
                    )
                    pose = item.get("camera_pose")
                    intrinsics = item.get("intrinsics")

                    df = DamageFrame(
                        capture_id=capture_id,
                        tier="lidar",
                        image_id=item.get("filename", Path(img_path).name),
                        image_path=img_path,
                        depth_path=depth_path,
                        timestamp_seconds=item.get("timestamp"),
                        camera_pose=pose,
                        intrinsics=intrinsics,
                    )
                    frames.append(df)
            except Exception:
                pass

        if not frames and kf_dir.exists():
            # Fallback to scanning jpg files
            jpgs = sorted(kf_dir.glob("*.jpg"))
            for jpg in jpgs:
                stem = jpg.stem
                depth_file = kf_dir / f"{stem}_depth.png"
                frames.append(
                    DamageFrame(
                        capture_id=capture_id,
                        tier="lidar",
                        image_id=jpg.name,
                        image_path=str(jpg),
                        depth_path=str(depth_file) if depth_file.exists() else None,
                    )
                )

        if max_frames and len(frames) > max_frames:
            frames = frames[:max_frames]
        return frames

    def _load_video_frames(
        self, capture_id: str, max_frames: Optional[int] = None
    ) -> List[DamageFrame]:
        """Extracts damage frames from Video reconstruction artifacts.

        Purpose:
            Loads Video keyframes, SfM camera poses, estimated depth maps, and intrinsics.

        Parameters:
            capture_id: Video capture identifier.
            max_frames: Optional frame limit.

        Returns:
            List of standardized DamageFrame instances.

        Assumptions:
            outputs/<capture_id>/video/ contains keyframes and sfm poses.

        Failure cases:
            Returns frames with pose=None if SfM poses are missing.

        Debugging clues:
            Check sfm/poses.json and depth/ directory paths.
        """
        base_dir = self.workspace_root / "outputs" / capture_id / "video"
        kf_dir = base_dir / "keyframes"
        poses_file = base_dir / "sfm" / "poses.json"
        cams_file = base_dir / "sfm" / "cameras.json"
        depth_dir = base_dir / "depth"

        poses_by_name: Dict[str, Any] = {}
        if poses_file.exists():
            try:
                with open(poses_file, "r", encoding="utf-8") as f:
                    poses_data = json.load(f)
                    if isinstance(poses_data, list):
                        for p in poses_data:
                            poses_by_name[p.get("image_name", "")] = p
                    elif isinstance(poses_data, dict):
                        poses_by_name = poses_data
            except Exception:
                pass

        intrinsics: Optional[Dict[str, Any]] = None
        if cams_file.exists():
            try:
                with open(cams_file, "r", encoding="utf-8") as f:
                    cams_data = json.load(f)
                    intrinsics = cams_data.get("intrinsics")
            except Exception:
                pass

        frames: List[DamageFrame] = []
        if kf_dir.exists():
            jpgs = sorted(kf_dir.glob("*.jpg"))
            for jpg in jpgs:
                img_name = jpg.name
                pose_entry = poses_by_name.get(img_name)
                camera_pose: Optional[Dict[str, Any]] = None
                if pose_entry:
                    w_from_c = pose_entry.get("world_from_cam", {})
                    pos = w_from_c.get("position")
                    quat = w_from_c.get("quaternion_wxyz")
                    if pos and quat:
                        # Convert wxyz to xyzw for ARKit standard
                        camera_pose = {
                            "position": pos,
                            "orientation_quaternion": [quat[1], quat[2], quat[3], quat[0]],
                        }

                depth_path: Optional[str] = None
                stem = jpg.stem
                npy_path = depth_dir / f"{stem}_depth.npy"
                png_path = depth_dir / f"{stem}_depth.png"
                if npy_path.exists():
                    depth_path = str(npy_path)
                elif png_path.exists():
                    depth_path = str(png_path)

                frames.append(
                    DamageFrame(
                        capture_id=capture_id,
                        tier="video",
                        image_id=img_name,
                        image_path=str(jpg),
                        depth_path=depth_path,
                        timestamp_seconds=pose_entry.get("timestamp_seconds") if pose_entry else None,
                        camera_pose=camera_pose,
                        intrinsics=intrinsics,
                    )
                )

        if max_frames and len(frames) > max_frames:
            frames = frames[:max_frames]
        return frames

    def _load_photo_frames(
        self, capture_id: str, max_frames: Optional[int] = None
    ) -> List[DamageFrame]:
        """Extracts damage frames from Photo reconstruction artifacts.

        Purpose:
            Loads Photo stills, SfM poses, estimated depth maps, and camera intrinsics.

        Parameters:
            capture_id: Photo capture identifier.
            max_frames: Optional frame limit.

        Returns:
            List of standardized DamageFrame instances.

        Assumptions:
            outputs/<capture_id>/photo/normalized or data/photo_dev contains images.

        Failure cases:
            Returns frames with pose=None if SfM poses are uncalculated.

        Debugging clues:
            Inspect photo/normalized or photo/sfm/poses.json.
        """
        base_dir = self.workspace_root / "outputs" / capture_id / "photo"
        norm_dir = base_dir / "normalized"
        if not norm_dir.exists():
            norm_dir = self.workspace_root / "data" / "photo_dev" / capture_id

        poses_file = base_dir / "sfm" / "poses.json"
        cams_file = base_dir / "sfm" / "cameras.json"
        depth_dir = base_dir / "depth"

        poses_by_name: Dict[str, Any] = {}
        if poses_file.exists():
            try:
                with open(poses_file, "r", encoding="utf-8") as f:
                    poses_data = json.load(f)
                    if isinstance(poses_data, list):
                        for p in poses_data:
                            poses_by_name[p.get("image_name", "")] = p
                    elif isinstance(poses_data, dict):
                        poses_by_name = poses_data
            except Exception:
                pass

        intrinsics: Optional[Dict[str, Any]] = None
        if cams_file.exists():
            try:
                with open(cams_file, "r", encoding="utf-8") as f:
                    cams_data = json.load(f)
                    intrinsics = cams_data.get("intrinsics")
            except Exception:
                pass

        frames: List[DamageFrame] = []
        if norm_dir.exists():
            jpgs = sorted(norm_dir.glob("*.jpg"))
            for jpg in jpgs:
                img_name = jpg.name
                pose_entry = poses_by_name.get(img_name)
                camera_pose: Optional[Dict[str, Any]] = None
                if pose_entry:
                    w_from_c = pose_entry.get("world_from_cam", {})
                    pos = w_from_c.get("position")
                    quat = w_from_c.get("quaternion_wxyz")
                    if pos and quat:
                        camera_pose = {
                            "position": pos,
                            "orientation_quaternion": [quat[1], quat[2], quat[3], quat[0]],
                        }

                depth_path: Optional[str] = None
                stem = jpg.stem
                npy_path = depth_dir / f"{stem}_depth.npy"
                png_path = depth_dir / f"{stem}_depth.png"
                if npy_path.exists():
                    depth_path = str(npy_path)
                elif png_path.exists():
                    depth_path = str(png_path)

                frames.append(
                    DamageFrame(
                        capture_id=capture_id,
                        tier="photo",
                        image_id=img_name,
                        image_path=str(jpg),
                        depth_path=depth_path,
                        timestamp_seconds=pose_entry.get("timestamp_seconds") if pose_entry else None,
                        camera_pose=camera_pose,
                        intrinsics=intrinsics,
                    )
                )

        if max_frames and len(frames) > max_frames:
            frames = frames[:max_frames]
        return frames
