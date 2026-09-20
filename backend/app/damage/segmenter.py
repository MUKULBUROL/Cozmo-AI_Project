"""Pixel-level damage boundary segmentation and contour extraction.

1. Why this file exists:
   Converts crude rectangular vision bounding boxes into precise binary pixel masks
   and boundary polygons. Metric damaged area and linear crack length strictly require
   pixel-level masks, as bounding boxes enclose extensive undamaged wall surface.

2. Pipeline stage:
   Stage 9 (Damage Detection, Metric Extent, Concealed-Damage Rules & Repair Scope) - Mask Segmentation.

3. Inputs:
   RGB image array (H, W, 3), candidate bounding box [x1, y1, x2, y2], canonical damage class,
   and optional aligned depth map (H, W).

4. Outputs:
   Dictionary containing binary mask (H, W bool), positive mask pixel count,
   boundary polygon [[u, v], ...], and segmentation confidence score.

5. Coordinate convention:
   2D pixel coordinates: (u, v) with origin (0, 0) at top-left.
   Bounding box: [x1, y1, x2, y2].

6. Unit convention:
   Pixel counts for area; dimensionless confidence in [0.0, 1.0].

7. Dependencies:
   typing, numpy, cv2, backend.app.models.output.DamageClass.

8. Assumptions:
   - Damaged region exhibits measurable contrast (color, luminance, or depth discontinuity)
     relative to surrounding undamaged host surface finish.
   - Morphological filtering removes isolated single-pixel noise.

9. Failure modes:
   - Extremely faint stains matching wall paint hue perfectly (falls back to inner core or soft contrast).
   - Uniform lighting glare across the bounding box.

10. First things to inspect while debugging:
    - Inspect mask_area_pixels (rejects empty or zero-pixel masks).
    - Check whether candidate box coordinates lie within image dimensions.
    - Inspect segmentation_confidence score and boundary contour points.
"""

from typing import Dict, Any, List, Optional, Tuple
import numpy as np
import cv2

from ..models.output import DamageClass


