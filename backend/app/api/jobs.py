"""Capture job model, ID generation, and thread-safe job persistence store.

Purpose:
    Provides the CaptureJob data model representing an evaluator upload's
    lifecycle (UPLOADING → QUEUED → PROCESSING → terminal state) and a
    thread-safe JobStore backed by in-memory state with per-job JSON
    persistence to disk.

Stage:
    Frontend Stage 3 — Live FastAPI Integration.

Inputs:
    Tier selection (CaptureTier enum) and upload metadata from the API layer.

Outputs:
    CaptureJob instances persisted as ``runtime/captures/<id>/job.json``.

Dependencies:
    pydantic, uuid, threading, pathlib, json, datetime.

Assumptions:
    Single-process FastAPI deployment. Job store is in-memory; restart
    loses in-flight state but completed results remain on disk.

Units / Coordinates:
    N/A — this is a job lifecycle module.

Failure Modes:
    - Disk write failure on job.json persistence (logged, non-fatal).
    - Job ID collision (astronomically unlikely with UUID4 hex).

First Debugging Points:
    Inspect ``runtime/captures/<id>/job.json`` for serialised job state.
    Check JobStore._jobs dict for in-memory state.
"""

import json
import threading
import uuid
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Optional, Dict

from pydantic import BaseModel, Field

from backend.app.models.capture import CaptureTier


class CaptureStatus(str, Enum):
    """Lifecycle status of a capture processing job.

    Terminal statuses: COMPLETE, PROVISIONAL, NOT_EVALUABLE, FAILED.
    """
    UPLOADING = "UPLOADING"
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    COMPLETE = "COMPLETE"
    PROVISIONAL = "PROVISIONAL"
    NOT_EVALUABLE = "NOT_EVALUABLE"
    FAILED = "FAILED"


# Statuses that indicate processing has finished and polling should stop.
TERMINAL_STATUSES = frozenset({
    CaptureStatus.COMPLETE,
    CaptureStatus.PROVISIONAL,
    CaptureStatus.NOT_EVALUABLE,
    CaptureStatus.FAILED,
})


class CaptureJob(BaseModel):
    """Represents a single evaluator capture upload and its processing state.

    Purpose:
        Tracks the full lifecycle from upload receipt through reconstruction
        to result availability.

    Parameters:
        id: Unique capture identifier (e.g. ``cap_f3a91c2b``).
        tier: Sensor tier (lidar / video / photo).
        status: Current lifecycle status.
        created_at: ISO 8601 timestamp of job creation.
        input_path: Filesystem path to uploaded input file.
        output_path: Filesystem path to reconstruction output directory.
        error: Human-readable error message if status is FAILED.
        progress_stage: Current processing sub-stage description.

    Assumptions:
        Paths are relative to project root or absolute.
    """
    id: str = Field(..., description="Unique capture job identifier")
    tier: CaptureTier = Field(..., description="Sensor tier")
    status: CaptureStatus = Field(
        default=CaptureStatus.UPLOADING,
        description="Current job lifecycle status",
    )
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO 8601 creation timestamp",
    )
    input_path: Optional[str] = Field(
        default=None, description="Path to uploaded input file"
    )
    output_path: Optional[str] = Field(
        default=None, description="Path to reconstruction output directory"
    )
    error: Optional[str] = Field(
        default=None, description="Error message on failure"
    )
    progress_stage: Optional[str] = Field(
        default=None, description="Current processing sub-stage"
    )


def generate_capture_id() -> str:
    """Generate a unique, short capture identifier.

    Purpose:
        Creates IDs like ``cap_a1b2c3d4`` that are URL-safe, unique,
        and visually distinguishable from existing fixture IDs.

    Returns:
        String in format ``cap_<8 hex chars>``.

    Assumptions:
        UUID4 provides sufficient entropy to avoid collisions.

    Failure Conditions:
        None — uuid4 is always available.
    """
    return f"cap_{uuid.uuid4().hex[:8]}"


