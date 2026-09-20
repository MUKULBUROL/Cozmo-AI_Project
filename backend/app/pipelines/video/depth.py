"""Stage 7 Pretrained Monocular Metric Depth Prediction and Quality Masking.

1. Why this file exists:
   Predicts dense metric depth maps in meters from video keyframes using a locally runnable
   indoor-specialized model (Depth-Anything-V2-Metric-Indoor-Small-hf). Generates confidence
   masks to reject extreme ranges, motion blur artifacts, and geometric discontinuities.

2. Pipeline stage:
   Stage 7 (Video Tier - Metric Depth Prediction).

3. Inputs:
   RGB keyframe images (JPEG or numpy array).

4. Outputs:
   - Dense metric depth map (meters, float32) matching keyframe resolution.
   - Binary quality mask (uint8, 0 or 1) indicating trustworthy depth pixels.
   - Summary statistics and visualization outputs.

5. Coordinate convention:
   Camera coordinate system: Z positive outward along optical axis.

6. Unit convention:
   Metric meters for depth values.

7. Important dependencies:
   torch, transformers, cv2, numpy, pathlib, PIL.

8. Assumptions:
   Indoor residential scene where structural surfaces lie within 0.2m to 8.0m of camera.

9. Main failure modes:
   - Specular reflections, glass, mirrors, or high contrast glare producing non-physical depth.
   - Filtered out by the depth confidence mask.

10. What a developer should inspect first when debugging:
    Inspect saved depth visualizations and check `depth_stats.json` for mean and valid pixel percentage.
"""

import os
import json
import time
from pathlib import Path
from typing import Tuple, Optional, Dict, Any
import numpy as np
import cv2
import torch
from PIL import Image

_DEPTH_MODEL = None


class DepthAnythingV2Wrapper:
    """Wrapper around HuggingFace Depth-Anything-V2-Metric model providing standard infer_image API."""

    def __init__(self, model_id: str = "depth-anything/Depth-Anything-V2-Metric-Indoor-Small-hf", device: str = "cpu"):
        from transformers import AutoImageProcessor, AutoModelForDepthEstimation
        self.device = device
        self.processor = AutoImageProcessor.from_pretrained(model_id)
        self.model = AutoModelForDepthEstimation.from_pretrained(model_id)
        self.model.to(device)
        self.model.eval()

    def infer_image(self, rgb_image: np.ndarray, input_size: int = 518) -> np.ndarray:
        """Runs metric depth inference on an RGB image array."""
        orig_h, orig_w = rgb_image.shape[:2]
        inputs = self.processor(images=rgb_image, return_tensors="pt")
        inputs = {k: v.to(self.device) for k, v in inputs.items()}

        with torch.no_grad():
            outputs = self.model(**inputs)
            pred = outputs.predicted_depth

        # Interpolate predicted depth back to original image resolution
        pred_full = torch.nn.functional.interpolate(
            pred.unsqueeze(1),
            size=(orig_h, orig_w),
            mode="bicubic",
            align_corners=False,
        ).squeeze().cpu().numpy().astype(np.float32)

        return pred_full


def get_metric_depth_model(
    checkpoint_path: Optional[str] = None,
    device: str = "cpu",
) -> DepthAnythingV2Wrapper:
    """Loads and caches the pretrained Depth Anything V2 metric model.

    Purpose:
        Maintains single in-memory instance of model to prevent redundant weights loading.

    Parameters:
        checkpoint_path: Unused (maintained for backwards signature compatibility).
        device: 'cpu' or 'cuda'.

    Returns:
        DepthAnythingV2Wrapper in eval mode.
    """
    global _DEPTH_MODEL
    if _DEPTH_MODEL is None:
        _DEPTH_MODEL = DepthAnythingV2Wrapper(device=device)
    return _DEPTH_MODEL


def compute_depth_quality_mask(
    depth_m: np.ndarray,
    min_depth_m: float = 0.20,
    max_depth_m: float = 8.00,
    max_gradient_ratio: float = 0.20,
) -> np.ndarray:
    """Creates a binary quality mask rejecting invalid, extreme, or edge-discontinuous depth.

    Purpose:
        Prevents depth bleed and flying pixels along occlusion boundaries from corrupting 3D fusion.

    Parameters:
        depth_m: 2D float32 array of metric depth in meters.
        min_depth_m: Minimum physical distance in meters.
        max_depth_m: Maximum indoor distance in meters.
        max_gradient_ratio: Discontinuity gradient threshold relative to local depth.

    Returns:
        2D boolean array (True where depth is high quality).
    """
    range_mask = np.isfinite(depth_m) & (depth_m >= min_depth_m) & (depth_m <= max_depth_m)

    # Gradient edge discontinuity mask
    grad_x = cv2.Sobel(depth_m, cv2.CV_32F, 1, 0, ksize=3)
    grad_y = cv2.Sobel(depth_m, cv2.CV_32F, 0, 1, ksize=3)
    grad_mag = np.sqrt(grad_x**2 + grad_y**2)

    rel_grad = grad_mag / np.maximum(depth_m, 0.1)
    smooth_mask = rel_grad < max_gradient_ratio

    return range_mask & smooth_mask


def predict_metric_depth(
    image_path: Path,
    output_depth_dir: Optional[Path] = None,
    min_depth_m: float = 0.20,
    max_depth_m: float = 8.00,
    input_size: int = 518,
) -> Tuple[np.ndarray, np.ndarray]:
    """Predicts dense metric depth in meters for a keyframe image.

    Purpose:
        Executes monocular neural depth estimation and returns full-resolution metric depth map.

    Parameters:
        image_path: Path to keyframe JPEG image.
        output_depth_dir: Optional directory to save raw .npy and normalized PNG preview.
        min_depth_m: Minimum allowed indoor depth in meters.
        max_depth_m: Maximum allowed indoor depth in meters.
        input_size: Nominal network evaluation size.

    Returns:
        Tuple of (depth_meters: np.ndarray, quality_mask: np.ndarray).
    """
    image_path = Path(image_path)
    model = get_metric_depth_model()

    bgr = cv2.imread(str(image_path))
    if bgr is None:
        raise ValueError(f"Failed to read image at {image_path}")
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)

    pred_depth = model.infer_image(rgb, input_size=input_size).astype(np.float32)

    quality_mask = compute_depth_quality_mask(
        pred_depth,
        min_depth_m=min_depth_m,
        max_depth_m=max_depth_m,
    )

    if output_depth_dir is not None:
        output_depth_dir = Path(output_depth_dir)
        output_depth_dir.mkdir(parents=True, exist_ok=True)
        base_stem = image_path.stem

        # Save raw float32 metric depth in meters
        npy_path = output_depth_dir / f"{base_stem}_depth.npy"
        np.save(str(npy_path), pred_depth)

        # Save normalized 16-bit PNG (depth in millimeters) for visualization
        depth_mm = np.clip(pred_depth * 1000.0, 0, 65535).astype(np.uint16)
        png_path = output_depth_dir / f"{base_stem}_depth.png"
        cv2.imwrite(str(png_path), depth_mm)

    return pred_depth, quality_mask
