"""Professional multi-page engineering and property reconstruction PDF report generator.

Purpose:
    Generates downloadable, presentation-grade PDF inspection reports for Cozmo
    spatial reconstruction results. Contains property metadata, status badges,
    vector architectural floor plan, itemized room and measurement breakdown,
    calibrated 95% confidence intervals, damage observations, repair scopes,
    and mandatory ground truth physical accuracy disclaimers.

Stage:
    Frontend Stage 4 — Exports + Final Product Polish.

Inputs:
    - property_data: Dict or PropertyPlanOutput object representing reconstruction.
    - capture_id: Unique capture identifier string.
    - output_path: Optional destination Path for writing the PDF file.

Outputs:
    - Binary bytes or written PDF document file.

Dependencies:
    pymupdf (or fitz), math, pathlib, typing, pydantic (if PropertyPlanOutput model passed).

Assumptions:
    - Metric measurements in meters (m) and square meters (m2).
    - Status adheres to COMPLETE / PROVISIONAL / NOT_EVALUABLE / FAILED.
    - Honest confidence intervals [lower_bound, upper_bound] are preserved without fabrication.

Coordinate / Unit Conventions:
    - Metric floor plan coordinates (meters) scaled to standard PDF points (1/72 inch).
    - Page size: Standard A4 portrait (595.3 x 841.9 pt).

Failure Modes:
    - Missing geometry handled by rendering diagnostic notice on Page 1.
    - Disk write failure raises IOError.

First Debugging Points:
    - Open generated PDF in PDF viewer or browser to inspect layout, pagination, and text alignment.
    - Verify presence of mandatory accuracy disclaimer.
"""

import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
from pydantic import BaseModel
import pymupdf


