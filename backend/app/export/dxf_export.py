"""CAD-compatible 2D DXF floor plan exporter in standard metric units.

Purpose:
    Generates standard AutoCAD R12/2000 compatible ASCII DXF files representing
    reconstructed floor plans with structured layers: WALLS, OPENINGS, ROOMS,
    DAMAGE, and TEXT.

Stage:
    Frontend Stage 4 — Exports + Final Product Polish.

Inputs:
    - property_data: Dict or PropertyPlanOutput object.
    - capture_id: Unique capture identifier string.
    - output_path: Optional destination Path for writing the DXF file.

Outputs:
    - ASCII DXF text string and optional written .dxf file.

Dependencies:
    math, pathlib, typing, pydantic (if PropertyPlanOutput model passed).

Assumptions:
    - Output coordinates are pure metric meters (m).
    - DXF header explicitly specifies metric units ($INSUNITS = 6 for meters, $MEASUREMENT = 1).
    - Can be imported directly into AutoCAD, LibreCAD, Revit, Rhino, and SketchUp.

Coordinate / Unit Conventions:
    - 2D Metric ground plane (X, Y in DXF corresponds to world X, Z in meters).

Failure Modes:
    - Empty room geometry outputs a valid DXF document with header/layers and notice text.
    - Write permission error raises IOError.

First Debugging Points:
    - Open generated .dxf in CAD software (e.g. LibreCAD) or parse section structure.
    - Verify layer table contains WALLS, OPENINGS, ROOMS, DAMAGE, TEXT.
    - Confirm coordinates match metric meters rather than screen pixels.
"""

import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
from pydantic import BaseModel


