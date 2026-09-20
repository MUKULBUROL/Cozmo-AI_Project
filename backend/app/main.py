"""Main FastAPI application entrypoint.

Re-exports the FastAPI app instance from backend.app.api.main for top-level usage.
"""

from backend.app.api.main import app

__all__ = ["app"]
