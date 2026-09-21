"""FastAPI REST endpoints for capture upload, status polling, and result retrieval.

Purpose:
    Implements the three core capture lifecycle endpoints that the
    frontend Stage 3 upload workflow requires:

    - POST /api/captures       — Upload a new capture file + tier
    - GET  /api/captures/{id}  — Poll processing status
    - GET  /api/captures/{id}/result — Retrieve reconstruction result

Stage:
    Frontend Stage 3 — Live FastAPI Integration.

Inputs:
    - POST: multipart file upload + tier form field.
    - GET:  capture ID path parameter.

Outputs:
    - POST: JSON ``{ id, tier, status }``
    - GET status: JSON ``{ id, tier, status, created_at, progress_stage, error }``
    - GET result: JSON ``PropertyPlanOutput`` from backend reconstruction.

Dependencies:
    fastapi, .jobs (JobStore, CaptureJob), .validators, backend pipeline scripts.

Assumptions:
    - JobStore is a singleton shared across the application.
    - Reconstruction pipelines are invoked as subprocess calls to existing
      CLI scripts (reconstruct_property.py, reconstruct_video.py,
      reconstruct_photos.py).
    - Processing runs in a background thread to avoid blocking the API.

Units / Coordinates:
    Result payloads use meters / square meters as defined by backend models.

Failure Modes:
    - Invalid file format → 422 with reason.
    - Unknown capture ID → 404.
    - Reconstruction failure → job status set to FAILED with error message.
    - Subprocess crash → caught and converted to FAILED status.

First Debugging Points:
    Check ``runtime/captures/<id>/job.json`` for job state.
    Check ``runtime/captures/<id>/outputs/`` for generated artifacts.
    Check server stderr for subprocess output on failures.
"""

import json
import shutil
import subprocess
import sys
import threading
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, Form, UploadFile, HTTPException, Response
from fastapi.responses import FileResponse

from backend.app.models.capture import CaptureTier
from backend.app.export import (
    export_property_json,
    export_property_svg,
    export_property_pdf,
    export_property_dxf,
)
from .jobs import CaptureStatus, JobStore, TERMINAL_STATUSES
from .validators import validate_upload

router = APIRouter(prefix="/api/captures", tags=["captures"])

# Singleton job store — initialised at module level, used by the FastAPI app.
job_store = JobStore()


@router.post("")
async def create_capture(
    file: UploadFile = File(..., description="Capture file (zip, mp4, etc.)"),
    tier: str = Form(..., description="Sensor tier: lidar, video, or photo"),
):
    """Create a new capture processing job from an uploaded file.

    Purpose:
        Receives a file upload and tier selection, validates the input,
        creates an isolated runtime directory, saves the file, and
        dispatches background reconstruction.

    Parameters:
        file: The uploaded capture file.
        tier: String tier identifier ("lidar", "video", or "photo").

    Returns:
        JSON with ``id``, ``tier``, and ``status`` fields.

    Failure Conditions:
        - Invalid tier string → 422.
        - File validation failure → 422 with reason.
        - File save failure → 500.

    Debugging Clues:
        Check the returned capture ID; inspect runtime/captures/<id>/.
    """
    # Validate tier
    try:
        capture_tier = CaptureTier(tier.lower())
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid tier '{tier}'. Must be one of: lidar, video, photo.",
        )

    # Read file content
    file_data = await file.read()
    filename = file.filename or "upload"

    # Validate upload format
    validation = validate_upload(filename, file_data, capture_tier)
    if not validation.valid:
        raise HTTPException(status_code=422, detail=validation.reason)

    # Create job with isolated directories
    job = job_store.create_job(capture_tier)

    # Save uploaded file to input directory
    input_path = Path(job.input_path) / filename
    try:
        input_path.write_bytes(file_data)
    except Exception as exc:
        job_store.update_status(
            job.id, CaptureStatus.FAILED, error=f"Failed to save upload: {exc}"
        )
        raise HTTPException(
            status_code=500, detail=f"Failed to save uploaded file: {exc}"
        )

    # Mark as queued and dispatch background processing
    job_store.update_status(job.id, CaptureStatus.QUEUED)

    # Store detected scan_id for LiDAR archives
    detected_scan_id = validation.detected_scan_id

    thread = threading.Thread(
        target=_run_reconstruction,
        args=(job.id, capture_tier, str(input_path), job.output_path, detected_scan_id),
        daemon=True,
    )
    thread.start()

    return {
        "id": job.id,
        "tier": capture_tier.value,
        "status": CaptureStatus.QUEUED.value,
    }


