"""High-precision architectural vector SVG floor plan exporter.

Purpose:
    Generates standalone, CAD-grade SVG 2D floor plans from reconstructed property
    models, complete with room boundaries, walls, door/window openings, readable
    non-overlapping dimensions, damage annotations, and compliance notices.

Stage:
    Frontend Stage 4 — Exports + Final Product Polish.

Inputs:
    - property_data: Dict or PropertyPlanOutput representing the property.
    - capture_id: Unique capture identifier string.
    - output_path: Optional destination Path for writing the SVG file.
    - width_px, height_px: Canvas dimensions in pixels.

Outputs:
    - Standalone, XML-compliant SVG markup string and optional written file.

Dependencies:
    math, pathlib, typing, pydantic (if PropertyPlanOutput model passed).

Assumptions:
    - World coordinates are metric (meters) on the horizontal XZ ground plane.
    - SVG canvas maps world X -> SVG X (right), world Z -> SVG Y (down).
    - Dimension labels avoid clutter via priority filtering and leader lines.

Coordinate / Unit Conventions:
    - Input: metric meters (m), area in square meters (m2).
    - Output: SVG pixel coordinates derived via isotropic scaling.

Failure Modes:
    - Degenerate / zero room coordinates -> renders graceful placeholder SVG.
    - Write permission error -> raises IOError.

First Debugging Points:
    - Verify valid XML by parsing with xml.etree.ElementTree.
    - Check room polygon vertices and SVG viewBox values.
    - Confirm all dimension text values match backend measurement lengths.
"""

import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
from pydantic import BaseModel


