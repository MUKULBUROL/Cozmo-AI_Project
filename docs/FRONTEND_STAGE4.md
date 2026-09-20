# Frontend Stage 4 — Multi-Format Deliverable Exports & Product Polish

**Stage:** Frontend Stage 4 (Exports + Final Product Polish + Submission UX)  
**Status:** Complete & Verified  
**Date:** 2026-09-21  

---

## 1. Stage 4 Architecture Overview

Stage 4 transitions the Cozmo AI Spatial Intelligence platform from an interactive inspection viewer into a full, evaluator-ready property deliverable workspace. It implements real, robust multi-format export engines producing standardized deliverables directly from live backend reconstruction outputs:

```
FastAPI Reconstructed Property Artifact (runtime/captures/<id>/outputs/property.json)
                                ↓
                 Backend Export Service (backend/app/export/)
        ┌───────────────────┬───────────────────┬───────────────────┐
        ▼                   ▼                   ▼                   ▼
    JSON Export         SVG Floor Plan      PDF Report          CAD DXF
(cozmo_<id>_prop.json) (cozmo_<id>_fp.svg) (cozmo_<id>_rep.pdf) (cozmo_<id>_fp.dxf)
```

### Key Principles:
1. **Zero Fixture Substitution**: Exports strictly reflect the active dynamic capture dataset.
2. **Deterministic Metric Coordinates**: All geometry and schedules utilize real metric dimensions in meters ($m$) and square meters ($m^2$).
3. **Honest Confidence Intervals & Status Gating**: Retains nominal values and calibrated $95\%$ confidence intervals $[lower\_bound, upper\_bound]$.
4. **Mandatory Ground Truth Physical Accuracy Notice**: Every report, drawing, and UI screen explicitly states:
   > *"Physical accuracy has not yet been validated against independent laser/tape ground truth."*

---

## 2. Export Format Specifications

### 2.1 Machine-Readable JSON (`cozmo_<capture_id>_property.json`)
- **Location**: `backend/app/export/json_export.py`
- **Schema**: Validated `PropertyPlanOutput` containing `property_id`, `capture_id`, `tier`, `status`, `reconstruction_method`, `total_floor_area`, itemized `rooms`, `walls`, `openings`, `damage_regions`, `scope_line_items`, `connections`, and `capture_metadata`.
- **Integrity**: Preserves `null`, `NOT_EVALUABLE`, and `PROVISIONAL` statuses without fabricating placeholder numbers.

### 2.2 Architectural Vector SVG (`cozmo_<capture_id>_floorplan.svg`)
- **Location**: `backend/app/export/svg_export.py`
- **Format**: XML-compliant standalone 2D vector graphic opening in vector editors (Illustrator, Inkscape, Figma, CAD viewers) and web browsers without React runtime dependencies.
- **Layers & Features**:
  - Background grid and framing box
  - Room polygon fills with stroke outlines and centroid room badges (Name + Area in $m^2$)
  - Structural wall strokes with thickness
  - Doorway cutouts and opening indicators
  - Collision-free metric wall dimension labels with outward leader offsets
  - Damage defect overlays (if observed)
  - 1.0 meter visual scale bar and accuracy disclaimer

### 2.3 Multi-Page Inspection PDF Report (`cozmo_<capture_id>_report.pdf`)
- **Location**: `backend/app/export/pdf_export.py`
- **Engine**: PyMuPDF (`pymupdf` 1.28.2) A4 portrait vector rendering.
- **Page 1**:
  - Header with Cozmo branding, capture ID, tier badge, status badge, timestamp, and method.
  - Summary metric cards (Total Area, Segmented Rooms, Detected Openings, Damage Findings).
  - High-resolution dark-mode architectural floor plan vector drawing with wall dimensions, opening indicators, and scale bar.
  - Prominent mandatory physical accuracy disclaimer footer.
- **Page 2**:
  - Room Measurement Summary table (Room Name, Floor Area $m^2$, Perimeter $m$, Ceiling Height $m$, Wall counts, Opening counts).
  - Metric Wall Measurements & $95\%$ Uncertainty Intervals table (Wall ID, Nominal Length, $[lower, upper]$ interval, Confidence $\%$, Method).
  - Damage Observations & Remediation Scope table (Damage Class, Associated Surface, Metric Extent, Repair Action, Status).
  - Mandatory accuracy disclaimer footer.

### 2.4 AutoCAD 2D DXF (`cozmo_<capture_id>_floorplan.dxf`)
- **Location**: `backend/app/export/dxf_export.py`
- **Format**: Standard ASCII DXF (AutoCAD R12/2000 compatible).
- **Units**: Pure Metric Meters ($m$) explicitly marked with `$INSUNITS = 6` and `$MEASUREMENT = 1`.
- **Layers**:
  - `WALLS` (Color 7 / White): Structural wall `LINE` entities.
  - `OPENINGS` (Color 4 / Cyan): Door and window opening `LINE` entities.
  - `ROOMS` (Color 3 / Green): Closed boundary `LWPOLYLINE` entities.
  - `DAMAGE` (Color 1 / Red): Closed damage defect `LWPOLYLINE` entities.
  - `TEXT` (Color 2 / Yellow): Room name, area, and metric dimension `TEXT` entities.

---

## 3. API Export Endpoints & Security Isolation

All exports are generated into per-capture isolated storage under `runtime/captures/<id>/exports/`:

| Endpoint | Method | Deliverable | Content-Type |
| :--- | :--- | :--- | :--- |
| `/api/captures/{id}/exports/json` | GET | `cozmo_<id>_property.json` | `application/json` |
| `/api/captures/{id}/exports/svg` | GET | `cozmo_<id>_floorplan.svg` | `image/svg+xml` |
| `/api/captures/{id}/exports/pdf` | GET | `cozmo_<id>_report.pdf` | `application/pdf` |
| `/api/captures/{id}/exports/dxf` | GET | `cozmo_<id>_floorplan.dxf` | `application/dxf` |

### Security & Path Traversal Prevention:
- `_validate_capture_id()` validates incoming capture ID parameters, rejecting `..`, `/`, and `\\` with HTTP 400.
- Rejects non-existent capture IDs with HTTP 404.
- Rejects non-terminal/processing captures with HTTP 409 Conflict.
- Attachment filenames sanitized and stamped with `cozmo_<id>_<format>`.

---

## 4. Evaluator Workflow

1. Navigate to `/` (Home) and click **+ New Capture**.
2. Select sensor tier (**LiDAR**, **RGB Video**, or **Photo Set**).
3. Upload archive (`.zip` or `.mp4`).
4. Monitor live background reconstruction on `/processing/[id]` with real-time status and elapsed time.
5. On completion, automatically redirected to `/property/[id]`.
6. Inspect interactive floor plan with pan, zoom, fit, and focus room tools.
7. Inspect itemized room dimensions, confidence intervals, damage detections, and repair scope.
8. Click **Export ▾** at bottom-right and select desired deliverable (PDF Report, Vector Floor Plan, Property JSON, AutoCAD DXF).