@router.get("/{capture_id}")
async def get_capture_status(capture_id: str):
    """Retrieve the current status of a capture processing job.

    Purpose:
        Provides the frontend polling endpoint to track job progress.

    Parameters:
        capture_id: The capture job identifier.

    Returns:
        JSON with id, tier, status, created_at, progress_stage, error.

    Failure Conditions:
        404 if capture_id not found.
    """
    job = job_store.get_job(capture_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Capture '{capture_id}' not found.")

    return {
        "id": job.id,
        "tier": job.tier.value,
        "status": job.status.value,
        "created_at": job.created_at,
        "progress_stage": job.progress_stage,
        "error": job.error,
    }


@router.get("/{capture_id}/result")
async def get_capture_result(capture_id: str):
    """Retrieve the reconstruction result for a completed capture.

    Purpose:
        Returns the PropertyPlanOutput JSON generated by the backend
        reconstruction pipeline for this specific capture.

    Parameters:
        capture_id: The capture job identifier.

    Returns:
        Raw property JSON from ``outputs/property.json`` or equivalent.

    Failure Conditions:
        404 if capture not found.
        409 if processing is not yet complete.
        404 if result file is missing after completion.

    Debugging Clues:
        Check ``runtime/captures/<id>/outputs/`` for property.json.
    """
    job = job_store.get_job(capture_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Capture '{capture_id}' not found.")

    if job.status not in TERMINAL_STATUSES:
        raise HTTPException(
            status_code=409,
            detail=f"Capture is still {job.status.value}. Poll status until terminal.",
        )

    if job.status == CaptureStatus.FAILED:
        raise HTTPException(
            status_code=422,
            detail=f"Capture processing failed: {job.error or 'Unknown error'}",
        )

    # Find result JSON
    result_json = _find_result_json(job)
    if result_json is None:
        # For NOT_EVALUABLE or cases with no output, return a structured failure
        return {
            "property_id": capture_id,
            "capture_id": capture_id,
            "tier": job.tier.value,
            "status": job.status.value,
            "rooms": [],
            "connections": [],
            "total_floor_area": None,
            "reconstruction_method": None,
            "failure_reasons": [job.error or "No result artifacts generated."],
        }

    try:
        with open(result_json, "r", encoding="utf-8") as f:
            data = json.load(f)
        # Ensure capture_id matches this job (not a leftover from old runs)
        data["capture_id"] = capture_id
        data["property_id"] = capture_id
        # Preserve honest status from job
        if job.status == CaptureStatus.NOT_EVALUABLE:
            data["status"] = "NOT_EVALUABLE"
        elif job.status == CaptureStatus.PROVISIONAL:
            data["status"] = "PROVISIONAL"
        return data
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to read result: {exc}",
        )


def _validate_capture_id(capture_id: str) -> None:
    """Security check ensuring capture_id does not attempt directory traversal.

    Purpose:
        Protects against path traversal attacks (e.g. '../', absolute paths).

    Parameters:
        capture_id: The identifier string to check.

    Failure Conditions:
        Raises 400 Bad Request if capture_id contains invalid characters.
    """
    if not capture_id or ".." in capture_id or "/" in capture_id or "\\" in capture_id:
        raise HTTPException(
            status_code=400,
            detail="Invalid capture ID. Path traversal is strictly forbidden.",
        )


def _get_capture_result_payload(capture_id: str) -> dict:
    """Helper to fetch verified result data for a terminal capture.

    Purpose:
        Retrieves the reconstruction JSON payload for export rendering.

    Parameters:
        capture_id: The capture ID.

    Returns:
        Result dictionary populated with capture_id and honest status.
    """
    _validate_capture_id(capture_id)
    job = job_store.get_job(capture_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Capture '{capture_id}' not found.")

    if job.status not in TERMINAL_STATUSES:
        raise HTTPException(
            status_code=409,
            detail=f"Capture is still {job.status.value}. Poll status until terminal.",
        )

    result_json = _find_result_json(job)
    if result_json is None:
        return {
            "property_id": capture_id,
            "capture_id": capture_id,
            "tier": job.tier.value,
            "status": job.status.value,
            "rooms": [],
            "connections": [],
            "total_floor_area": None,
            "reconstruction_method": None,
            "failure_reasons": [job.error or "No result artifacts generated."],
        }

    try:
        with open(result_json, "r", encoding="utf-8") as f:
            data = json.load(f)
        data["capture_id"] = capture_id
        data["property_id"] = capture_id
        if job.status == CaptureStatus.NOT_EVALUABLE:
            data["status"] = "NOT_EVALUABLE"
        elif job.status == CaptureStatus.PROVISIONAL:
            data["status"] = "PROVISIONAL"
        return data
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Failed to read result data: {exc}"
        )


@router.get("/{capture_id}/exports/json")
@router.get("/{capture_id}/export/json")
async def export_json_endpoint(capture_id: str):
    """Retrieve or download machine-readable property JSON export.

    Purpose:
        Provides the standard JSON deliverable for the specified capture.
    """
    data = _get_capture_result_payload(capture_id)
    job = job_store.get_job(capture_id)
    exports_dir = Path(job.output_path).parent / "exports"
    exports_dir.mkdir(parents=True, exist_ok=True)
    out_file = exports_dir / f"cozmo_{capture_id}_property.json"

    json_str = export_property_json(data, capture_id, output_path=out_file)
    return Response(
        content=json_str,
        media_type="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="cozmo_{capture_id}_property.json"'
        },
    )


