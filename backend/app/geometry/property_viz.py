"""Stage 6 Whole-Property Debug SVG Visualizer.

1. Why this file exists:
    Generates property_debug.svg: an intuitive, high-resolution vector floor plan
    rendering all segmented rooms, hallways/connectors, wall boundaries, door openings,
    and adjacency graph edges in unified global coordinates.

2. Pipeline stage:
    Stage 6 — Visual Property Diagnostics.

3. Inputs:
    List of Room2D objects, list of RoomAdjacencyEdge connections, detected openings, and property metadata.

4. Outputs:
    Standalone vector property_debug.svg visual artifact.

5. Coordinate conventions:
    Global X maps to SVG horizontal axis.
    Global Z maps to SVG vertical axis.
    Units in meters (m) scaled to pixels.

6. Unit assumptions:
    Distances in meters, area in m2, canvas dimensions in pixels.

7. Important dependencies:
    math, pathlib, shapely.geometry, backend.app.models.floorplan.

8. What is most likely to break:
    Zero or negative spatial bounds when no valid rooms are provided.

9. What a developer should inspect first:
    Verify room labels, dimensions, and adjacency connection lines in SVG.
"""

import math
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import numpy as np
from shapely.geometry import Polygon

from backend.app.models.floorplan import Room2D, RoomAdjacencyEdge, Point2D


