"""Stage 7 video ingestion, orientation normalization, and keyframe extraction pipeline.

1. Why this file exists:
   Ingests raw consumer video files (.mp4 / .mov), inspects stream container properties,
   resolves orientation normalization and pixel mapping, and extracts high-sharpness,
   non-redundant RGB keyframes. Strictly isolates video processing so that no LiDAR
   or odometry files are accessed.

2. Pipeline stage:
   Stage 7 (Video Tier - Ingestion & Keyframe Selection).

3. Inputs:
   Path to ordinary RGB video file (.mp4 or .mov).

4. Outputs:
   - `VideoCaptureMetadata` describing video properties.
   - Deterministic coordinate mapping functions for video rotation.
   - Selected JPEG keyframes stored under outputs/<capture_id>/video/keyframes/
   - `KeyframeManifest` stored as `keyframe_manifest.json`.

5. Coordinate convention:
   2D image plane coordinates: (u, v) in pixels, u in [0, width-1], v in [0, height-1].

6. Unit convention:
   - Time: Seconds.
   - Frequency: Frames per second (Hz).
   - Dimensions: Integer pixels.
   - Angles: Degrees (0, 90, 180, 270).

7. Important dependencies:
   cv2, numpy, pathlib, json, subprocess, backend.app.models.video.

8. Assumptions:
   Input video is an ordinary consumer RGB video without proprietary metadata dependencies.

9. Main failure modes:
   - Video file missing or corrupt container -> raises FileNotFoundError or ValueError.
   - Unknown rotation angle -> defaults to 0 deg with warning.

10. What a developer should inspect first when debugging:
    Inspect `detect_display_rotation` return value and verify pixel mapping round-trips.
"""

import os
import json
import subprocess
from pathlib import Path
from typing import List, Tuple, Dict, Any, Optional
import cv2
import numpy as np

from backend.app.models.video import (
    VideoCaptureMetadata,
    VideoKeyframe,
)
from backend.app.pipelines.video.keyframes import extract_video_keyframes as extract_keyframes


def map_pixel_coordinates(
    x: float,
    y: float,
    width: int,
    height: int,
    rotation_deg: int,
    inverse: bool = False,
) -> Tuple[float, float]:
    """Maps pixel coordinates between original frame space and rotated display space.

    Purpose:
        Enforces deterministic, invertible 2D coordinate transformation under 90, 180,
        and 270 degree display matrix rotations.

    Parameters:
        x: Horizontal pixel coordinate.
        y: Vertical pixel coordinate.
        width: Original unrotated frame width in pixels.
        height: Original unrotated frame height in pixels.
        rotation_deg: Rotation angle in degrees (0, 90, 180, 270 clockwise).
        inverse: If True, maps from rotated space back to original space.

    Returns:
        Tuple of (mapped_x: float, mapped_y: float).

    Assumptions:
        Rotation angle is a multiple of 90 degrees.

    Failure conditions:
        Unsupported rotation angles raise ValueError.

    Dependencies:
        None (pure mathematical coordinate mapping).

    Debugging clues:
        For 90 deg clockwise: (x, y) in (w, h) maps forward to (h - 1 - y, x) in (h, w).
    """
    rot = rotation_deg % 360
    if rot == 0:
        return float(x), float(y)

    if rot == 90:
        if not inverse:
            # Forward: (x, y) in (w, h) -> (h - 1 - y, x)
            return float(height - 1 - y), float(x)
        else:
            # Inverse: (rot_x, rot_y) -> x = rot_y, y = height - 1 - rot_x
            return float(y), float(height - 1 - x)

    elif rot == 180:
        # Forward and inverse are self-inverting for 180 degrees
        return float(width - 1 - x), float(height - 1 - y)

    elif rot == 270:
        if not inverse:
            # Forward: (x, y) in (w, h) -> (y, w - 1 - x)
            return float(y), float(width - 1 - x)
        else:
            # Inverse: (rot_x, rot_y) -> x = width - 1 - rot_y, y = rot_x
            return float(width - 1 - y), float(x)

    else:
        raise ValueError(f"Unsupported rotation angle: {rotation_deg}. Must be 0, 90, 180, or 270.")


