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
   - Summary statistics in `depth_stats.json`.

5. Coordinate convention:
   Camera coordinate system: Z positive outward along optical axis.

6. Unit convention:
   Metric meters for depth values.

7. Important dependencies:
   torch, transformers, cv2, numpy, pathlib, PIL.

8. Assumptions:
   Indoor residential scene where structural surfaces lie within 0.2m to 6.0m of camera.

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
_IMAGE_PROCESSOR = None


def get_metric_depth_model(model_id: str = "depth-anything/Depth-Anything-V2-Metric-Indoor-Small-hf"):
    """Loads and caches the pretrained metric depth model on CPU.

    Purpose:
        Maintains single in-memory instance of model to prevent redundant weights loading.

    Parameters:
        model_id: Hugging Face model identifier.

    Returns:
        Tuple of (model, image_processor).
    """
    global _DEPTH_MODEL, _IMAGE_PROCESSOR
    if _DEPTH_MODEL is None or _IMAGE_PROCESSOR is None:
        from transformers import AutoImageProcessor, AutoModelForDepthEstimation
        _IMAGE_PROCESSOR = AutoImageProcessor.from_pretrained(model_id)
        _DEPTH_MODEL = AutoModelForDepthEstimation.from_pretrained(model_id)
        _DEPTH_MODEL.eval()
    return _DEPTH_MODEL, _IMAGE_PROCESSOR


def compute_depth_quality_mask(
    depth_m: np.ndarray,
    min_depth_m: float = 0.20,
    max_depth_m: float = 6.00,
    max_gradient_ratio: float = 0.15,
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

    Assumptions:
        Structural walls and floors produce smooth, continuous depth within valid indoor bounds.
    """
    # Finite and valid range mask
    range_mask = np.isfinite(depth_m) & (depth_m >= min_depth_m) & (depth_m <= max_depth_m)

    # Gradient edge discontinuity mask
    grad_x = cv2.Sobel(depth_m, cv2.CV_32F, 1, 0, ksize=3)
    grad_y = cv2.Sobel(depth_m, cv2.CV_32F, 0, 1, ksize=3)
    grad_mag = np.sqrt(grad_x**2 + grad_y**2)

    # Discontinuity threshold proportional to local depth
    rel_grad = grad_mag / np.maximum(depth_m, 0.1)
    smooth_mask = rel_grad < max_gradient_ratio

    return range_mask & smooth_mask


def predict_metric_depth(
    image_path: Path,
    output_depth_dir: Optional[Path] = None,
    min_depth_m: float = 0.20,
    max_depth_m: float = 6.00,
) -> Tuple[np.ndarray, np.ndarray]:
    """Predicts dense metric depth in meters for a keyframe image.

    Purpose:
        Executes monocular neural depth estimation and returns full-resolution metric depth map.

    Parameters:
        image_path: Path to keyframe JPEG image.
        output_depth_dir: Optional directory to save raw .npy and normalized PNG preview.
        min_depth_m: Minimum allowed indoor depth in meters.
        max_depth_m: Maximum allowed indoor depth in meters.

    Returns:
        Tuple of (depth_meters: np.ndarray, quality_mask: np.ndarray).

    Assumptions:
        Image is an RGB frame from an indoor walkthrough.

    Dependencies:
        torch, transformers, get_metric_depth_model, compute_depth_quality_mask.
    """
    image_path = Path(image_path)
    model, processor = get_metric_depth_model()

    pil_img = Image.open(str(image_path)).convert("RGB")
    orig_w, orig_h = pil_img.size

    inputs = processor(images=pil_img, return_tensors="pt")

    with torch.no_grad():
        outputs = model(**inputs)
        # Predicted depth is in meters
        pred_depth = outputs.predicted_depth

    # Interpolate predicted depth to original image resolution
    pred_depth = torch.nn.functional.interpolate(
        pred_depth.unsqueeze(1),
        size=(orig_h, orig_w),
        mode="bicubic",
        align_corners=False,
    ).squeeze().cpu().numpy().astype(np.float32)

    # Generate confidence quality mask
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