@router.get("/{capture_id}/exports/svg")
@router.get("/{capture_id}/export/svg")
async def export_svg_endpoint(capture_id: str):
    """Retrieve or download architectural vector floor plan SVG export.

    Purpose:
        Provides the standalone 2D vector floor plan SVG for the specified capture.
    """
    data = _get_capture_result_payload(capture_id)
    job = job_store.get_job(capture_id)
    exports_dir = Path(job.output_path).parent / "exports"
    exports_dir.mkdir(parents=True, exist_ok=True)
    out_file = exports_dir / f"cozmo_{capture_id}_floorplan.svg"

    svg_str = export_property_svg(data, capture_id, output_path=out_file)
    return Response(
        content=svg_str,
        media_type="image/svg+xml",
        headers={
            "Content-Disposition": f'attachment; filename="cozmo_{capture_id}_floorplan.svg"'
        },
    )


@router.get("/{capture_id}/exports/pdf")
@router.get("/{capture_id}/export/pdf")
async def export_pdf_endpoint(capture_id: str):
    """Retrieve or download multi-page property reconstruction PDF report.

    Purpose:
        Provides the complete engineering report PDF with vector drawing and schedules.
    """
    data = _get_capture_result_payload(capture_id)
    job = job_store.get_job(capture_id)
    exports_dir = Path(job.output_path).parent / "exports"
    exports_dir.mkdir(parents=True, exist_ok=True)
    out_file = exports_dir / f"cozmo_{capture_id}_report.pdf"

    pdf_bytes = export_property_pdf(data, capture_id, output_path=out_file)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="cozmo_{capture_id}_report.pdf"'
        },
    )


@router.get("/{capture_id}/exports/dxf")
@router.get("/{capture_id}/export/dxf")
async def export_dxf_endpoint(capture_id: str):
    """Retrieve or download standard CAD 2D DXF floor plan export.

    Purpose:
        Provides the metric CAD-compatible DXF deliverable with structured layers.
    """
    data = _get_capture_result_payload(capture_id)
    job = job_store.get_job(capture_id)
    exports_dir = Path(job.output_path).parent / "exports"
    exports_dir.mkdir(parents=True, exist_ok=True)
    out_file = exports_dir / f"cozmo_{capture_id}_floorplan.dxf"

    dxf_str = export_property_dxf(data, capture_id, output_path=out_file)
    return Response(
        content=dxf_str,
        media_type="application/dxf",
        headers={
            "Content-Disposition": f'attachment; filename="cozmo_{capture_id}_floorplan.dxf"'
        },
    )


def _find_result_json(job) -> Optional[str]:
    """Locate the reconstruction property.json in the job output directory.

    Purpose:
        Searches known output paths for the property JSON result file.

    Parameters:
        job: CaptureJob instance.

    Returns:
        Absolute path string to property.json, or None.

    Debugging Clues:
        List files in job.output_path to see what was generated.
    """
    output_dir = Path(job.output_path)

    # Direct property.json in output dir
    candidates = [
        output_dir / "property.json",
        output_dir / "property" / "property.json",
    ]

    # Also search one level deep (e.g. outputs/video/reconstruction_stats.json)
    if output_dir.exists():
        for subdir in output_dir.iterdir():
            if subdir.is_dir():
                candidates.append(subdir / "property.json")

    for candidate in candidates:
        if candidate.exists():
            return str(candidate)

    return None


