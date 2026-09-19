"""Master Stage 3 orchestrator: 2D wall projection, corner detection, and room polygon generation.

1. Why this file exists:
   Serves as the central coordinator for Stage 3. Loads Stage 2 structural planes,
   applies quality gates, projects to 2D lines in the horizontal XZ floor plane,
   determines finite extents, discovers candidate corners, infers gap closures,
   extracts closed room polygons, computes evidence-based validation metrics,
   and exports all standardized JSON deliverables and SVG debug visualizations.

2. Pipeline stage:
   Stage 3 (2D Wall Projection, Corner Intersections & Room Polygon) - Core Pipeline.

3. Inputs:
   outputs/<scan_id>/structure/structure.json
   outputs/<scan_id>/structure/walls.ply (optional)

4. Outputs:
   outputs/<scan_id>/floorplan_geometry/
     ├── wall_quality.json
     ├── projected_walls.json
     ├── corners.json
     ├── room_polygon.json
     ├── polygon_stats.json
     └── floorplan_debug.svg

5. Coordinate/Unit assumptions:
   Y is vertical (upward).
   XZ is the horizontal ground plane.
   All coordinates, spans, lengths, and areas are metric (meters, square meters).

6. Dependencies:
   numpy, open3d (optional), pathlib, json, shapely,
   .wall_quality, .projection_2d, .corner_detection, .polygon_builder, .polygon_validation.

7. Most likely failure/debugging points:
   - Missing structure.json from Stage 2.
   - All walls rejected by quality filter if thresholds are improperly calibrated.
   - Graph disconnection preventing closed cycle formation.
"""

import os
import json
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List
import numpy as np

from .wall_quality import evaluate_wall_quality
from .projection_2d import project_walls_to_2d, merge_near_duplicate_2d_lines
from .corner_detection import detect_candidate_corners
from .polygon_builder import extract_room_polygon
from .polygon_validation import validate_room_polygon, compute_polygon_quality_metrics


