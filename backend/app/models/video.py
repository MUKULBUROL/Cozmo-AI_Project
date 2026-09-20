"""Stage 7 Video Tier data models and schema definitions.

1. Why this file exists:
   Defines the domain contracts for video-only reconstruction, ensuring that ordinary
   handheld iPhone RGB video (.mp4, .mov) can be ingested, keyframed, reconstructed via
   visual SfM, and scaled to metric dimensions without requiring or reading LiDAR/ARKit data.

2. Pipeline stage:
   Stage 7 (Handheld iPhone RGB Video -> Metric 3D -> Shared Geometry Pipeline).

3. Inputs:
   Metadata parsed from video streams, keyframe selectors, visual SfM, and metric depth estimators.

4. Outputs:
   Typed Pydantic models for video capture metadata, keyframes, camera intrinsics,
   visual camera poses, and robust metric scale estimates.

5. Coordinate convention:
   - Image space: Pixel coordinates (u, v) with top-left origin (0,0).
   - Camera space: OpenCV standard (X right, Y down, Z forward) or ARKit (X right, Y up, Z forward).
   - World space: Metric coordinates in meters, right-handed with Z up for floorplan representation.

6. Unit convention:
   - Time: Seconds (timestamps, video duration).
   - Angles: Degrees for rotation metadata (0, 90, 180, 270) and radians for orientations.
   - Scale factor: Metric conversion multiplier (meters per SfM arbitrary unit).
   - Uncertainty: Standard deviations in meters or dimensionless relative uncertainty.

7. Important dependencies:
   pydantic, typing, pathlib.

8. Assumptions:
   Video tier receives RGB video files without accompanying depth or odometry files.

9. Main failure modes:
   - Inconsistent frame counts or dimensions in metadata.
   - Non-positive scale factor or degenerate uncertainty values.

10. What a developer should inspect first when debugging:
    Inspect `VideoCaptureMetadata.orientation_rotation_deg` and `MetricScaleEstimate.status`
    when diagnosing geometry orientation or scaling anomalies.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, computed_field


class VideoCaptureMetadata(BaseModel):
    """Metadata describing the ingested video capture and container stream parameters.

    Purpose:
        Captures resolution, frame rate, duration, and orientation directly from video headers.
    """
    capture_id: str = Field(..., description="Unique identifier for the video capture")
    video_path: str = Field(..., description="Filesystem path to source video file")
    codec: str = Field(default="hevc", description="Video compression codec (e.g., hevc, h264)")
    width: int = Field(..., gt=0, description="Video frame width in pixels")
    height: int = Field(..., gt=0, description="Video frame height in pixels")
    frame_count: int = Field(..., ge=0, description="Total frame count in video stream")
    fps: float = Field(..., gt=0.0, description="Video framerate in frames per second")
    duration_seconds: float = Field(..., ge=0.0, description="Video total duration in seconds")
    file_size_bytes: int = Field(default=0, ge=0, description="Video file size on disk in bytes")
    orientation_rotation_deg: int = Field(default=0, description="Display matrix rotation (0, 90, 180, 270)")
    camera_model_status: str = Field(default="unknown", description="Status of camera intrinsics/calibration")

    @property
    def orientation(self) -> str:
        """Returns string representation of orientation."""
        if self.orientation_rotation_deg == 90:
            return "rotated_90"
        elif self.orientation_rotation_deg == 180:
            return "rotated_180"
        elif self.orientation_rotation_deg == 270:
            return "rotated_270"
        return "portrait" if self.height > self.width else "landscape"

    @computed_field
    @property
    def aspect_ratio(self) -> str:
        """Computes standardized aspect ratio string (e.g. 4:3, 16:9)."""
        gcd_val = _compute_gcd(self.width, self.height)
        w_ratio = self.width // gcd_val
        h_ratio = self.height // gcd_val
        if (w_ratio, h_ratio) in [(4, 3), (16, 9), (3, 2), (1, 1)]:
            return f"{w_ratio}:{h_ratio}"
        return f"{self.width}:{self.height}"


def _compute_gcd(a: int, b: int) -> int:
    """Helper function to calculate greatest common divisor for aspect ratio."""
    while b:
        a, b = b, a % b
    return a if a > 0 else 1


class VideoKeyframe(BaseModel):
    """Metadata representing an individual selected keyframe.

    Purpose:
        Stores frame index, temporal timestamp, sharpness score, and saved image path.
    """
    keyframe_id: int = Field(..., ge=0, description="0-indexed keyframe identifier")
    frame_index: int = Field(..., ge=0, description="Source frame index in video file")
    timestamp: float = Field(..., ge=0.0, description="Timestamp in seconds from video start")
    image_path: str = Field(..., description="File path to saved keyframe JPEG image")
    sharpness_score: float = Field(..., ge=0.0, description="Laplacian variance sharpness metric")
    width: int = Field(..., gt=0, description="Image width in pixels")
    height: int = Field(..., gt=0, description="Image height in pixels")
    selection_reason: str = Field(default="sharpness_stride", description="Selection rationale")


class VideoCameraIntrinsics(BaseModel):
    """Camera intrinsics with provenance tracking for video reconstruction."""
    fx: float = Field(..., gt=0.0, description="Focal length X in pixels")
    fy: float = Field(..., gt=0.0, description="Focal length Y in pixels")
    cx: float = Field(..., gt=0.0, description="Principal point X in pixels")
    cy: float = Field(..., gt=0.0, description="Principal point Y in pixels")
    width: int = Field(..., gt=0, description="Sensor width in pixels")
    height: int = Field(..., gt=0, description="Sensor height in pixels")
    source: str = Field(default="sfm_self_calibration", description="Provenance of intrinsics")
    camera_model: str = Field(default="PINHOLE", description="Camera model type (e.g. PINHOLE, SIMPLE_RADIAL)")
    distortion_coefficients: List[float] = Field(default_factory=list, description="Lens distortion coefficients")
    confidence_status: str = Field(default="GOOD", description="Intrinsics confidence (GOOD, PROVISIONAL, FAILED)")


class SfmCameraPose(BaseModel):
    """Camera pose estimated by visual SfM for a keyframe."""
    model_config = {"extra": "allow"}

    keyframe_id: int = Field(..., description="Keyframe identifier")
    frame_index: int = Field(..., description="Video frame index")
    timestamp: float = Field(..., description="Capture timestamp in seconds")
    # Translation vector
    t_vec: List[float] = Field(default_factory=list, description="Translation vector [tx, ty, tz]")
    # 3x3 Rotation matrix flattened or list of lists
    r_matrix: List[List[float]] = Field(default_factory=list, description="3x3 rotation matrix")
    # Unit quaternion (qw, qx, qy, qz)
    qw: float = Field(1.0, description="Quaternion W")
    qx: float = Field(0.0, description="Quaternion X")
    qy: float = Field(0.0, description="Quaternion Y")
    qz: float = Field(0.0, description="Quaternion Z")
    reprojection_error: float = Field(0.0, description="Mean reprojection error in pixels")
    inlier_count: int = Field(0, description="Number of triangulated 2D-3D inliers")
    is_metric: bool = Field(False, description="True if translation has been scaled to meters")

    @property
    def tx(self) -> float:
        """Return world-frame camera-center X in SfM units or meters when ``is_metric``."""
        return self.t_vec[0] if len(self.t_vec) > 0 else 0.0

    @property
    def ty(self) -> float:
        """Return world-frame camera-center Y in SfM units or meters when ``is_metric``."""
        return self.t_vec[1] if len(self.t_vec) > 1 else 0.0

    @property
    def tz(self) -> float:
        """Return world-frame camera-center Z in SfM units or meters when ``is_metric``."""
        return self.t_vec[2] if len(self.t_vec) > 2 else 0.0

    @property
    def timestamp_seconds(self) -> float:
        """Return the source-video timestamp in seconds for contract compatibility."""
        return self.timestamp



class MetricScaleEstimate(BaseModel):
    """Global metric scale estimate from visual SfM and RGB-predicted metric depth.

    Scale is meters per arbitrary SfM unit. Correspondence counters and optional raw ratios
    preserve the evidence used by MAD rejection; no LiDAR measurement is represented here.
    """
    scale_factor: float = Field(..., gt=0.0, description="Metric multiplier s where X_meters = s * X_sfm")
    supporting_frames: int = Field(..., ge=0, description="Keyframes contributing valid scale correspondences")
    supporting_points: int = Field(..., ge=0, description="Total 3D-depth correspondences used")
    median_ratio: float = Field(..., gt=0.0, description="Median scale ratio")
    mad: float = Field(..., ge=0.0, description="Median Absolute Deviation of scale ratio")
    relative_scale_uncertainty: float = Field(..., ge=0.0, description="Relative uncertainty sigma_s / s")
    status: str = Field(default="GOOD", description="Scale status (GOOD, PROVISIONAL, FAILED)")
    inlier_ratio: float = Field(default=1.0, ge=0.0, le=1.0, description="Ratio of correspondences within MAD gate")
    total_correspondences: int = Field(default=0, ge=0, description="Raw SfM/depth matches before rejection")
    inlier_count: int = Field(default=0, ge=0, description="Correspondences retained by the MAD gate")
    rejected_count: int = Field(default=0, ge=0, description="Correspondences rejected by the MAD gate")
    raw_scale_ratios: List[float] = Field(default_factory=list, description="Raw meters-per-SfM-unit ratios")