def _run_reconstruction(
    job_id: str,
    tier: CaptureTier,
    input_path: str,
    output_dir: str,
    detected_scan_id: Optional[str] = None,
) -> None:
    """Background worker that invokes the correct reconstruction pipeline.

    Purpose:
        Runs the appropriate CLI reconstruction script as a subprocess,
        updating job status throughout the lifecycle.

    Parameters:
        job_id: The capture job ID.
        tier: Sensor tier determining which pipeline to run.
        input_path: Path to the uploaded input file.
        output_dir: Path to write reconstruction outputs.
        detected_scan_id: For LiDAR, the scan ID found in the archive.

    Assumptions:
        Python environment has all required backend dependencies.
        CLI scripts are importable from the project root.

    Failure Conditions:
        Subprocess failures are caught and set job status to FAILED.

    Debugging Clues:
        Check stderr output printed to server console.
    """
    try:
        job_store.update_status(
            job_id, CaptureStatus.PROCESSING, progress_stage="Preparing input"
        )

        if tier == CaptureTier.LIDAR:
            _process_lidar(job_id, input_path, output_dir, detected_scan_id)
        elif tier == CaptureTier.VIDEO:
            _process_video(job_id, input_path, output_dir)
        elif tier == CaptureTier.PHOTO:
            _process_photo(job_id, input_path, output_dir)
        else:
            job_store.update_status(
                job_id, CaptureStatus.FAILED, error=f"Unknown tier: {tier}"
            )

    except Exception as exc:
        print(f"[Worker] Reconstruction failed for {job_id}: {exc}", file=sys.stderr)
        job_store.update_status(
            job_id, CaptureStatus.FAILED, error=str(exc)
        )


def _process_lidar(
    job_id: str,
    input_path: str,
    output_dir: str,
    detected_scan_id: Optional[str],
) -> None:
    """Execute LiDAR reconstruction pipeline.

    Purpose:
        Invokes ``scripts/reconstruct_property.py`` with the uploaded
        archive and scan ID, writing outputs directly to the job's isolated
        output directory.

    Parameters:
        job_id: Capture job ID.
        input_path: Path to the uploaded zip archive.
        output_dir: Target output directory.
        detected_scan_id: Scan ID detected inside the archive.

    Failure Conditions:
        Missing dependencies, invalid archive structure.
    """
    scan_id = detected_scan_id or job_id

    job_store.update_status(
        job_id, CaptureStatus.PROCESSING, progress_stage="Reconstructing geometry"
    )

    cmd = [
        sys.executable, "-m", "scripts.reconstruct_property",
        "--scan", scan_id,
        "--archive", input_path,
        "--headless",
        "--output-dir", output_dir,
    ]

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=600,  # 10 minute timeout
    )

    # Check for property.json in the isolated output directory
    property_json = Path(output_dir) / "property.json"
    if not property_json.exists():
        fallback_json = Path("outputs") / scan_id / "property" / "property.json"
        if fallback_json.exists():
            _copy_outputs(str(fallback_json.parent), output_dir)
            property_json = Path(output_dir) / "property.json"

    if result.returncode != 0:
        error_msg = result.stderr.strip() or result.stdout.strip() or "Unknown error"
        if property_json.exists():
            job_store.update_status(
                job_id, CaptureStatus.PROVISIONAL,
                error=f"Completed with warnings: {error_msg[:200]}",
                progress_stage="Finalised (provisional)",
            )
        else:
            job_store.update_status(
                job_id, CaptureStatus.FAILED, error=error_msg[:500]
            )
        return

    if property_json.exists():
        job_store.update_status(
            job_id, CaptureStatus.COMPLETE, progress_stage="Complete"
        )
    else:
        job_store.update_status(
            job_id, CaptureStatus.NOT_EVALUABLE,
            error="Pipeline completed but no property output was generated.",
        )