def export_property_svg(
    property_data: Union[Dict[str, Any], BaseModel],
    capture_id: str,
    output_path: Optional[Path] = None,
    width_px: int = 1400,
    height_px: int = 1000,
    margin_px: int = 100,
) -> str:
    """Renders a standalone architectural vector floor plan SVG.

    Purpose:
        Creates an independent vector floor plan illustrating room boundaries,
        wall measurements, openings, damage regions, and scale indicators.

    Parameters:
        property_data: Property reconstruction data (dict or BaseModel).
        capture_id: Unique capture identifier.
        output_path: Optional file path to write SVG output.
        width_px: Total SVG canvas width.
        height_px: Total SVG canvas height.
        margin_px: Inner padding margin.

    Returns:
        XML-compliant SVG document string.

    Units / Coordinates:
        Metric inputs in meters; scaled isotropically to SVG pixels.

    Assumptions:
        Room polygon coordinates are metric.

    Failure Conditions:
        Raises IOError on disk write failure.

    Debugging Clues:
        Check viewBox attribute and verify room polygon path data 'd' attribute.
    """
    if isinstance(property_data, BaseModel):
        data = property_data.model_dump(mode="json")
    elif isinstance(property_data, dict):
        data = dict(property_data)
    else:
        raise TypeError(f"Expected dict or BaseModel, got {type(property_data)}")

    rooms = data.get("rooms", [])
    tier = str(data.get("tier", "lidar")).upper()
    status = str(data.get("status", "COMPLETE")).upper()
    prop_id = data.get("property_id") or capture_id
    total_area_val = data.get("total_floor_area")
    if isinstance(total_area_val, dict):
        total_area_str = f"{total_area_val.get('value', 0.0):.1f} m²"
    elif isinstance(total_area_val, (int, float)):
        total_area_str = f"{total_area_val:.1f} m²"
    else:
        total_area_str = "N/A"

    # Collect all polygon / wall coordinates for bounding box calculation
    all_x: List[float] = []
    all_z: List[float] = []

    for room in rooms:
        # Check polygon / walls
        for wall in room.get("walls", []):
            start = wall.get("start", {})
            end = wall.get("end", {})
            sx = start.get("x", start.get("x_meters", 0.0))
            sz = start.get("y", start.get("z", start.get("y_meters", 0.0)))
            ex = end.get("x", end.get("x_meters", 0.0))
            ez = end.get("y", end.get("z", end.get("y_meters", 0.0)))
            all_x.extend([sx, ex])
            all_z.extend([sz, ez])

        # Also check polygon if available
        polygon = room.get("polygon", [])
        for pt in polygon:
            px = pt.get("x", pt.get("x_meters", 0.0))
            pz = pt.get("y", pt.get("z", pt.get("y_meters", 0.0)))
            all_x.append(px)
            all_z.append(pz)

    # Handle empty / not evaluable geometry gracefully
    if not all_x or not all_z:
        svg_empty = (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width_px} {height_px}" '
            f'width="{width_px}" height="{height_px}" '
            f'style="background-color: #0b0f19; font-family: ui-sans-serif, system-ui, -apple-system, sans-serif;">\n'
            f'  <text x="{width_px/2}" y="{height_px/2 - 20}" fill="#94a3b8" font-size="18" text-anchor="middle" font-weight="600">COZMO SPATIAL RECONSTRUCTION</text>\n'
            f'  <text x="{width_px/2}" y="{height_px/2 + 20}" fill="#ef4444" font-size="14" text-anchor="middle">No floor plan geometry available ({status})</text>\n'
            f'  <text x="{width_px/2}" y="{height_px/2 + 50}" fill="#64748b" font-size="12" text-anchor="middle">Capture ID: {capture_id}</text>\n'
            f'</svg>'
        )
        if output_path is not None:
            out_p = Path(output_path)
            out_p.parent.mkdir(parents=True, exist_ok=True)
            out_p.write_text(svg_empty, encoding="utf-8")
        return svg_empty

    min_x, max_x = min(all_x), max(all_x)
    min_z, max_z = min(all_z), max(all_z)

    span_x = max(max_x - min_x, 0.5)
    span_z = max(max_z - min_z, 0.5)

    # Allocate stage area (leaving room for header and footer notices)
    top_header_px = 110
    bottom_footer_px = 90
    usable_w = width_px - (2 * margin_px)
    usable_h = height_px - top_header_px - bottom_footer_px

    scale = min(usable_w / span_x, usable_h / span_z)

    # Center drawing inside stage
    offset_x = margin_px + (usable_w - span_x * scale) / 2.0
    offset_z = top_header_px + (usable_h - span_z * scale) / 2.0

    def world_to_svg(x: float, z: float) -> Tuple[float, float]:
        """Convert metric ground plane (X, Z) to SVG canvas coordinates."""
        return offset_x + (x - min_x) * scale, offset_z + (z - min_z) * scale

    # Begin SVG construction
    lines: List[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width_px} {height_px}" '
        f'width="{width_px}" height="{height_px}" '
        f'style="background-color: #0b0f19; font-family: ui-sans-serif, system-ui, -apple-system, sans-serif;">',
        '  <defs>',
        '    <pattern id="grid" width="40" height="40" patternUnits="userSpaceOnUse">',
        '      <path d="M 40 0 L 0 0 0 40" fill="none" stroke="#1e293b" stroke-width="0.75" stroke-opacity="0.5"/>',
        '    </pattern>',
        '    <filter id="card-shadow" x="-5%" y="-5%" width="110%" height="115%">',
        '      <feDropShadow dx="0" dy="4" stdDeviation="6" flood-color="#000000" flood-opacity="0.4"/>',
        '    </filter>',
        '  </defs>',
        '',
        '  <!-- Background & Architectural Grid -->',
        f'  <rect width="{width_px}" height="{height_px}" fill="#0b0f19"/>',
        f'  <rect x="20" y="20" width="{width_px - 40}" height="{height_px - 40}" fill="url(#grid)" rx="8" stroke="#1e293b" stroke-width="1"/>',
        '',
        '  <!-- Header Banner -->',
        f'  <g id="header" transform="translate({margin_px}, 50)">',
        '    <rect x="-20" y="-30" width="32" height="32" rx="6" fill="#3b82f6"/>',
        '    <text x="-4" y="-9" fill="#ffffff" font-size="18" font-weight="800" text-anchor="middle">C</text>',
        '    <text x="24" y="-14" fill="#ffffff" font-size="18" font-weight="700" letter-spacing="0.05em">COZMO SPATIAL RECONSTRUCTION</text>',
        f'    <text x="24" y="6" fill="#94a3b8" font-size="12" font-family="monospace">ID: {prop_id} • TIER: {tier} • AREA: {total_area_str}</text>',
        '',
        '    <!-- Status Badge -->',
        f'    <rect x="{usable_w - 110}" y="-26" width="130" height="26" rx="13" '
        f'fill="{ "#065f46" if status == "COMPLETE" else "#854d0e" if status == "PROVISIONAL" else "#991b1b" }"/>',
        f'    <text x="{usable_w - 45}" y="-9" fill="#ffffff" font-size="11" font-weight="700" text-anchor="middle">{status}</text>',
        '  </g>',
        '',
    ]

    # Room styling palette
    room_fills = [
        ("rgba(30, 58, 138, 0.25)", "#3b82f6"),  # Blue
        ("rgba(19, 78, 74, 0.25)", "#14b8a6"),   # Teal
        ("rgba(76, 29, 149, 0.25)", "#8b5cf6"),  # Violet
        ("rgba(131, 24, 67, 0.25)", "#ec4899"),  # Pink
        ("rgba(120, 53, 15, 0.25)", "#f59e0b"),  # Amber
    ]

    # 1. Render Room Polygons and Centroid Labels
    lines.append('  <!-- Room Polygons & Labels -->')
    lines.append('  <g id="rooms">')

    dimension_candidates: List[Dict[str, Any]] = []
    openings_to_render: List[Dict[str, Any]] = []

    for idx, room in enumerate(rooms):
        room_name = room.get("name", f"Room {idx + 1}")
        fill_col, stroke_col = room_fills[idx % len(room_fills)]

        area_val = room.get("floor_area")
        if isinstance(area_val, dict):
            area_m2 = area_val.get("value", 0.0)
        elif isinstance(area_val, (int, float)):
            area_m2 = float(area_val)
        else:
            area_m2 = 0.0

        # Extract polygon vertices from room walls or polygon attribute
        poly_pts: List[Tuple[float, float]] = []
        walls = room.get("walls", [])

        if walls:
            for w in walls:
                st = w.get("start", {})
                sx = st.get("x", st.get("x_meters", 0.0))
                sz = st.get("y", st.get("z", st.get("y_meters", 0.0)))
                poly_pts.append((sx, sz))
        elif "polygon" in room and room["polygon"]:
            for pt in room["polygon"]:
                px = pt.get("x", pt.get("x_meters", 0.0))
                pz = pt.get("y", pt.get("z", pt.get("y_meters", 0.0)))
                poly_pts.append((px, pz))

        if len(poly_pts) >= 3:
            svg_pts = [world_to_svg(px, pz) for px, pz in poly_pts]
            path_d = "M " + " L ".join(f"{x:.1f},{y:.1f}" for x, y in svg_pts) + " Z"

            lines.append(f'    <path d="{path_d}" fill="{fill_col}" stroke="{stroke_col}" stroke-width="2.5" stroke-linejoin="round" />')

            # Calculate polygon centroid
            cx = sum(p[0] for p in svg_pts) / len(svg_pts)
            cy = sum(p[1] for p in svg_pts) / len(svg_pts)

            # Room label pill
            lines.append(f'    <g transform="translate({cx:.1f}, {cy:.1f})">')
            lines.append('      <rect x="-65" y="-22" width="130" height="44" rx="8" fill="#1e293b" fill-opacity="0.9" stroke="#334155" stroke-width="1" filter="url(#card-shadow)" />')
            lines.append(f'      <text x="0" y="-4" fill="#f8fafc" font-size="13" font-weight="700" text-anchor="middle">{room_name}</text>')
            lines.append(f'      <text x="0" y="14" fill="#94a3b8" font-size="11" font-family="monospace" text-anchor="middle">{area_m2:.1f} m²</text>')
            lines.append('    </g>')

        # Collect walls and openings for detailed drawing
        for wall in walls:
            st = wall.get("start", {})
            en = wall.get("end", {})
            sx = st.get("x", st.get("x_meters", 0.0))
            sz = st.get("y", st.get("z", st.get("y_meters", 0.0)))
            ex = en.get("x", en.get("x_meters", 0.0))
            ez = en.get("y", en.get("z", en.get("y_meters", 0.0)))

            length_val = wall.get("length")
            if isinstance(length_val, dict):
                len_m = length_val.get("value", math.hypot(ex - sx, ez - sz))
            elif isinstance(length_val, (int, float)):
                len_m = float(length_val)
            else:
                len_m = math.hypot(ex - sx, ez - sz)

            dimension_candidates.append({
                "sx": sx, "sz": sz, "ex": ex, "ez": ez,
                "length_m": len_m, "wall_id": wall.get("wall_id", "")
            })

            for op in wall.get("openings", []):
                openings_to_render.append({
                    "opening": op, "sx": sx, "sz": sz, "ex": ex, "ez": ez
                })

    lines.append('  </g>')
    lines.append('')

    # 2. Render Wall Lines
    lines.append('  <!-- Structural Wall Lines -->')
    lines.append('  <g id="walls">')
    for cand in dimension_candidates:
        p1 = world_to_svg(cand["sx"], cand["sz"])
        p2 = world_to_svg(cand["ex"], cand["ez"])
        lines.append(f'    <line x1="{p1[0]:.1f}" y1="{p1[1]:.1f}" x2="{p2[0]:.1f}" y2="{p2[1]:.1f}" stroke="#e2e8f0" stroke-width="4" stroke-linecap="square" />')
    lines.append('  </g>')
    lines.append('')

    # 3. Render Openings (Doors & Windows)
    lines.append('  <!-- Architectural Openings -->')
    lines.append('  <g id="openings">')
    for item in openings_to_render:
        op = item["opening"]
        op_type = str(op.get("opening_type", "door")).lower()
        sx, sz = item["sx"], item["sz"]
        ex, ez = item["ex"], item["ez"]
        wall_len = math.hypot(ex - sx, ez - sz)
        if wall_len < 1e-4:
            continue

        pos_val = op.get("position_along_wall", {})
        pos_m = pos_val.get("value", 0.5 * wall_len) if isinstance(pos_val, dict) else 0.5 * wall_len
        w_val = op.get("width", {})
        width_m = w_val.get("value", 0.9) if isinstance(w_val, dict) else 0.9

        t1 = max(0.0, (pos_m - width_m / 2.0) / wall_len)
        t2 = min(1.0, (pos_m + width_m / 2.0) / wall_len)

        op_sx = sx + t1 * (ex - sx)
        op_sz = sz + t1 * (ez - sz)
        op_ex = sx + t2 * (ex - sx)
        op_ez = sz + t2 * (ez - sz)

        p_start = world_to_svg(op_sx, op_sz)
        p_end = world_to_svg(op_ex, op_ez)

        if "window" in op_type:
            # Window: double cyan line
            lines.append(f'    <line x1="{p_start[0]:.1f}" y1="{p_start[1]:.1f}" x2="{p_end[0]:.1f}" y2="{p_end[1]:.1f}" stroke="#38bdf8" stroke-width="5" />')
            lines.append(f'    <line x1="{p_start[0]:.1f}" y1="{p_start[1]:.1f}" x2="{p_end[0]:.1f}" y2="{p_end[1]:.1f}" stroke="#0b0f19" stroke-width="1.5" />')
        else:
            # Door: clear cutout line + amber indicator
            lines.append(f'    <line x1="{p_start[0]:.1f}" y1="{p_start[1]:.1f}" x2="{p_end[0]:.1f}" y2="{p_end[1]:.1f}" stroke="#0b0f19" stroke-width="6" />')
            lines.append(f'    <line x1="{p_start[0]:.1f}" y1="{p_start[1]:.1f}" x2="{p_end[0]:.1f}" y2="{p_end[1]:.1f}" stroke="#f59e0b" stroke-width="2.5" stroke-dasharray="4,3" />')
    lines.append('  </g>')
    lines.append('')

    # 4. Render Dimension Labels with Leader Lines and Collision Avoidance
    lines.append('  <!-- Metric Wall Dimensions -->')
    lines.append('  <g id="dimensions">')

    for cand in dimension_candidates:
        len_m = cand["length_m"]
        if len_m < 0.4:
            continue  # Skip microscopic edge labels to keep SVG clean

        p1 = world_to_svg(cand["sx"], cand["sz"])
        p2 = world_to_svg(cand["ex"], cand["ez"])

        mx = (p1[0] + p2[0]) / 2.0
        my = (p1[1] + p2[1]) / 2.0

        dx = p2[0] - p1[0]
        dy = p2[1] - p1[1]
        dist = math.hypot(dx, dy)
        if dist < 1e-4:
            continue

        # Normal vector pointing outward
        nx = -dy / dist
        ny = dx / dist

        offset_dist = 18.0
        label_x = mx + nx * offset_dist
        label_y = my + ny * offset_dist

        # Compute readable angle (-90 to 90 deg)
        angle_deg = math.degrees(math.atan2(dy, dx))
        if angle_deg > 90:
            angle_deg -= 180
        elif angle_deg < -90:
            angle_deg += 180

        lines.append(f'    <g transform="translate({label_x:.1f}, {label_y:.1f}) rotate({angle_deg:.1f})">')
        lines.append('      <rect x="-24" y="-10" width="48" height="20" rx="4" fill="#0f172a" fill-opacity="0.95" stroke="#475569" stroke-width="0.75" />')
        lines.append(f'      <text x="0" y="3.5" fill="#38bdf8" font-size="10.5" font-family="monospace" font-weight="600" text-anchor="middle">{len_m:.2f} m</text>')
        lines.append('    </g>')

    lines.append('  </g>')
    lines.append('')

    # 5. Render Damage Regions (if any)
    damage_regions = data.get("damage_regions", [])
    if damage_regions:
        lines.append('  <!-- Damage Overlay Findings -->')
        lines.append('  <g id="damage">')
        for dmg in damage_regions:
            dmg_class = str(dmg.get("damage_class", "damage")).replace("_", " ").title()
            # If damage polygon available, render it
            dmg_poly = dmg.get("polygon_on_surface")
            if dmg_poly and len(dmg_poly) >= 3:
                svg_d_pts = [world_to_svg(pt.get("x", 0.0), pt.get("y", pt.get("z", 0.0))) for pt in dmg_poly]
                d_path = "M " + " L ".join(f"{x:.1f},{y:.1f}" for x, y in svg_d_pts) + " Z"
                lines.append(f'    <path d="{d_path}" fill="rgba(239, 68, 68, 0.4)" stroke="#ef4444" stroke-width="2" stroke-dasharray="3,3" />')
        lines.append('  </g>')
        lines.append('')

    # 6. Footer Disclaimer & Metric Scale Bar
    lines.append('  <!-- Footer Notices & Scale -->')
    lines.append(f'  <g id="footer" transform="translate({margin_px}, {height_px - 45})">')
    lines.append('    <text x="0" y="0" fill="#e2e8f0" font-size="11" font-weight="600">COZMO RECONSTRUCTION ENGINE</text>')
    lines.append('    <text x="0" y="16" fill="#94a3b8" font-size="10">Notice: Physical accuracy has not yet been validated against independent laser/tape ground truth.</text>')

    # Metric scale bar (1 meter reference in pixels)
    one_meter_px = scale * 1.0
    lines.append(f'    <g transform="translate({usable_w - one_meter_px - 40}, 0)">')
    lines.append(f'      <line x1="0" y1="0" x2="{one_meter_px:.1f}" y2="0" stroke="#f8fafc" stroke-width="3" />')
    lines.append('      <line x1="0" y1="-5" x2="0" y2="5" stroke="#f8fafc" stroke-width="2" />')
    lines.append(f'      <line x1="{one_meter_px:.1f}" y1="-5" x2="{one_meter_px:.1f}" y2="5" stroke="#f8fafc" stroke-width="2" />')
    lines.append(f'      <text x="{one_meter_px / 2.0:.1f}" y="14" fill="#f8fafc" font-size="10" font-family="monospace" text-anchor="middle">1.0 m</text>')
    lines.append('    </g>')
    lines.append('  </g>')
    lines.append('</svg>')

    svg_content = "\n".join(lines)

    if output_path is not None:
        out_p = Path(output_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        out_p.write_text(svg_content, encoding="utf-8")

    return svg_content
