"""Visualization utilities for opening detections, debug camera frames, and 2D floor-plan overlays.

1. Why this file exists:
   Generates transparent visual verification artifacts for Stage 5 opening detection and metric
   measurement. Produces annotated RGB debug frames (visualizing 2D bounding boxes, refined jamb lines,
   and detector scores) and an architectural SVG floor-plan overlay (visualizing structural walls,
   opening locations, clearance widths, and uncertainty tolerances).

2. Pipeline stage:
   Stage 5 (Door/Window Detection & Metric Opening Measurement) - Debug Visualization.

3. Inputs:
   RGB frame paths, 2D candidate detections, refined boundary pixels, Stage 3 room polygon,
   Stage 2 structural walls, and Stage 5 accepted/uncertain openings.

4. Outputs:
   - Annotated JPEG debug images in outputs/<scan_id>/openings/debug_frames/
   - Scalable Vector Graphics (SVG) drawing at outputs/<scan_id>/openings/opening_debug.svg

5. Coordinate/Unit conventions:
   RGB image coordinates in pixels (u, v) with origin at top-left.
   Floor plan coordinates in metric meters (x, z) projected to SVG canvas viewbox.

6. Dependencies:
   math, os, typing, cv2 or PIL, numpy.

7. Most likely failure/debugging points:
   - OpenCV headless drawing failure or missing font rendering.
   - SVG scale/offset distortion if polygon bounding box is degenerate or inverted.
   - Missing debug frames directory (auto-created).
"""

import math
import os
from typing import Any, Dict, List, Optional, Tuple
import cv2
import numpy as np


