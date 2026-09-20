"""Tests for FastAPI capture management and reconstruction endpoints.

Purpose:
    Validates capture lifecycle HTTP endpoints:
    - POST /api/captures (upload & dispatch)
    - GET /api/captures/{id} (status polling)
    - GET /api/captures/{id}/result (result retrieval)
    - GET /health and GET /api/health

Stage:
    Frontend Stage 3 — Live FastAPI Integration.
"""

import io
import json
import zipfile
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.api.jobs import CaptureJob, CaptureStatus, JobStore
from backend.app.models.capture import CaptureTier


@pytest.fixture
def client():
    """Create a FastAPI TestClient."""
    return TestClient(app)


def _create_mock_lidar_zip() -> io.BytesIO:
    """Create a valid in-memory zip archive mimicking an ARKit LiDAR capture."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("test_scan/odometry.csv", "frame,timestamp,x,y,z,qx,qy,qz,qw\n0,0.0,0,0,0,0,0,0,1\n")
        zf.writestr("test_scan/camera_matrix.csv", "1000,0,960\n0,1000,720\n0,0,1\n")
    buf.seek(0)
    return buf


def _create_mock_photo_zip() -> io.BytesIO:
    """Create a valid in-memory zip archive containing dummy images."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("room_photos/img_001.jpg", b"\xff\xd8\xff\xe0" + b"\x00" * 100)
        zf.writestr("room_photos/img_002.png", b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
    buf.seek(0)
    return buf


class TestHealthEndpoints:
    """Validate system health check endpoints."""

    def test_health_root(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["service"] == "cozmo-spatial-api"

    def test_health_api(self, client):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"

    def test_docs_accessible(self, client):
        resp = client.get("/docs")
        assert resp.status_code == 200

    def test_openapi_json(self, client):
        resp = client.get("/openapi.json")
        assert resp.status_code == 200
        data = resp.json()
        assert "paths" in data
        assert "/api/captures" in data["paths"]


class TestCaptureCreation:
    """Validate POST /api/captures endpoint."""

    @patch("backend.app.api.captures.threading.Thread")
    def test_create_lidar_capture_valid(self, mock_thread, client, tmp_path):
        zip_buf = _create_mock_lidar_zip()
        files = {"file": ("capture.zip", zip_buf.getvalue(), "application/zip")}
        data = {"tier": "lidar"}

        resp = client.post("/api/captures", files=files, data=data)
        assert resp.status_code == 200
        payload = resp.json()
        assert "id" in payload
        assert payload["id"].startswith("cap_")
        assert payload["tier"] == "lidar"
        assert payload["status"] == "QUEUED"

    @patch("backend.app.api.captures.threading.Thread")
    def test_create_video_capture_mp4(self, mock_thread, client):
        video_bytes = b"\x00\x00\x00 ftypisom" + b"\x00" * 200
        files = {"file": ("recording.mp4", video_bytes, "video/mp4")}
        data = {"tier": "video"}

        resp = client.post("/api/captures", files=files, data=data)
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["tier"] == "video"
        assert payload["status"] == "QUEUED"

    @patch("backend.app.api.captures.threading.Thread")
    def test_create_photo_capture_valid(self, mock_thread, client):
        photo_buf = _create_mock_photo_zip()
        files = {"file": ("photos.zip", photo_buf.getvalue(), "application/zip")}
        data = {"tier": "photo"}

        resp = client.post("/api/captures", files=files, data=data)
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["tier"] == "photo"

    def test_create_capture_invalid_tier(self, client):
        files = {"file": ("test.zip", b"dummy", "application/zip")}
        data = {"tier": "quantum_sensor"}

        resp = client.post("/api/captures", files=files, data=data)
        assert resp.status_code == 422
        assert "Invalid tier" in resp.json()["detail"]

    def test_create_capture_empty_file(self, client):
        files = {"file": ("empty.zip", b"", "application/zip")}
        data = {"tier": "lidar"}

        resp = client.post("/api/captures", files=files, data=data)
        assert resp.status_code == 422
        assert "empty" in resp.json()["detail"].lower()

    def test_create_capture_unsupported_format_for_tier(self, client):
        # LiDAR rejecting .mp4
        files = {"file": ("video.mp4", b"data", "video/mp4")}
        data = {"tier": "lidar"}

        resp = client.post("/api/captures", files=files, data=data)
        assert resp.status_code == 422
        assert "requires a .zip" in resp.json()["detail"]

    def test_create_capture_invalid_zip_content(self, client):
        # Zip without odometry.csv for LiDAR
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("random.txt", "hello")
        buf.seek(0)

        files = {"file": ("invalid_lidar.zip", buf.getvalue(), "application/zip")}
        data = {"tier": "lidar"}

        resp = client.post("/api/captures", files=files, data=data)
        assert resp.status_code == 422
        assert "odometry.csv" in resp.json()["detail"]


class TestCaptureStatusPolling:
    """Validate GET /api/captures/{id} status polling endpoint."""

    def test_get_status_unknown_capture_404(self, client):
        resp = client.get("/api/captures/cap_nonexistent")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    @patch("backend.app.api.captures.threading.Thread")
    def test_get_status_queued_and_transitions(self, mock_thread, client):
        zip_buf = _create_mock_lidar_zip()
        create_resp = client.post(
            "/api/captures",
            files={"file": ("capture.zip", zip_buf.getvalue(), "application/zip")},
            data={"tier": "lidar"},
        )
        cap_id = create_resp.json()["id"]

        # Initial status check
        status_resp = client.get(f"/api/captures/{cap_id}")
        assert status_resp.status_code == 200
        body = status_resp.json()
        assert body["id"] == cap_id
        assert body["status"] == "QUEUED"
        assert body["tier"] == "lidar"
        assert "created_at" in body


class TestCaptureResultRetrieval:
    """Validate GET /api/captures/{id}/result endpoint."""

    def test_get_result_unknown_capture_404(self, client):
        resp = client.get("/api/captures/cap_unknown999/result")
        assert resp.status_code == 404

    def test_get_result_while_processing_returns_409(self, client):
        from backend.app.api.captures import job_store
        job = job_store.create_job(CaptureTier.LIDAR)
        job_store.update_status(job.id, CaptureStatus.PROCESSING, progress_stage="Aligning frames")

        resp = client.get(f"/api/captures/{job.id}/result")
        assert resp.status_code == 409
        assert "PROCESSING" in resp.json()["detail"]

    def test_get_result_when_failed_returns_422(self, client):
        from backend.app.api.captures import job_store
        job = job_store.create_job(CaptureTier.LIDAR)
        job_store.update_status(job.id, CaptureStatus.FAILED, error="Degenerate point cloud: 0 points extracted.")

        resp = client.get(f"/api/captures/{job.id}/result")
        assert resp.status_code == 422
        assert "Degenerate point cloud" in resp.json()["detail"]

    def test_get_result_complete_returns_property_json(self, client, tmp_path):
        from backend.app.api.captures import job_store
        job = job_store.create_job(CaptureTier.LIDAR)

        # Write mock property.json to job's output directory
        mock_output = {
            "property_id": "prop_test",
            "capture_id": "test_id",
            "tier": "lidar",
            "rooms": [
                {
                    "room_id": "room_01",
                    "name": "Living Room",
                    "floor_area": {"value": 22.5, "unit": "m2", "confidence": 0.9},
                    "walls": [],
                }
            ],
            "connections": [],
            "total_floor_area": {"value": 22.5, "unit": "m2"},
        }
        out_file = Path(job.output_path) / "property.json"
        out_file.write_text(json.dumps(mock_output), encoding="utf-8")

        job_store.update_status(job.id, CaptureStatus.COMPLETE)

        resp = client.get(f"/api/captures/{job.id}/result")
        assert resp.status_code == 200
        res = resp.json()
        assert res["capture_id"] == job.id
        assert len(res["rooms"]) == 1
        assert res["rooms"][0]["name"] == "Living Room"

    def test_get_result_not_evaluable_returns_clean_payload(self, client):
        from backend.app.api.captures import job_store
        job = job_store.create_job(CaptureTier.VIDEO)
        job_store.update_status(
            job.id,
            CaptureStatus.NOT_EVALUABLE,
            error="Feature matching failed: visual overlap < 20%.",
        )

        resp = client.get(f"/api/captures/{job.id}/result")
        assert resp.status_code == 200
        res = resp.json()
        assert res["status"] == "NOT_EVALUABLE"
        assert res["rooms"] == []
        assert "visual overlap < 20%" in res["failure_reasons"][0]
