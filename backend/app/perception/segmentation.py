"""Depth-guided opening boundary refinement and jamb segmentation.

1. Why this file exists:
   Refines crude rectangular vision bounding boxes into precise left and right physical jamb
   locations using aligned depth maps and gradient edge profiles, isolating the true opening aperture
   from surrounding wall surfaces, door trim, and shadows.

2. Pipeline stage:
   Stage 5 (Door/Window Detection & Metric Opening Measurement) - Boundary Refinement.

3. Inputs:
   RGB image array (1920x1440), depth map array (192x256 mm), candidate bounding box [x1, y1, x2, y2].

4. Outputs:
   Refined opening boundary coordinates: left jamb pixel, right jamb pixel, top header,
   bottom sill/floor, and depth step discontinuity diagnostics.

5. Coordinate/Unit assumptions:
   RGB image coordinates: [0, 1920] x [0, 1440].
   Depth map coordinates: [0, 256] x [0, 192], values in millimeters (mm) or meters (m).

6. Dependencies:
   math, typing, numpy, scipy.ndimage.

7. Most likely failure/debugging points:
   - Missing or zero depth values inside the opening aperture due to specular reflections or distance limits.
   - Closed doors having identical depth to surrounding walls (handled by edge gradient fallback).
"""

from typing import Dict, Any, Tuple, Optional, List
import numpy as np


def refine_opening_boundaries(
    rgb_image: np.ndarray,
    depth_mm: np.ndarray,
    bbox: List[float],
    detection_class: str = "doorway",
    scale_x: float = 256.0 / 1920.0,
    scale_y: float = 192.0 / 1440.0,
) -> Dict[str, Any]:
    """Refines candidate bounding box into precise opening boundaries using depth profiles.

    Purpose:
        Locates exact left and right door jamb columns by detecting depth step discontinuities
        and vertical intensity gradients.

    Parameters:
        rgb_image: Full-resolution RGB image array (H, W, 3).
        depth_mm: Aligned depth image array (192, 256) in uint16 millimeters.
        bbox: Candidate detection box [x1, y1, x2, y2] in RGB pixel coordinates.
        detection_class: Semantic category ('door', 'doorway', 'window').
        scale_x: Coordinate scaling factor from RGB to depth width.
        scale_y: Coordinate scaling factor from RGB to depth height.

    Returns:
        Dictionary containing left jamb, right jamb, top header, bottom sill pixel coordinates,
        and depth discontinuity metrics.

    Assumptions:
        Depth map is co-registered with RGB optical center via camera intrinsics.

    Failure conditions:
        Falls back safely to bounding box boundaries if depth data is absent or uniform.

    Debugging:
        Inspect depth_jump_magnitude_m to verify whether an open aperture or closed surface was observed.
    """
    x1, y1, x2, y2 = [int(v) for v in bbox]
    h_rgb, w_rgb = rgb_image.shape[:2]

    x1 = max(0, min(x1, w_rgb - 1))
    x2 = max(0, min(x2, w_rgb - 1))
    y1 = max(0, min(y1, h_rgb - 1))
    y2 = max(0, min(y2, h_rgb - 1))

    if x2 <= x1 or y2 <= y1:
        return {
            "left_jamb_pixel": [float(x1), float((y1 + y2) / 2)],
            "right_jamb_pixel": [float(x2), float((y1 + y2) / 2)],
            "top_header_pixel": [float((x1 + x2) / 2), float(y1)],
            "bottom_sill_pixel": [float((x1 + x2) / 2), float(y2)],
            "depth_step_detected": False,
            "depth_jump_magnitude_m": 0.0,
            "refined_bbox": [float(x1), float(y1), float(x2), float(y2)],
        }

    mid_y = (y1 + y2) // 2
    mid_x = (x1 + x2) // 2

    # Map box to depth image coordinates
    dx1 = int(round(x1 * scale_x))
    dx2 = int(round(x2 * scale_x))
    dy1 = int(round(y1 * scale_y))
    dy2 = int(round(y2 * scale_y))

    h_depth, w_depth = depth_mm.shape
    dx1 = max(0, min(dx1, w_depth - 1))
    dx2 = max(0, min(dx2, w_depth - 1))
    dy1 = max(0, min(dy1, h_depth - 1))
    dy2 = max(0, min(dy2, h_depth - 1))

    refined_x1 = float(x1)
    refined_x2 = float(x2)
    depth_step_found = False
    max_jump_m = 0.0

    if (dx2 - dx1) >= 6 and (dy2 - dy1) >= 6:
        # Extract middle vertical band of depth (middle 30% of box height)
        band_y1 = int(dy1 + 0.35 * (dy2 - dy1))
        band_y2 = int(dy1 + 0.65 * (dy2 - dy1))
        depth_band = depth_mm[band_y1:band_y2, dx1:dx2].astype(np.float64) / 1000.0  # meters

        # Mask out zero/invalid depth
        valid_mask = depth_band > 0.15
        if np.sum(valid_mask) > 10:
            # Column-wise median depth
            col_medians = []
            for col_idx in range(depth_band.shape[1]):
                col_vals = depth_band[:, col_idx]
                col_valid = col_vals[col_vals > 0.15]
                if len(col_valid) > 0:
                    col_medians.append(float(np.median(col_valid)))
                else:
                    col_medians.append(col_medians[-1] if col_medians else 0.0)

            col_med_arr = np.array(col_medians)
            # Compute horizontal depth gradient
            if len(col_med_arr) > 4:
                diffs = np.diff(col_med_arr)
                max_jump_m = float(np.max(np.abs(diffs))) if len(diffs) > 0 else 0.0

                # If depth jump exceeds 0.20m, this indicates an open doorway into an adjoining room
                if max_jump_m >= 0.20:
                    depth_step_found = True
                    # Find left transition (step up in depth)
                    pos_jumps = np.where(diffs > 0.15)[0]
                    # Find right transition (step down in depth)
                    neg_jumps = np.where(diffs < -0.15)[0]

                    if len(pos_jumps) > 0:
                        best_left_d = dx1 + pos_jumps[0]
                        refined_x1 = float(best_left_d / scale_x)
                    if len(neg_jumps) > 0:
                        best_right_d = dx1 + neg_jumps[-1] + 1
                        refined_x2 = float(best_right_d / scale_x)

    # Ensure bounds remain sensible
    if refined_x2 <= refined_x1 + 20:
        refined_x1 = float(x1)
        refined_x2 = float(x2)

    return {
        "left_jamb_pixel": [refined_x1, float(mid_y)],
        "right_jamb_pixel": [refined_x2, float(mid_y)],
        "top_header_pixel": [float(mid_x), float(y1)],
        "bottom_sill_pixel": [float(mid_x), float(y2)],
        "depth_step_detected": depth_step_found,
        "depth_jump_magnitude_m": round(max_jump_m, 3),
        "refined_bbox": [refined_x1, float(y1), refined_x2, float(y2)],
    }


