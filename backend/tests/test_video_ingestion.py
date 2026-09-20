"""Unit tests for Stage 7 video ingestion and keyframe extraction.

1. Why this file exists:
   Verifies that video ingestion, orientation calculation, sharpness filtering,
   and keyframe manifest generation function deterministically using synthetic video inputs
   without touching LiDAR sensor data.

2. Pipeline stage:
   Stage 7 (Video Tier - Ingestion & Contract Tests).

3. Inputs:
   Synthetic video frames generated programmatically using OpenCV.

4. Outputs:
   Pytest assertions confirming correct metadata parsing, sharpness ranking, and manifest output.

5. Unit convention:
   Pixels for dimensions, seconds for duration and timestamps.
"""

import tempfile
from pathlib import Path
import numpy as np
import cv2
import pytest

from backend.app.pipelines.video.contract import (
    VideoCaptureMetadata,
    VideoOrientation,
    KeyframeMetadata,
    KeyframeManifest,
    VideoReconstructionStatus,
)
from backend.app.pipelines.video.ingestion import (
    compute_frame_sharpness,
    compute_frame_difference,
    extract_video_metadata,
    extract_keyframes,
)


def create_synthetic_test_video(output_path: Path, width: int = 320, height: int = 240, fps: float = 30.0, num_frames: int = 60) -> None:
    """Generates a synthetic MP4 video file with moving geometric shapes for testing."""
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(str(output_path), fourcc, fps, (width, height))
    for i in range(num_frames):
        img = np.ones((height, width, 3), dtype=np.uint8) * 128
        # Draw moving sharp rectangle
        x = int((i * 4) % (width - 60))
        y = int((i * 2) % (height - 60))
        cv2.rectangle(img, (x, y), (x + 50, y + 50), (255, 0, 0), -1)
        # Add high-contrast text
        cv2.putText(img, f"Frame {i}", (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        out.write(img)
    out.release()


def test_compute_frame_sharpness():
    """Sharp textured image must have significantly higher variance than flat/blurred image."""
    flat = np.ones((200, 200, 3), dtype=np.uint8) * 100
    sharp = np.random.randint(0, 255, (200, 200, 3), dtype=np.uint8)
    blurry = cv2.GaussianBlur(sharp, (25, 25), 5.0)

    score_flat = compute_frame_sharpness(flat)
    score_sharp = compute_frame_sharpness(sharp)
    score_blurry = compute_frame_sharpness(blurry)

    assert score_flat == 0.0
    assert score_sharp > score_blurry
    assert score_sharp > 50.0


def test_compute_frame_difference():
    """Identical frames produce ~0.0 diff; shifted/altered frames produce > 0.05 diff."""
    img1 = np.ones((200, 200, 3), dtype=np.uint8) * 120
    img2 = img1.copy()
    img3 = img1.copy()
    cv2.rectangle(img3, (50, 50), (150, 150), (0, 0, 0), -1)

    diff_same = compute_frame_difference(img1, img2)
    diff_different = compute_frame_difference(img1, img3)

    assert diff_same < 0.001
    assert diff_different > 0.05


def test_extract_video_metadata():
    """Verify video container properties are correctly parsed from synthetic stream."""
    with tempfile.TemporaryDirectory() as tmpdir:
        video_path = Path(tmpdir) / "test_video.mp4"
        create_synthetic_test_video(video_path, width=320, height=240, fps=30.0, num_frames=60)

        meta = extract_video_metadata(video_path, capture_id="test_cap_01")
        assert meta.capture_id == "test_cap_01"
        assert meta.width == 320
        assert meta.height == 240
        assert meta.fps == 30.0
        assert meta.frame_count >= 50
        assert meta.orientation == VideoOrientation.LANDSCAPE
        assert meta.duration_seconds > 1.5


def test_extract_keyframes_creates_manifest():
    """Keyframe extraction must write frames and a valid keyframe_manifest.json."""
    with tempfile.TemporaryDirectory() as tmpdir:
        video_path = Path(tmpdir) / "test_video.mp4"
        output_dir = Path(tmpdir) / "outputs" / "test_cap_01" / "video"
        create_synthetic_test_video(video_path, width=320, height=240, fps=30.0, num_frames=60)

        keyframes = extract_keyframes(
            video_path=video_path,
            output_dir=output_dir,
            min_frame_stride=5,
            max_frame_stride=20,
            blur_threshold=10.0,
            max_keyframes=10,
        )

        assert len(keyframes) > 0

        # Verify keyframe files exist on disk
        for kf in keyframes:
            kf_file = Path(kf.image_path)
            assert kf_file.exists()
            assert kf.width == 320
            assert kf.height == 240

        # Verify manifest JSON file exists
        manifest_file = output_dir / "keyframe_manifest.json"
        assert manifest_file.exists()