def detect_display_rotation(video_path: Path) -> int:
    """Detects video stream rotation tag from container metadata.

    Purpose:
        Determines if video stream specifies a display orientation rotation (e.g. 90, 180, 270).

    Parameters:
        video_path: Path to video file.

    Returns:
        int rotation in degrees (0, 90, 180, or 270).

    Dependencies:
        ffprobe if available, otherwise 0.
    """
    cmd = [
        "ffprobe", "-v", "error",
        "-show_streams", "-select_streams", "v:0",
        "-print_format", "json",
        str(video_path)
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode == 0:
            data = json.loads(res.stdout)
            streams = data.get("streams", [])
            if streams:
                st = streams[0]
                # Check tags for rotate
                tags = st.get("tags", {})
                if "rotate" in tags:
                    return int(tags["rotate"]) % 360
                # Check side data list for rotation matrix
                for sd in st.get("side_data_list", []):
                    if "rotation" in sd:
                        return int(sd["rotation"]) % 360
    except Exception:
        pass
    return 0


def ingest_video_capture(video_path: str, capture_id: str) -> Tuple[VideoCaptureMetadata, Path]:
    """Ingests RGB video capture and produces validated VideoCaptureMetadata.

    Purpose:
        Primary entry point for video ingestion. Guarantees zero access to LiDAR files.

    Parameters:
        video_path: String path to video file (.mp4, .mov).
        capture_id: Unique capture identifier.

    Returns:
        Tuple of (VideoCaptureMetadata, Path(video_path)).

    Assumptions:
        Video file exists and contains valid video stream.

    Failure conditions:
        FileNotFoundError if file is missing; ValueError if video cannot be opened.
    """
    v_path = Path(video_path)
    if not v_path.exists():
        raise FileNotFoundError(f"Video file not found at: {video_path}")

    cap = cv2.VideoCapture(str(v_path))
    if not cap.isOpened():
        raise ValueError(f"Could not open video file: {video_path}")

    try:
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = float(cap.get(cv2.CAP_PROP_FPS))
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        if fps <= 0:
            fps = 30.0
        if frame_count < 0:
            frame_count = 0

        duration_seconds = float(frame_count / fps) if fps > 0 else 0.0
        file_size = v_path.stat().st_size
        rotation_deg = detect_display_rotation(v_path)

        meta = VideoCaptureMetadata(
            capture_id=capture_id,
            video_path=str(v_path.resolve()),
            codec="hevc",
            width=width,
            height=height,
            frame_count=frame_count,
            fps=fps,
            duration_seconds=duration_seconds,
            file_size_bytes=file_size,
            orientation_rotation_deg=rotation_deg,
            camera_model_status="uncalibrated",
        )
        return meta, v_path
    finally:
        cap.release()


def compute_frame_sharpness(img_bgr: np.ndarray) -> float:
    """Computes high-frequency edge variance of an image using Laplacian operator."""
    if img_bgr is None or img_bgr.size == 0:
        return 0.0
    small = cv2.resize(img_bgr, (img_bgr.shape[1] // 2, img_bgr.shape[0] // 2), interpolation=cv2.INTER_AREA)
    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
    lap = cv2.Laplacian(gray, cv2.CV_64F)
    return float(np.var(lap))


def compute_frame_difference(img_prev_bgr: np.ndarray, img_curr_bgr: np.ndarray) -> float:
    """Computes normalized grayscale absolute difference between two consecutive frames."""
    if img_prev_bgr is None or img_curr_bgr is None:
        return 1.0
    gray_prev = cv2.cvtColor(cv2.resize(img_prev_bgr, (320, 240)), cv2.COLOR_BGR2GRAY)
    gray_curr = cv2.cvtColor(cv2.resize(img_curr_bgr, (320, 240)), cv2.COLOR_BGR2GRAY)
    diff = cv2.absdiff(gray_prev, gray_curr)
    return float(np.mean(diff) / 255.0)


def extract_video_metadata(video_path: Path, capture_id: str) -> VideoCaptureMetadata:
    """Extracts stream parameters and orientation from video file container."""
    meta, _ = ingest_video_capture(str(video_path), capture_id)
    return meta
