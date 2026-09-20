"""Data models for visual damage perception, 3D metric extent, and repair scope.

1. Why this file exists:
   Defines standardized, machine-readable Pydantic data schemas for Stage 9 damage
   inspection. Standardizes 2D image observations, 3D metric regions on structural
   surfaces, rule-based concealed damage risk flags, image quality assessments,
   and deterministic repair scope line items across LiDAR, Video, and Photo tiers.

2. Pipeline stage:
   Stage 9 (Damage Detection, Metric Extent, Concealed-Damage Rules & Repair Scope).

3. Inputs:
   Downstream vision perception outputs, 3D plane projection coordinates, metric
   measurements, rule engine flags, and scope line items.

4. Outputs:
   Validated, type-safe Pydantic models for pipeline processing and JSON serialization.

5. Coordinate convention:
   2D pixel coordinates: (u, v) with origin (0, 0) at top-left of image.
   3D world coordinates: Right-handed metric system (Y-axis upward vertical, XZ ground plane).
   2D surface coordinates: Local orthonormal planar coordinates (u_local, v_local) on host plane.

6. Unit convention:
   Lengths: metric meters (m).
   Areas: metric square meters (m2).
   Confidence scores: dimensionless scalar bounded in [0.0, 1.0].
   Angles: radians / degrees.

7. Dependencies:
   enum, typing, pydantic, numpy (for array conversion if needed).

8. Assumptions:
   - AI models classify semantic damage categories; physical dimensions derive from geometry.
   - Concealed damage is represented as a risk flag and recommendation, never as an empirical diagnosis.
   - Uncertain or unmeasurable extents explicitly return NOT_EVALUABLE or PROVISIONAL statuses.

9. Failure modes:
   - Serialization errors when passing unvalidated numpy arrays instead of Python lists/floats.
   - Inverted bounds in uncertainty intervals (lower_bound > upper_bound).
   - Missing required fields on 3D geometric entities when projection fails.

10. First things to inspect while debugging:
    - Inspect model validation errors when instantiating DamageRegion3D.
    - Check whether lower_bound and upper_bound in Measurement are populated and ordered.
    - Verify that status strings match the DamageStatus enum.
"""

from enum import Enum
from typing import List, Optional, Dict, Any, Tuple
from pydantic import BaseModel, Field, model_validator
from .output import Measurement, DamageClass
from .floorplan import Point2D


class DamageStatus(str, Enum):
    """Lifecycle and geometric validity status of a damage detection."""
    ACCEPTED = "ACCEPTED"
    PROVISIONAL = "PROVISIONAL"
    UNCERTAIN = "UNCERTAIN"
    REJECTED = "REJECTED"
    NOT_EVALUABLE = "NOT_EVALUABLE"


class DamageQualityStatus(str, Enum):
    """Quality gate validation status for an RGB input image."""
    USABLE = "USABLE"
    PROVISIONAL = "PROVISIONAL"
    REJECTED = "REJECTED"


class SurfaceType(str, Enum):
    """Structural host surface classification."""
    WALL = "wall"
    FLOOR = "floor"
    CEILING = "ceiling"
    OPENING_JAMB = "opening_jamb"
    OTHER = "other"


class DamageQualityGate(BaseModel):
    """Image quality assessment metrics for a frame before damage inference."""
    image_id: str = Field(..., description="Unique frame or image identifier")
    status: DamageQualityStatus = Field(..., description="Quality acceptance status")
    sharpness_score: float = Field(..., description="Laplacian variance focus score")
    mean_brightness: float = Field(..., ge=0.0, le=255.0, description="Average pixel luminance")
    contrast_score: float = Field(..., description="Luminance standard deviation")
    width: int = Field(..., gt=0, description="Image pixel width")
    height: int = Field(..., gt=0, description="Image pixel height")
    rejection_reasons: List[str] = Field(default_factory=list, description="Reasons if rejected or provisional")


class DamageFrame(BaseModel):
    """Cross-tier unified RGB observation frame metadata."""
    capture_id: str = Field(..., description="Scan or session identifier")
    tier: str = Field(..., description="Capture modality: 'lidar', 'video', or 'photo'")
    image_id: str = Field(..., description="Frame or still image identifier")
    image_path: str = Field(..., description="Filesystem path to RGB image file")
    depth_path: Optional[str] = Field(None, description="Path to depth map file if available")
    timestamp_seconds: Optional[float] = Field(None, description="Frame capture timestamp")
    camera_pose: Optional[Dict[str, Any]] = Field(None, description="6D camera pose dictionary (position, quaternion)")
    intrinsics: Optional[Dict[str, Any]] = Field(None, description="Camera intrinsics dictionary (fx, fy, cx, cy)")
    quality: Optional[DamageQualityGate] = Field(None, description="Image quality assessment gate result")


