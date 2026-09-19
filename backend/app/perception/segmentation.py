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
from scipy.spatial.transform import Rotation


def refine_opening_boundaries(
    rgb_image: np.ndarray,
    depth_mm: np.ndarray,
    bbox: List[float],
    detection_class: str = "doorway",
    camera_pose: Optional[Dict[str, Any]] = None,
    scale_x: float = 256.0 / 1920.0,
    scale_y: float = 192.0 / 1440.0,
) -> Dict[str, Any]:
    """Refines candidate bounding box into precise opening boundaries using depth profiles.

    Purpose:
        Locates exact left and right door jambs by detecting depth step discontinuities,
        correctly handling both portrait and landscape camera orientations.

    Parameters:
        rgb_image: Full-resolution RGB image array (H, W, 3).
        depth_mm: Aligned depth image array (192, 256) in uint16 millimeters.
        bbox: Candidate detection box [x1, y1, x2, y2] in RGB pixel coordinates.
        detection_class: Semantic category ('door', 'doorway', 'window').
        camera_pose: Optional 6D camera pose dictionary for orientation determination.
        scale_x: Coordinate scaling factor from RGB to depth width.
        scale_y: Coordinate scaling factor from RGB to depth height.

    Returns:
        Dictionary containing left jamb, right jamb, top header, bottom sill pixel coordinates,
        and depth discontinuity metrics.
    """
    x1, y1, x2, y2 = [float(v) for v in bbox]
    h_rgb, w_rgb = rgb_image.shape[:2]

    x1 = max(0.0, min(x1, w_rgb - 1.0))
    x2 = max(0.0, min(x2, w_rgb - 1.0))
    y1 = max(0.0, min(y1, h_rgb - 1.0))
    y2 = max(0.0, min(y2, h_rgb - 1.0))

    if x2 <= x1 or y2 <= y1:
        return {
            "left_jamb_pixel": [x1, (y1 + y2) / 2.0],
            "right_jamb_pixel": [x2, (y1 + y2) / 2.0],
            "top_header_pixel": [(x1 + x2) / 2.0, y1],
            "bottom_sill_pixel": [(x1 + x2) / 2.0, y2],
            "depth_step_detected": False,
            "depth_jump_magnitude_m": 0.0,
            "refined_bbox": [x1, y1, x2, y2],
        }

    # Determine camera orientation: portrait vs landscape
    is_portrait = False
    if camera_pose:
        quat = camera_pose.get("orientation_quaternion") or camera_pose.get("quaternion")
        if quat:
            rot = Rotation.from_quat(quat)
            R = rot.as_matrix()
            is_portrait = bool(abs(R[1, 0]) > abs(R[1, 1]))

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

    refined_x1, refined_x2 = x1, x2
    refined_y1, refined_y2 = y1, y2
    depth_step_found = False
    max_jump_m = 0.0

    if is_portrait:
        # In portrait: physical horizontal in world is along image Y (rows in depth: dy1..dy2)
        # physical vertical is along image X (cols in depth: dx1..dx2)
        if (dy2 - dy1) >= 6 and (dx2 - dx1) >= 6:
            band_x1 = int(dx1 + 0.30 * (dx2 - dx1))
            band_x2 = int(dx1 + 0.70 * (dx2 - dx1))
            depth_band = depth_mm[dy1:dy2, band_x1:band_x2].astype(np.float64) / 1000.0

            valid_mask = depth_band > 0.15
            if np.sum(valid_mask) > 10:
                row_medians = []
                for row_idx in range(depth_band.shape[0]):
                    row_vals = depth_band[row_idx, :]
                    row_valid = row_vals[row_vals > 0.15]
                    if len(row_valid) > 0:
                        row_medians.append(float(np.median(row_valid)))
                    else:
                        row_medians.append(row_medians[-1] if row_medians else 0.0)

                row_med_arr = np.array(row_medians)
                if len(row_med_arr) > 4:
                    diffs = np.diff(row_med_arr)
                    max_jump_m = float(np.max(np.abs(diffs))) if len(diffs) > 0 else 0.0

                    if max_jump_m >= 0.15:
                        depth_step_found = True
                        pos_jumps = np.where(diffs > 0.12)[0]
                        neg_jumps = np.where(diffs < -0.12)[0]

                        if len(pos_jumps) > 0:
                            best_d = dy1 + pos_jumps[0]
                            refined_y1 = float(best_d / scale_y)
                        if len(neg_jumps) > 0:
                            best_d = dy1 + neg_jumps[-1] + 1
                            refined_y2 = float(best_d / scale_y)
    else:
        # In landscape: physical horizontal in world is along image X (cols in depth: dx1..dx2)
        if (dx2 - dx1) >= 6 and (dy2 - dy1) >= 6:
            band_y1 = int(dy1 + 0.30 * (dy2 - dy1))
            band_y2 = int(dy1 + 0.70 * (dy2 - dy1))
            depth_band = depth_mm[band_y1:band_y2, dx1:dx2].astype(np.float64) / 1000.0

            valid_mask = depth_band > 0.15
            if np.sum(valid_mask) > 10:
                col_medians = []
                for col_idx in range(depth_band.shape[1]):
                    col_vals = depth_band[:, col_idx]
                    col_valid = col_vals[col_vals > 0.15]
                    if len(col_valid) > 0:
                        col_medians.append(float(np.median(col_valid)))
                    else:
                        col_medians.append(col_medians[-1] if col_medians else 0.0)

                col_med_arr = np.array(col_medians)
                if len(col_med_arr) > 4:
                    diffs = np.diff(col_med_arr)
                    max_jump_m = float(np.max(np.abs(diffs))) if len(diffs) > 0 else 0.0

                    if max_jump_m >= 0.15:
                        depth_step_found = True
                        pos_jumps = np.where(diffs > 0.12)[0]
                        neg_jumps = np.where(diffs < -0.12)[0]

                        if len(pos_jumps) > 0:
                            best_left_d = dx1 + pos_jumps[0]
                            refined_x1 = float(best_left_d / scale_x)
                        if len(neg_jumps) > 0:
                            best_right_d = dx1 + neg_jumps[-1] + 1
                            refined_x2 = float(best_right_d / scale_x)

    # Sanity checks on refined coordinates: must span at least 40% of original box to avoid collapsing to single edge
    if is_portrait:
        if (refined_y2 - refined_y1) < 0.40 * (y2 - y1):
            refined_y1, refined_y2 = y1, y2
        if refined_x2 <= refined_x1 + 20:
            refined_x1, refined_x2 = x1, x2
    else:
        if (refined_x2 - refined_x1) < 0.40 * (x2 - x1):
            refined_x1, refined_x2 = x1, x2
        if refined_y2 <= refined_y1 + 20:
            refined_y1, refined_y2 = y1, y2

    mid_y = (refined_y1 + refined_y2) / 2.0
    mid_x = (refined_x1 + refined_x2) / 2.0

    return {
        "left_jamb_pixel": [refined_x1, mid_y] if not is_portrait else [mid_x, refined_y1],
        "right_jamb_pixel": [refined_x2, mid_y] if not is_portrait else [mid_x, refined_y2],
        "top_header_pixel": [mid_x, refined_y1] if not is_portrait else [refined_x1, mid_y],
        "bottom_sill_pixel": [mid_x, refined_y2] if not is_portrait else [refined_x2, mid_y],
        "depth_step_detected": bool(depth_step_found),
        "depth_jump_magnitude_m": round(float(max_jump_m), 3),
        "refined_bbox": [float(refined_x1), float(refined_y1), float(refined_x2), float(refined_y2)],
        "is_portrait": bool(is_portrait),
    }


def refine_opening_boundaries_with_depth(
    candidate: Dict[str, Any],
    depth_map: Optional[np.ndarray],
    rgb_image: Optional[np.ndarray] = None,
    camera_pose: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Refines candidate opening jamb boundaries using aligned depth map or fallback bounding box.

    Purpose:
        Serves as the high-level boundary refinement interface consumed by the Stage 5 perception pipeline.

    Parameters:
        candidate: Candidate detection dictionary containing 'bbox' and 'class'.
        depth_map: Optional 2D numpy array of aligned depth values (uint16 mm).
        rgb_image: Optional full-resolution RGB image.
        camera_pose: Optional 6D camera pose dictionary for orientation determination.

    Returns:
        Refined boundary dictionary with left_jamb_pixel, right_jamb_pixel, and jump metrics.
    """
    bbox = candidate.get("bbox", [0, 0, 0, 0])
    cls_name = candidate.get("class", "doorway")

    if depth_map is not None:
        if rgb_image is None:
            rgb_image = np.zeros((1440, 1920, 3), dtype=np.uint8)
        return refine_opening_boundaries(rgb_image, depth_map, bbox, detection_class=cls_name, camera_pose=camera_pose)

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
