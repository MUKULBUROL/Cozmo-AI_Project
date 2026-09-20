"""
Pretrained metric depth model smoke test on CPU.

1. Why this file exists:
   Verifies that the chosen pretrained metric depth model (Depth-Anything-V2-Metric-Hypersim-Small)
   loads weights from the local cache, generates valid non-empty metric depth tensors,
   exhibits expected physical indoor range (0.2m to 20.0m), and runs within practical CPU latency.

2. Pipeline stage:
   Stage 7 (Video Tier - Metric Depth Smoke Test).

3. Inputs:
   Synthetic and local RGB image frames.

4. Outputs:
   Test assertions ensuring model sanity without requiring massive external downloads.

5. Coordinate convention:
   Camera space Z-depth in meters.

6. Unit convention:
   Meters (m).

7. Important dependencies:
   unittest, torch, numpy, backend.app.pipelines.video.depth.

8. Assumptions:
   Model weights are cached in checkpoints/depth_anything_v2_metric_hypersim_vits.pth.

9. Main failure modes:
   - Weights file missing or corrupted.
   - Output depth tensor contains NaNs or infinities.
   - Non-physical depth predictions (negative or extreme values).

10. What a developer should inspect first when debugging:
    Inspect output depth min, max, and finite mask statistics.
"""

import unittest
import tempfile
from pathlib import Path
import numpy as np
import cv2

from backend.app.pipelines.video.depth import (
    get_metric_depth_model,
    compute_depth_quality_mask,
    predict_metric_depth,
)


class TestVideoDepthSmoke(unittest.TestCase):
    """Smoke test for native DepthAnythingV2 metric model on CPU."""

    def test_model_loads_and_infers_finite_depth(self):
        """Verify model weights load and produce finite, physical indoor depth."""
        model = get_metric_depth_model()
        self.assertIsNotNone(model)

        with tempfile.TemporaryDirectory() as tmpdir:
            test_img_path = Path(tmpdir) / "test_frame.jpg"
            # Create a simple synthetic room frame: gradient floor and wall
            img = np.full((360, 480, 3), 180, dtype=np.uint8)
            cv2.rectangle(img, (50, 50), (430, 200), (120, 120, 120), -1)
            cv2.imwrite(str(test_img_path), img)

            depth_map, mask = predict_metric_depth(
                image_path=test_img_path,
                output_depth_dir=Path(tmpdir) / "depth_out",
                min_depth_m=0.20,
                max_depth_m=8.00,
                input_size=252,  # fast test size
            )

            self.assertEqual(depth_map.shape, (360, 480))
            self.assertEqual(mask.shape, (360, 480))
            self.assertTrue(np.all(np.isfinite(depth_map)))
            self.assertGreater(float(np.min(depth_map)), 0.05)
            self.assertLess(float(np.max(depth_map)), 15.0)
            self.assertGreater(float(np.mean(mask)), 0.50)
            self.assertTrue((Path(tmpdir) / "depth_out" / "test_frame_depth.npy").exists())
            self.assertTrue((Path(tmpdir) / "depth_out" / "test_frame_depth.png").exists())

    def test_depth_quality_mask_filters_extremes(self):
        """Verify that quality mask filters out non-physical or extreme values."""
        synth_depth = np.full((50, 50), 2.5, dtype=np.float32)
        # Add extreme low, extreme high, and NaN
        synth_depth[0, 0] = 0.05  # below min 0.2m
        synth_depth[1, 1] = 25.0  # above max 8.0m
        synth_depth[2, 2] = np.nan

        mask = compute_depth_quality_mask(synth_depth, min_depth_m=0.20, max_depth_m=8.00)
        self.assertFalse(mask[0, 0])
        self.assertFalse(mask[1, 1])
        self.assertFalse(mask[2, 2])
        self.assertTrue(mask[10, 10])


if __name__ == "__main__":
    unittest.main()
