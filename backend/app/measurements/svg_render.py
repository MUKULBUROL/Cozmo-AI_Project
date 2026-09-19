"""High-contrast dimensioned debug SVG visualization for Stage 4 floor plan measurements.

1. Why this file exists:
   Generates inspectable, dimensioned SVG engineering drawings visualizing room polygons,
   individual wall dimensions with confidence intervals, corner identification, inferred gap closures,
   and validity gating status without requiring CAD or desktop viewer software.

2. Pipeline stage:
   Stage 4 (Metric Measurements, Room Area & Uncertainty) - Visual Diagnostics.

3. Inputs:
   Metric wall dimensions, corner coordinates, uncertainty intervals, room polygon vertices,
   and validity gate status.

4. Outputs:
   Stand-alone dimensioned SVG file: outputs/<scan_id>/measurements/dimensioned_debug.svg.

5. Coordinate/Unit assumptions:
   Input coordinates in metric meters (m).
   Rendered SVG maps X to horizontal screen axis and Z to vertical screen axis (inverted).

6. Dependencies:
   math, pathlib, typing, numpy.

7. Most likely failure/debugging points:
   - Degenerate zero-span bounding box if all coordinates are coincident.
   - Text overlapping on extremely short edges (handled with alternate leader offsets).
"""

import math
from pathlib import Path
from typing import List, Dict, Any, Tuple


