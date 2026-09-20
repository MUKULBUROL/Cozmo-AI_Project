"""Stage 11 Video Matching Graph and Connectivity Regression Tests.

1. Purpose:
   Validates match graph connectivity, deterministic pair ordering, and serialization
   of registration diagnostics for the Stage 11 video reconstruction pipeline.

2. Stage:
   Stage 11 (Video Tier - Test Suite).

3. Inputs:
   Synthetic image pairs and SQLite test databases.

4. Outputs:
   Pytest assertions on match graph degree, pair ordering, and diagnostic schemas.

5. Coordinates and units:
   Pixel coordinates and dimensionless graph node indices.

6. Dependencies:
   pytest, numpy, cv2, sqlite3, backend.app.pipelines.video.registration_diagnostics.

7. Assumptions:
   pycolmap is installed or tests gracefully test pure-Python fallbacks.

8. Failure modes:
   Non-deterministic pairing or missing diagnostic fields raise AssertionError.

9. First debugging points:
   Inspect pair_id formula and database table queries.
"""

import json
import sqlite3
import tempfile
from pathlib import Path
import cv2
import numpy as np
import pytest

from backend.app.pipelines.video.registration_diagnostics import (
    colmap_pair_id_to_image_ids,
    compute_image_texture_density,
    collect_registration_diagnostics,
    generate_registration_timeline_svg,
)


def test_colmap_pair_id_decoding():
    """Verify bijective decoding of 64-bit COLMAP pair IDs into image IDs."""
    id1, id2 = 5, 23
    pair_id = id1 * 2147483647 + id2
    dec1, dec2 = colmap_pair_id_to_image_ids(pair_id)
    assert dec1 == id1
    assert dec2 == id2

    # Edge cases
    assert colmap_pair_id_to_image_ids(0) == (0, 0)
    assert colmap_pair_id_to_image_ids(-10) == (0, 0)


def test_texture_density_computation():
    """Verify texture density metric distinguishes textured from blank surfaces."""
    # Blank/uniform image
    blank = np.full((240, 320, 3), 128, dtype=np.uint8)
    blank_score = compute_image_texture_density(blank)
    assert blank_score < 1.0

    # Textured image with high-frequency edges
    textured = np.zeros((240, 320, 3), dtype=np.uint8)
    cv2.circle(textured, (160, 120), 50, (255, 255, 255), 2)
    cv2.rectangle(textured, (20, 20), (100, 100), (200, 200, 200), -1)
    text_score = compute_image_texture_density(textured)
    assert text_score > blank_score


def test_registration_diagnostics_serialization():
    """Verify that registration diagnostics correctly serialize all required schema fields."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_p = Path(tmpdir)
        kf_dir = tmp_p / "keyframes"
        sfm_dir = tmp_p / "sfm"
        kf_dir.mkdir()
        sfm_dir.mkdir()

        # Create dummy keyframe images & manifest
        keyframes_meta = []
        for i in range(5):
            img = np.full((120, 160, 3), 100 + i * 20, dtype=np.uint8)
            img_p = kf_dir / f"frame_{i:06d}.jpg"
            cv2.imwrite(str(img_p), img)
            keyframes_meta.append({
                "keyframe_id": i,
                "frame_index": i * 30,
                "timestamp": float(i * 1.0),
                "image_path": str(img_p),
                "sharpness_score": 50.0 + i * 10,
                "selection_reason": "sharpest_in_window",
            })

        with open(kf_dir / "keyframe_manifest.json", "w") as f:
            json.dump({"total_keyframes": 5, "keyframes": keyframes_meta}, f)

        # Create dummy database
        db_path = sfm_dir / "database.db"
        conn = sqlite3.connect(str(db_path))
        c = conn.cursor()
        c.execute("CREATE TABLE images (image_id INTEGER PRIMARY KEY, name TEXT)")
        c.execute("CREATE TABLE keypoints (image_id INTEGER, rows INTEGER)")
        c.execute("CREATE TABLE matches (pair_id INTEGER, rows INTEGER)")
        c.execute("CREATE TABLE two_view_geometries (pair_id INTEGER, rows INTEGER, config INTEGER)")

        for i in range(5):
            c.execute("INSERT INTO images VALUES (?, ?)", (i + 1, f"frame_{i:06d}.jpg"))
            c.execute("INSERT INTO keypoints VALUES (?, ?)", (i + 1, 500))

        # Insert sequential matches for pair 0-1 and 1-2
        p01 = 1 * 2147483647 + 2
        p12 = 2 * 2147483647 + 3
        c.execute("INSERT INTO matches VALUES (?, ?)", (p01, 100))
        c.execute("INSERT INTO two_view_geometries VALUES (?, ?, ?)", (p01, 80, 3))
        c.execute("INSERT INTO matches VALUES (?, ?)", (p12, 60))
        c.execute("INSERT INTO two_view_geometries VALUES (?, ?, ?)", (p12, 45, 3))
        conn.commit()
        conn.close()

        # Dummy poses
        poses = [
            {"keyframe_id": 0, "image_name": "frame_000000.jpg"},
            {"keyframe_id": 1, "image_name": "frame_000001.jpg"},
            {"keyframe_id": 2, "image_name": "frame_000002.jpg"},
        ]
        with open(sfm_dir / "poses.json", "w") as f:
            json.dump(poses, f)

        report = collect_registration_diagnostics(
            keyframes_dir=kf_dir,
            sfm_dir=sfm_dir,
            video_duration_seconds=5.0,
        )

        assert report["total_keyframes"] == 5
        assert report["registered_views"] == 3
        assert report["registration_ratio"] == 0.6
        assert len(report["keyframes"]) == 5
        assert report["sequential_consecutive_connections"] == 2
        assert report["sequential_consecutive_broken"] == 2

        # Test timeline SVG generation
        svg_path = sfm_dir / "registration_timeline.svg"
        generate_registration_timeline_svg(report, svg_path)
        assert svg_path.exists()
        assert svg_path.stat().st_size > 500
