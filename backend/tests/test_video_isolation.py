"""Regression test verifying Video-Tier isolation from LiDAR / ARKit data.

1. Why this file exists:
   Guarantees that the video reconstruction pipeline operates strictly on ordinary RGB video
   files (.mp4 / .mov) and does not secretly attempt to read or depend on `odometry.csv`,
   `depth/`, `confidence/`, or LiDAR point clouds, even if placed in an isolated temporary directory.

2. Pipeline stage:
   Stage 7 (Video Tier - Architectural Isolation Verification).

3. Inputs:
   Standalone synthetic or isolated MP4 video files in pristine temporary directories.

4. Outputs:
   Pytest assertions confirming successful execution without sensor artifacts.

5. Coordinates and units:
   Synthetic frames use top-left pixels, 24 frames/second, and no 3D coordinate system.

6. Assumptions and dependencies:
   OpenCV MP4 encoding is available; NumPy creates deterministic RGB test content.

7. Failure modes and first debugging points:
   Codec failures yield an unreadable video. Inspect the temporary video metadata and keyframe
   manifest before investigating isolation assertions.
"""

import tempfile
import shutil
from pathlib import Path
import numpy as np
import cv2
import pytest

from backend.app.pipelines.video.ingestion import ingest_video_capture
from backend.app.pipelines.video.keyframes import extract_video_keyframes
from backend.app.models.video import VideoCaptureMetadata


def test_video_pipeline_strict_isolation():
    """Execute ingestion/keyframing when the capture contains only one RGB MP4.

    Parameters and return value are supplied by pytest (none). Frames use 320x240 pixels and
    timestamps in seconds; no world coordinates or metric depth exist. The test assumes OpenCV's
    MP4 writer is available and fails on decode/keyframe errors or any sensor-file dependency.
    Inspect the generated manifest and asserted directory inventory first.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        isolated_dir = Path(tmpdir) / "isolated_capture"
        isolated_dir.mkdir()

        # Create isolated pure video file
        video_file = isolated_dir / "walkthrough.mp4"
        fps = 24.0
        width, height = 320, 240
        writer = cv2.VideoWriter(str(video_file), cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height))

        for f in range(30):
            frame = np.full((height, width, 3), 100, dtype=np.uint8)
            # Add dynamic motion
            x = int((f * 6) % (width - 40))
            cv2.rectangle(frame, (x, 40), (x + 35, 100), (220, 180, 50), -1)
            writer.write(frame)
        writer.release()

        # Strictly assert NO sensor files exist in isolated_dir
        assert not (isolated_dir / "odometry.csv").exists()
        assert not (isolated_dir / "depth").exists()
        assert not (isolated_dir / "confidence").exists()
        assert not (isolated_dir / "pointcloud.ply").exists()

        # 1. Test Ingestion
        metadata, v_path = ingest_video_capture(str(video_file), capture_id="iso_001")
        assert isinstance(metadata, VideoCaptureMetadata)
        assert metadata.frame_count >= 25
        assert metadata.width == width
        assert metadata.height == height

        # 2. Test Keyframe Extraction
        out_keyframes_dir = isolated_dir / "keyframes_out"
        keyframes = extract_video_keyframes(
            video_path=video_file,
            output_dir=out_keyframes_dir,
            min_frame_stride=4,
            max_frame_stride=15,
            blur_threshold=10.0,
            max_keyframes=5,
        )

        assert len(keyframes) >= 2
        assert (out_keyframes_dir / "keyframe_manifest.json").exists()

        # Confirm still no sensor files were generated or read
        assert not (isolated_dir / "odometry.csv").exists()
        assert not (isolated_dir / "depth").exists()
        assert not (isolated_dir / "confidence").exists()
