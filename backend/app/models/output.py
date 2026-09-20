"""Data models defining the exact Challenge Output Contract with honest confidence intervals.

1. Why this file exists:
   Defines standardized Pydantic data schemas representing reconstructed physical spaces,
   metric measurements, uncertainty intervals, walls, rooms, damages, and full property outputs.

2. Pipeline stage:
   Cross-stage contract (Stages 0, 1, 2, 3, 4, 5) - Core Challenge Deliverable Schema.

3. Inputs:
   Downstream metric measurements, detected planes, segmented openings, and damage regions.

4. Outputs:
   Validated, machine-readable Pydantic models for JSON serialization.

5. Coordinate/Unit assumptions:
   Metric units (meters 'm', square meters 'm2', degrees 'deg').
   Y-axis upward vertical, XZ horizontal ground plane.

6. Dependencies:
   enum, typing, pydantic.

7. Most likely failure/debugging points:
   - Negative lower_bound / inverted intervals (lower_bound > upper_bound).
   - Confidence out of [0.0, 1.0] bounds.
   - NoneType on mandatory geometric fields when measurements fail.
"""

from enum import Enum
from typing import List, Optional, Generic, TypeVar, Dict, Any
from pydantic import BaseModel, Field, model_validator
from .capture import CaptureTier
from .floorplan import Point2D, RoomAdjacencyEdge
from .geometry import OpeningType

T = TypeVar("T")


class Measurement(BaseModel, Generic[T]):
    """Honest measurement representation with calibrated confidence interval."""
    value: T = Field(..., description="Measured nominal value")
    unit: str = Field(..., description="Measurement unit (e.g. 'm', 'm2', 'deg')")
    lower_bound: T = Field(..., description="Lower bound of uncertainty interval")
    upper_bound: T = Field(..., description="Upper bound of uncertainty interval")
    interval: Optional[List[T]] = Field(default=None, description="[lower_bound, upper_bound] interval")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Calibrated confidence level (e.g. 0.95 for 95% interval)")
    method: str = Field(..., description="Source/method: e.g. lidar_plane_fit, visual_sfm, monocular_depth_edge")

    def model_post_init(self, __context: Any) -> None:
        """Synchronizes interval and bound attributes.

        Purpose:
            Ensures interval is populated as [lower_bound, upper_bound] if not passed.

        Parameters:
            __context: Pydantic internal context object.

        Returns:
            None.

        Assumptions:
            lower_bound and upper_bound are of compatible type T.

        Failure conditions:
            None.

        Debugging:
            Inspect self.interval when serializing to JSON.
        """
        if self.interval is None and self.lower_bound is not None and self.upper_bound is not None:
            self.interval = [self.lower_bound, self.upper_bound]


class DamageClass(str, Enum):
    WATER_STAIN = "water_stain"
    CRACK_STRUCTURAL = "crack_structural"
    CRACK_COSMETIC = "crack_cosmetic"
    SURFACE_CRACK = "surface_crack"
    MOLD = "mold"
    MOLD_LIKE_DISCOLORATION = "mold_like_discoloration"
    HOLE_OR_MISSING_MATERIAL = "hole_or_missing_material"
    IMPACT = "impact"
    FIRE_SMOKE = "fire_smoke"
    BURN_OR_CHAR = "burn_or_char"
    SURFACE_BREAKAGE = "surface_breakage"
    CORROSION = "corrosion"
    SURFACE_PEELING = "surface_peeling"
    OTHER_VISIBLE_DAMAGE = "other_visible_damage"


class DamageRegion(BaseModel):
    """Metric damage extent linked to a specific physical surface."""
    damage_id: str
    surface_id: str = Field(..., description="Key of the associated wall, ceiling, or floor")
    damage_class: DamageClass
    extent_area: Optional[Measurement[float]] = Field(default=None, description="Metric surface area of damage (m2)")
    extent_length: Optional[Measurement[float]] = Field(default=None, description="Metric linear length of crack (m)")
    polygon_on_surface: Optional[List[Point2D]] = Field(default=None, description="2D polygon relative to surface plane")
    concealed_damage_flag: bool = Field(False, description="Flag for concealed damage inside/behind surface")
    concealed_trigger_rule: Optional[str] = Field(None, description="Rule triggering concealed-damage flag")
    scope_line_items: List[str] = Field(default_factory=list, description="Remediation scope items (e.g. 'Drywall replacement 4x8')")
    status: str = Field("ACCEPTED", description="Geometric and validation status (ACCEPTED, PROVISIONAL, etc.)")
    confidence: float = Field(0.85, ge=0.0, le=1.0, description="Confidence in damage observation and extent")
    supporting_images: List[str] = Field(default_factory=list, description="Frame identifiers observing this damage")
    concealed_flags: List[Dict[str, Any]] = Field(default_factory=list, description="Structured concealed damage risk flags")
    detailed_scope_items: List[Dict[str, Any]] = Field(default_factory=list, description="Structured repair scope line items")


class DimensionedOpening(BaseModel):
    """Opening with calibrated measurement confidence."""
    opening_id: str
    wall_id: str
    opening_type: OpeningType
    width: Measurement[float]
    height: Optional[Measurement[float]] = None
    sill_height: Optional[Measurement[float]] = None
    position_along_wall: Measurement[float]


class DimensionedWall(BaseModel):
    """Wall with start/end coordinates and calibrated measurement confidence."""
    wall_id: str
    start: Point2D
    end: Point2D
    length: Measurement[float]
    height: Optional[Measurement[float]] = None
    thickness: Measurement[float]
    openings: List[DimensionedOpening] = Field(default_factory=list)


class DimensionedRoom(BaseModel):
    """Per-room floor plan output complying with the challenge schema."""
    room_id: str
    name: str
    floor_area: Measurement[float]
    perimeter: Measurement[float]
    ceiling_height: Optional[Measurement[float]] = Field(default=None, description="Measured clear ceiling height, null if unobserved")
    walls: List[DimensionedWall] = Field(default_factory=list)
    openings: List[DimensionedOpening] = Field(default_factory=list)
    damage_regions: List[DamageRegion] = Field(default_factory=list)


class PropertyPlanOutput(BaseModel):
    """Whole-property stitched floor plan challenge output contract."""
    property_id: str
    capture_id: str
    tier: CaptureTier
    rooms: List[DimensionedRoom] = Field(default_factory=list)
    connections: List[RoomAdjacencyEdge] = Field(default_factory=list)
    total_floor_area: Measurement[float]
    exterior_footprint: Optional[Measurement[float]] = None
    capture_metadata: Dict[str, Any] = Field(default_factory=dict)
    reconstruction_method: str
    stitching_residual_meters: Optional[float] = None
    damage_regions: List[DamageRegion] = Field(default_factory=list, description="All property damage regions")
    concealed_damage_flags: List[Dict[str, Any]] = Field(default_factory=list, description="Whole-property concealed damage risk flags")
    scope_line_items: List[Dict[str, Any]] = Field(default_factory=list, description="Whole-property repair scope line items")