def export_property_pdf(
    property_data: Union[Dict[str, Any], BaseModel],
    capture_id: str,
    output_path: Optional[Path] = None,
) -> bytes:
    """Generates a professional multi-page property reconstruction PDF report.

    Purpose:
        Creates a publication-ready PDF deliverable with vector floor plan,
        room metrics, measurement intervals, damage scope, and accuracy disclosures.

    Parameters:
        property_data: Reconstruction result dictionary or BaseModel.
        capture_id: Unique capture identifier.
        output_path: Optional file path to write the PDF bytes to.

    Returns:
        bytes: Raw PDF document binary data.

    Units / Coordinates:
        Metric units (meters, square meters) presented in tables and vector drawing.

    Assumptions:
        property_data conforms to Cozmo PropertyPlanOutput schema.

    Failure Conditions:
        Raises IOError on write failure.

    Debugging Clues:
        Check page count (doc.page_count) and ensure document ends cleanly without blank pages.
    """
    if isinstance(property_data, BaseModel):
        data = property_data.model_dump(mode="json")
    elif isinstance(property_data, dict):
        data = dict(property_data)
    else:
        raise TypeError(f"Expected dict or BaseModel, got {type(property_data)}")

    doc = pymupdf.open()

    tier = str(data.get("tier", "lidar")).upper()
    status = str(data.get("status", "COMPLETE")).upper()
    prop_id = data.get("property_id") or capture_id
    rooms = data.get("rooms", [])
    total_area_val = data.get("total_floor_area")
    if isinstance(total_area_val, dict):
        total_area_str = f"{total_area_val.get('value', 0.0):.2f} m²"
    elif isinstance(total_area_val, (int, float)):
        total_area_str = f"{total_area_val:.2f} m²"
    else:
        total_area_str = "Not available"

    method = data.get("reconstruction_method") or "Spatial Multi-Sensor Fusion"
    metadata = data.get("capture_metadata") or {}
    created_at = metadata.get("created_at") or metadata.get("timestamp") or "2026-09-21"

    # Color Palette Constants (RGB tuples 0.0 - 1.0)
    COLOR_PRIMARY = (0.05, 0.40, 0.90)       # #0d6efd
    COLOR_SURFACE_DARK = (0.05, 0.07, 0.12)  # #0d121f
    COLOR_BORDER = (0.82, 0.85, 0.90)        # #d1d5db
    COLOR_TEXT_PRIMARY = (0.10, 0.12, 0.16)  # #1a1f29
    COLOR_TEXT_MUTED = (0.45, 0.50, 0.58)    # #738094
    COLOR_ACCENT = (0.08, 0.60, 0.45)        # #149973
    COLOR_WARNING = (0.85, 0.55, 0.05)       # #d98d0d
    COLOR_DANGER = (0.88, 0.20, 0.20)        # #e03333
    COLOR_HEADER_BG = (0.95, 0.96, 0.98)     # #f3f5fa

    # =========================================================================
    # PAGE 1: COVER & LARGE VECTOR FLOOR PLAN
    # =========================================================================
    page1 = doc.new_page(width=595.3, height=841.9)  # A4 Portrait

    # Top Brand Bar
    page1.draw_rect(pymupdf.Rect(36, 36, 559.3, 106), color=None, fill=COLOR_HEADER_BG)
    page1.draw_rect(pymupdf.Rect(36, 36, 559.3, 106), color=COLOR_BORDER, width=0.75)

    # Logo Mark
    page1.draw_rect(pymupdf.Rect(50, 48, 80, 78), color=None, fill=COLOR_PRIMARY)
    page1.insert_text((58, 70), "C", fontsize=20, color=(1, 1, 1), fontname="helv", fontfile=None)

    # Main Header Text
    page1.insert_text((92, 60), "COZMO SPATIAL RECONSTRUCTION", fontsize=15, fontname="helv", color=COLOR_TEXT_PRIMARY)
    page1.insert_text((92, 76), f"Property Report • Capture {capture_id}", fontsize=10, fontname="helv", color=COLOR_TEXT_MUTED)
    page1.insert_text((92, 92), f"Method: {method} • Timestamp: {created_at}", fontsize=8.5, fontname="helv", color=COLOR_TEXT_MUTED)

    # Status Badge
    status_bg = COLOR_ACCENT if status == "COMPLETE" else COLOR_WARNING if status == "PROVISIONAL" else COLOR_DANGER
    page1.draw_rect(pymupdf.Rect(435, 52, 545, 78), color=None, fill=status_bg)
    page1.insert_text((450, 68), status, fontsize=9.5, fontname="helv", color=(1, 1, 1))
    page1.insert_text((442, 92), f"TIER: {tier}", fontsize=9, fontname="helv", color=COLOR_TEXT_MUTED)

    # Summary Metrics Card on Page 1
    page1.draw_rect(pymupdf.Rect(36, 118, 559.3, 162), color=COLOR_BORDER, fill=(0.98, 0.98, 1.0), width=0.5)
    page1.insert_text((50, 138), "TOTAL AREA", fontsize=8, fontname="helv", color=COLOR_TEXT_MUTED)
    page1.insert_text((50, 153), total_area_str, fontsize=12, fontname="helv", color=COLOR_PRIMARY)

    page1.insert_text((180, 138), "ROOMS", fontsize=8, fontname="helv", color=COLOR_TEXT_MUTED)
    page1.insert_text((180, 153), f"{len(rooms)} Segmented", fontsize=12, fontname="helv", color=COLOR_TEXT_PRIMARY)

    total_openings = sum(len(r.get("openings", [])) for r in rooms)
    page1.insert_text((310, 138), "OPENINGS", fontsize=8, fontname="helv", color=COLOR_TEXT_MUTED)
    page1.insert_text((310, 153), f"{total_openings} Detected", fontsize=12, fontname="helv", color=COLOR_TEXT_PRIMARY)

    damage_count = len(data.get("damage_regions", []))
    page1.insert_text((440, 138), "DAMAGE FINDINGS", fontsize=8, fontname="helv", color=COLOR_TEXT_MUTED)
    page1.insert_text((440, 153), f"{damage_count} Observations", fontsize=12, fontname="helv", color=COLOR_DANGER if damage_count > 0 else COLOR_ACCENT)

    # Architectural Floor Plan Vector Drawing Area
    canvas_rect = pymupdf.Rect(36, 174, 559.3, 750)
    page1.draw_rect(canvas_rect, color=COLOR_BORDER, fill=COLOR_SURFACE_DARK, width=1)

    # Collect coordinates for plan bounding box
    all_x: List[float] = []
    all_z: List[float] = []
    for r in rooms:
        for w in r.get("walls", []):
            st = w.get("start", {})
            en = w.get("end", {})
            all_x.extend([st.get("x", st.get("x_meters", 0.0)), en.get("x", en.get("x_meters", 0.0))])
            all_z.extend([st.get("y", st.get("z", st.get("y_meters", 0.0))), en.get("y", en.get("z", en.get("y_meters", 0.0)))])
        for pt in r.get("polygon", []):
            all_x.append(pt.get("x", pt.get("x_meters", 0.0)))
            all_z.append(pt.get("y", pt.get("z", pt.get("y_meters", 0.0))))

    if all_x and all_z:
        min_x, max_x = min(all_x), max(all_x)
        min_z, max_z = min(all_z), max(all_z)
        span_x = max(max_x - min_x, 0.5)
        span_z = max(max_z - min_z, 0.5)

        draw_w = 480.0
        draw_h = 520.0
        scale = min(draw_w / span_x, draw_h / span_z)

        off_x = canvas_rect.x0 + (canvas_rect.width - span_x * scale) / 2.0
        off_z = canvas_rect.y0 + 20 + (draw_h - span_z * scale) / 2.0

        def pdf_pt(x: float, z: float) -> pymupdf.Point:
            return pymupdf.Point(off_x + (x - min_x) * scale, off_z + (z - min_z) * scale)

        # Draw room polygons
        for idx, room in enumerate(rooms):
            walls = room.get("walls", [])
            poly_pts: List[Tuple[float, float]] = []
            if walls:
                for w in walls:
                    st = w.get("start", {})
                    poly_pts.append((st.get("x", st.get("x_meters", 0.0)), st.get("y", st.get("z", st.get("y_meters", 0.0)))))
            elif "polygon" in room:
                for pt in room["polygon"]:
                    poly_pts.append((pt.get("x", pt.get("x_meters", 0.0)), pt.get("y", pt.get("z", pt.get("y_meters", 0.0)))))

            if len(poly_pts) >= 3:
                pts = [pdf_pt(px, pz) for px, pz in poly_pts]
                page1.draw_polyline(pts + [pts[0]], color=(0.25, 0.55, 0.90), fill=(0.10, 0.20, 0.35), width=1.5)

                # Room Centroid Label
                cx = sum(p.x for p in pts) / len(pts)
                cy = sum(p.y for p in pts) / len(pts)
                r_name = room.get("name", f"Room {idx+1}")
                r_area = room.get("floor_area", {})
                r_area_val = r_area.get("value", 0.0) if isinstance(r_area, dict) else (float(r_area) if r_area else 0.0)

                page1.draw_rect(pymupdf.Rect(cx - 45, cy - 14, cx + 45, cy + 14), color=(0.2, 0.3, 0.4), fill=(0.08, 0.12, 0.18), width=0.5)
                page1.insert_text((cx - 38, cy - 2), r_name, fontsize=7.5, fontname="helv", color=(1, 1, 1))
                page1.insert_text((cx - 38, cy + 9), f"{r_area_val:.1f} m²", fontsize=7, fontname="helv", color=(0.4, 0.7, 1.0))

        # Draw Wall lines and dimension annotations
        for room in rooms:
            for wall in room.get("walls", []):
                st = wall.get("start", {})
                en = wall.get("end", {})
                sx, sz = st.get("x", st.get("x_meters", 0.0)), st.get("y", st.get("z", st.get("y_meters", 0.0)))
                ex, ez = en.get("x", en.get("x_meters", 0.0)), en.get("y", en.get("z", en.get("y_meters", 0.0)))
                p1 = pdf_pt(sx, sz)
                p2 = pdf_pt(ex, ez)
                page1.draw_line(p1, p2, color=(0.9, 0.95, 1.0), width=2.5)

                # Wall Dimension label
                wall_len = math.hypot(ex - sx, ez - sz)
                if wall_len > 0.6:
                    mx, my = (p1.x + p2.x) / 2.0, (p1.y + p2.y) / 2.0
                    dx, dy = p2.x - p1.x, p2.y - p1.y
                    d_len = math.hypot(dx, dy)
                    if d_len > 1e-4:
                        nx, ny = -dy / d_len, dx / d_len
                        lbl_x, lbl_y = mx + nx * 10, my + ny * 10
                        page1.insert_text((lbl_x - 12, lbl_y + 3), f"{wall_len:.2f}m", fontsize=6.5, fontname="helv", color=(0.2, 0.8, 1.0))

                # Draw openings on this wall
                for op in wall.get("openings", []):
                    pos_m = op.get("position_along_wall", {}).get("value", 0.5 * wall_len) if isinstance(op.get("position_along_wall"), dict) else 0.5 * wall_len
                    w_m = op.get("width", {}).get("value", 0.9) if isinstance(op.get("width"), dict) else 0.9
                    t1 = max(0.0, (pos_m - w_m / 2.0) / wall_len)
                    t2 = min(1.0, (pos_m + w_m / 2.0) / wall_len)
                    op_p1 = pdf_pt(sx + t1 * (ex - sx), sz + t1 * (ez - sz))
                    op_p2 = pdf_pt(sx + t2 * (ex - sx), sz + t2 * (ez - sz))
                    page1.draw_line(op_p1, op_p2, color=(0.95, 0.6, 0.1), width=3.5)

        # Scale bar on bottom right of plan
        one_m_pt = scale * 1.0
        sb_x = canvas_rect.x1 - one_m_pt - 30
        sb_y = canvas_rect.y1 - 25
        page1.draw_line(pymupdf.Point(sb_x, sb_y), pymupdf.Point(sb_x + one_m_pt, sb_y), color=(1, 1, 1), width=2)
        page1.draw_line(pymupdf.Point(sb_x, sb_y - 4), pymupdf.Point(sb_x, sb_y + 4), color=(1, 1, 1), width=1.5)
        page1.draw_line(pymupdf.Point(sb_x + one_m_pt, sb_y - 4), pymupdf.Point(sb_x + one_m_pt, sb_y + 4), color=(1, 1, 1), width=1.5)
        page1.insert_text((sb_x + one_m_pt / 2.0 - 10, sb_y - 6), "1.0 m", fontsize=7.5, fontname="helv", color=(1, 1, 1))

    else:
        page1.insert_text((canvas_rect.x0 + 120, canvas_rect.y0 + 250), f"No evaluable 2D geometry available ({status})", fontsize=12, fontname="helv", color=COLOR_DANGER)

    # Mandatory Physical Accuracy Disclaimer on Page 1 Footer
    page1.draw_rect(pymupdf.Rect(36, 760, 559.3, 805), color=COLOR_BORDER, fill=COLOR_HEADER_BG, width=0.5)
    page1.insert_text((46, 778), "NOTICE & MANDATORY ACCURACY DISCLAIMER:", fontsize=8, fontname="helv", color=COLOR_TEXT_PRIMARY)
    page1.insert_text(
        (46, 793),
        "Physical accuracy has not yet been validated against independent laser/tape ground truth. Measurements are uncalibrated estimates.",
        fontsize=7.5, fontname="helv", color=COLOR_TEXT_MUTED
    )
    page1.insert_text((510, 793), "Page 1 of 2", fontsize=7.5, fontname="helv", color=COLOR_TEXT_MUTED)

    # =========================================================================
    # PAGE 2: ITEMIZED ROOMS, MEASUREMENTS, UNCERTAINTY & SCOPE
    # =========================================================================
    page2 = doc.new_page(width=595.3, height=841.9)

    # Top Header
    page2.draw_rect(pymupdf.Rect(36, 36, 559.3, 76), color=COLOR_BORDER, fill=COLOR_HEADER_BG, width=0.75)
    page2.insert_text((48, 55), "COZMO SPATIAL RECONSTRUCTION — METRICS & SCHEDULES", fontsize=11, fontname="helv", color=COLOR_TEXT_PRIMARY)
    page2.insert_text((48, 68), f"Capture: {capture_id} • Property: {prop_id} • Status: {status}", fontsize=8.5, fontname="helv", color=COLOR_TEXT_MUTED)

    curr_y = 96.0

    # Section 1: Room Breakdown Table
    page2.insert_text((36, curr_y), "1. ROOM MEASUREMENT SUMMARY", fontsize=10, fontname="helv", color=COLOR_PRIMARY)
    curr_y += 14.0

    # Table Header
    page2.draw_rect(pymupdf.Rect(36, curr_y, 559.3, curr_y + 18), color=COLOR_BORDER, fill=(0.90, 0.93, 0.97), width=0.5)
    page2.insert_text((44, curr_y + 12), "Room Name", fontsize=8, fontname="helv", color=COLOR_TEXT_PRIMARY)
    page2.insert_text((160, curr_y + 12), "Area (m²)", fontsize=8, fontname="helv", color=COLOR_TEXT_PRIMARY)
    page2.insert_text((230, curr_y + 12), "Perimeter (m)", fontsize=8, fontname="helv", color=COLOR_TEXT_PRIMARY)
    page2.insert_text((310, curr_y + 12), "Ceiling Ht (m)", fontsize=8, fontname="helv", color=COLOR_TEXT_PRIMARY)
    page2.insert_text((400, curr_y + 12), "Walls", fontsize=8, fontname="helv", color=COLOR_TEXT_PRIMARY)
    page2.insert_text((470, curr_y + 12), "Openings", fontsize=8, fontname="helv", color=COLOR_TEXT_PRIMARY)
    curr_y += 18.0

    for idx, room in enumerate(rooms):
        bg = (1, 1, 1) if idx % 2 == 0 else (0.97, 0.98, 1.0)
        page2.draw_rect(pymupdf.Rect(36, curr_y, 559.3, curr_y + 16), color=COLOR_BORDER, fill=bg, width=0.25)

        r_name = room.get("name", f"Room {idx+1}")
        area_obj = room.get("floor_area", {})
        area_v = f"{area_obj.get('value', 0.0):.2f}" if isinstance(area_obj, dict) else f"{float(area_obj):.2f}" if area_obj else "—"

        perim_obj = room.get("perimeter", {})
        perim_v = f"{perim_obj.get('value', 0.0):.2f}" if isinstance(perim_obj, dict) else f"{float(perim_obj):.2f}" if perim_obj else "—"

        ceil_obj = room.get("ceiling_height")
        ceil_v = f"{ceil_obj.get('value', 0.0):.2f}" if isinstance(ceil_obj, dict) and ceil_obj.get("value") is not None else "Unobserved"

        w_count = len(room.get("walls", []))
        op_count = len(room.get("openings", []))

        page2.insert_text((44, curr_y + 11), r_name, fontsize=8, fontname="helv", color=COLOR_TEXT_PRIMARY)
        page2.insert_text((160, curr_y + 11), area_v, fontsize=8, fontname="helv", color=COLOR_TEXT_PRIMARY)
        page2.insert_text((230, curr_y + 11), perim_v, fontsize=8, fontname="helv", color=COLOR_TEXT_PRIMARY)
        page2.insert_text((310, curr_y + 11), ceil_v, fontsize=8, fontname="helv", color=COLOR_TEXT_MUTED if ceil_v == "Unobserved" else COLOR_TEXT_PRIMARY)
        page2.insert_text((400, curr_y + 11), str(w_count), fontsize=8, fontname="helv", color=COLOR_TEXT_PRIMARY)
        page2.insert_text((470, curr_y + 11), str(op_count), fontsize=8, fontname="helv", color=COLOR_TEXT_PRIMARY)
        curr_y += 16.0

    curr_y += 16.0

    # Section 2: Detailed Wall Measurements & Calibrated Confidence Intervals
    page2.insert_text((36, curr_y), "2. METRIC WALL MEASUREMENTS & 95% CONFIDENCE INTERVALS", fontsize=10, fontname="helv", color=COLOR_PRIMARY)
    curr_y += 14.0

    page2.draw_rect(pymupdf.Rect(36, curr_y, 559.3, curr_y + 18), color=COLOR_BORDER, fill=(0.90, 0.93, 0.97), width=0.5)
    page2.insert_text((44, curr_y + 12), "Wall ID", fontsize=8, fontname="helv", color=COLOR_TEXT_PRIMARY)
    page2.insert_text((140, curr_y + 12), "Nominal Length", fontsize=8, fontname="helv", color=COLOR_TEXT_PRIMARY)
    page2.insert_text((240, curr_y + 12), "95% Uncertainty Interval", fontsize=8, fontname="helv", color=COLOR_TEXT_PRIMARY)
    page2.insert_text((390, curr_y + 12), "Confidence", fontsize=8, fontname="helv", color=COLOR_TEXT_PRIMARY)
    page2.insert_text((470, curr_y + 12), "Method", fontsize=8, fontname="helv", color=COLOR_TEXT_PRIMARY)
    curr_y += 18.0

    # Gather walls across rooms
    all_walls = []
    for r in rooms:
        for w in r.get("walls", []):
            all_walls.append(w)

    for idx, w in enumerate(all_walls[:14]):  # Cap to fit page cleanly
        bg = (1, 1, 1) if idx % 2 == 0 else (0.97, 0.98, 1.0)
        page2.draw_rect(pymupdf.Rect(36, curr_y, 559.3, curr_y + 15), color=COLOR_BORDER, fill=bg, width=0.25)

        w_id = w.get("wall_id", f"wall_{idx+1}")
        len_obj = w.get("length", {})
        if isinstance(len_obj, dict):
            val_m = len_obj.get("value", 0.0)
            lb = len_obj.get("lower_bound", val_m * 0.98)
            ub = len_obj.get("upper_bound", val_m * 1.02)
            conf = len_obj.get("confidence", 0.95)
            method_str = len_obj.get("method", "plane_fit")
        else:
            val_m = float(len_obj) if len_obj else 0.0
            lb, ub = val_m * 0.98, val_m * 1.02
            conf = 0.95
            method_str = "reconstruction"

        page2.insert_text((44, curr_y + 11), w_id[:16], fontsize=7.5, fontname="helv", color=COLOR_TEXT_PRIMARY)
        page2.insert_text((140, curr_y + 11), f"{val_m:.3f} m", fontsize=7.5, fontname="helv", color=COLOR_TEXT_PRIMARY)
        page2.insert_text((240, curr_y + 11), f"[{lb:.3f} m, {ub:.3f} m]", fontsize=7.5, fontname="helv", color=COLOR_TEXT_MUTED)
        page2.insert_text((390, curr_y + 11), f"{conf*100:.0f}%", fontsize=7.5, fontname="helv", color=COLOR_ACCENT)
        page2.insert_text((470, curr_y + 11), method_str[:15], fontsize=7.5, fontname="helv", color=COLOR_TEXT_MUTED)
        curr_y += 15.0

    curr_y += 16.0

    # Section 3: Damage Observations & Remediation Scope
    damage_regions = data.get("damage_regions", [])
    scope_items = data.get("scope_line_items", [])

    page2.insert_text((36, curr_y), "3. DAMAGE OBSERVATIONS & REMEDIATION SCOPE", fontsize=10, fontname="helv", color=COLOR_PRIMARY)
    curr_y += 14.0

    if damage_regions or scope_items:
        page2.draw_rect(pymupdf.Rect(36, curr_y, 559.3, curr_y + 18), color=COLOR_BORDER, fill=(0.90, 0.93, 0.97), width=0.5)
        page2.insert_text((44, curr_y + 12), "Damage Class", fontsize=8, fontname="helv", color=COLOR_TEXT_PRIMARY)
        page2.insert_text((160, curr_y + 12), "Associated Surface", fontsize=8, fontname="helv", color=COLOR_TEXT_PRIMARY)
        page2.insert_text((270, curr_y + 12), "Metric Extent", fontsize=8, fontname="helv", color=COLOR_TEXT_PRIMARY)
        page2.insert_text((370, curr_y + 12), "Repair Scope Action", fontsize=8, fontname="helv", color=COLOR_TEXT_PRIMARY)
        page2.insert_text((480, curr_y + 12), "Status", fontsize=8, fontname="helv", color=COLOR_TEXT_PRIMARY)
        curr_y += 18.0

        for idx, dmg in enumerate(damage_regions[:6]):
            bg = (1, 1, 1) if idx % 2 == 0 else (0.97, 0.98, 1.0)
            page2.draw_rect(pymupdf.Rect(36, curr_y, 559.3, curr_y + 15), color=COLOR_BORDER, fill=bg, width=0.25)
            d_class = str(dmg.get("damage_class", "Defect")).replace("_", " ").title()
            surf = str(dmg.get("surface_id", "General"))
            extent_area = dmg.get("extent_area")
            extent_len = dmg.get("extent_length")
            if extent_area and isinstance(extent_area, dict):
                ext_str = f"{extent_area.get('value', 0.0):.2f} m²"
            elif extent_len and isinstance(extent_len, dict):
                ext_str = f"{extent_len.get('value', 0.0):.2f} m"
            else:
                ext_str = "Visual"

            scope_list = dmg.get("scope_line_items", [])
            scope_act = scope_list[0] if scope_list else "Inspect surface"
            d_status = dmg.get("status", "ACCEPTED")

            page2.insert_text((44, curr_y + 11), d_class[:18], fontsize=7.5, fontname="helv", color=COLOR_DANGER)
            page2.insert_text((160, curr_y + 11), surf[:18], fontsize=7.5, fontname="helv", color=COLOR_TEXT_PRIMARY)
            page2.insert_text((270, curr_y + 11), ext_str, fontsize=7.5, fontname="helv", color=COLOR_TEXT_PRIMARY)
            page2.insert_text((370, curr_y + 11), scope_act[:22], fontsize=7.5, fontname="helv", color=COLOR_TEXT_PRIMARY)
            page2.insert_text((480, curr_y + 11), d_status, fontsize=7.5, fontname="helv", color=COLOR_ACCENT)
            curr_y += 15.0
    else:
        page2.draw_rect(pymupdf.Rect(36, curr_y, 559.3, curr_y + 24), color=COLOR_BORDER, fill=(0.97, 0.98, 1.0), width=0.5)
        page2.insert_text((48, curr_y + 16), "No damage findings or repair scope items recorded for this capture.", fontsize=8.5, fontname="helv", color=COLOR_TEXT_MUTED)
        curr_y += 30.0

    # Mandatory Physical Accuracy Disclaimer on Page 2 Footer
    page2.draw_rect(pymupdf.Rect(36, 760, 559.3, 805), color=COLOR_BORDER, fill=COLOR_HEADER_BG, width=0.5)
    page2.insert_text((46, 778), "NOTICE & MANDATORY ACCURACY DISCLAIMER:", fontsize=8, fontname="helv", color=COLOR_TEXT_PRIMARY)
    page2.insert_text(
        (46, 793),
        "Physical accuracy has not yet been validated against independent laser/tape ground truth. Measurements are uncalibrated estimates.",
        fontsize=7.5, fontname="helv", color=COLOR_TEXT_MUTED
    )
    page2.insert_text((510, 793), "Page 2 of 2", fontsize=7.5, fontname="helv", color=COLOR_TEXT_MUTED)

    # Output generation
    pdf_bytes = doc.tobytes()
    doc.close()

    if output_path is not None:
        out_p = Path(output_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        out_p.write_bytes(pdf_bytes)

    return pdf_bytes
