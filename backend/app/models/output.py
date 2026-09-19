"""Data models defining the exact Challenge Output Contract with honest confidence intervals."""

from enum import Enum
from typing import List, Optional, Generic, TypeVar, Dict, Any
from pydantic import BaseModel, Field
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
    confidence: float = Field(..., ge=0.0, le=1.0, description="Calibrated confidence level (e.g. 0.95 for 95% interval)")
    method: str = Field(..., description="Source/method: e.g. lidar_plane_fit, visual_sfm, monocular_depth_edge")


class DamageClass(str, Enum):
    WATER_STAIN = "water_stain"
    CRACK_STRUCTURAL = "crack_structural"
    CRACK_COSMETIC = "crack_cosmetic"
    MOLD = "mold"
    IMPACT = "impact"
    FIRE_SMOKE = "fire_smoke"
    CORROSION = "corrosion"
    SURFACE_PEELING = "surface_peeling"


class DamageRegion(BaseModel):
    """Metric damage extent linked to a specific physical surface."""
    damage_id: str
    surface_id: str = Field(..., description="Key of the associated wall, ceiling, or floor")
    damage_class: DamageClass
    extent_area: Measurement[float] = Field(..., description="Metric surface area of damage (m2)")
    polygon_on_surface: Optional[List[Point2D]] = Field(default=None, description="2D polygon relative to surface plane")
    concealed_damage_flag: bool = Field(False, description="Flag for concealed damage inside/behind surface")
    concealed_trigger_rule: Optional[str] = Field(None, description="Rule triggering concealed-damage flag")
    scope_line_items: List[str] = Field(default_factory=list, description="Remediation scope items (e.g. 'Drywall replacement 4x8')")


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
    ceiling_height: Measurement[float]
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