class DamageMaskSegmenter:
    """Extracts fine pixel-level binary masks from candidate bounding boxes."""

    def __init__(
        self,
        min_mask_pixels: int = 25,
        default_confidence: float = 0.85,
        use_grabcut: bool = True,
    ):
        """Initializes segmenter parameters.

        Purpose:
            Configures minimum pixel thresholds and refinement algorithms.

        Parameters:
            min_mask_pixels: Minimum acceptable positive mask area in pixels.
            default_confidence: Baseline segmentation confidence score.
            use_grabcut: Whether to use iterative GrabCut refinement where feasible.

        Returns:
            None.

        Assumptions:
            GrabCut is executed only on cropped ROI for computational speed.

        Failure cases:
            None.

        Debugging clues:
            Disable GrabCut if running on low-resource environments with extreme time constraints.
        """
        self.min_mask_pixels = min_mask_pixels
        self.default_confidence = default_confidence
        self.use_grabcut = use_grabcut

    def segment_candidate(
        self,
        rgb_image: np.ndarray,
        bbox: List[float],
        damage_class: DamageClass,
        depth_map: Optional[np.ndarray] = None,
    ) -> Dict[str, Any]:
        """Segments the damage region within the bounding box.

        Purpose:
            Isolates damaged pixels from surrounding undamaged wall surface and extracts
            the outer boundary polygon.

        Parameters:
            rgb_image: Full-resolution uint8 RGB image array (H, W, 3).
            bbox: Candidate box [x1, y1, x2, y2] in pixel coordinates.
            damage_class: Canonical damage category for tuning segmentation heuristics.
            depth_map: Optional aligned depth map array (H_d, W_d).

        Returns:
            Dictionary with:
            {
                'mask': np.ndarray (H, W bool),
                'mask_area_pixels': int,
                'boundary_polygon': List[List[float]],
                'segmentation_confidence': float,
                'is_fallback': bool,
            }

        Assumptions:
            Image is in RGB channel order.

        Failure cases:
            Falls back to an elliptical inner core if adaptive contrast yields zero pixels.

        Debugging clues:
            Inspect returned boundary_polygon length and mask_area_pixels.
        """
        h_img, w_img = rgb_image.shape[:2]
        x1 = max(0, min(int(round(bbox[0])), w_img - 1))
        y1 = max(0, min(int(round(bbox[1])), h_img - 1))
        x2 = max(0, min(int(round(bbox[2])), w_img))
        y2 = max(0, min(int(round(bbox[3])), h_img))

        full_mask = np.zeros((h_img, w_img), dtype=bool)

        box_w = x2 - x1
        box_h = y2 - y1
        if box_w < 3 or box_h < 3:
            return {
                "mask": full_mask,
                "mask_area_pixels": 0,
                "boundary_polygon": [],
                "segmentation_confidence": 0.0,
                "is_fallback": True,
            }

        roi = rgb_image[y1:y2, x1:x2]

        # Determine segmentation strategy based on damage class
        is_crack = damage_class in [DamageClass.SURFACE_CRACK, DamageClass.CRACK_STRUCTURAL]
        is_hole = damage_class == DamageClass.HOLE_OR_MISSING_MATERIAL
        is_stain_or_mold = damage_class in [
            DamageClass.WATER_STAIN,
            DamageClass.MOLD_LIKE_DISCOLORATION,
            DamageClass.MOLD,
            DamageClass.BURN_OR_CHAR,
        ]

        roi_mask = None

        if is_crack:
            roi_mask = self._segment_crack(roi)
        elif is_hole and depth_map is not None:
            roi_mask = self._segment_depth_step_or_contrast(roi, depth_map, x1, y1, x2, y2, h_img, w_img)
        else:
            roi_mask = self._segment_stain_or_contrast(roi)

        # Validate extracted mask
        positive_px = int(np.count_nonzero(roi_mask))
        is_fallback = False
        conf = self.default_confidence

        if positive_px < self.min_mask_pixels:
            # Fallback: create an inscribed elliptical kernel inside bounding box
            roi_mask = np.zeros((box_h, box_w), dtype=np.uint8)
            center = (box_w // 2, box_h // 2)
            axes = (max(1, int(box_w * 0.40)), max(1, int(box_h * 0.40)))
            cv2.ellipse(roi_mask, center, axes, 0, 0, 360, 1, -1)
            positive_px = int(np.count_nonzero(roi_mask))
            is_fallback = True
            conf = 0.50

        # Place ROI mask into full image mask
        full_mask[y1:y2, x1:x2] = (roi_mask > 0)

        # Extract boundary contour polygon
        boundary_pts = self._extract_contour_polygon(roi_mask, offset_x=x1, offset_y=y1)

        return {
            "mask": full_mask,
            "mask_area_pixels": positive_px,
            "boundary_polygon": boundary_pts,
            "segmentation_confidence": round(conf, 3),
            "is_fallback": is_fallback,
        }

    def _segment_stain_or_contrast(self, roi: np.ndarray) -> np.ndarray:
        """Segments water stains or discoloration via color/luminance contrast."""
        h, w = roi.shape[:2]
        gray = cv2.cvtColor(roi, cv2.COLOR_RGB2GRAY)

        # Gaussian smoothing to suppress micro-texture
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)

        # Compute difference from border pixels (representing undamaged wall background)
        border_pixels = np.concatenate([
            blurred[0, :], blurred[-1, :], blurred[:, 0], blurred[:, -1]
        ])
        bg_mean = np.median(border_pixels)
        bg_std = max(np.std(border_pixels), 8.0)

        # Pixels deviating by more than 1.5 standard deviations from background
        diff = np.abs(blurred.astype(float) - bg_mean)
        thresh_val = max(12.0, 1.5 * bg_std)
        binary = (diff > thresh_val).astype(np.uint8)

        # Morphological opening and closing
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)
        binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)

        # Retain only the largest connected component
        num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(binary)
        if num_labels > 1:
            largest_label = 1 + np.argmax(stats[1:, cv2.CC_STAT_AREA])
            binary = (labels == largest_label).astype(np.uint8)

        return binary

    def _segment_crack(self, roi: np.ndarray) -> np.ndarray:
        """Segments thin linear crack boundaries via multi-scale edge and valley detection."""
        gray = cv2.cvtColor(roi, cv2.COLOR_RGB2GRAY)
        blurred = cv2.GaussianBlur(gray, (3, 3), 0)

        # Adaptive thresholding to catch dark crack lines
        adaptive = cv2.adaptiveThreshold(
            blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 11, 4
        )

        # Canny edge detector
        v = np.median(blurred)
        lower = int(max(0, (1.0 - 0.33) * v))
        upper = int(min(255, (1.0 + 0.33) * v))
        edges = cv2.Canny(blurred, lower, upper)

        combined = cv2.bitwise_or(adaptive, edges)

        # Morphological closing along linear structuring elements
        kernel_h = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 1))
        kernel_v = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 3))
        closed = cv2.morphologyEx(combined, cv2.MORPH_CLOSE, kernel_h)
        closed = cv2.morphologyEx(closed, cv2.MORPH_CLOSE, kernel_v)

        return (closed > 0).astype(np.uint8)

    def _segment_depth_step_or_contrast(
        self,
        roi: np.ndarray,
        depth_map: np.ndarray,
        x1: int,
        y1: int,
        x2: int,
        y2: int,
        h_img: int,
        w_img: int,
    ) -> np.ndarray:
        """Segments material breach or hole using depth discontinuity with contrast fallback."""
        h_depth, w_depth = depth_map.shape[:2]
        # Rescale coordinates to depth map dimensions
        dx1 = int(round(x1 * (w_depth / w_img)))
        dy1 = int(round(y1 * (h_depth / h_img)))
        dx2 = int(round(x2 * (w_depth / w_img)))
        dy2 = int(round(y2 * (h_depth / h_img)))

        dx1 = max(0, min(dx1, w_depth - 1))
        dy1 = max(0, min(dy1, h_depth - 1))
        dx2 = max(0, min(dx2, w_depth))
        dy2 = max(0, min(dy2, h_depth))

        if (dx2 - dx1) > 2 and (dy2 - dy1) > 2:
            roi_d = depth_map[dy1:dy2, dx1:dx2].astype(float)
            valid_d = roi_d[roi_d > 0]
            if len(valid_d) > 10:
                med_d = np.median(valid_d)
                # Hole/breach exhibits significant depth step (> 0.08 m or mm equivalent)
                step_val = 80.0 if np.max(valid_d) > 100.0 else 0.08
                depth_diff = np.abs(roi_d - med_d)
                d_mask = (depth_diff > step_val).astype(np.uint8)
                # Resize d_mask back to roi shape
                resized_mask = cv2.resize(d_mask, (x2 - x1, y2 - y1), interpolation=cv2.INTER_NEAREST)
                if np.count_nonzero(resized_mask) >= self.min_mask_pixels:
                    return resized_mask

        # Fallback to contrast segmentation
        return self._segment_stain_or_contrast(roi)

    def _extract_contour_polygon(
        self, roi_mask: np.ndarray, offset_x: int, offset_y: int
    ) -> List[List[float]]:
        """Extracts and approximates the exterior boundary contour polygon."""
        contours, _ = cv2.findContours(
            roi_mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        if not contours:
            return []

        # Find largest contour by area
        largest_cnt = max(contours, key=cv2.contourArea)
        # Approximate contour to reduce vertex count
        epsilon = 0.02 * cv2.arcLength(largest_cnt, True)
        approx = cv2.approxPolyDP(largest_cnt, max(1.5, epsilon), True)

        polygon: List[List[float]] = []
        for pt in approx:
            u = float(pt[0][0] + offset_x)
            v = float(pt[0][1] + offset_y)
            polygon.append([round(u, 1), round(v, 1)])

        return polygon
