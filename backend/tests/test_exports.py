"""Unit and integration tests for Stage 4 property export capabilities and API routes.

Purpose:
    Validates machine-readable JSON, architectural SVG, multi-page PDF report,
    and CAD DXF exporters, ensuring cross-format metric consistency, capture isolation,
    and API route compliance.

Stage:
    Frontend Stage 4 — Exports + Final Product Polish.

Dependencies:
    pytest, json, xml.etree.ElementTree, pymupdf, fastapi.testclient.
"""

import json
import xml.etree.ElementTree as ET
from pathlib import Path
import pytest
import pymupdf
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.models.capture import CaptureTier
from backend.app.api.jobs import CaptureStatus
from backend.app.api.captures import job_store
from backend.app.export import (
    export_property_json,
    export_property_svg,
    export_property_pdf,
    export_property_dxf,
    export_all_formats,
)


@pytest.fixture
def sample_property_data():
    """Generates a realistic multi-room property reconstruction payload."""
    return {
        "property_id": "test_prop_001",
        "capture_id": "cap_test_001",
        "tier": "lidar",
        "status": "COMPLETE",
        "reconstruction_method": "LiDAR Multi-Plane Fusion",
        "total_floor_area": {
            "value": 48.50,
            "unit": "m2",
            "lower_bound": 47.90,
            "upper_bound": 49.10,
            "confidence": 0.95,
            "method": "lidar_polygon_integral",
        },
        "rooms": [
            {
                "room_id": "room_living",
                "name": "Living Room",
                "floor_area": {
                    "value": 28.50,
                    "unit": "m2",
                    "lower_bound": 28.10,
                    "upper_bound": 28.90,
                    "confidence": 0.95,
                    "method": "polygon",
                },
                "perimeter": {
                    "value": 21.60,
                    "unit": "m",
                    "lower_bound": 21.40,
                    "upper_bound": 21.80,
                    "confidence": 0.95,
                    "method": "boundary",
                },
                "ceiling_height": {
                    "value": 2.75,
                    "unit": "m",
                    "lower_bound": 2.70,
                    "upper_bound": 2.80,
                    "confidence": 0.95,
                    "method": "plane_delta",
                },
                "walls": [
                    {
                        "wall_id": "wall_lv_1",
                        "start": {"x": 0.0, "y": 0.0},
                        "end": {"x": 6.0, "y": 0.0},
                        "length": {"value": 6.000, "unit": "m", "lower_bound": 5.98, "upper_bound": 6.02, "confidence": 0.95, "method": "plane_fit"},
                        "thickness": {"value": 0.15, "unit": "m", "lower_bound": 0.14, "upper_bound": 0.16, "confidence": 0.95, "method": "ransac"},
                        "openings": [
                            {
                                "opening_id": "op_win_1",
                                "wall_id": "wall_lv_1",
                                "opening_type": "window",
                                "width": {"value": 1.50, "unit": "m", "lower_bound": 1.48, "upper_bound": 1.52, "confidence": 0.95, "method": "bbox"},
                                "position_along_wall": {"value": 3.00, "unit": "m", "lower_bound": 2.95, "upper_bound": 3.05, "confidence": 0.95, "method": "center"},
                            }
                        ],
                    },
                    {
                        "wall_id": "wall_lv_2",
                        "start": {"x": 6.0, "y": 0.0},
                        "end": {"x": 6.0, "y": 4.75},
                        "length": {"value": 4.750, "unit": "m", "lower_bound": 4.73, "upper_bound": 4.77, "confidence": 0.95, "method": "plane_fit"},
                        "thickness": {"value": 0.15, "unit": "m", "lower_bound": 0.14, "upper_bound": 0.16, "confidence": 0.95, "method": "ransac"},
                        "openings": [],
                    },
                    {
                        "wall_id": "wall_lv_3",
                        "start": {"x": 6.0, "y": 4.75},
                        "end": {"x": 0.0, "y": 4.75},
                        "length": {"value": 6.000, "unit": "m", "lower_bound": 5.98, "upper_bound": 6.02, "confidence": 0.95, "method": "plane_fit"},
                        "thickness": {"value": 0.15, "unit": "m", "lower_bound": 0.14, "upper_bound": 0.16, "confidence": 0.95, "method": "ransac"},
                        "openings": [
                            {
                                "opening_id": "op_door_1",
                                "wall_id": "wall_lv_3",
                                "opening_type": "door",
                                "width": {"value": 0.90, "unit": "m", "lower_bound": 0.88, "upper_bound": 0.92, "confidence": 0.95, "method": "door_gap"},
                                "position_along_wall": {"value": 1.50, "unit": "m", "lower_bound": 1.45, "upper_bound": 1.55, "confidence": 0.95, "method": "center"},
                            }
                        ],
                    },
                    {
                        "wall_id": "wall_lv_4",
                        "start": {"x": 0.0, "y": 4.75},
                        "end": {"x": 0.0, "y": 0.0},
                        "length": {"value": 4.750, "unit": "m", "lower_bound": 4.73, "upper_bound": 4.77, "confidence": 0.95, "method": "plane_fit"},
                        "thickness": {"value": 0.15, "unit": "m", "lower_bound": 0.14, "upper_bound": 0.16, "confidence": 0.95, "method": "ransac"},
                        "openings": [],
                    },
                ],
                "openings": [],
                "damages": [],
            }
        ],
        "damage_regions": [
            {
                "damage_id": "dmg_001",
                "surface_id": "wall_lv_2",
                "damage_class": "water_stain",
                "extent_area": {"value": 0.85, "unit": "m2", "lower_bound": 0.75, "upper_bound": 0.95, "confidence": 0.90, "method": "cv_mask"},
                "scope_line_items": ["Drywall inspection and stain remediation"],
                "status": "ACCEPTED",
                "confidence": 0.92,
            }
        ],
        "scope_line_items": [
            {"id": "scope_001", "action": "Drywall repair", "quantity": 0.85, "unit": "m2", "inspection_required": True}
        ],
    }


