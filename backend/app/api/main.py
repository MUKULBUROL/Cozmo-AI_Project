"""FastAPI application entrypoint for the Cozmo Spatial Intelligence API.

Purpose:
    Re-exports the FastAPI app instance from the api package for use with
    ``uvicorn backend.app.api.main:app``.

Stage:
    Frontend Stage 3 — Live FastAPI Integration.

Dependencies:
    backend.app.api (package __init__).
"""

from backend.app.api import app  # noqa: F401

__all__ = ["app"]