class JobStore:
    """Thread-safe in-memory capture job registry with disk persistence.

    Purpose:
        Central registry for all capture jobs. Supports concurrent access
        from FastAPI request handlers and background processing threads.

    Dependencies:
        threading.Lock for thread safety; pathlib/json for persistence.

    Assumptions:
        Single-process deployment. Job data is authoritative in memory;
        disk JSON is for crash recovery and debugging only.

    Failure Modes:
        - Disk write errors logged but do not fail operations.
        - Job not found returns None (caller must handle).

    First Debugging Points:
        Check self._jobs dict keys; inspect job.json on disk.
    """

    def __init__(self, runtime_dir: str = "runtime/captures") -> None:
        """Initialise the job store.

        Parameters:
            runtime_dir: Base directory for per-capture runtime data.
        """
        self._jobs: Dict[str, CaptureJob] = {}
        self._lock = threading.Lock()
        self._runtime_dir = Path(runtime_dir)
        self._runtime_dir.mkdir(parents=True, exist_ok=True)
        self._load_persisted_jobs()

    def _load_persisted_jobs(self) -> None:
        """Scan runtime directory for existing job.json files to restore state on startup."""
        try:
            for job_file in self._runtime_dir.glob("*/job.json"):
                try:
                    data = json.loads(job_file.read_text(encoding="utf-8"))
                    job = CaptureJob.model_validate(data)
                    self._jobs[job.id] = job
                except Exception:
                    continue
        except Exception:
            pass

    def create_job(self, tier: CaptureTier) -> CaptureJob:
        """Create a new capture job with a unique ID and prepare directories.

        Purpose:
            Allocates a fresh capture ID, creates isolated input/output
            directories, and registers the job in memory.

        Parameters:
            tier: The sensor tier for this capture.

        Returns:
            The newly created CaptureJob.

        Assumptions:
            Caller will subsequently write the uploaded file into input_path.

        Failure Conditions:
            Filesystem permission errors creating directories.
        """
        job_id = generate_capture_id()
        job_dir = self._runtime_dir / job_id
        input_dir = job_dir / "input"
        output_dir = job_dir / "outputs"

        input_dir.mkdir(parents=True, exist_ok=True)
        output_dir.mkdir(parents=True, exist_ok=True)

        job = CaptureJob(
            id=job_id,
            tier=tier,
            status=CaptureStatus.UPLOADING,
            input_path=str(input_dir),
            output_path=str(output_dir),
        )

        with self._lock:
            self._jobs[job_id] = job

        self._persist(job)
        return job

    def get_job(self, job_id: str) -> Optional[CaptureJob]:
        """Retrieve a job by ID.

        Parameters:
            job_id: The capture job identifier.

        Returns:
            CaptureJob or None if not found.
        """
        with self._lock:
            return self._jobs.get(job_id)

    def update_status(
        self,
        job_id: str,
        status: CaptureStatus,
        error: Optional[str] = None,
        progress_stage: Optional[str] = None,
    ) -> Optional[CaptureJob]:
        """Update a job's status and optionally set error/progress fields.

        Purpose:
            Called by the background worker to advance job lifecycle.

        Parameters:
            job_id: Target job.
            status: New status value.
            error: Error message (typically set with FAILED status).
            progress_stage: Human-readable processing stage description.

        Returns:
            Updated CaptureJob or None if job not found.

        Failure Conditions:
            Returns None for unknown job_id.
        """
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return None

            job.status = status
            if error is not None:
                job.error = error
            if progress_stage is not None:
                job.progress_stage = progress_stage

        self._persist(job)
        return job

    def _persist(self, job: CaptureJob) -> None:
        """Write job state to disk as JSON.

        Purpose:
            Enables post-mortem debugging and potential crash recovery.

        Parameters:
            job: The job to persist.

        Failure Conditions:
            Disk write errors are caught and logged to stderr.
        """
        try:
            job_dir = self._runtime_dir / job.id
            job_dir.mkdir(parents=True, exist_ok=True)
            job_file = job_dir / "job.json"
            job_file.write_text(
                job.model_dump_json(indent=2), encoding="utf-8"
            )
        except Exception as exc:
            import sys
            print(
                f"[JobStore] Warning: failed to persist job {job.id}: {exc}",
                file=sys.stderr,
            )
