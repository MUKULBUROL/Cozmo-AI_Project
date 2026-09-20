# Frontend Stage 3 — FastAPI Backend Integration Audit

## 1. Executive Summary

Prior to Stage 3, the Cozmo spatial intelligence backend operated strictly via standalone CLI entrypoints (`scripts/reconstruct_property.py`, `scripts/reconstruct_video.py`, `scripts/reconstruct_photos.py`, `scripts/reconstruct_lidar.py`). There was no HTTP API server or asynchronous execution daemon.

Frontend Stage 3 establishes a production-grade, typed FastAPI server layer (`backend/app/api/`) that bridges web frontend uploads to the underlying computer vision and reconstruction pipelines.

---

## 2. API Architecture

```
backend/app/
├── main.py                # Top-level re-export of FastAPI app instance
└── api/
    ├── __init__.py        # FastAPI app factory, CORS middleware, health endpoints
    ├── main.py            # API entrypoint module
    ├── captures.py        # REST router: upload, status polling, result retrieval
    ├── jobs.py            # Thread-safe JobStore with disk persistence & lifecycle
    └── validators.py      # Tier-specific file and archive structural validators
```

### Module Responsibilities

1. **`backend.app.api.main:app` / `backend.app.main:app`**:
   - Central FastAPI application instance configured with CORS for `http://localhost:3000` and `http://localhost:3001`.
   - Mounts `/docs`, `/redoc`, `/openapi.json`, and `/health` / `/api/health`.
   - Includes the `/api/captures` router.

2. **`backend.app.api.jobs` (`JobStore`, `CaptureJob`, `CaptureStatus`)**:
   - Manages the complete capture lifecycle: `UPLOADING` → `QUEUED` → `PROCESSING` → (`COMPLETE` | `PROVISIONAL` | `NOT_EVALUABLE` | `FAILED`).
   - Thread-safe in-memory registry protected by `threading.Lock`.
   - Persists state to `runtime/captures/<capture_id>/job.json` and restores state on server startup.
   - Generates collision-resistant unique IDs with `cap_<8 hex chars>`.

3. **`backend.app.api.validators` (`validate_upload`)**:
   - Performs rapid pre-execution validation before disk storage and queue dispatch.
   - Rejects oversized files (> 2 GB), empty payloads, and unsupported extensions.
   - Inspects archive internals:
     - LiDAR: confirms `<scan_id>/odometry.csv` exists and extracts `detected_scan_id`.
     - Video: accepts `.mp4`, `.mov`, or `.zip` containing video streams.
     - Photo: validates JPEG/PNG presence inside image archives.

4. **`backend.app.api.captures` (HTTP Router & Worker Dispatcher)**:
   - `POST /api/captures`: Validates payload, allocates isolated workspace, stores input bytes, returns `{ id, tier, status: "QUEUED" }`, and launches background processing thread.
   - `GET /api/captures/{id}`: Returns live polling payload with status, progress stage, timestamps, and error messages.
   - `GET /api/captures/{id}/result`: Returns fresh reconstruction JSON or explicit status reasons; returns 409 while processing, 404 for unknown IDs, and 422 for failed jobs.

---

## 3. Asynchronous Worker Execution & Process Safety

All pipeline executions are dispatched in non-blocking background daemon threads.

### Safe Subprocess Execution
Reconstruction scripts are executed via `subprocess.run` with **strict argument arrays** (zero `shell=True` execution):

```python
cmd = [
    sys.executable, "-m", "scripts.reconstruct_property",
    "--scan", scan_id,
    "--archive", input_path,
    "--headless",
    "--output-dir", output_dir,
]
result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
```

### Capture Workspace Isolation
Every capture is assigned an isolated directory hierarchy under `runtime/captures/`:

```
runtime/captures/<capture-id>/
├── input/
│   └── <uploaded_file>
├── outputs/
│   ├── property.json
│   ├── baseline/
│   ├── optimized/
│   └── structure/
└── job.json
```

- **Cross-job isolation**: Capture A cannot overwrite or access Capture B.
- **Historical protection**: Historical evaluation directories (`outputs/c00a170fe1`, `outputs/c7d28f72c6`, `outputs/benchmarks/`, `outputs/fix_loop/`) are never overwritten.

---

## 4. Result Discovery & Normalization Contract

When reconstruction completes:
1. `_find_result_json` searches `runtime/captures/<id>/outputs/` for `property.json`.
2. Returned JSON has its `capture_id` and `property_id` normalized to the live job ID.
3. If no geometry was produced, a structured `NOT_EVALUABLE` response is returned with explicit failure reasons.
4. **Strict rule**: No fixture substitution occurs under any circumstances.

---

## 5. Test Coverage

- **Backend API Tests** (`backend/tests/test_api_captures.py`): 18 unit tests covering health endpoints, creation, tier rejection, invalid archives, polling transitions, 409 conflict during processing, 422 on failure, 404 on missing captures, and complete payload retrieval.
- **Full Backend Suite**: 190 tests passed cleanly in pytest.
- **Dataset Validator**: `python3 -m scripts.validate_dataset` passed.
- **Byte Integrity**: SHA-256 validation verified identical bytes stored in `runtime/captures/<id>/input/`.