class DamageObservation2D(BaseModel):
    """Raw 2D visual damage detection and segmentation in an individual image."""
    observation_id: str = Field(..., description="Unique 2D observation identifier")
    image_id: str = Field(..., description="Source frame or image identifier")
    capture_id: str = Field(..., description="Parent capture identifier")
    tier: str = Field(..., description="Capture modality tier")
    class_name: str = Field(..., description="Raw detected semantic class name")
    canonical_class: DamageClass = Field(..., description="Mapped canonical damage class")
    class_confidence: float = Field(..., ge=0.0, le=1.0, description="Detection confidence score")
    bbox: List[float] = Field(..., description="Bounding box [x1, y1, x2, y2] in pixel coordinates")
    mask_area_pixels: int = Field(..., ge=0, description="Total positive pixels in binary segmentation mask")
    segmentation_confidence: float = Field(..., ge=0.0, le=1.0, description="Segmentation boundary confidence")
    boundary_polygon: Optional[List[List[float]]] = Field(default=None, description="2D pixel contour coordinates [[u, v], ...]")
    is_clipped_by_border: bool = Field(False, description="True if bounding box/mask intersects image boundary")
    view_angle_deg: Optional[float] = Field(None, description="Angle between camera ray and host plane normal in degrees")


class ConcealedDamageFlag(BaseModel):
    """Deterministic risk flag for concealed or secondary property issues."""
    rule_id: str = Field(..., description="Unique identifier of the rule that fired")
    damage_id: str = Field(..., description="ID of the supporting visible damage region")
    suspected_issue: str = Field(..., description="Human-readable suspected concealed issue")
    evidence: str = Field(..., description="Observable evidence basis triggering this rule")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Rule confidence weight")
    requires_inspection: bool = Field(True, description="Strictly true: always requires physical inspection")
    inspection_recommendation: str = Field(..., description="Actionable protocol recommendation (e.g. moisture probe)")
    is_risk_flag_only: bool = Field(True, description="Strictly true: flags risk, never asserts unseen factual reality")


class ScopeLineItem(BaseModel):
    """Deterministic remediation scope item derived from visible damage and metric extent."""
    line_item_id: str = Field(..., description="Unique scope line item identifier")
    damage_id: str = Field(..., description="Reference to the underlying damage region")
    action: str = Field(..., description="Remediation or diagnostic action (e.g. 'Drywall removal', 'Moisture survey')")
    target_surface: str = Field(..., description="Associated structural surface description or surface_id")
    quantity: Optional[float] = Field(None, description="Physical quantity from metric geometry, null if unmeasurable")
    unit: str = Field(..., description="Unit of measure: 'm2', 'linear_m', 'count', 'inspection'")
    basis: str = Field(..., description="Evidence basis justifying this scope item")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence in scope recommendation")
    inspection_required: bool = Field(True, description="Flag indicating prerequisite physical inspection")


class DamageRegion3D(BaseModel):
    """Fused 3D metric damage region attached to a verified structural surface."""
    damage_id: str = Field(..., description="Unique 3D damage identifier")
    damage_class: DamageClass = Field(..., description="Canonical damage category")
    class_confidence: float = Field(..., ge=0.0, le=1.0, description="Fused semantic confidence")
    host_surface_id: str = Field(..., description="Identifier of host structural wall, floor, or ceiling")
    host_surface_type: SurfaceType = Field(..., description="Structural classification of the host surface")
    host_room_id: Optional[str] = Field(None, description="Associated room identifier if localized")
    centroid_3d: List[float] = Field(..., description="3D world coordinates [x, y, z] of damage center in meters")
    polygon_3d: Optional[List[List[float]]] = Field(default=None, description="3D boundary coordinates in world meters")
    polygon_on_surface: Optional[List[Point2D]] = Field(default=None, description="2D polygon in host plane local coordinates")
    metric_area: Optional[Measurement[float]] = Field(None, description="Surface area measurement (m2), null for purely linear damage")
    metric_length: Optional[Measurement[float]] = Field(None, description="Linear crack length measurement (m), null for area damage")
    status: DamageStatus = Field(..., description="Overall damage validation status")
    supporting_observations: List[str] = Field(default_factory=list, description="Observation IDs supporting this 3D region")
    supporting_images: List[str] = Field(default_factory=list, description="Image IDs observing this damage")
    measurement_spread_m2: Optional[float] = Field(None, description="Variance or spread across multi-view area observations")
    best_image_id: Optional[str] = Field(None, description="Image ID of optimal viewing angle/sharpness")
    concealed_flags: List[ConcealedDamageFlag] = Field(default_factory=list, description="Associated concealed damage risk flags")
    scope_line_items: List[ScopeLineItem] = Field(default_factory=list, description="Generated repair scope line items")