def export_property_dxf(
    property_data: Union[Dict[str, Any], BaseModel],
    capture_id: str,
    output_path: Optional[Path] = None,
) -> str:
    """Generates a standard CAD-compatible 2D DXF floor plan in metric meters.

    Purpose:
        Produces a clean AutoCAD DXF file containing distinct layers for walls,
        room perimeters, openings, damage annotations, and metric dimension text.

    Parameters:
        property_data: Reconstruction result dictionary or BaseModel.
        capture_id: Unique capture identifier.
        output_path: Optional file path to write DXF output.

    Returns:
        ASCII DXF file contents as a string.

    Units / Coordinates:
        X and Y coordinates are in METERS (m).

    Assumptions:
        World coordinates are in standard metric ground coordinates.

    Failure Conditions:
        Raises IOError on disk write error.

    Debugging Clues:
        Check HEADER variable $INSUNITS (value 6 = meters).
        Check ENTITIES section for LINE, LWPOLYLINE, and TEXT tags.
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

    dxf_lines: List[str] = []

    def line(code: int, val: Any) -> None:
        dxf_lines.append(f"{code:3d}")
        dxf_lines.append(str(val))

    # 1. HEADER SECTION
    line(0, "SECTION")
    line(2, "HEADER")

    # Metric measurement system (1 = metric)
    line(9, "$MEASUREMENT")
    line(70, 1)

    # Drawing units (6 = Meters)
    line(9, "$INSUNITS")
    line(70, 6)

    # Drawing title
    line(9, "$PROJECTNAME")
    line(1, f"COZMO_{capture_id}")

    line(0, "ENDSEC")

    # 2. TABLES SECTION (Linetypes, Layers, Styles)
    line(0, "SECTION")
    line(2, "TABLES")

    # Linetype Table
    line(0, "TABLE")
    line(2, "LTYPE")
    line(70, 2)

    line(0, "LTYPE")
    line(2, "CONTINUOUS")
    line(70, 0)
    line(3, "Solid line")
    line(72, 65)
    line(73, 0)
    line(40, 0.0)

    line(0, "LTYPE")
    line(2, "DASHED")
    line(70, 0)
    line(3, "Dashed line __ __ __")
    line(72, 65)
    line(73, 2)
    line(40, 0.5)
    line(49, 0.3)
    line(49, -0.2)

    line(0, "ENDTAB")

    # Layer Table
    # Layers: WALLS (white/7), OPENINGS (cyan/4), ROOMS (green/3), DAMAGE (red/1), TEXT (yellow/2)
    layers = [
        ("0", 7, "CONTINUOUS"),
        ("WALLS", 7, "CONTINUOUS"),
        ("OPENINGS", 4, "CONTINUOUS"),
        ("ROOMS", 3, "CONTINUOUS"),
        ("DAMAGE", 1, "DASHED"),
        ("TEXT", 2, "CONTINUOUS"),
    ]

    line(0, "TABLE")
    line(2, "LAYER")
    line(70, len(layers))

    for lname, lcolor, ltype in layers:
        line(0, "LAYER")
        line(2, lname)
        line(70, 0)
        line(62, lcolor)
        line(6, ltype)

    line(0, "ENDTAB")

    # Style Table
    line(0, "TABLE")
    line(2, "STYLE")
    line(70, 1)
    line(0, "STYLE")
    line(2, "STANDARD")
    line(70, 0)
    line(40, 0.0)
    line(41, 1.0)
    line(50, 0.0)
    line(71, 0)
    line(42, 0.2)
    line(3, "txt")
    line(4, "")
    line(0, "ENDTAB")

    line(0, "ENDSEC")

    # 3. BLOCKS SECTION (Empty for standard 2D drawings)
    line(0, "SECTION")
    line(2, "BLOCKS")
    line(0, "ENDSEC")

    # 4. ENTITIES SECTION (Actual geometric entities in meters)
    line(0, "SECTION")
    line(2, "ENTITIES")

    if not rooms:
        # Informative text entity if no geometry
        line(0, "TEXT")
        line(8, "TEXT")
        line(10, 0.0)
        line(20, 0.0)
        line(30, 0.0)
        line(40, 0.3)  # 30 cm text height
        line(1, f"COZMO - No geometry available ({status})")
    else:
        # A. Room Boundary Polylines & Centroid Labels
        for idx, room in enumerate(rooms):
            r_name = room.get("name", f"Room {idx+1}")
            area_obj = room.get("floor_area", {})
            area_m2 = area_obj.get("value", 0.0) if isinstance(area_obj, dict) else (float(area_obj) if area_obj else 0.0)

            poly_pts: List[Tuple[float, float]] = []
            walls = room.get("walls", [])
            if walls:
                for w in walls:
                    st = w.get("start", {})
                    poly_pts.append((st.get("x", st.get("x_meters", 0.0)), st.get("y", st.get("z", st.get("y_meters", 0.0)))))
            elif "polygon" in room:
                for pt in room["polygon"]:
                    poly_pts.append((pt.get("x", pt.get("x_meters", 0.0)), pt.get("y", pt.get("z", pt.get("y_meters", 0.0)))))

            if len(poly_pts) >= 3:
                # Closed LWPOLYLINE on layer ROOMS
                line(0, "LWPOLYLINE")
                line(8, "ROOMS")
                line(90, len(poly_pts))
                line(70, 1)  # 1 = Closed polyline
                line(43, 0.0)  # Constant width
                for px, py in poly_pts:
                    line(10, f"{px:.4f}")
                    line(20, f"{py:.4f}")

                # Room Centroid Text
                cx = sum(p[0] for p in poly_pts) / len(poly_pts)
                cy = sum(p[1] for p in poly_pts) / len(poly_pts)

                # Room Name Text
                line(0, "TEXT")
                line(8, "TEXT")
                line(10, f"{cx:.4f}")
                line(20, f"{cy + 0.15:.4f}")
                line(30, 0.0)
                line(40, 0.20)  # 20cm height
                line(1, r_name)

                # Room Area Text
                line(0, "TEXT")
                line(8, "TEXT")
                line(10, f"{cx:.4f}")
                line(20, f"{cy - 0.15:.4f}")
                line(30, 0.0)
                line(40, 0.15)  # 15cm height
                line(1, f"{area_m2:.2f} m2")

            # B. Walls (LINE entities on layer WALLS)
            for wall in walls:
                st = wall.get("start", {})
                en = wall.get("end", {})
                sx, sz = st.get("x", st.get("x_meters", 0.0)), st.get("y", st.get("z", st.get("y_meters", 0.0)))
                ex, ez = en.get("x", en.get("x_meters", 0.0)), en.get("y", en.get("z", en.get("y_meters", 0.0)))

                line(0, "LINE")
                line(8, "WALLS")
                line(10, f"{sx:.4f}")
                line(20, f"{sz:.4f}")
                line(30, 0.0)
                line(11, f"{ex:.4f}")
                line(21, f"{ez:.4f}")
                line(31, 0.0)

                # Wall Dimension Text
                wall_len = math.hypot(ex - sx, ez - sz)
                if wall_len > 0.5:
                    mx = (sx + ex) / 2.0
                    my = (sz + ez) / 2.0
                    dx, dy = ex - sx, ez - sz
                    dist = math.hypot(dx, dy)
                    if dist > 1e-4:
                        nx, ny = -dy / dist, dx / dist
                        tx = mx + nx * 0.15
                        ty = my + ny * 0.15
                        rot_deg = math.degrees(math.atan2(dy, dx))
                        if rot_deg > 90:
                            rot_deg -= 180
                        elif rot_deg < -90:
                            rot_deg += 180

                        line(0, "TEXT")
                        line(8, "TEXT")
                        line(10, f"{tx:.4f}")
                        line(20, f"{ty:.4f}")
                        line(30, 0.0)
                        line(40, 0.12)  # 12cm height
                        line(50, f"{rot_deg:.2f}")
                        line(1, f"{wall_len:.2f}m")

                # C. Openings (LINE entities on layer OPENINGS)
                for op in wall.get("openings", []):
                    pos_m = op.get("position_along_wall", {}).get("value", 0.5 * wall_len) if isinstance(op.get("position_along_wall"), dict) else 0.5 * wall_len
                    w_m = op.get("width", {}).get("value", 0.9) if isinstance(op.get("width"), dict) else 0.9
                    t1 = max(0.0, (pos_m - w_m / 2.0) / wall_len)
                    t2 = min(1.0, (pos_m + w_m / 2.0) / wall_len)

                    op_sx = sx + t1 * (ex - sx)
                    op_sz = sz + t1 * (ez - sz)
                    op_ex = sx + t2 * (ex - sx)
                    op_ez = sz + t2 * (ez - sz)

                    line(0, "LINE")
                    line(8, "OPENINGS")
                    line(10, f"{op_sx:.4f}")
                    line(20, f"{op_sz:.4f}")
                    line(30, 0.0)
                    line(11, f"{op_ex:.4f}")
                    line(21, f"{op_ez:.4f}")
                    line(31, 0.0)

        # D. Damage Regions (LWPOLYLINE on layer DAMAGE)
        for dmg in data.get("damage_regions", []):
            dmg_poly = dmg.get("polygon_on_surface")
            if dmg_poly and len(dmg_poly) >= 3:
                line(0, "LWPOLYLINE")
                line(8, "DAMAGE")
                line(90, len(dmg_poly))
                line(70, 1)  # Closed
                line(43, 0.0)
                for pt in dmg_poly:
                    px = pt.get("x", 0.0)
                    py = pt.get("y", pt.get("z", 0.0))
                    line(10, f"{px:.4f}")
                    line(20, f"{py:.4f}")

    line(0, "ENDSEC")

    # 5. EOF
    line(0, "EOF")

    dxf_content = "\n".join(dxf_lines) + "\n"

    if output_path is not None:
        out_p = Path(output_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        out_p.write_text(dxf_content, encoding="utf-8")

    return dxf_content
