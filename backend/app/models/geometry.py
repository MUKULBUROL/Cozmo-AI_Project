"""Data models for structural 3D geometry extracted from point clouds."""

from enum import Enum
from typing import List, Optional, Tuple
from pydantic import BaseModel, Field


class SurfaceType(str, Enum):
    WALL = "wall"
    FLOOR = "floor"
    CEILING = "ceiling"
    DOOR = "door"
    WINDOW = "window"
    OBSTACLE = "obstacle"


class PlaneEquation(BaseModel):
    """Plane equation ax + by + cz + d = 0 with normalized normal [a, b, c]."""
    a: float
    b: float
    c: float
    d: float
    inlier_count: int = Field(0, description="Number of supporting 3D points")
    inlier_rmse: float = Field(..., description="Root-mean-squared error of inlier points (m)")


class WallSegment3D(BaseModel):
    """A fitted 3D vertical wall segment."""
    wall_id: str
    plane: PlaneEquation
    # Bottom endpoints on floor (x, y, z) in meters
    start_point: Tuple[float, float, float]
    end_point: Tuple[float, float, float]
    length_meters: float
    height_meters: float
    thickness_meters: Optional[float] = None
    confidence: float = Field(..., ge=0.0, le=1.0)


class OpeningType(str, Enum):
    DOOR = "door"
    WINDOW = "window"
    PASSAGE = "passage"


class Opening3D(BaseModel):
    """A detected opening in a wall (door or window)."""
    opening_id: str
    wall_id: str
    opening_type: OpeningType
    center_point: Tuple[float, float, float]
    width_meters: float
    height_meters: float
    sill_height_meters: float = Field(0.0, description="Height from floor to bottom of opening")
    confidence: float = Field(..., ge=0.0, le=1.0)


class RoomGeometry3D(BaseModel):
    """Extracted 3D metric geometry for a single enclosed space."""
    room_id: str
    floor_plane: PlaneEquation
    ceiling_plane: Optional[PlaneEquation] = None
    walls: List[WallSegment3D] = Field(default_factory=list)
    openings: List[Opening3D] = Field(default_factory=list)
    clear_ceiling_height_meters: Optional[float] = None
    floor_area_sqm: float
