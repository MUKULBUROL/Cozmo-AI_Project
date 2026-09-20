"""FastAPI application entrypoint for the Cozmo Spatial Intelligence API.

Purpose:
    Creates and configures the FastAPI application instance with CORS
    middleware, health check, and capture processing routes.

Stage:
    Frontend Stage 3 — Live FastAPI Integration.

Inputs:
    Environment variables:
      - COZMO_CORS_ORIGINS: Comma-separated allowed origins
        (default: ``http://localhost:3000,http://localhost:3001``).
      - COZMO_RUNTIME_DIR: Base directory for capture runtime data
        (default: ``runtime/captures``).

Outputs:
    HTTP API at the configured host/port (default ``http://localhost:8000``).

Dependencies:
    fastapi, uvicorn, .captures (router).

Assumptions:
    Run from the project root directory so backend module imports resolve.
    Development deployment only — no production hardening or auth.

Units / Coordinates:
    N/A — API configuration module.

Failure Modes:
    - Missing dependencies → ImportError at startup.
    - Port conflict → uvicorn bind error.
    - CORS misconfiguration → browser blocks requests.

First Debugging Points:
    Check ``GET /api/health`` returns 200.
    Verify CORS headers in browser Network tab.
    Run: ``uvicorn backend.app.api.main:app --reload --port 8000``
"""

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .captures import router as captures_router

# ---------------------------------------------------------------------------
# Environment configuration
# ---------------------------------------------------------------------------
_DEFAULT_ORIGINS = "http://localhost:3000,http://localhost:3001"
_cors_origins_str = os.environ.get("COZMO_CORS_ORIGINS", _DEFAULT_ORIGINS)
CORS_ORIGINS = [o.strip() for o in _cors_origins_str.split(",") if o.strip()]

# ---------------------------------------------------------------------------
# FastAPI app instance
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Cozmo Spatial Intelligence API",
    description=(
        "Backend API for the Cozmo spatial reconstruction system. "
        "Accepts sensor capture uploads, processes them through "
        "tier-specific reconstruction pipelines, and returns "
        "dimensioned floor plan results."
    ),
    version="0.3.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ---------------------------------------------------------------------------
# CORS middleware — required for frontend ↔ backend communication
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Route registration
# ---------------------------------------------------------------------------
app.include_router(captures_router)


@app.get("/health", tags=["system"])
@app.get("/api/health", tags=["system"])
async def health_check():
    """Health check endpoint.

    Purpose:
        Returns a simple OK response for connectivity verification
        by the frontend API client and monitoring systems.

    Returns:
        JSON ``{ "status": "ok", "service": "cozmo-spatial-api" }``.

    Debugging Clues:
        If this fails, the server is not running or CORS is blocking.
    """
    return {"status": "ok", "service": "cozmo-spatial-api"}
