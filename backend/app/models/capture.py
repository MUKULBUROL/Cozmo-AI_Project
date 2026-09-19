"""Data models for raw sensor captures and metadata across iPhone input tiers."""

from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class CaptureTier(str, Enum):
    PHOTO = "photo"
    VIDEO = "video"
    LIDAR = "lidar"


class CameraIntrinsics(BaseModel):
    """Pinhole camera intrinsic parameters."""
    fx: float = Field(..., description="Focal length along X axis in pixels")
    fy: float = Field(..., description="Focal length along Y axis in pixels")
    cx: float = Field(..., description="Principal point X coordinate in pixels")
    cy: float = Field(..., description="Principal point Y coordinate in pixels")
    width: int = Field(..., description="Image width in pixels")
    height: int = Field(..., description="Image height in pixels")
    distortion_center_x: Optional[float] = None
    distortion_center_y: Optional[float] = None


class Pose6D(BaseModel):
    """6-DoF camera pose in world coordinate system (ARKit Y-up, right-handed)."""
    timestamp: float = Field(..., description="Capture timestamp in seconds")
    frame_index: int = Field(..., description="Zero-indexed frame identifier")
    # Translation (meters)
    x: float
    y: float
    z: float
    # Rotation (unit quaternion)
    qx: float
    qy: float
    qz: float
    qw: float
    # Per-frame intrinsics if dynamic
    intrinsics: Optional[CameraIntrinsics] = None


class IMUReading(BaseModel):
    """High-frequency IMU linear acceleration and angular velocity."""
    timestamp: float
    a_x: float = Field(..., description="Acceleration X (g)")
    a_y: float = Field(..., description="Acceleration Y (g, gravity along -Y)")
    a_z: float = Field(..., description="Acceleration Z (g)")
    alpha_x: float = Field(..., description="Angular velocity X (rad/s)")
    alpha_y: float = Field(..., description="Angular velocity Y (rad/s)")
    alpha_z: float = Field(..., description="Angular velocity Z (rad/s)")


class FrameMetadata(BaseModel):
    """Metadata for an individual synchronized frame."""
    frame_index: int
    timestamp: float
    has_rgb: bool = True
    has_depth: bool = False
    has_confidence: bool = False
    depth_path: Optional[str] = None
    confidence_path: Optional[str] = None
    pose: Optional[Pose6D] = None


class RawCaptureSession(BaseModel):
    """Represents an ingested capture session before reconstruction."""
    capture_id: str
    property_id: str
    room_id: Optional[str] = None
    tier: CaptureTier
    video_path: Optional[str] = None
    photo_paths: List[str] = Field(default_factory=list)
    frames: List[FrameMetadata] = Field(default_factory=list)
    global_intrinsics: Optional[CameraIntrinsics] = None
    imu_readings: List[IMUReading] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