def render_dimensioned_debug_svg(
    polygon_vertices: List[Tuple[float, float]],
    wall_dimensions: List[Dict[str, Any]],
    corners: List[Dict[str, Any]],
    measurement_stats: Dict[str, Any],
    output_path: Path,
) -> None:
    """Renders a dimensioned dark-mode SVG debug diagram of the room floorplan.

    Purpose:
        Provides clear graphical inspection of edge lengths, 95% intervals, corner classifications,
        T-junction doorway transitions, area, perimeter, and validity gate badges.

    Parameters:
        polygon_vertices: Ordered list of (x, z) coordinates defining the closed boundary.
        wall_dimensions: List of wall measurement dictionaries with lengths and intervals.
        corners: List of corner dictionaries with position, inference status, and IDs.
        measurement_stats: Summary statistics dictionary from measurement engine.
        output_path: Target filesystem path for generated SVG file.

    Returns:
        None.

    Assumptions:
        Coordinates are metric in meters. Output directory will be created if missing.

    Failure conditions:
        Falls back to default bounds if vertices list is empty.

    Debugging:
        Open output SVG in Chrome, Firefox, or VSCode SVG preview to inspect dimension labels.
    """
    svg_w, svg_h = 1000, 800
    margin = 110

    # Collect coordinates to compute bounding box
    all_x: List[float] = [v[0] for v in polygon_vertices]
    all_z: List[float] = [v[1] for v in polygon_vertices]
    for c in corners:
        all_x.append(c.get("x", 0.0))
        all_z.append(c.get("z", 0.0))

    if not all_x:
        all_x, all_z = [0.0, 5.0], [0.0, 5.0]

    min_x, max_x = min(all_x), max(all_x)
    min_z, max_z = min(all_z), max(all_z)

    span_x = max(max_x - min_x, 0.5)
    span_z = max(max_z - min_z, 0.5)

    # Maintain uniform aspect ratio
    scale = min((svg_w - 2 * margin) / span_x, (svg_h - 2 * margin) / span_z)
    center_x = (min_x + max_x) / 2.0
    center_z = (min_z + max_z) / 2.0

    def to_svg(x: float, z: float) -> Tuple[float, float]:
        """Maps physical metric coordinates (x, z) to canvas pixel coordinates (sx, sy)."""
        sx = (svg_w / 2.0) + (x - center_x) * scale
        # Invert Z so positive Z points upward in visual room coordinates
        sy = (svg_h / 2.0) - (z - center_z) * scale
        return sx, sy

    svg_lines: List[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {svg_w} {svg_h}" width="{svg_w}" height="{svg_h}" style="background:#0f172a; font-family:ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,monospace;">',
        '  <defs>',
        '    <!-- Dimension arrow markers -->',
        '    <marker id="dim-arrow-start" markerWidth="6" markerHeight="6" refX="5" refY="3" orient="auto">',
        '      <path d="M5,1 L1,3 L5,5" fill="none" stroke="#38bdf8" stroke-width="1.2"/>',
        '    </marker>',
        '    <marker id="dim-arrow-end" markerWidth="6" markerHeight="6" refX="1" refY="3" orient="auto">',
        '      <path d="M1,1 L5,3 L1,5" fill="none" stroke="#38bdf8" stroke-width="1.2"/>',
        '    </marker>',
        '    <marker id="dim-arrow-inf-start" markerWidth="6" markerHeight="6" refX="5" refY="3" orient="auto">',
        '      <path d="M5,1 L1,3 L5,5" fill="none" stroke="#f59e0b" stroke-width="1.2"/>',
        '    </marker>',
        '    <marker id="dim-arrow-inf-end" markerWidth="6" markerHeight="6" refX="1" refY="3" orient="auto">',
        '      <path d="M1,1 L5,3 L1,5" fill="none" stroke="#f59e0b" stroke-width="1.2"/>',
        '    </marker>',
        '  </defs>',
        '  <!-- Background grid -->',
        '  <pattern id="grid" width="40" height="40" patternUnits="userSpaceOnUse">',
        '    <path d="M 40 0 L 0 0 0 40" fill="none" stroke="#1e293b" stroke-width="0.8"/>',
        '  </pattern>',
        f'  <rect width="{svg_w}" height="{svg_h}" fill="url(#grid)"/>',
    ]

    # 1. Draw Closed Room Polygon
    if len(polygon_vertices) >= 3:
        pts_str = " ".join([f"{to_svg(v[0], v[1])[0]:.1f},{to_svg(v[0], v[1])[1]:.1f}" for v in polygon_vertices])
        svg_lines.append(
            f'  <polygon points="{pts_str}" fill="#1e293b" fill-opacity="0.6" stroke="#475569" stroke-width="2" stroke-linejoin="round"/>'
        )

    # 2. Draw Dimensioned Wall Edges with Offset Leader Lines
    for w in wall_dimensions:
        p1 = w.get("start", [0.0, 0.0])
        p2 = w.get("end", [0.0, 0.0])
        sx1, sy1 = to_svg(p1[0], p1[1])
        sx2, sy2 = to_svg(p2[0], p2[1])

        is_inf = w.get("has_inferred_corner", False)
        edge_color = "#f59e0b" if is_inf else "#38bdf8"
        marker_s = "dim-arrow-inf-start" if is_inf else "dim-arrow-start"
        marker_e = "dim-arrow-inf-end" if is_inf else "dim-arrow-end"

        # Edge stroke
        svg_lines.append(
            f'  <line x1="{sx1:.1f}" y1="{sy1:.1f}" x2="{sx2:.1f}" y2="{sy2:.1f}" stroke="{edge_color}" stroke-width="3" stroke-linecap="round"/>'
        )

        # Dimension line calculation
        dx = sx2 - sx1
        dy = sy2 - sy1
        seg_len = math.hypot(dx, dy)
        if seg_len > 1e-4:
            # Perpendicular normal outward
            nx = -dy / seg_len
            ny = dx / seg_len

            # Check outward direction relative to polygon centroid
            poly_cx = sum(v[0] for v in polygon_vertices) / len(polygon_vertices)
            poly_cz = sum(v[1] for v in polygon_vertices) / len(polygon_vertices)
            scx, scy = to_svg(poly_cx, poly_cz)
            mid_x = (sx1 + sx2) / 2.0
            mid_y = (sy1 + sy2) / 2.0

            # If normal points towards centroid, flip it outward
            if (mid_x + nx * 10 - scx) ** 2 + (mid_y + ny * 10 - scy) ** 2 < (mid_x - scx) ** 2 + (mid_y - scy) ** 2:
                nx, ny = -nx, -ny

            offset = 24.0
            lx1 = sx1 + nx * offset
            ly1 = sy1 + ny * offset
            lx2 = sx2 + nx * offset
            ly2 = sy2 + ny * offset

            # Leader extension lines
            svg_lines.append(
                f'  <line x1="{sx1:.1f}" y1="{sy1:.1f}" x2="{lx1 + nx * 4:.1f}" y2="{ly1 + ny * 4:.1f}" stroke="#64748b" stroke-width="1" stroke-dasharray="2,2"/>'
            )
            svg_lines.append(
                f'  <line x1="{sx2:.1f}" y1="{sy2:.1f}" x2="{lx2 + nx * 4:.1f}" y2="{ly2 + ny * 4:.1f}" stroke="#64748b" stroke-width="1" stroke-dasharray="2,2"/>'
            )
            # Dimension span line
            svg_lines.append(
                f'  <line x1="{lx1:.1f}" y1="{ly1:.1f}" x2="{lx2:.1f}" y2="{ly2:.1f}" stroke="{edge_color}" stroke-width="1.4" marker-start="url(#{marker_s})" marker-end="url(#{marker_e})"/>'
            )

            # Dimension label text
            l_mid_x = (lx1 + lx2) / 2.0 + nx * 12.0
            l_mid_y = (ly1 + ly2) / 2.0 + ny * 12.0

            val = w.get("length_m", 0.0)
            interval = w.get("interval_95_m", [val, val])
            wall_lbl = f'{w.get("wall_id", "")}: {val:.2f}m'
            int_lbl = f'[{interval[0]:.2f}-{interval[1]:.2f}]'

            svg_lines.append(
                f'  <text x="{l_mid_x:.1f}" y="{l_mid_y:.1f}" fill="{edge_color}" font-size="11" font-weight="bold" text-anchor="middle">'
                f'{wall_lbl} <tspan font-size="9" fill="#94a3b8">{int_lbl}</tspan></text>'
            )

    # 3. Draw Corners
    corner_dict = {c.get("id"): c for c in corners}
    for c in corners:
        cx, cy = to_svg(c.get("x", 0.0), c.get("z", 0.0))
        is_inf = c.get("inferred", False)
        dot_col = "#f59e0b" if is_inf else "#22c55e"

        if is_inf:
            svg_lines.append(
                f'  <circle cx="{cx:.1f}" cy="{cy:.1f}" r="10" fill="none" stroke="#f59e0b" stroke-width="1.8" stroke-dasharray="3,3"/>'
            )
        svg_lines.append(f'  <circle cx="{cx:.1f}" cy="{cy:.1f}" r="5" fill="{dot_col}"/>')

        lbl = c.get("id", "") + ("*" if is_inf else "")
        svg_lines.append(
            f'  <text x="{cx + 8:.1f}" y="{cy - 8:.1f}" fill="{dot_col}" font-size="10" font-weight="bold">{lbl}</text>'
        )

    # 4. HUD Information Overlay (Top-Left)
    scan_id = measurement_stats.get("scan_id", "unknown")
    status = measurement_stats.get("measurement_status", "provisional").upper()
    reasons = measurement_stats.get("reasons", [])
    area_val = measurement_stats.get("floor_area_m2", 0.0)
    area_int = measurement_stats.get("floor_area_interval", [0.0, 0.0])
    perim_val = measurement_stats.get("perimeter_m", 0.0)
    perim_int = measurement_stats.get("perimeter_interval", [0.0, 0.0])
    ceil_stat = measurement_stats.get("ceiling_height_status", "not_observed")
    ceil_val = measurement_stats.get("ceiling_height_m")
    inf_count = measurement_stats.get("inferred_corner_count", 0)

    status_badge_fill = "#166534" if status == "VALID" else ("#854d0e" if status == "PROVISIONAL" else "#991b1b")
    status_text_color = "#4ade80" if status == "VALID" else ("#fde047" if status == "PROVISIONAL" else "#fca5a5")

    hud_h = 240 + max(0, len(reasons) * 16)
    svg_lines.extend([
        '  <!-- Status & Measurements HUD -->',
        '  <g transform="translate(24, 24)">',
        f'    <rect width="360" height="{hud_h}" rx="8" fill="#1e293b" opacity="0.94" stroke="#334155" stroke-width="1.5"/>',
        f'    <text x="16" y="26" fill="#f8fafc" font-size="13" font-weight="bold">STAGE 4 DIMENSIONED PLAN: {scan_id}</text>',
        f'    <rect x="16" y="38" width="130" height="22" rx="4" fill="{status_badge_fill}"/>',
        f'    <text x="26" y="53" fill="{status_text_color}" font-size="11" font-weight="bold">STATUS: {status}</text>',
        f'    <text x="16" y="80" fill="#94a3b8" font-size="11">Floor Area: <tspan fill="#f8fafc" font-weight="bold">{area_val:.2f} m²</tspan> <tspan fill="#64748b">[{area_int[0]:.2f} - {area_int[1]:.2f}]</tspan></text>',
        f'    <text x="16" y="100" fill="#94a3b8" font-size="11">Perimeter:  <tspan fill="#f8fafc" font-weight="bold">{perim_val:.2f} m</tspan> <tspan fill="#64748b">[{perim_int[0]:.2f} - {perim_int[1]:.2f}]</tspan></text>',
    ])

    if ceil_val is not None:
        svg_lines.append(f'    <text x="16" y="120" fill="#94a3b8" font-size="11">Ceiling Ht: <tspan fill="#f8fafc" font-weight="bold">{ceil_val:.2f} m</tspan></text>')
    else:
        svg_lines.append('    <text x="16" y="120" fill="#94a3b8" font-size="11">Ceiling Ht: <tspan fill="#f59e0b" font-weight="bold">NOT OBSERVED</tspan></text>')

    svg_lines.extend([
        f'    <text x="16" y="140" fill="#94a3b8" font-size="11">Walls Measured: <tspan fill="#38bdf8">{len(wall_dimensions)}</tspan> | Inferred Corners: <tspan fill="#f59e0b">{inf_count}</tspan></text>',
        '    <line x1="16" y1="152" x2="344" y2="152" stroke="#334155" stroke-width="1"/>',
    ])

    if reasons:
        svg_lines.append('    <text x="16" y="168" fill="#fde047" font-size="10" font-weight="bold">Gate Advisory Reasons:</text>')
        curr_y = 184
        for r in reasons:
            svg_lines.append(f'    <text x="24" y="{curr_y}" fill="#94a3b8" font-size="10">• {r}</text>')
            curr_y += 16
    else:
        svg_lines.append('    <text x="16" y="168" fill="#4ade80" font-size="10">✓ All geometric health criteria fully satisfied.</text>')

    svg_lines.append('  </g>')

    # 5. Bottom Disclaimer Banner (Ground Truth Warning & CAD distinction)
    svg_lines.extend([
        '  <!-- Disclaimer Banner -->',
        f'  <g transform="translate(24, {svg_h - 45})">',
        '    <rect width="952" height="30" rx="4" fill="#1e293b" opacity="0.85" stroke="#334155" stroke-width="1"/>',
        '    <text x="16" y="19" fill="#f59e0b" font-size="10" font-weight="bold">STAGE 4 ENGINEERING DIAGNOSTIC — NOT PRODUCTION CAD / BLUEPRINT.</text>',
        '    <text x="460" y="19" fill="#94a3b8" font-size="10">Dimensions are geometric estimates from 3D reconstruction. Calibrated physical ground truth required.</text>',
        '  </g>',
        '</svg>'
    ])

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(svg_lines))
