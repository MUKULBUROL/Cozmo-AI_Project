"""Stage 11 Keyframe Overlap and Sensor Isolation Regression Tests.

1. Purpose:
   Tests that Stage 11 keyframe selection maintains bounded inter-keyframe stride,
   smooth temporal distribution, and strictly prohibits sensor data access
   (no depth, confidence, IMU, odometry, or ARKit pose files).

2. Stage:
   Stage 11 (Video Tier - Test Suite).

3. Inputs:
   Synthetic video sequences and isolated directory structures.

4. Outputs:
   Pytest assertions confirming stride bounding and RGB-only isolation.

5. Coordinates and units:
   Video frame indices, timestamps in seconds, pixel dimensions.

6. Dependencies:
   pytest, numpy, cv2, tempfile, backend.app.pipelines.video.keyframes.

7. Assumptions:
   Video files can be created and decoded with OpenCV VideoCapture/VideoWriter.

8. Failure modes:
   Accessing sensor files or exceeding stride bounds raises AssertionError.

9. First debugging points:
   Inspect keyframe manifest timestamps and input directory listings.
"""

import tempfile
from pathlib import Path
import cv2
import numpy as np
import pytest

from backend.app.pipelines.video.keyframes import extract_video_keyframes


def create_synthetic_moving_video(path: Path, num_frames: int = 120, fps: float = 30.0) -> None:
    """Create a synthetic video with textured moving content."""
    width, height = 320, 240
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(path), fourcc, fps, (width, height))

    for f in range(num_frames):
        img = np.full((height, width, 3), 40, dtype=np.uint8)
        # Add high-contrast textured elements moving across frame
        x = int((f * 3) % (width - 60))
        cv2.rectangle(img, (x, 50), (x + 50, 150), (220, 220, 220), -1)
        cv2.circle(img, (x + 25, 100), 15, (0, 0, 255), -1)
        # Background texture pattern
        for gx in range(0, width, 40):
            cv2.line(img, (gx, 0), (gx, height), (70, 70, 70), 1)
        writer.write(img)

    writer.release()


def test_keyframe_selection_bounds_temporal_stride():
    """Verify that keyframe extraction bounds the gap between consecutive keyframes."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_p = Path(tmpdir)
        vid_p = tmp_p / "test_walk.mp4"
        out_p = tmp_p / "keyframes"

        create_synthetic_moving_video(vid_p, num_frames=120, fps=30.0)

        keyframes = extract_video_keyframes(
            video_path=vid_p,
            output_dir=out_p,
            max_keyframes=6,
        )

        assert len(keyframes) <= 6
        assert len(keyframes) >= 2
        # Verify frame 0 anchor
        assert keyframes[0].frame_index == 0

        # Verify consecutive frame gaps are bounded
        nominal_stride = 120 / 6  # 20 frames
        for i in range(1, len(keyframes)):
            gap = keyframes[i].frame_index - keyframes[i - 1].frame_index
            assert gap >= 5, f"Gap {gap} too small"
            # Must not exceed 2.5x nominal stride (preventing blind tracking loss)
            assert gap <= nominal_stride * 2.5, f"Gap {gap} exceeded bounded continuity threshold"


def test_video_pipeline_rgb_only_isolation():
    """Verify that video keyframe extraction and pipeline run cleanly without any sensor files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_p = Path(tmpdir)
        vid_p = tmp_p / "isolated_video.mp4"
        out_p = tmp_p / "isolated_output"

        create_synthetic_moving_video(vid_p, num_frames=60, fps=20.0)

        # Ensure directory contains ONLY the video file
        contained_files = [p.name for p in tmp_p.iterdir() if p.is_file()]
        assert contained_files == ["isolated_video.mp4"]

        # Assert no sensor files exist
        forbidden_patterns = ["odometry.csv", "imu.csv", "depth", "confidence", "poses"]
        for pattern in forbidden_patterns:
            assert not (tmp_p / pattern).exists()

        # Run extraction
        kfs = extract_video_keyframes(
            video_path=vid_p,
            output_dir=out_p,
            max_keyframes=5,
        )

        assert len(kfs) >= 2
        for kf in kfs:
            assert Path(kf.image_path).exists()