def _process_video(job_id: str, input_path: str, output_dir: str) -> None:
    """Execute Video SfM reconstruction pipeline.

    Purpose:
        Invokes ``scripts/reconstruct_video.py`` with the uploaded video.

    Parameters:
        job_id: Capture job ID.
        input_path: Path to uploaded video file or archive.
        output_dir: Target output directory.

    Failure Conditions:
        Missing COLMAP/depth dependencies, insufficient visual overlap.
    """
    job_store.update_status(
        job_id, CaptureStatus.PROCESSING, progress_stage="Extracting frames"
    )

    cmd = [
        sys.executable, "-m", "scripts.reconstruct_video",
        "--input", input_path,
        "--capture-id", job_id,
        "--output-dir", output_dir,
    ]

    # If input is a zip archive, try to find video inside
    if input_path.lower().endswith(".zip"):
        import zipfile
        with zipfile.ZipFile(input_path, "r") as zf:
            video_files = [n for n in zf.namelist() if n.endswith(".mp4")]
            if video_files:
                extract_dir = Path(output_dir) / "extracted"
                extract_dir.mkdir(parents=True, exist_ok=True)
                zf.extract(video_files[0], str(extract_dir))
                cmd = [
                    sys.executable, "-m", "scripts.reconstruct_video",
                    "--input", str(extract_dir / video_files[0]),
                    "--capture-id", job_id,
                    "--output-dir", output_dir,
                ]

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=900,  # 15 minute timeout
    )

    # Check for property.json in the output directory
    property_json = Path(output_dir) / "property.json"
    if not property_json.exists():
        fallback_json = Path("outputs") / job_id / "video" / "property.json"
        if fallback_json.exists():
            _copy_outputs(str(fallback_json.parent), output_dir)
            property_json = Path(output_dir) / "property.json"

    if property_json.exists():
        # Video results are always PROVISIONAL per Stage 11 rules
        job_store.update_status(
            job_id, CaptureStatus.PROVISIONAL, progress_stage="Complete (provisional)"
        )
    elif result.returncode != 0:
        error_msg = result.stderr.strip() or result.stdout.strip() or "Reconstruction failed"
        job_store.update_status(
            job_id, CaptureStatus.FAILED, error=error_msg[:500]
        )
    else:
        job_store.update_status(
            job_id, CaptureStatus.NOT_EVALUABLE,
            error="Video pipeline completed but produced no evaluable geometry.",
        )


def _process_photo(job_id: str, input_path: str, output_dir: str) -> None:
    """Execute Photo reconstruction pipeline.

    Purpose:
        Invokes ``scripts/reconstruct_photos.py`` with the uploaded
        photo archive.

    Parameters:
        job_id: Capture job ID.
        input_path: Path to uploaded zip archive of images.
        output_dir: Target output directory.

    Failure Conditions:
        Insufficient image overlap, too few images.
    """
    job_store.update_status(
        job_id, CaptureStatus.PROCESSING, progress_stage="Extracting images"
    )

    # Extract images from zip
    import zipfile
    extract_dir = Path(output_dir) / "extracted_images"
    extract_dir.mkdir(parents=True, exist_ok=True)

    try:
        with zipfile.ZipFile(input_path, "r") as zf:
            zf.extractall(str(extract_dir))
    except Exception as exc:
        job_store.update_status(
            job_id, CaptureStatus.FAILED, error=f"Failed to extract archive: {exc}"
        )
        return

    # Find the actual image directory (may be nested)
    image_dir = extract_dir
    for child in extract_dir.iterdir():
        if child.is_dir() and not child.name.startswith("__"):
            image_dir = child
            break

    cmd = [
        sys.executable, "-m", "scripts.reconstruct_photos",
        "--input", str(image_dir),
        "--capture-id", job_id,
        "--output-dir", output_dir,
    ]

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=600,
    )

    property_json = Path(output_dir) / "property.json"
    if not property_json.exists():
        fallback_json = Path("outputs") / job_id / "photo" / "property.json"
        if fallback_json.exists():
            _copy_outputs(str(fallback_json.parent), output_dir)
            property_json = Path(output_dir) / "property.json"

    if property_json.exists():
        job_store.update_status(
            job_id, CaptureStatus.PROVISIONAL, progress_stage="Complete"
        )
    elif result.returncode != 0:
        error_msg = result.stderr.strip() or result.stdout.strip() or "Photo reconstruction failed"
        job_store.update_status(
            job_id, CaptureStatus.FAILED, error=error_msg[:500]
        )
    else:
        job_store.update_status(
            job_id, CaptureStatus.NOT_EVALUABLE,
            error="Photo pipeline completed but produced no evaluable geometry.",
        )


def _copy_outputs(source_dir: str, dest_dir: str) -> None:
    """Copy reconstruction output files to the job's isolated output directory.

    Purpose:
        CLI scripts write to ``outputs/<id>/<tier>/``.  This copies
        results to the job-specific ``runtime/captures/<id>/outputs/``
        so each job's output is self-contained.

    Parameters:
        source_dir: Path to the pipeline's output directory.
        dest_dir: Job-specific output directory.

    Failure Conditions:
        Permission errors on copy.
    """
    src = Path(source_dir)
    dst = Path(dest_dir)
    dst.mkdir(parents=True, exist_ok=True)

    for item in src.iterdir():
        dest_item = dst / item.name
        if item.is_dir():
            shutil.copytree(str(item), str(dest_item), dirs_exist_ok=True)
        else:
            shutil.copy2(str(item), str(dest_item))
