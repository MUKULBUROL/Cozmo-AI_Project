"""Data models for 2D floor plans, vector topology, and room adjacency."""

from typing import List, Optional, Tuple, Dict, Any
from pydantic import BaseModel, Field
from .geometry import OpeningType


class Point2D(BaseModel):
    x: float = Field(..., description="Floor coordinate X (meters)")
    y: float = Field(..., description="Floor coordinate Y/Z (meters)")


class Wall2D(BaseModel):
    """2D wall segment projected on the floor plane."""
    wall_id: str
    start: Point2D
    end: Point2D
    length_meters: float
    thickness_meters: float = 0.15


class Opening2D(BaseModel):
    """2D opening (door, window) located on a wall."""
    opening_id: str
    wall_id: str
    opening_type: OpeningType
    start: Point2D
    end: Point2D
    width_meters: float


class Room2D(BaseModel):
    """2D representation of a room polygon with interior boundaries."""
    room_id: str
    name: str
    polygon: List[Point2D]
    area_sqm: float
    perimeter_meters: float
    walls: List[Wall2D] = Field(default_factory=list)
    openings: List[Opening2D] = Field(default_factory=list)


class RoomAdjacencyEdge(BaseModel):
    """Topological connection between two adjacent rooms."""
    room_a_id: str
    room_b_id: str
    connecting_opening_id: Optional[str] = None
    is_shared_wall: bool = True
    shared_wall_length_meters: Optional[float] = None


class PropertyFloorPlan(BaseModel):
    """Complete multi-room stitched floor plan."""
    property_id: str
    rooms: List[Room2D] = Field(default_factory=list)
    connections: List[RoomAdjacencyEdge] = Field(default_factory=list)
    total_floor_area_sqm: float
    exterior_footprint_sqm: Optional[float] = None
