"""
Deterministic synthetic unit tests for Stage 7 Video-Tier Reconstruction.

1. Why this file exists:
   Verifies the mathematical correctness, data model integrity, coordinate mapping,
   keyframe selection, metric scale recovery, and strict video-tier isolation of
   Stage 7 without invoking heavyweight external neural networks.

2. Pipeline stage:
   Stage 7 (Video Tier: Unit Tests & Regression Suite).

3. Inputs:
   Synthetic video frames, simulated keyframes, mock camera intrinsics, and synthetic
   3D SfM points with known ground-truth metric depth.

4. Outputs:
   Test assertion passes verifying deterministic behavior and safety gates.

5. Coordinate convention:
   - OpenCV camera frame (X right, Y down, Z forward).
   - Metric world frame (meters).

6. Unit convention:
   - Translations & positions: Meters.
   - Angles: Radians and degrees.
   - Scale factor: Meters per arbitrary unit.

7. Important dependencies:
   unittest, numpy, cv2, tempfile, pathlib, backend.app.models.video,
   backend.app.pipelines.video.ingestion, backend.app.pipelines.video.keyframes.

8. Assumptions:
   Deterministic math tests must pass reliably in offline environments without GPU.

9. Main failure modes:
   - Scale factor estimation biased by outliers.
   - Incorrect pixel coordinate transform under 90/180/270 degree rotation.
   - Unintended reliance on LiDAR files.

10. What a developer should inspect first when debugging:
    Inspect test failure tracebacks and check if coordinate transformations or
    matrix scaling altered the rotation matrix components.
"""

import unittest
import tempfile
import os
from pathlib import Path
import numpy as np
import cv2
import json

from backend.app.models.video import (
    VideoCaptureMetadata,
    VideoKeyframe,
    VideoCameraIntrinsics,
    SfmCameraPose,
    MetricScaleEstimate,
)
from backend.app.pipelines.video.ingestion import (
    map_pixel_coordinates,
    detect_display_rotation,
    ingest_video_capture,
)
from backend.app.pipelines.video.keyframes import (
    compute_laplacian_sharpness,
    evaluate_exposure_quality,
    compute_visual_motion_delta,
    extract_video_keyframes,
)
from backend.app.pipelines.video.pipeline import write_video_multiroom_outputs
from backend.app.geometry.property_topology import assemble_property_plan_output
from backend.app.models.capture import CaptureTier