def save_annotated_frame(
    image_path: str,
    output_path: str,
    detections: List[Dict[str, Any]],
) -> None:
    """Renders 2D bounding boxes, semantic labels, and refined jamb boundaries on an RGB keyframe.

    Purpose:
        Enables visual inspection of what the semantic detector recognized and where jamb boundaries lie.

    Parameters:
        image_path: Filepath to the original RGB keyframe.
        output_path: Destination filepath for the annotated debug image.
        detections: List of detection dictionaries containing bbox, class, detector_score, and boundary_pixels.

    Returns:
        None. Saves image to disk.

    Assumptions:
        image_path exists and is readable by OpenCV.

    Failure conditions:
        Silently skips writing if image cannot be read.

    Debugging:
        Check image_path resolution and bounding box coordinate scales.
    """
    img = cv2.imread(image_path)
    if img is None:
        return

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    h, w = img.shape[:2]

    color_map = {
        "door": (0, 255, 0),        # Green
        "doorway": (0, 200, 255),   # Yellow-Orange
        "open doorway": (0, 165, 255),
        "window": (255, 144, 30),   # Sky blue (BGR)
    }

    for det in detections:
        bbox = det.get("bbox", [])
        if len(bbox) != 4:
            continue

        x1, y1, x2, y2 = [int(v) for v in bbox]
        cls_name = det.get("class", "opening")
        score = det.get("detector_score", 0.0)
        color = color_map.get(cls_name, (0, 255, 0))

        # 1. Draw bounding box
        cv2.rectangle(img, (x1, y1), (x2, y2), color, 3)

        # 2. Draw refined jamb lines if available
        bp = det.get("boundary_pixels")
        if bp:
            lj = bp.get("left_jamb_pixel")
            rj = bp.get("right_jamb_pixel")
            if lj and len(lj) >= 2:
                lx = int(lj[0])
                cv2.line(img, (lx, y1), (lx, y2), (255, 0, 0), 2)  # Blue = left jamb
                cv2.putText(img, "L-JAMB", (lx - 30, y1 + 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 0), 2)
            if rj and len(rj) >= 2:
                rx = int(rj[0])
                cv2.line(img, (rx, y1), (rx, y2), (0, 0, 255), 2)  # Red = right jamb
                cv2.putText(img, "R-JAMB", (rx - 30, y1 + 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)

        # 3. Label badge
        label = f"{cls_name} {score:.2f}"
        proj_w = det.get("projected_geometry", {}).get("width_m")
        if proj_w is not None:
            label += f" | {proj_w:.2f}m"

        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.8, 2)
        cv2.rectangle(img, (x1, max(0, y1 - th - 10)), (x1 + tw + 10, y1), color, -1)
        cv2.putText(img, label, (x1 + 5, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 2)

    cv2.imwrite(output_path, img)


def render_openings_floorplan_svg(
    output_svg_path: str,
    room_polygon_vertices: List[List[float]],
    openings: List[Dict[str, Any]],
    structural_walls: List[Dict[str, Any]],
    uncertain_openings: Optional[List[Dict[str, Any]]] = None,
) -> None:
    """Generates an architectural 2D SVG floor plan displaying wall boundaries and opening placements.

    Purpose:
        Visualizes physical spatial placement of doors and windows along structural wall boundaries
        with metric clearance widths and uncertainty labels.

    Parameters:
        output_svg_path: Destination SVG filepath.
        room_polygon_vertices: List of [x, z] 2D coordinates defining closed room boundary.
        openings: List of accepted Stage 5 opening records.
        structural_walls: List of Stage 2 structural wall definitions.
        uncertain_openings: Optional list of provisional or uncertain openings.

    Returns:
        None. Writes SVG file.

    Assumptions:
        Coordinates are metric meters (x, z) where X is right and Z is depth.

    Failure conditions:
        Gracefully handles empty polygon by drawing default canvas.

    Debugging:
        Check bounding box margin if polygon appears clipped at canvas edges.
    """
    os.makedirs(os.path.dirname(output_svg_path), exist_ok=True)

    # Collect all 2D points to determine bounds
    all_pts = list(room_polygon_vertices)
    for op in openings:
        all_pts.append([op["left_jamb_3d"][0], op["left_jamb_3d"][2]])
        all_pts.append([op["right_jamb_3d"][0], op["right_jamb_3d"][2]])

    if not all_pts:
        all_pts = [[-2.0, -2.0], [2.0, 2.0]]

    xs = [p[0] for p in all_pts]
    zs = [p[1] for p in all_pts]
    min_x, max_x = min(xs) - 0.8, max(xs) + 0.8
    min_z, max_z = min(zs) - 0.8, max(zs) + 0.8

    span_x = max(1.0, max_x - min_x)
    span_z = max(1.0, max_z - min_z)

    # SVG Canvas dimensions
    svg_width = 900
    svg_height = 800
    margin = 70

    scale_x = (svg_width - 2 * margin) / span_x
    scale_z = (svg_height - 2 * margin) / span_z
    scale = min(scale_x, scale_z)

    def to_svg(x: float, z: float) -> Tuple[float, float]:
        sx = margin + (x - min_x) * scale
        # Invert Z so negative Z is up, positive Z is down or standard architectural convention
        sz = margin + (max_z - z) * scale
        return sx, sz

    svg_lines: List[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {svg_width} {svg_height}" width="100%" height="100%">',
        '  <defs>',
        '    <filter id="shadow" x="-5%" y="-5%" width="110%" height="110%">',
        '      <feDropShadow dx="2" dy="2" stdDeviation="3" flood-opacity="0.25"/>',
        '    </filter>',
        '  </defs>',
        '  <style>',
        '    .bg { fill: #0f172a; }',
        '    .grid { stroke: #1e293b; stroke-width: 1; stroke-dasharray: 4,4; }',
        '    .wall-poly { fill: #1e293b; fill-opacity: 0.6; stroke: #94a3b8; stroke-width: 4; stroke-linejoin: round; }',
        '    .door-opening { stroke: #10b981; stroke-width: 8; stroke-linecap: round; }',
        '    .window-opening { stroke: #38bdf8; stroke-width: 8; stroke-linecap: round; }',
        '    .uncertain-opening { stroke: #f59e0b; stroke-width: 6; stroke-dasharray: 6,4; }',
        '    .label { font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }',
        '    .title { font-size: 20px; font-weight: 700; fill: #f8fafc; }',
        '    .subtitle { font-size: 13px; fill: #94a3b8; }',
        '    .badge-bg { fill: #1e293b; stroke: #334155; stroke-width: 1; rx: 6; }',
        '    .opening-text { font-size: 13px; font-weight: 600; fill: #f8fafc; }',
        '    .meta-text { font-size: 11px; fill: #94a3b8; }',
        '    .jamb-pin { fill: #ef4444; stroke: #ffffff; stroke-width: 1.5; }',
        '  </style>',
        f'  <rect width="{svg_width}" height="{svg_height}" class="bg" />',
        '  <!-- Grid lines -->',
    ]

    # Draw grid
    for gx in range(int(math.floor(min_x)), int(math.ceil(max_x)) + 1):
        sx1, sz1 = to_svg(gx, min_z)
        sx2, sz2 = to_svg(gx, max_z)
        svg_lines.append(f'  <line x1="{sx1:.1f}" y1="{sz1:.1f}" x2="{sx2:.1f}" y2="{sz2:.1f}" class="grid" />')
    for gz in range(int(math.floor(min_z)), int(math.ceil(max_z)) + 1):
        sx1, sz1 = to_svg(min_x, gz)
        sx2, sz2 = to_svg(max_x, gz)
        svg_lines.append(f'  <line x1="{sx1:.1f}" y1="{sz1:.1f}" x2="{sx2:.1f}" y2="{sz2:.1f}" class="grid" />')

    # Draw room polygon
    if room_polygon_vertices and len(room_polygon_vertices) >= 3:
        svg_pts = " ".join(f"{to_svg(p[0], p[1])[0]:.1f},{to_svg(p[0], p[1])[1]:.1f}" for p in room_polygon_vertices)
        svg_lines.append(f'  <polygon points="{svg_pts}" class="wall-poly" filter="url(#shadow)" />')

    # Draw accepted openings
    for op in openings:
        lx, lz = op["left_jamb_3d"][0], op["left_jamb_3d"][2]
        rx, rz = op["right_jamb_3d"][0], op["right_jamb_3d"][2]
        slx, slz = to_svg(lx, lz)
        srx, srz = to_svg(rx, rz)

        cls_type = op.get("type", "doorway")
        stroke_cls = "window-opening" if cls_type == "window" else "door-opening"

        # Clearance threshold line
        svg_lines.append(f'  <line x1="{slx:.1f}" y1="{slz:.1f}" x2="{srx:.1f}" y2="{srz:.1f}" class="{stroke_cls}" />')

        # Jamb endpoints
        svg_lines.append(f'  <circle cx="{slx:.1f}" cy="{slz:.1f}" r="4" class="jamb-pin" />')
        svg_lines.append(f'  <circle cx="{srx:.1f}" cy="{srz:.1f}" r="4" class="jamb-pin" />')

        # Midpoint label badge
        mx = (slx + srx) / 2.0
        mz = (slz + srz) / 2.0
        op_id = op["id"]
        w_val = op["width"]["value"]
        w_int = op["width"]["interval"]
        frames_cnt = op.get("supporting_frames", 1)

        badge_w = 175
        badge_h = 56
        bx = mx - badge_w / 2.0
        by = mz - badge_h - 14

        svg_lines.append(f'  <g filter="url(#shadow)">')
        svg_lines.append(f'    <rect x="{bx:.1f}" y="{by:.1f}" width="{badge_w}" height="{badge_h}" class="badge-bg" />')
        svg_lines.append(f'    <text x="{bx + 8:.1f}" y="{by + 18:.1f}" class="label opening-text">{op_id} ({cls_type})</text>')
        svg_lines.append(f'    <text x="{bx + 8:.1f}" y="{by + 34:.1f}" class="label subtitle">Width: {w_val:.3f}m ±{op["width"]["half_width_uncertainty_m"]:.3f}m</text>')
        svg_lines.append(f'    <text x="{bx + 8:.1f}" y="{by + 48:.1f}" class="label meta-text">[{w_int[0]:.2f}m, {w_int[1]:.2f}m] · {frames_cnt} frames</text>')
        svg_lines.append(f'  </g>')

    # Title header
    svg_lines.extend([
        '  <!-- Header Text -->',
        f'  <text x="30" y="45" class="label title">CosmoAI — Stage 5 Opening Verification Overlay</text>',
        f'  <text x="30" y="65" class="label subtitle">Metric architectural opening widths, 3D jamb projections &amp; engineering uncertainty</text>',
        '</svg>',
    ])

    with open(output_svg_path, "w", encoding="utf-8") as f:
        f.write("\n".join(svg_lines))