def render_floorplan_debug_svg(
    accepted_walls: List[Dict[str, Any]],
    rejected_walls: List[Dict[str, Any]],
    projected_walls: List[Dict[str, Any]],
    accepted_corners: List[Dict[str, Any]],
    rejected_corners: List[Dict[str, Any]],
    polygon_data: Dict[str, Any],
    validation_data: Dict[str, Any],
    quality_data: Dict[str, Any],
    scan_id: str,
    output_path: Path,
) -> None:
    """Renders a rich, high-contrast SVG debug visualization of the 2D floorplan geometry.

    Purpose:
        Enables rapid visual inspection of accepted/rejected walls, finite segments,
        candidate corners, inferred gap closures, and final polygon enclosure.

    Parameters:
        accepted_walls: Stage 2 walls passing quality gate.
        rejected_walls: Stage 2 walls rejected with reasons.
        projected_walls: 2D projected and merged wall segments.
        accepted_corners: Validated candidate corners.
        rejected_corners: Discarded intersections.
        polygon_data: Closed room polygon vertices and metadata.
        validation_data: Geometric validation report.
        quality_data: Measurable confidence metrics.
        scan_id: Scan identifier string.
        output_path: Target SVG file path.

    Assumptions:
        Coordinates are in meters. Mapping maps X to SVG X, and Z to SVG Y (inverted).

    Failure conditions:
        Falls back safely to default bounding box if vertices are empty.

    Debugging:
        Open output SVG in any web browser to inspect geometric relationships.
    """
    # Collect all 2D points to establish bounding box
    all_pts: List[Tuple[float, float]] = []
    for w in projected_walls:
        all_pts.append((w["start"][0], w["start"][1]))
        all_pts.append((w["end"][0], w["end"][1]))
    for c in accepted_corners:
        all_pts.append((c["x"], c["z"]))
    for pt in polygon_data.get("vertices", []):
        all_pts.append((pt[0], pt[1]))

    if not all_pts:
        all_pts = [(0.0, 0.0), (1.0, 1.0)]

    pts_arr = np.array(all_pts)
    min_x, max_x = float(np.min(pts_arr[:, 0])), float(np.max(pts_arr[:, 0]))
    min_z, max_z = float(np.min(pts_arr[:, 1])), float(np.max(pts_arr[:, 1]))

    # Add 1.5m margin
    margin = 1.5
    min_x -= margin
    max_x += margin
    min_z -= margin
    max_z += margin

    span_x = max(1.0, max_x - min_x)
    span_z = max(1.0, max_z - min_z)

    # Scaling: 120 pixels per meter
    scale = 120.0
    width_px = int(span_x * scale)
    height_px = int(span_z * scale)

    def to_svg(x: float, z: float) -> Tuple[float, float]:
        # X maps left-to-right, Z maps bottom-to-top (standard Cartesian)
        px = (x - min_x) * scale
        pz = (max_z - z) * scale  # Invert Z for SVG Y
        return px, pz

    svg_lines: List[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width_px} {height_px}" '
        f'width="{width_px}" height="{height_px}" style="background-color: #0f172a; font-family: ui-monospace, SFMono-Regular, monospace;">',
        '<defs>',
        '  <pattern id="grid" width="60" height="60" patternUnits="userSpaceOnUse">',
        '    <path d="M 60 0 L 0 0 0 60" fill="none" stroke="#1e293b" stroke-width="1"/>',
        '  </pattern>',
        '  <pattern id="grid-1m" width="120" height="120" patternUnits="userSpaceOnUse">',
        '    <rect width="120" height="120" fill="url(#grid)"/>',
        '    <path d="M 120 0 L 0 0 0 120" fill="none" stroke="#334155" stroke-width="1.5"/>',
        '  </pattern>',
        '</defs>',
        f'<rect width="{width_px}" height="{height_px}" fill="url(#grid-1m)"/>',
    ]

    # 1. Draw Rejected Walls (Dashed red)
    for rw in rejected_walls:
        bounds = rw.get("bounds", {})
        bx = bounds.get("x", [0.0, 0.0])
        bz = bounds.get("z", [0.0, 0.0])
        p1_x, p1_z = to_svg(bx[0], bz[0])
        p2_x, p2_z = to_svg(bx[1], bz[1])
        svg_lines.append(
            f'  <line x1="{p1_x:.1f}" y1="{p1_z:.1f}" x2="{p2_x:.1f}" y2="{p2_z:.1f}" '
            f'stroke="#f43f5e" stroke-width="2" stroke-dasharray="6,6" opacity="0.6"/>'
        )
        mid_x, mid_z = (p1_x + p2_x) / 2, (p1_z + p2_z) / 2
        reason = rw.get("rejection_reasons", ["rejected"])[0]
        svg_lines.append(
            f'  <text x="{mid_x:.1f}" y="{mid_z:.1f}" fill="#f43f5e" font-size="11" opacity="0.8">'
            f'{rw.get("id", "wall")} [REJECTED: {reason}]</text>'
        )

    # 2. Draw Final Closed Room Polygon (Fill and boundary)
    poly_vertices = polygon_data.get("vertices", [])
    if len(poly_vertices) >= 4 and polygon_data.get("valid", False):
        svg_pts = " ".join(f"{to_svg(v[0], v[1])[0]:.1f},{to_svg(v[0], v[1])[1]:.1f}" for v in poly_vertices)
        svg_lines.append(
            f'  <polygon points="{svg_pts}" fill="rgba(34, 197, 94, 0.18)" '
            f'stroke="#22c55e" stroke-width="4" stroke-linejoin="round"/>'
        )

    # 3. Draw Observed Finite Wall Segments (Solid Cyan/Blue)
    for w in projected_walls:
        s_px, s_pz = to_svg(w["start"][0], w["start"][1])
        e_px, e_pz = to_svg(w["end"][0], w["end"][1])
        svg_lines.append(
            f'  <line x1="{s_px:.1f}" y1="{s_pz:.1f}" x2="{e_px:.1f}" y2="{e_pz:.1f}" '
            f'stroke="#38bdf8" stroke-width="5" stroke-linecap="round"/>'
        )
        # Endpoint tick marks
        svg_lines.append(f'  <circle cx="{s_px:.1f}" cy="{s_pz:.1f}" r="4" fill="#0284c7"/>')
        svg_lines.append(f'  <circle cx="{e_px:.1f}" cy="{e_pz:.1f}" r="4" fill="#0284c7"/>')

        # Wall ID and Length label
        mid_x = (s_px + e_px) / 2
        mid_z = (s_pz + e_pz) / 2
        svg_lines.append(
            f'  <rect x="{mid_x - 35:.1f}" y="{mid_z - 16:.1f}" width="70" height="18" rx="4" fill="#0f172a" opacity="0.85"/>'
        )
        svg_lines.append(
            f'  <text x="{mid_x:.1f}" y="{mid_z - 3:.1f}" fill="#38bdf8" font-size="11" text-anchor="middle" font-weight="bold">'
            f'{w["wall_id"]} ({w["length_m"]:.2f}m)</text>'
        )

    # 4. Draw Candidate and Inferred Corners
    for c in accepted_corners:
        cx, cz = to_svg(c["x"], c["z"])
        is_inf = c.get("inferred", False)
        dot_color = "#f59e0b" if is_inf else "#22c55e"

        # Highlight inferred gap extensions
        if is_inf:
            svg_lines.append(
                f'  <circle cx="{cx:.1f}" cy="{cz:.1f}" r="9" fill="none" stroke="#f59e0b" stroke-width="2" stroke-dasharray="3,3"/>'
            )

        svg_lines.append(f'  <circle cx="{cx:.1f}" cy="{cz:.1f}" r="6" fill="{dot_color}"/>')

        # Corner Label
        label_text = f'{c["id"]}' + (' [INF]' if is_inf else '')
        svg_lines.append(
            f'  <text x="{cx + 10:.1f}" y="{cz - 6:.1f}" fill="{dot_color}" font-size="12" font-weight="bold">'
            f'{label_text} ({c["x"]:.2f}, {c["z"]:.2f})</text>'
        )

    # 5. Legend & Statistics HUD Box (Top-Left Overlay)
    area_sqm = polygon_data.get("area_sqm", 0.0)
    perim_m = polygon_data.get("perimeter_m", 0.0)
    is_valid = polygon_data.get("valid", False)
    is_closed = polygon_data.get("closed", False)
    quality_score = quality_data.get("composite_quality_score", 0.0)
    support_ratio = quality_data.get("boundary_support_ratio", 0.0)

    status_color = "#22c55e" if (is_valid and is_closed) else "#ef4444"

    svg_lines.extend([
        '  <!-- HUD / Legend Overlay -->',
        '  <g transform="translate(24, 24)">',
        '    <rect width="320" height="230" rx="8" fill="#1e293b" opacity="0.92" stroke="#334155" stroke-width="1.5"/>',
        f'    <text x="16" y="28" fill="#f8fafc" font-size="14" font-weight="bold">STAGE 3 ROOM FOOTPRINT: {scan_id}</text>',
        f'    <text x="16" y="52" fill="{status_color}" font-size="13" font-weight="bold">Polygon Valid: {"YES" if is_valid else "NO"} | Closed: {"YES" if is_closed else "NO"}</text>',
        f'    <text x="16" y="74" fill="#94a3b8" font-size="12">Area: <tspan fill="#f8fafc" font-weight="bold">{area_sqm:.2f} m²</tspan> | Perim: <tspan fill="#f8fafc" font-weight="bold">{perim_m:.2f} m</tspan></text>',
        f'    <text x="16" y="96" fill="#94a3b8" font-size="12">Walls Accepted: <tspan fill="#38bdf8">{len(accepted_walls)}</tspan> | Rejected: <tspan fill="#f43f5e">{len(rejected_walls)}</tspan></text>',
        f'    <text x="16" y="118" fill="#94a3b8" font-size="12">Corners Accepted: <tspan fill="#22c55e">{len(accepted_corners)}</tspan> (Inferred: <tspan fill="#f59e0b">{quality_data.get("inferred_corner_count", 0)}</tspan>)</text>',
        f'    <text x="16" y="140" fill="#94a3b8" font-size="12">Boundary Wall Support: <tspan fill="#f8fafc">{(support_ratio * 100):.1f}%</tspan></text>',
        f'    <text x="16" y="162" fill="#94a3b8" font-size="12">Evidence Quality Score: <tspan fill="#22c55e">{quality_score:.3f} / 1.000</tspan></text>',
        '    <line x1="16" y1="174" x2="304" y2="174" stroke="#334155" stroke-width="1"/>',
        '    <!-- Legend markers -->',
        '    <line x1="16" y1="192" x2="40" y2="192" stroke="#38bdf8" stroke-width="4"/>',
        '    <text x="46" y="196" fill="#94a3b8" font-size="11">Wall Segment</text>',
        '    <circle cx="150" cy="192" r="5" fill="#22c55e"/>',
        '    <text x="160" y="196" fill="#94a3b8" font-size="11">Observed Corner</text>',
        '    <circle cx="16" cy="214" r="5" fill="#f59e0b"/>',
        '    <text x="26" y="218" fill="#94a3b8" font-size="11">Inferred Gap Closure</text>',
        '    <line x1="150" y1="214" x2="174" y2="214" stroke="#f43f5e" stroke-width="2" stroke-dasharray="4,4"/>',
        '    <text x="180" y="218" fill="#94a3b8" font-size="11">Rejected Plane</text>',
        '  </g>',
    ])

    svg_lines.append('</svg>')

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(svg_lines))


