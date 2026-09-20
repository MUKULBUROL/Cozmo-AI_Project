"""Image quality gate and optical pre-validation for visual damage detection.

1. Why this file exists:
   Screens RGB candidate frames prior to damage inference to reject or downgrade
   images affected by severe motion blur, extreme under/over-exposure, or inadequate
   resolution, preventing false-positive damage hallucination from corrupted visual input.

2. Pipeline stage:
   Stage 9 (Damage Detection, Metric Extent, Concealed-Damage Rules & Repair Scope) - Quality Gate.

3. Inputs:
   File path to RGB image or uint8 RGB numpy image array.

4. Outputs:
   DamageQualityGate Pydantic model containing sharpness score, mean luminance,
   contrast standard deviation, image dimensions, and USABLE/PROVISIONAL/REJECTED status.

5. Coordinate convention:
   2D image pixel array with dimensions (Height, Width, Channels).

6. Unit convention:
   Pixel dimensions: integer counts.
   Sharpness score: Laplacian variance (dimensionless float).
   Luminance / Brightness: range [0.0, 255.0].
   Contrast: standard deviation of luminance [0.0, 128.0].

7. Dependencies:
   typing, numpy, cv2, PIL.Image, backend.app.models.damage.

8. Assumptions:
   - Images are loaded as standard 3-channel RGB or BGR arrays.
   - Low-quality frames (e.g. extreme blur) should not run full damage inference.

9. Failure modes:
   - Corrupted or truncated JPEG/PNG image files.
   - Zero-byte images or non-image files.

10. First things to inspect while debugging:
    - Inspect sharpness_score threshold (default rejection < 25.0, provisional < 60.0).
    - Check mean_brightness (darkness < 20.0, overexposure > 240.0).
    - Check image resolution width and height.
"""

from pathlib import Path
from typing import Union, List, Optional, Tuple
import numpy as np
import cv2
from PIL import Image

from ..models.damage import DamageQualityGate, DamageQualityStatus


