"""Core data models and schemas for Floorplan AI."""

from .capture import (
    CaptureTier,
    CameraIntrinsics,
    Pose6D,
    IMUReading,
    FrameMetadata,
    RawCaptureSession,
)
from .reconstruction import (
    BoundingBox3D,
    CameraTrajectory,
    PointCloudSummary,
    ReconstructionResult,
)
from .geometry import (
    SurfaceType,
    PlaneEquation,
    WallSegment3D,
    OpeningType,
    Opening3D,
    RoomGeometry3D,
)
from .floorplan import (
    Point2D,
    Wall2D,
    Opening2D,
    Room2D,
    RoomAdjacencyEdge,
    PropertyFloorPlan,
)
from .output import (
    Measurement,
    DamageClass,
    DamageRegion,
    DimensionedOpening,
    DimensionedWall,
    DimensionedRoom,
    PropertyPlanOutput,
)
from .room_polygon import (
    CoordinateSystemInfo,
    WallExtent2D,
    CandidateCornerRecord,
    RoomPolygonData,
    Stage3PolygonResult,
)

__all__ = [
    "CaptureTier",
    "CameraIntrinsics",
    "Pose6D",
    "IMUReading",
    "FrameMetadata",
    "RawCaptureSession",
    "BoundingBox3D",
    "CameraTrajectory",
    "PointCloudSummary",
    "ReconstructionResult",
    "SurfaceType",
    "PlaneEquation",
    "WallSegment3D",
    "OpeningType",
    "Opening3D",
    "RoomGeometry3D",
    "Point2D",
    "Wall2D",
    "Opening2D",
    "Room2D",
    "RoomAdjacencyEdge",
    "PropertyFloorPlan",
    "Measurement",
    "DamageClass",
    "DamageRegion",
    "DimensionedOpening",
    "DimensionedWall",
    "DimensionedRoom",
    "PropertyPlanOutput",
    "CoordinateSystemInfo",
    "WallExtent2D",
    "CandidateCornerRecord",
    "RoomPolygonData",
    "Stage3PolygonResult",
]