def render_property_debug_svg(
    rooms: List[Room2D],
    connections: List[RoomAdjacencyEdge],
    detected_openings: Optional[List[Dict[str, Any]]] = None,
    scan_id: str = "unknown",
    drift_status: str = "IMPROVED",
    output_path: Optional[Path] = None,
    width_px: int = 1200,
    height_px: int = 900,
    margin_px: int = 80,
) -> str:
    """Renders a comprehensive multi-room architectural floor plan SVG.

    Purpose:
        Produces immediate visual verification of room layouts, dimensions,
        door openings, and inter-room connectivity.

    Parameters:
        rooms: List of Room2D objects in global coordinates.
        connections: List of RoomAdjacencyEdge connections.
        detected_openings: Optional list of opening dictionaries.
        scan_id: Capture identifier string.
        drift_status: Status of drift correction.
        output_path: Optional file destination Path.
        width_px: Canvas width in pixels.
        height_px: Canvas height in pixels.
        margin_px: Canvas margins in pixels.

    Returns:
        Complete SVG markup string.

    Assumptions:
        Room polygon vertices are in global metric coordinates.

    Failure conditions:
        Empty rooms list renders an informative placeholder SVG.

    Debugging:
        Open property_debug.svg in browser to confirm room shapes match physical property.
    """
    if not rooms:
        return f'<svg xmlns="http://www.w3.org/2000/svg" width="{width_px}" height="{height_px}"><text x="50" y="50" fill="white">No rooms available</text></svg>'

    # Determine global bounds across all rooms
    all_x = []
    all_z = []
    for r in rooms:
        for p in r.polygon:
            all_x.append(p.x)
            all_z.append(p.y)

    min_x, max_x = min(all_x), max(all_x)
    min_z, max_z = min(all_z), max(all_z)

    span_x = max(max_x - min_x, 1.0)
    span_z = max(max_z - min_z, 1.0)

    usable_w = width_px - 2 * margin_px
    usable_h = height_px - 2 * margin_px - 100
    scale = min(usable_w / span_x, usable_h / span_z)

    offset_x = margin_px + (usable_w - span_x * scale) / 2.0
    offset_z = margin_px + 90 + (usable_h - span_z * scale) / 2.0

    def to_svg(x: float, z: float) -> Tuple[float, float]:
        return offset_x + (x - min_x) * scale, offset_z + (z - min_z) * scale

    total_area = sum(r.area_sqm for r in rooms)

    svg_lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width_px} {height_px}" '
        f'width="{width_px}" height="{height_px}" style="background-color: #0b0f19; font-family: ui-sans-serif, system-ui, sans-serif;">',
        '  <defs>',
        '    <marker id="arrow" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">',
        '      <path d="M 0 0 L 10 5 L 0 10 z" fill="#facc15" />',
        '    </marker>',
        '  </defs>',
        # Header banner
        f'  <rect x="24" y="16" width="{width_px - 48}" height="76" rx="8" fill="#111827" stroke="#1f2937" stroke-width="1.5"/>',
        f'  <text x="44" y="44" fill="#f8fafc" font-size="18" font-weight="bold">WHOLE PROPERTY FLOOR PLAN: {scan_id}</text>',
        f'  <text x="44" y="68" fill="#94a3b8" font-size="13">Rooms: {len(rooms)} | Total Area: {total_area:.1f} m² | Connections: {len(connections)} | Drift Correction: <tspan fill="#10b981" font-weight="bold">{drift_status}</tspan></text>',
    ]

    # Coordinate Grid
    grid_step_m = 2.0
    gx = math.floor(min_x / grid_step_m) * grid_step_m
    while gx <= max_x + grid_step_m:
        sx, _ = to_svg(gx, min_z)
        svg_lines.append(f'  <line x1="{sx:.1f}" y1="{margin_px + 90}" x2="{sx:.1f}" y2="{height_px - margin_px}" stroke="#1e293b" stroke-width="1"/>')
        gx += grid_step_m

    gz = math.floor(min_z / grid_step_m) * grid_step_m
    while gz <= max_z + grid_step_m:
        _, sz = to_svg(min_x, gz)
        svg_lines.append(f'  <line x1="{margin_px}" y1="{sz:.1f}" x2="{width_px - margin_px}" y2="{sz:.1f}" stroke="#1e293b" stroke-width="1"/>')
        gz += grid_step_m

    # Room colors palette
    room_colors = [
        {"fill": "#1e293b", "stroke": "#38bdf8", "text": "#7dd3fc"},
        {"fill": "#1e1b4b", "stroke": "#818cf8", "text": "#a5b4fc"},
        {"fill": "#064e3b", "stroke": "#34d399", "text": "#6ee7b7"},
        {"fill": "#3b0764", "stroke": "#c084fc", "text": "#d8b4fe"},
        {"fill": "#1f2937", "stroke": "#fbbf24", "text": "#fde68a"},
    ]

    room_centroids: Dict[str, Tuple[float, float]] = {}

    # Render each room polygon
    for idx, r in enumerate(rooms):
        color = room_colors[idx % len(room_colors)]
        if "connector" in r.room_id.lower():
            color = {"fill": "#064e3b", "stroke": "#10b981", "text": "#a7f3d0"}

        pts_str = " ".join(f"{to_svg(p.x, p.y)[0]:.1f},{to_svg(p.x, p.y)[1]:.1f}" for p in r.polygon)
        svg_lines.append(f'  <polygon points="{pts_str}" fill="{color["fill"]}" fill-opacity="0.6" stroke="{color["stroke"]}" stroke-width="2.5"/>')

        # Centroid calculation using Shapely representative point for irregular/corridor polygons
        poly_geom = Polygon([(p.x, p.y) for p in r.polygon])
        rep_pt = poly_geom.representative_point() if poly_geom.is_valid else poly_geom.centroid
        cx, cy = float(rep_pt.x), float(rep_pt.y)
        scx, scy = to_svg(cx, cy)
        room_centroids[r.room_id] = (scx, scy)

        # Label inside room
        svg_lines.append(f'  <text x="{scx:.1f}" y="{scy - 10:.1f}" fill="{color["text"]}" font-size="14" font-weight="bold" text-anchor="middle">{r.name.upper()}</text>')
        svg_lines.append(f'  <text x="{scx:.1f}" y="{scy + 8:.1f}" fill="#f8fafc" font-size="12" text-anchor="middle">{r.area_sqm:.1f} m²</text>')
        svg_lines.append(f'  <text x="{scx:.1f}" y="{scy + 24:.1f}" fill="#94a3b8" font-size="10" text-anchor="middle">Perim: {r.perimeter_meters:.1f}m</text>')

    # Render door openings if available
    if detected_openings:
        for op in detected_openings:
            pos = op.get("position_3d") or op.get("center_xz")
            if pos:
                op_x = pos[0]
                op_z = pos[2] if len(pos) > 2 else pos[1]
                sop_x, sop_z = to_svg(op_x, op_z)
                svg_lines.append(f'  <circle cx="{sop_x:.1f}" cy="{sop_z:.1f}" r="5" fill="#f59e0b" stroke="#ffffff" stroke-width="1.5"/>')
                svg_lines.append(f'  <text x="{sop_x + 8:.1f}" y="{sop_z + 3:.1f}" fill="#f59e0b" font-size="9">DOOR</text>')

    # Render adjacency edges (connection arrows)
    for conn in connections:
        if conn.room_a_id in room_centroids and conn.room_b_id in room_centroids:
            p1 = room_centroids[conn.room_a_id]
            p2 = room_centroids[conn.room_b_id]
            svg_lines.append(f'  <line x1="{p1[0]:.1f}" y1="{p1[1]:.1f}" x2="{p2[0]:.1f}" y2="{p2[1]:.1f}" stroke="#facc15" stroke-width="2" stroke-dasharray="4,4" marker-end="url(#arrow)"/>')

    svg_lines.append('</svg>')
    svg_markup = "\n".join(svg_lines)

    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(svg_markup)

    return svg_markup
