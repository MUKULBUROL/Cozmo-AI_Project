"""Stage 8 photo-only reconstruction data contracts.

1. Why this file exists:
   Defines auditable metadata and quality contracts for ordinary still-image room captures.
2. Pipeline stage:
   Stage 8, from photo ingestion through property stitching.
3. Inputs:
   Pillow EXIF metadata, image-quality measurements, SfM summaries, and room transforms.
4. Outputs:
   Pydantic records serialized into photo manifests and reconstruction reports.
5. Coordinate system:
   Image coordinates use top-left pixel origin; local/global geometry uses right-handed Y-up
   metric world coordinates with XZ as the floor plane.
6. Units:
   Pixels for images, seconds for timestamps, meters for geometry, and degrees for yaw.
7. Dependencies:
   Pydantic and Python standard-library typing.
8. Assumptions:
   Every selected image belongs to one room capture and contains no trusted external pose.
9. Failure modes:
   Invalid dimensions, non-finite quality values, and malformed transforms fail validation.
10. First debugging points:
   Inspect ``photo_manifest.json`` and the rejected-image records before investigating SfM.
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class PhotoQuality(BaseModel):
    """Describe one normalized image's visual usability.

    Values are image-space diagnostics only: sharpness is Laplacian variance, exposure values
    are 0-255 grayscale statistics, and duplicate similarity is a 0-1 perceptual score. Warnings
    are advisory and do not reject difficult images by themselves. Invalid numeric values are
    rejected by Pydantic; inspect the source decode when that occurs.
    """

    sharpness: float = Field(..., ge=0.0)
    mean_luminance: float = Field(..., ge=0.0, le=255.0)
    dark_fraction: float = Field(..., ge=0.0, le=1.0)
    bright_fraction: float = Field(..., ge=0.0, le=1.0)
    duplicate_similarity: float = Field(default=0.0, ge=0.0, le=1.0)
    warnings: List[str] = Field(default_factory=list)


class PhotoRecord(BaseModel):
    """Represent one accepted still image and its normalized processing copy.

    ``image_path`` is the normalized RGB image consumed by SfM and depth inference; dimensions
    distinguish the original encoded orientation from the EXIF-transposed processing image.
    Focal lengths are optional because synthetic and privacy-stripped JPEGs commonly lack EXIF.
    Decode failures never produce this model and are recorded separately in the manifest.
    """

    photo_id: int = Field(..., ge=0)
    capture_id: str
    room_id: str
    source_path: str
    image_path: str
    original_width: int = Field(..., gt=0)
    original_height: int = Field(..., gt=0)
    width: int = Field(..., gt=0)
    height: int = Field(..., gt=0)
    orientation: int = Field(default=1, ge=1, le=8)
    orientation_transform: str = "identity"
    exif: Dict[str, Any] = Field(default_factory=dict)
    timestamp: Optional[str] = None
    camera_make: Optional[str] = None
    camera_model: Optional[str] = None
    focal_length_mm: Optional[float] = Field(default=None, gt=0.0)
    focal_length_35mm: Optional[float] = Field(default=None, gt=0.0)
    intrinsics_source: str = "sfm_self_calibration"
    quality: PhotoQuality


class PhotoCaptureManifest(BaseModel):
    """Record deterministic room ingestion and every image selection decision.

    Counts refer only to direct children of the requested room directory. ``selected_photos``
    contains 2-8 records in ordinary challenge mode. Rejected/corrupt paths retain reasons so a
    missing image is never silent. A manifest with fewer than two selected images is invalid and
    is not constructed by ingestion.
    """

    capture_id: str
    room_id: str
    input_directory: str
    synthetic_development_set: bool = False
    discovered_count: int = Field(..., ge=0)
    selected_count: int = Field(..., ge=2, le=8)
    selection_policy: str
    selected_photos: List[PhotoRecord]
    omitted_paths: List[str] = Field(default_factory=list)
    rejected_images: List[Dict[str, str]] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


class RoomAlignment(BaseModel):
    """Describe a traceable room-local to property-global rigid floor-plane transform.

    Translation is in XZ meters and yaw is degrees about global Y. Scale remains exactly one
    because each room must already be metric. ``evidence`` names observed connector/shared-feature
    support; inferred transforms are explicitly marked. Invalid scale is rejected by validation.
    """

    room_id: str
    translation_x_m: float = 0.0
    translation_z_m: float = 0.0
    yaw_degrees: float = 0.0
    scale: float = Field(default=1.0, gt=0.0)
    evidence: List[str] = Field(default_factory=list)
    inferred: bool = False
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class PhotoSfmQuality(BaseModel):
    """Summarize photo-specific pose and sparse-geometry coverage gates.

    Ratios are dimensionless because SfM remains arbitrary-scale at this point. Camera spread is
    normalized by sparse-scene extent, point occupancy measures a PCA-plane grid, and image
    coverage combines registration and track support. Failure reasons are stable machine-readable
    codes. Empty or degenerate geometry produces zero scores rather than fabricated coverage.
    """

    matching_strategy: str = "exhaustive"
    connected_components: int = Field(..., ge=0)
    baseline_spread_ratio: float = Field(..., ge=0.0)
    point_distribution_score: float = Field(..., ge=0.0, le=1.0)
    image_coverage_score: float = Field(..., ge=0.0, le=1.0)
    viewpoint_diversity_score: float = Field(..., ge=0.0, le=1.0)
    status: str
    failure_reasons: List[str] = Field(default_factory=list)