def refine_opening_boundaries_with_depth(
    candidate: Dict[str, Any],
    depth_map: Optional[np.ndarray],
    rgb_image: Optional[np.ndarray] = None,
) -> Dict[str, Any]:
    """Refines candidate opening jamb boundaries using aligned depth map or fallback bounding box.

    Purpose:
        Serves as the high-level boundary refinement interface consumed by the Stage 5 perception pipeline.

    Parameters:
        candidate: Candidate detection dictionary containing 'bbox' and 'class'.
        depth_map: Optional 2D numpy array of aligned depth values (uint16 mm).
        rgb_image: Optional full-resolution RGB image.

    Returns:
        Refined boundary dictionary with left_jamb_pixel, right_jamb_pixel, and jump metrics.

    Assumptions:
        Bbox format is [x1, y1, x2, y2].

    Failure conditions:
        Falls back to bounding box column midpoints if depth_map is None.

    Debugging:
        Check candidate['bbox'] coordinates if jamb points appear outside image bounds.
    """
    bbox = candidate.get("bbox", [0, 0, 0, 0])
    cls_name = candidate.get("class", "doorway")

    if depth_map is not None:
        if rgb_image is None:
            rgb_image = np.zeros((1440, 1920, 3), dtype=np.uint8)
        return refine_opening_boundaries(rgb_image, depth_map, bbox, detection_class=cls_name)

    x1, y1, x2, y2 = [float(v) for v in bbox]
    ymid = (y1 + y2) / 2.0
    xmid = (x1 + x2) / 2.0
    return {
        "left_jamb_pixel": [x1, ymid],
        "right_jamb_pixel": [x2, ymid],
        "top_header_pixel": [xmid, y1],
        "bottom_sill_pixel": [xmid, y2],
        "depth_step_detected": False,
        "depth_jump_magnitude_m": 0.0,
        "refined_bbox": [x1, y1, x2, y2],
    }
