# Cozmo AI Project — Stage 4 Export Audit

**Stage:** Frontend Stage 4 (Exports + Final Product Polish + Submission UX)  
**Date:** 2026-09-21  

---

## 1. Executive Summary

This audit catalogs existing export capabilities, file structures, coordinate systems, and deliverable generators across the Cozmo AI codebase. It outlines the adapter architecture required to deliver real, consistent JSON, SVG, PDF, and DXF exports directly from backend reconstruction results.

---

## 2. Component Classification & Audit Matrix

| Export Target | Existing Status | Component / Location | Assessment & Plan |
| :--- | :--- | :--- | :--- |
| **JSON Export** | **PARTIAL** | `backend/app/models/output.py`<br>`backend/app/geometry/property_topology.py`<br>`backend/app/api/captures.py` | `PropertyPlanOutput` exists and is saved to `property.json`. We need a dedicated export module in `backend/app/export/json_export.py` ensuring sanitized filename (`cozmo_<capture_id>_property.json`), preserving confidence intervals, damage, and metadata without fabricating defaults. |
| **SVG Export** | **PARTIAL** | `backend/app/geometry/property_viz.py`<br>`backend/app/measurements/svg_render.py` | Diagnostic SVG renderers exist for internal pipelines. We will create a clean architectural vector floor-plan SVG exporter in `backend/app/export/svg_export.py` featuring crisp dark/light styling, room polygons, readable non-overlapping dimensions, opening cutouts/indicators, and damage overlays, independent of React runtime. |
| **PDF Report** | **NEEDS_ADAPTER** | Environment has `pymupdf` (1.28.2), `matplotlib`, `pillow` | No existing end-to-end report generator. We will build `backend/app/export/pdf_export.py` using `fitz` (PyMuPDF) to generate a multi-page report: Page 1 with summary metadata, status badge, and large vector floor plan; Page 2+ with room areas, ceiling heights, wall dimensions, openings, damage findings, scope line items, and the mandatory physical accuracy disclaimer. |
| **DXF Export** | **MISSING** | `backend/app/export/` | No DXF generator existed. We will implement `backend/app/export/dxf_export.py` generating standard AutoCAD R12/2000 ASCII DXF format in real metric meters ($m$) with structured layers: `WALLS`, `OPENINGS`, `ROOMS`, `DAMAGE`, and `TEXT`. Zero heavyweight dependencies required. |

---

## 3. Coordinate System & Measurement Conventions

- **Floor Plan Coordinate Space**: Global horizontal metric ground plane $(X, Z)$ in meters ($m$). $Y$ is vertical height ($m$).
- **Area Units**: Square meters ($m^2$).
- **Confidence Intervals**: Preserved as honest $[lower\_bound, upper\_bound]$ at specified confidence level (e.g., $95\%$).
- **Status Gating**: Complete adherence to `COMPLETE`, `PROVISIONAL`, `NOT_EVALUABLE`, and `FAILED` states. Missing values are preserved as `null` / `None`, never converted into fictitious defaults.
- **Physical Accuracy Disclaimer**: Mandatorily included in PDF reports, UI headers, and metadata exports:
  > *"Physical accuracy has not yet been validated against independent laser/tape ground truth."*

---

## 4. API & Storage Architecture

1. **Storage Isolation**: Exports generated per capture are stored under:
   `runtime/captures/<capture_id>/exports/`
2. **Endpoints**:
   - `GET /api/captures/{id}/exports/json`
   - `GET /api/captures/{id}/exports/svg`
   - `GET /api/captures/{id}/exports/pdf`
   - `GET /api/captures/{id}/exports/dxf`
3. **Security**: Capture IDs are strictly validated to prevent directory traversal (`../`). Files are streamed with appropriate `Content-Disposition: attachment; filename="cozmo_<capture_id>_..."`.