def test_json_export_validity(sample_property_data, tmp_path):
    """Verifies that JSON export produces valid, readable JSON with exact data."""
    out_file = tmp_path / "test.json"
    result_str = export_property_json(sample_property_data, "cap_test_001", output_path=out_file)

    assert out_file.exists()
    parsed = json.loads(result_str)
    assert parsed["capture_id"] == "cap_test_001"
    assert parsed["total_floor_area"]["value"] == 48.50
    assert len(parsed["rooms"]) == 1
    assert parsed["rooms"][0]["walls"][0]["length"]["value"] == 6.000
    assert parsed["damage_regions"][0]["damage_class"] == "water_stain"


def test_svg_export_validity(sample_property_data, tmp_path):
    """Verifies that SVG export produces valid XML with geometry, dimensions, and notices."""
    out_file = tmp_path / "test.svg"
    svg_str = export_property_svg(sample_property_data, "cap_test_001", output_path=out_file)

    assert out_file.exists()
    assert len(svg_str) > 500

    # Parse as XML
    root = ET.fromstring(svg_str)
    assert "svg" in root.tag.lower()

    # Verify key elements
    assert "Living Room" in svg_str
    assert "6.00 m" in svg_str or "6.00m" in svg_str
    assert "Physical accuracy has not yet been validated" in svg_str
    assert "1.0 m" in svg_str  # scale bar


def test_pdf_export_validity(sample_property_data, tmp_path):
    """Verifies that PDF export produces a valid 2-page document with disclaimer."""
    out_file = tmp_path / "test.pdf"
    pdf_bytes = export_property_pdf(sample_property_data, "cap_test_001", output_path=out_file)

    assert out_file.exists()
    assert len(pdf_bytes) > 1000
    assert pdf_bytes.startswith(b"%PDF")

    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    assert doc.page_count == 2

    # Verify text on page 1 and page 2
    page1_text = doc[0].get_text()
    assert "COZMO SPATIAL RECONSTRUCTION" in page1_text
    assert "cap_test_001" in page1_text
    assert "Physical accuracy has not yet been validated" in page1_text

    page2_text = doc[1].get_text()
    assert "ROOM MEASUREMENT SUMMARY" in page2_text
    assert "Living Room" in page2_text
    assert "METRIC WALL MEASUREMENTS" in page2_text
    assert "Physical accuracy has not yet been validated" in page2_text

    doc.close()