class DamageImageQualityGate:
    """Pre-inference filter validating visual sharpness, illumination, and resolution."""

    def __init__(
        self,
        min_width: int = 640,
        min_height: int = 480,
        min_sharpness_usable: float = 15.0,
        min_sharpness_provisional: float = 5.0,
        min_brightness: float = 20.0,
        max_brightness: float = 240.0,
        min_contrast: float = 12.0,
    ):
        """Initializes the quality gate thresholds.

        Purpose:
            Configures operational boundaries for blur, illumination, and size filtering.

        Parameters:
            min_width: Minimum acceptable image width in pixels.
            min_height: Minimum acceptable image height in pixels.
            min_sharpness_usable: Laplacian variance cutoff for fully USABLE status.
            min_sharpness_provisional: Laplacian variance cutoff for PROVISIONAL status.
            min_brightness: Lower average luminance threshold (below is underexposed/dark).
            max_brightness: Upper average luminance threshold (above is washed out/overexposed).
            min_contrast: Minimum acceptable luminance standard deviation.

        Returns:
            None.

        Assumptions:
            Laplacian variance scales with high-frequency edge content.

        Failure cases:
            None.

        Debugging clues:
            Lower min_sharpness_usable if inspecting intentionally soft or matte indoor surfaces.
        """
        self.min_width = min_width
        self.min_height = min_height
        self.min_sharpness_usable = min_sharpness_usable
        self.min_sharpness_provisional = min_sharpness_provisional
        self.min_brightness = min_brightness
        self.max_brightness = max_brightness
        self.min_contrast = min_contrast

    def assess_image(
        self,
        image_input: Union[str, Path, np.ndarray],
        image_id: Optional[str] = None,
    ) -> DamageQualityGate:
        """Evaluates image quality metrics and assigns gate status.

        Purpose:
            Extracts sharpness, brightness, contrast, and resolution diagnostics,
            categorizing the frame into USABLE, PROVISIONAL, or REJECTED.

        Parameters:
            image_input: File path string, Path object, or uint8 image array (H, W, 3).
            image_id: Optional identifier string for the image (defaults to filename).

        Returns:
            DamageQualityGate Pydantic object.

        Assumptions:
            Array inputs have uint8 dtype in range [0, 255].

        Failure cases:
            Returns REJECTED status with 'file_unreadable' reason if loading fails.

        Debugging clues:
            Inspect rejection_reasons in the returned gate object.
        """
        img_arr: Optional[np.ndarray] = None
        img_name = image_id or "unknown_frame"

        if isinstance(image_input, (str, Path)):
            path_obj = Path(image_input)
            if not image_id:
                img_name = path_obj.name
            if not path_obj.exists():
                return DamageQualityGate(
                    image_id=img_name,
                    status=DamageQualityStatus.REJECTED,
                    sharpness_score=0.0,
                    mean_brightness=0.0,
                    contrast_score=0.0,
                    width=1,
                    height=1,
                    rejection_reasons=["file_not_found"],
                )
            try:
                # Use PIL or cv2
                pil_img = Image.open(str(path_obj)).convert("RGB")
                img_arr = np.array(pil_img)
            except Exception as e:
                return DamageQualityGate(
                    image_id=img_name,
                    status=DamageQualityStatus.REJECTED,
                    sharpness_score=0.0,
                    mean_brightness=0.0,
                    contrast_score=0.0,
                    width=1,
                    height=1,
                    rejection_reasons=[f"file_unreadable: {str(e)}"],
                )
        elif isinstance(image_input, np.ndarray):
            img_arr = image_input
        else:
            return DamageQualityGate(
                image_id=img_name,
                status=DamageQualityStatus.REJECTED,
                sharpness_score=0.0,
                mean_brightness=0.0,
                contrast_score=0.0,
                width=1,
                height=1,
                rejection_reasons=["invalid_input_type"],
            )

        if img_arr is None or img_arr.size == 0 or len(img_arr.shape) < 2:
            return DamageQualityGate(
                image_id=img_name,
                status=DamageQualityStatus.REJECTED,
                sharpness_score=0.0,
                mean_brightness=0.0,
                contrast_score=0.0,
                width=1,
                height=1,
                rejection_reasons=["empty_image_array"],
            )

        h, w = img_arr.shape[:2]
        rejection_reasons: List[str] = []

        # Check resolution
        if w < self.min_width or h < self.min_height:
            rejection_reasons.append(f"low_resolution_{w}x{h}")

        # Convert to grayscale for illumination and focus analysis
        if len(img_arr.shape) == 3:
            gray = cv2.cvtColor(img_arr, cv2.COLOR_RGB2GRAY)
        else:
            gray = img_arr

        # 1. Focus sharpness via Laplacian variance
        lap = cv2.Laplacian(gray, cv2.CV_64F)
        sharpness = float(lap.var())

        # 2. Illumination and contrast
        mean_bright = float(np.mean(gray))
        contrast = float(np.std(gray))

        if mean_bright < self.min_brightness:
            rejection_reasons.append(f"extreme_darkness_{mean_bright:.1f}")
        elif mean_bright > self.max_brightness:
            rejection_reasons.append(f"overexposure_{mean_bright:.1f}")

        if contrast < self.min_contrast:
            rejection_reasons.append(f"insufficient_contrast_{contrast:.1f}")

        # Determine status
        status = DamageQualityStatus.USABLE
        if any("low_resolution" in r or "extreme_darkness" in r or "overexposure" in r for r in rejection_reasons):
            status = DamageQualityStatus.REJECTED
        elif sharpness < self.min_sharpness_provisional:
            rejection_reasons.append(f"severe_blur_{sharpness:.1f}")
            status = DamageQualityStatus.REJECTED
        elif sharpness < self.min_sharpness_usable or rejection_reasons:
            if sharpness < self.min_sharpness_usable:
                rejection_reasons.append(f"moderate_blur_{sharpness:.1f}")
            status = DamageQualityStatus.PROVISIONAL

        return DamageQualityGate(
            image_id=img_name,
            status=status,
            sharpness_score=round(sharpness, 2),
            mean_brightness=round(mean_bright, 2),
            contrast_score=round(contrast, 2),
            width=w,
            height=h,
            rejection_reasons=rejection_reasons,
        )