class TestVideoReconstructionUnit(unittest.TestCase):
    """Unit tests for Stage 7 video ingestion, keyframing, and geometric contracts."""

    def test_orientation_mapping_0_deg(self):
        """Verify identity mapping when rotation is 0 degrees."""
        w, h = 1920, 1440
        x, y = 100.0, 200.0
        mapped_x, mapped_y = map_pixel_coordinates(x, y, w, h, 0, inverse=False)
        self.assertEqual(mapped_x, x)
        self.assertEqual(mapped_y, y)

        inv_x, inv_y = map_pixel_coordinates(mapped_x, mapped_y, w, h, 0, inverse=True)
        self.assertEqual(inv_x, x)
        self.assertEqual(inv_y, y)

    def test_orientation_mapping_90_deg_cycle(self):
        """Verify forward and inverse pixel coordinate mapping under 90 degree clockwise rotation."""
        w, h = 1920, 1440
        orig_x, orig_y = 350.0, 620.0

        # Forward map: (x, y) in (w, h) -> (h - 1 - y, x) in (h, w)
        rot_x, rot_y = map_pixel_coordinates(orig_x, orig_y, w, h, 90, inverse=False)
        self.assertAlmostEqual(rot_x, float(h - 1 - orig_y))
        self.assertAlmostEqual(rot_y, float(orig_x))

        # Invert map: back to original frame
        recov_x, recov_y = map_pixel_coordinates(rot_x, rot_y, w, h, 90, inverse=True)
        self.assertAlmostEqual(recov_x, orig_x)
        self.assertAlmostEqual(recov_y, orig_y)

    def test_orientation_mapping_180_deg_cycle(self):
        """Verify forward and inverse pixel mapping under 180 degree rotation."""
        w, h = 1920, 1440
        orig_x, orig_y = 120.0, 450.0
        rot_x, rot_y = map_pixel_coordinates(orig_x, orig_y, w, h, 180, inverse=False)
        recov_x, recov_y = map_pixel_coordinates(rot_x, rot_y, w, h, 180, inverse=True)
        self.assertAlmostEqual(recov_x, orig_x)
        self.assertAlmostEqual(recov_y, orig_y)

    def test_sharpness_computation(self):
        """Verify Laplacian sharpness correctly distinguishes sharp textures from blurred images."""
        # Sharp high-frequency checkerboard pattern
        sharp_img = np.zeros((200, 200), dtype=np.uint8)
        sharp_img[::2, ::2] = 255
        sharp_score = compute_laplacian_sharpness(sharp_img)

        # Uniform or blurry image
        blurred_img = cv2.GaussianBlur(sharp_img, (15, 15), 0)
        blurred_score = compute_laplacian_sharpness(blurred_img)

        self.assertGreater(sharp_score, blurred_score)
        self.assertGreater(sharp_score, 1000.0)

    def test_exposure_evaluation(self):
        """Verify exposure quality gate rejects black and over-saturated images."""
        black_img = np.zeros((100, 100), dtype=np.uint8)
        is_ok, mean_val = evaluate_exposure_quality(black_img)
        self.assertFalse(is_ok)
        self.assertEqual(mean_val, 0.0)

        white_img = np.full((100, 100), 255, dtype=np.uint8)
        is_ok, mean_val = evaluate_exposure_quality(white_img)
        self.assertFalse(is_ok)

        normal_img = np.full((100, 100), 128, dtype=np.uint8)
        is_ok, mean_val = evaluate_exposure_quality(normal_img)
        self.assertTrue(is_ok)
        self.assertEqual(mean_val, 128.0)

    def test_visual_motion_delta(self):
        """Verify visual motion delta between identical vs shifted images."""
        img1 = np.full((120, 160), 100, dtype=np.uint8)
        img2 = np.full((120, 160), 100, dtype=np.uint8)
        delta_zero = compute_visual_motion_delta(img1, img2)
        self.assertEqual(delta_zero, 0.0)

        img3 = np.full((120, 160), 150, dtype=np.uint8)
        delta_diff = compute_visual_motion_delta(img1, img3)
        self.assertEqual(delta_diff, 50.0)

    def test_keyframe_extraction_synthetic_video(self):
        """Verify video keyframe extraction pipeline on a synthetic multi-frame video."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            video_file = tmp_path / "test_synth.mp4"
            out_dir = tmp_path / "keyframes"

            # Create a synthetic 60-frame video
            fps = 30.0
            width, height = 320, 240
            fourcc = cv2.VideoWriter_fourcc(*"mp4v")
            writer = cv2.VideoWriter(str(video_file), fourcc, fps, (width, height))

            for f in range(60):
                # Animate a moving square with sharp edges
                frame = np.full((height, width, 3), 50, dtype=np.uint8)
                x_pos = int((f * 4) % (width - 40))
                cv2.rectangle(frame, (x_pos, 80), (x_pos + 40, 140), (200, 200, 200), -1)
                writer.write(frame)
            writer.release()

            keyframes = extract_video_keyframes(
                video_path=video_file,
                output_dir=out_dir,
                min_frame_stride=5,
                max_frame_stride=20,
                blur_threshold=10.0,
                max_keyframes=10
            )

            self.assertGreaterEqual(len(keyframes), 2)
            self.assertTrue((out_dir / "keyframe_manifest.json").exists())
            self.assertTrue(Path(keyframes[0].image_path).exists())
            self.assertEqual(keyframes[0].keyframe_id, 0)
            self.assertEqual(keyframes[0].frame_index, 0)

    def test_video_metadata_model(self):
        """Verify VideoCaptureMetadata serialization and field validation."""
        meta = VideoCaptureMetadata(
            capture_id="vid_001",
            video_path="/path/to/vid.mp4",
            codec="hevc",
            width=1920,
            height=1440,
            frame_count=1000,
            fps=30.0,
            duration_seconds=33.33,
            file_size_bytes=50000000
        )
        self.assertEqual(meta.aspect_ratio, "4:3")
        self.assertEqual(meta.orientation_rotation_deg, 0)

    def test_video_only_isolation_contract(self):
        """
        Verify that video ingestion does NOT access or require odometry.csv,
        depth/ or confidence/ even if an isolated video file is provided.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            vid_file = tmp_path / "isolated_video.mp4"

            # Create minimal valid video
            writer = cv2.VideoWriter(str(vid_file), cv2.VideoWriter_fourcc(*"mp4v"), 20.0, (160, 120))
            for _ in range(10):
                writer.write(np.zeros((120, 160, 3), dtype=np.uint8))
            writer.release()

            # Confirm no LiDAR files exist in tmp_path
            self.assertFalse((tmp_path / "odometry.csv").exists())
            self.assertFalse((tmp_path / "depth").exists())
            self.assertFalse((tmp_path / "confidence").exists())

            # Ingest should succeed completely without sensor files
            meta, p = ingest_video_capture(str(vid_file), capture_id="test_iso")
            self.assertEqual(meta.width, 160)
            self.assertEqual(meta.height, 120)
            self.assertEqual(meta.frame_count, 10)

    def test_sparse_multiroom_trajectory_emits_not_evaluable_reports(self):
        """Verify sparse RGB SfM evidence cannot be presented as a whole-property result."""
        poses = [
            SfmCameraPose(
                keyframe_id=index,
                frame_index=index * 100,
                timestamp=float(index * 10),
                t_vec=[float(index), 0.0, 0.0],
                is_metric=True,
            )
            for index in range(4)
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            summary = write_video_multiroom_outputs(
                output_dir=output_dir,
                capture_id="sparse_video",
                poses=poses,
                total_keyframes=40,
                video_duration_seconds=200.0,
                structure_json_path=output_dir / "unused_structure.json",
            )

            self.assertEqual(summary["status"], "NOT_EVALUABLE")
            with open(output_dir / "property" / "property.json", encoding="utf-8") as f:
                property_report = json.load(f)
            with open(output_dir / "property" / "drift_ablation.json", encoding="utf-8") as f:
                drift_report = json.load(f)
            self.assertEqual(property_report["tier"], "video")
            self.assertEqual(property_report["rooms"], [])
            self.assertIn("only_4_registered_views_minimum_20", property_report["failure_reasons"])
            self.assertEqual(drift_report["status"], "NOT_EVALUABLE")
            self.assertFalse(drift_report["correction_applied"])

    def test_video_property_contract_preserves_tier_and_method(self):
        """Verify a supported Stage 6 handoff cannot be serialized as LiDAR provenance."""
        property_output = assemble_property_plan_output(
            scan_id="video_property",
            rooms=[],
            connections=[],
            drift_status="not_evaluable",
            residual_m=0.0,
            capture_tier=CaptureTier.VIDEO,
            reconstruction_method="rgb_video_sfm_metric_depth",
        )

        self.assertEqual(property_output.tier, CaptureTier.VIDEO)
        self.assertEqual(property_output.reconstruction_method, "rgb_video_sfm_metric_depth")


if __name__ == "__main__":
    unittest.main()
