"""Stage 8 public interfaces for photo-only room and property reconstruction.

1. Why this file exists: exposes stable Stage 8 entry points without leaking implementation files.
2. Pipeline stage: Stage 8 photo input through metric reconstruction and property alignment.
3. Inputs: standalone still-image room or property directories.
4. Outputs: typed manifests and common metric reconstruction artifacts.
5. Coordinate system: normalized pixels, then right-handed Y-up metric world coordinates.
6. Units: pixels for images and meters for reconstructed geometry.
7. Dependencies: the sibling photo modules and shared Stage 2-6 pipeline.
8. Assumptions: callers supply only still-image directories, never sensor capture archives.
9. Failure modes: imports remain lightweight; runtime dependencies fail in their owning stages.
10. First debugging points: inspect the photo manifest and reconstruction statistics.
"""

from backend.app.pipelines.photo.ingestion import ingest_photo_room
from backend.app.pipelines.photo.models import PhotoCaptureManifest, PhotoRecord

__all__ = ["PhotoCaptureManifest", "PhotoRecord", "ingest_photo_room"]