def run_stage3_pipeline(
    scan_id: str,
    structure_json_path: Path,
    walls_ply_path: Optional[Path] = None,
    output_dir: Optional[Path] = None,
    max_wall_rmse_m: float = 0.15,
    min_wall_confidence: float = 0.40,
    min_wall_height_span_m: float = 1.00,
    min_wall_inliers: int = 4000,
    max_corner_extension_m: float = 0.35,
    max_point_to_segment_m: float = 0.40,
) -> Dict[str, Any]:
    """Executes the complete Stage 3 2D room polygon extraction workflow.

    Purpose:
        Main entry point for Stage 3. Evaluates quality, projects planes to 2D lines,
        merges duplicates, identifies candidate corners, infers gap closures,
        extracts closed room polygon, runs geometric validation, and writes outputs.

    Parameters:
        scan_id: Unique capture identifier (e.g. 'c00a170fe1').
        structure_json_path: Path to Stage 2 structure.json file.
        walls_ply_path: Optional path to Stage 2 walls.ply point cloud.
        output_dir: Directory where Stage 3 deliverables will be written.
        max_wall_rmse_m: Max plane RMSE for quality gate.
        min_wall_confidence: Min structural confidence for quality gate.
        min_wall_height_span_m: Min vertical height span in meters.
        min_wall_inliers: Min point inliers for quality gate.
        max_corner_extension_m: Maximum gap extension allowed for corners.
        max_point_to_segment_m: Maximum proximity distance to wall segment.

    Returns:
        Dictionary summarizing pipeline execution results.

    Assumptions:
        Stage 2 outputs exist and are valid. Coordinates are metric in meters.

    Failure conditions:
        Raises FileNotFoundError if structure_json_path does not exist.

    Debugging:
        Inspect wall_quality.json or room_polygon.json in output_dir.
    """
    if not structure_json_path.exists():
        raise FileNotFoundError(f"Stage 2 output not found at {structure_json_path}")

    if output_dir is None:
        output_dir = Path(f"outputs/{scan_id}/floorplan_geometry")
    output_dir.mkdir(parents=True, exist_ok=True)

    with open(structure_json_path, "r", encoding="utf-8") as f:
        stage2_data = json.load(f)

    raw_walls = stage2_data.get("walls", [])

    # Load wall point cloud if present
    wall_points_3d = None
    if walls_ply_path is not None and walls_ply_path.exists():
        try:
            import open3d as o3d
            pcd = o3d.io.read_point_cloud(str(walls_ply_path))
            wall_points_3d = np.asarray(pcd.points)
        except Exception as e:
            print(f"Warning: Could not read {walls_ply_path}: {e}")

    # STEP 1: Wall Quality Gate
    accepted_walls, uncertain_walls, rejected_walls = evaluate_wall_quality(
        walls=raw_walls,
        max_rmse_m=max_wall_rmse_m,
        min_confidence=min_wall_confidence,
        min_height_span_m=min_wall_height_span_m,
        min_inliers=min_wall_inliers,
    )

    quality_report = {
        "scan_id": scan_id,
        "total_stage2_walls": len(raw_walls),
        "accepted_count": len(accepted_walls),
        "rejected_count": len(rejected_walls),
        "accepted_walls": [
            {
                "wall_id": w["id"],
                "inliers": w.get("inlier_count", 0),
                "rmse_m": w.get("rmse_m", 0.0),
                "confidence": w.get("confidence", 0.0),
                "height_m": w.get("spans_m", {}).get("height_y", 0.0),
            }
            for w in accepted_walls
        ],
        "rejected_walls": [
            {
                "wall_id": w["id"],
                "reasons": w.get("rejection_reasons", []),
                "rmse_m": w.get("rmse_m", 0.0),
                "confidence": w.get("confidence", 0.0),
                "height_m": w.get("spans_m", {}).get("height_y", 0.0),
            }
            for w in rejected_walls
        ],
    }
    with open(output_dir / "wall_quality.json", "w", encoding="utf-8") as f:
        json.dump(quality_report, f, indent=2)

    # STEP 2 & 3: Project to 2D & Determine Finite Extents
    raw_projected = project_walls_to_2d(accepted_walls, all_points_3d=wall_points_3d)

    # STEP 4: Normalize and Merge Duplicate 2D Lines
    merged_walls, merge_log = merge_near_duplicate_2d_lines(raw_projected)

    projected_report = {
        "scan_id": scan_id,
        "raw_projected_count": len(raw_projected),
        "merged_walls_count": len(merged_walls),
        "merge_actions": merge_log,
        "projected_walls": merged_walls,
    }
    with open(output_dir / "projected_walls.json", "w", encoding="utf-8") as f:
        json.dump(projected_report, f, indent=2)

    # STEP 5, 6, 7: Detect Candidate Corners & Infer Gap Snapping
    accepted_corners, rejected_corners = detect_candidate_corners(
        projected_walls=merged_walls,
        max_extension_m=max_corner_extension_m,
        max_point_to_segment_m=max_point_to_segment_m,
    )

    corners_report = {
        "scan_id": scan_id,
        "candidate_corners_count": len(accepted_corners) + len(rejected_corners),
        "accepted_corners_count": len(accepted_corners),
        "rejected_corners_count": len(rejected_corners),
        "inferred_corners_count": sum(1 for c in accepted_corners if c.get("inferred", False)),
        "accepted_corners": accepted_corners,
        "rejected_corners": rejected_corners,
    }
    with open(output_dir / "corners.json", "w", encoding="utf-8") as f:
        json.dump(corners_report, f, indent=2)

    # STEP 8 & 9: Build Connectivity Graph & Extract Closed Room Polygon
    # Use floor mean bounds or camera trajectory centroid as reference point if available
    ref_interior_pt = None
    if wall_points_3d is not None and len(wall_points_3d) > 0:
        ref_interior_pt = (
            float(np.median(wall_points_3d[:, 0])),
            float(np.median(wall_points_3d[:, 2])),
        )

    polygon_data = extract_room_polygon(
        corners=accepted_corners,
        walls=merged_walls,
        reference_interior_pt=ref_interior_pt,
    )

    # STEP 10: Polygon Validation
    validation_data = validate_room_polygon(polygon_data)

    # STEP 11: Quality / Confidence
    quality_metrics = compute_polygon_quality_metrics(
        polygon_dict=polygon_data,
        accepted_corners=accepted_corners,
        projected_walls=merged_walls,
    )

    # STEP 12 & 13: Export room_polygon.json, polygon_stats.json, and floorplan_debug.svg
    final_polygon_export = {
        "scan_id": scan_id,
        "coordinate_system": {
            "vertical_axis": "Y",
            "floor_plane": "XZ",
            "unit": "m",
        },
        "walls": [
            {
                "wall_id": w["wall_id"],
                "line": w["line"],
                "start": w["start"],
                "end": w["end"],
                "length_m": round(w["length_m"], 3),
                "inlier_count": w["inlier_count"],
                "confidence": round(w["confidence"], 3),
            }
            for w in merged_walls
        ],
        "corners": accepted_corners,
        "polygon": {
            "vertices": polygon_data.get("vertices", []),
            "closed": bool(validation_data.get("is_closed", False)),
            "valid": bool(validation_data.get("is_valid", False)),
            "area_sqm": round(polygon_data.get("area_sqm", 0.0), 3),
            "perimeter_m": round(polygon_data.get("perimeter_m", 0.0), 3),
            "corner_ids": polygon_data.get("corner_ids", []),
            "wall_ids": polygon_data.get("wall_ids", []),
        },
        "quality": quality_metrics,
    }

    with open(output_dir / "room_polygon.json", "w", encoding="utf-8") as f:
        json.dump(final_polygon_export, f, indent=2)

    stats_export = {
        "scan_id": scan_id,
        "validation": validation_data,
        "quality": quality_metrics,
        "diagnostics": polygon_data.get("diagnostics", {}),
    }
    with open(output_dir / "polygon_stats.json", "w", encoding="utf-8") as f:
        json.dump(stats_export, f, indent=2)

    # STEP 13: Render Debug SVG
    render_floorplan_debug_svg(
        accepted_walls=accepted_walls,
        rejected_walls=rejected_walls,
        projected_walls=merged_walls,
        accepted_corners=accepted_corners,
        rejected_corners=rejected_corners,
        polygon_data=polygon_data,
        validation_data=validation_data,
        quality_data=quality_metrics,
        scan_id=scan_id,
        output_path=output_dir / "floorplan_debug.svg",
    )

    return {
        "scan_id": scan_id,
        "accepted_walls": len(accepted_walls),
        "rejected_walls": len(rejected_walls),
        "candidate_corners": len(accepted_corners) + len(rejected_corners),
        "accepted_corners": len(accepted_corners),
        "inferred_corners": quality_metrics.get("inferred_corner_count", 0),
        "polygon_valid": validation_data.get("is_valid", False),
        "polygon_closed": validation_data.get("is_closed", False),
        "self_intersections": validation_data.get("self_intersections_count", 0),
        "area_sqm": polygon_data.get("area_sqm", 0.0),
        "perimeter_m": polygon_data.get("perimeter_m", 0.0),
        "quality_score": quality_metrics.get("composite_quality_score", 0.0),
        "output_dir": str(output_dir),
    }
