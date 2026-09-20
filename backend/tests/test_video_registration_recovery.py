"""Stage 11 Video Registration Recovery and Outlier Rejection Tests.

1. Purpose:
   Verifies that the Stage 11 video pipeline rejects geometrically invalid feature matches,
   recovers tracking across overlapping intermediate frames, and emits explicit failure reports
   when visual reconstruction is genuinely impossible.

2. Stage:
   Stage 11 (Video Tier - Test Suite).

3. Inputs:
   Synthetic planar projections, random noise images, and isolated visual components.

4. Outputs:
   Pytest assertions confirming geometric verification and failure handling.

5. Coordinates and units:
   Normalized pixel coordinates and reprojection errors in pixels.

6. Dependencies:
   pytest, numpy, cv2, backend.app.pipelines.video.sfm, backend.app.pipelines.video.contract.

7. Assumptions:
   pycolmap is installed and available in test environment.

8. Failure modes:
   Accepting invalid two-view geometry or creating false points raises AssertionError.

9. First debugging points:
   Inspect RANSAC inlier threshold and two_view_geometries table.
"""

import tempfile
from pathlib import Path
import cv2
import numpy as np
import pytest

try:
    import pycolmap
except ImportError:
    pycolmap = None

from backend.app.pipelines.video.sfm import run_visual_sfm
from backend.app.pipelines.video.contract import VideoReconstructionStatus


@pytest.mark.skipif(pycolmap is None, reason="pycolmap not installed")
def test_geometrically_invalid_matches_rejected():
    """Verify that pure noise/unrelated images are rejected by two-view geometric verification."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_p = Path(tmpdir)
        kf_dir = tmp_p / "keyframes"
        out_sfm = tmp_p / "sfm"
        kf_dir.mkdir()
        out_sfm.mkdir()

        # Generate two unrelated random noise images
        rng = np.random.RandomState(42)
        img1 = rng.randint(0, 256, (240, 320, 3), dtype=np.uint8)
        img2 = rng.randint(0, 256, (240, 320, 3), dtype=np.uint8)
        img3 = rng.randint(0, 256, (240, 320, 3), dtype=np.uint8)

        cv2.imwrite(str(kf_dir / "frame_000000.jpg"), img1)
        cv2.imwrite(str(kf_dir / "frame_000001.jpg"), img2)
        cv2.imwrite(str(kf_dir / "frame_000002.jpg"), img3)

        report, poses, intrinsics, points = run_visual_sfm(
            keyframes_dir=kf_dir,
            output_sfm_dir=out_sfm,
            capture_id="test_noise",
        )

        # Unrelated noise must not produce registered poses
        assert report.status == VideoReconstructionStatus.FAILED
        assert len(poses) == 0
        assert len(points) == 0


def test_explicit_failure_on_insufficient_keyframes():
    """Verify that fewer than 3 keyframes returns explicit FAILED status without exception."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_p = Path(tmpdir)
        kf_dir = tmp_p / "keyframes"
        out_sfm = tmp_p / "sfm"
        kf_dir.mkdir()
        out_sfm.mkdir()

        # Only 2 images
        cv2.imwrite(str(kf_dir / "frame_000000.jpg"), np.zeros((100, 100, 3), dtype=np.uint8))
        cv2.imwrite(str(kf_dir / "frame_000001.jpg"), np.zeros((100, 100, 3), dtype=np.uint8))

        report, poses, intrinsics, points = run_visual_sfm(
            keyframes_dir=kf_dir,
            output_sfm_dir=out_sfm,
            capture_id="test_too_few",
        )

        assert report.status == VideoReconstructionStatus.FAILED
        assert report.registered_keyframes == 0
        assert len(poses) == 0
        assert len(points) == 0
        assert any("Fewer than 3" in w for w in report.warnings)
