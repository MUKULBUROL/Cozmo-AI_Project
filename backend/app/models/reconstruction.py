"""Data models for common intermediate 3D reconstruction results."""

from typing import List, Optional, Dict, Any, Tuple
from pydantic import BaseModel, Field
from .capture import CaptureTier, Pose6D


class BoundingBox3D(BaseModel):
    """Axis-aligned 3D bounding box in metric coordinates."""
    min_x: float
    max_x: float
    min_y: float
    max_y: float
    min_z: float
    max_z: float

    @property
    def width(self) -> float:
        return self.max_x - self.min_x

    @property
    def height(self) -> float:
        return self.max_y - self.min_y

    @property
    def depth(self) -> float:
        return self.max_z - self.min_z


class CameraTrajectory(BaseModel):
    """Optimized camera trajectory with loop closure corrections."""
    poses: List[Pose6D] = Field(default_factory=list)
    accumulated_drift_meters: float = Field(0.0, description="Estimated drift before loop closure")
    loop_closure_detected: bool = False
    loop_residual_meters: Optional[float] = None


class PointCloudSummary(BaseModel):
    """Metadata summary of a dense or sparse 3D point cloud."""
    point_count: int
    has_colors: bool = True
    has_normals: bool = False
    bounds: BoundingBox3D
    voxel_size_meters: Optional[float] = None
    density_pts_per_m3: Optional[float] = None


class ReconstructionResult(BaseModel):
    """Common 3D representation into which PHOTO, VIDEO, and LIDAR tiers converge."""
    reconstruction_id: str
    capture_id: str
    tier: CaptureTier
    point_cloud_summary: PointCloudSummary
    point_cloud_file: Optional[str] = None
    mesh_file: Optional[str] = None
    trajectory: Optional[CameraTrajectory] = None
    scale_factor_applied: float = Field(1.0, description="Metric scale correction factor")
    reconstruction_method: str = Field(..., description="e.g. ARKit_LiDAR, COLMAP_SfM, DepthAnything_SLAM")
    reconstruction_time_seconds: float
    metrics: Dict[str, Any] = Field(default_factory=dict)