def test_dxf_export_validity(sample_property_data, tmp_path):
    """Verifies that DXF export produces standard CAD entities in metric meters."""
    out_file = tmp_path / "test.dxf"
    dxf_str = export_property_dxf(sample_property_data, "cap_test_001", output_path=out_file)

    assert out_file.exists()
    assert len(dxf_str) > 500

    assert "SECTION" in dxf_str
    assert "HEADER" in dxf_str
    assert "$INSUNITS" in dxf_str
    assert "TABLES" in dxf_str
    assert "WALLS" in dxf_str
    assert "OPENINGS" in dxf_str
    assert "ROOMS" in dxf_str
    assert "ENTITIES" in dxf_str
    assert "LINE" in dxf_str
    assert "EOF" in dxf_str


def test_multi_capture_isolation(tmp_path):
    """Verifies that exports from Capture A and Capture B never cross-contaminate."""
    data_a = {
        "property_id": "prop_alpha",
        "capture_id": "cap_alpha",
        "tier": "lidar",
        "status": "COMPLETE",
        "total_floor_area": {"value": 100.0, "unit": "m2"},
        "rooms": [],
    }
    data_b = {
        "property_id": "prop_beta",
        "capture_id": "cap_beta",
        "tier": "video",
        "status": "PROVISIONAL",
        "total_floor_area": {"value": 50.0, "unit": "m2"},
        "rooms": [],
    }

    dir_a = tmp_path / "cap_alpha" / "exports"
    dir_b = tmp_path / "cap_beta" / "exports"

    res_a = export_all_formats(data_a, "cap_alpha", dir_a)
    res_b = export_all_formats(data_b, "cap_beta", dir_b)

    # Check file names
    assert "cap_alpha" in str(res_a["json"])
    assert "cap_beta" in str(res_b["json"])

    # Check contents
    json_a = json.loads(res_a["json"].read_text())
    json_b = json.loads(res_b["json"].read_text())

    assert json_a["capture_id"] == "cap_alpha"
    assert json_a["total_floor_area"]["value"] == 100.0
    assert json_b["capture_id"] == "cap_beta"
    assert json_b["total_floor_area"]["value"] == 50.0


def test_fastapi_export_routes(sample_property_data):
    """Tests FastAPI export endpoints with mock job and result."""
    client = TestClient(app)

    # Register mock job in job_store
    job = job_store.create_job(CaptureTier.LIDAR)
    job_id = job.id

    # Create output property.json
    out_dir = Path(job.output_path)
    out_dir.mkdir(parents=True, exist_ok=True)
    prop_json = out_dir / "property.json"
    prop_json.write_text(json.dumps(sample_property_data), encoding="utf-8")

    job_store.update_status(job_id, CaptureStatus.COMPLETE)

    # 1. Test JSON export
    resp_json = client.get(f"/api/captures/{job_id}/exports/json")
    assert resp_json.status_code == 200
    assert resp_json.headers["content-type"] == "application/json"
    assert f'cozmo_{job_id}_property.json' in resp_json.headers["content-disposition"]
    data = resp_json.json()
    assert data["capture_id"] == job_id

    # 2. Test SVG export
    resp_svg = client.get(f"/api/captures/{job_id}/exports/svg")
    assert resp_svg.status_code == 200
    assert "image/svg+xml" in resp_svg.headers["content-type"]
    assert "<svg" in resp_svg.text

    # 3. Test PDF export
    resp_pdf = client.get(f"/api/captures/{job_id}/exports/pdf")
    assert resp_pdf.status_code == 200
    assert resp_pdf.headers["content-type"] == "application/pdf"
    assert resp_pdf.content.startswith(b"%PDF")

    # 4. Test DXF export
    resp_dxf = client.get(f"/api/captures/{job_id}/exports/dxf")
    assert resp_dxf.status_code == 200
    assert "SECTION" in resp_dxf.text

    # 5. Test 404 for unknown capture
    resp_404 = client.get("/api/captures/cap_nonexistent/exports/json")
    assert resp_404.status_code == 404

    # 6. Test 400 for path traversal attempt
    resp_traversal = client.get("/api/captures/..%2F..%2Fetc/exports/json")
    assert resp_traversal.status_code in (400, 404)
