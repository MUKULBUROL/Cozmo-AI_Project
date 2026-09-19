"""Pydantic data models for Stage 3 2D wall projections, candidate corners, and room polygon.

1. Why this file exists:
   Defines validated data structures for the Stage 3 floorplan geometry pipeline,
   including coordinate system metadata, projected wall lines, detected corners,
   and closed polygon boundaries.

2. Pipeline stage:
   Stage 3 (2D Wall Projection & Room Polygon Extraction) - Data Models.

3. Inputs:
   Constructed geometry structures from geometry processing pipeline.

4. Outputs:
   Strictly validated JSON-serializable Pydantic schemas.

5. Coordinate/Unit assumptions:
   Y is vertical, XZ is the horizontal ground plane. Units are meters.

6. Dependencies:
   pydantic, typing.

7. Most likely failure/debugging points:
   Validation errors if coordinates contain NaNs or incorrect list structures.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class CoordinateSystemInfo(BaseModel):
    """Metadata describing the 3D-to-2D projection coordinate frame."""
    vertical_axis: str = Field("Y", description="3D axis pointing vertically upward")
    floor_plane: str = Field("XZ", description="Horizontal floor projection plane")
    unit: str = Field("m", description="Metric distance unit")


class WallExtent2D(BaseModel):
    """Finite 2D wall segment endpoints on the XZ floor plane."""
    wall_id: str
    line: List[float] = Field(..., description="[A, B, C] normalized line equation Ax + Bz + C = 0")
    start: List[float] = Field(..., description="[x, z] start coordinate in meters")
    end: List[float] = Field(..., description="[x, z] end coordinate in meters")
    length_m: float = Field(..., description="Observed finite wall length in meters")
    inlier_count: int = Field(..., description="Supporting 3D point count")
    confidence: float = Field(..., description="Stage 2 structural confidence")


class CandidateCornerRecord(BaseModel):
    """Candidate intersection corner between two walls."""
    id: str
    x: float
    z: float
    wall_ids: List[str]
    distance_to_wall_a_extent_m: float
    distance_to_wall_b_extent_m: float
    angle_deg: float
    is_near_orthogonal: bool
    inferred: bool
    status: str


class RoomPolygonData(BaseModel):
    """Ordered room polygon boundary geometry."""
    vertices: List[List[float]] = Field(..., description="Ordered [[x, z], ...] closed loop")
    closed: bool
    valid: bool
    area_sqm: float
    perimeter_m: float
    corner_ids: List[str] = Field(default_factory=list)
    wall_ids: List[str] = Field(default_factory=list)


class Stage3PolygonResult(BaseModel):
    """Top-level Stage 3 floorplan geometry export contract."""
    scan_id: str
    coordinate_system: CoordinateSystemInfo
    walls: List[WallExtent2D]
    corners: List[CandidateCornerRecord]
    polygon: RoomPolygonData
    quality: Dict[str, Any] = Field(default_factory=dict)
