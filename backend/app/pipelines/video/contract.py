"""Stage 7 video reconstruction contract and data models.

1. Why this file exists:
   Defines the formal data contracts, metadata structures, and status enumerations for
   the video input tier. Guarantees that video reconstruction operates purely on RGB video
   captures without requiring or reading LiDAR sensor depth, ARKit odometry, or confidence maps.

2. Pipeline stage:
   Stage 7 (Handheld iPhone RGB Video -> Metric 3D -> Shared Geometry Pipeline).

3. Inputs:
   Pure RGB video streams (.mp4, .mov) and downstream visual estimation outputs.

4. Outputs:
   Strongly-typed Pydantic models for video capture metadata, keyframe descriptors,
   camera intrinsics, pose quality reports, and metric scale recovery estimates.

5. Coordinate convention:
   - Image space: Pixel coordinates (u, v) with (0,0) at top-left.
   - Camera space: Right-handed convention (X right, Y down or ARKit Y up, Z forward).
   - World space: Metric coordinates in meters, Z upward for structural floorplan alignment.

6. Unit convention:
   - Time: Seconds (timestamps, video duration).
   - Frequency: Frames per second (fps).
   - Dimensions: Pixels (width, height).
   - Geometry: Meters (translations, point clouds, metric depth).

7. Important dependencies:
   pydantic, typing, enum, pathlib.

8. Assumptions:
   Input video is an ordinary consumer RGB video without proprietary metadata dependencies.

9. Main failure modes:
   - Corrupt or unreadable video container.
   - Zero extracted keyframes due to extreme motion blur or corrupted frames.
   - Degenerate scale estimates marked as FAILED status.

10. What a developer should inspect first when debugging:
    Inspect `VideoReconstructionStatus` and `MetricScaleResult.status` to determine
    whether a failure originated in video ingestion, visual SfM, or metric scale recovery.
"""

from enum import Enum
from pathlib import Path
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class VideoReconstructionStatus(str, Enum):
    """Quality status classification for video reconstruction stages."""
    GOOD = "GOOD"
    PROVISIONAL = "PROVISIONAL"
    FAILED = "FAILED"


class VideoOrientation(str, Enum):
    """Orientation classification of video capture frames."""
    LANDSCAPE = "landscape"
    PORTRAIT = "portrait"
    ROTATED_90 = "rotated_90"
    ROTATED_180 = "rotated_180"
    ROTATED_270 = "rotated_270"


class VideoCaptureMetadata(BaseModel):
    """Metadata extracted directly from video container and stream headers.

    Purpose:
        Represents fundamental video stream parameters without reading LiDAR files.
    """
    capture_id: str = Field(..., description="Unique capture identifier")
    video_path: str = Field(..., description="Path to source video file (.mp4 or .mov)")
    frame_count: int = Field(..., ge=0, description="Total number of frames in video stream")
    fps: float = Field(..., gt=0.0, description="Nominal or average frames per second")
    width: int = Field(..., gt=0, description="Frame width in pixels")
    height: int = Field(..., gt=0, description="Frame height in pixels")
    duration_seconds: float = Field(..., ge=0.0, description="Total duration of video in seconds")
    orientation: VideoOrientation = Field(default=VideoOrientation.LANDSCAPE, description="Physical frame orientation")
    codec: str = Field(default="hevc", description="Video compression codec (e.g. hevc, h264)")
    container_format: str = Field(default="mov,mp4,m4a,3gp,3g2,mj2", description="Container format identifier")
    has_optical_metadata: bool = Field(default=False, description="True if EXIF/lens metadata was present in container")


class KeyframeMetadata(BaseModel):
    """Metadata for an individual selected keyframe.

    Purpose:
        Captures temporal, visual quality, and selection provenance for keyframes.
    """
    frame_index: int = Field(..., ge=0, description="0-indexed frame number in source video")
    timestamp_seconds: float = Field(..., ge=0.0, description="Timestamp within video stream in seconds")
    image_path: str = Field(..., description="Relative or absolute path to saved keyframe image")
    width: int = Field(..., gt=0, description="Keyframe image width in pixels")
    height: int = Field(..., gt=0, description="Keyframe image height in pixels")
    sharpness_score: float = Field(..., ge=0.0, description="Laplacian variance sharpness metric")
    selection_reason: str = Field(..., description="Heuristic reason for selecting frame (e.g. motion_stride, sharpest_in_window)")


class KeyframeManifest(BaseModel):
    """Manifest summarizing all extracted keyframes for a video capture."""
    capture_id: str = Field(..., description="Capture identifier")
    total_video_frames: int = Field(..., ge=0, description="Total source video frame count")
    selected_keyframe_count: int = Field(..., ge=0, description="Number of extracted keyframes")
    average_sharpness: float = Field(..., ge=0.0, description="Average Laplacian variance of selected keyframes")
    keyframes: List[KeyframeMetadata] = Field(default_factory=list, description="List of keyframe records")


class VideoCameraPose(BaseModel):
    """Reconstructed camera pose for a registered keyframe.

    Purpose:
        Represents arbitrary-scale or metric camera pose in world coordinates.
    """
    frame_index: int = Field(..., description="Keyframe index")
    timestamp_seconds: float = Field(..., description="Keyframe timestamp")
    # Translation vector
    tx: float = Field(..., description="Translation X")
    ty: float = Field(..., description="Translation Y")
    tz: float = Field(..., description="Translation Z")
    # Rotation unit quaternion (qw, qx, qy, qz)
    qw: float = Field(..., description="Quaternion W component")
    qx: float = Field(..., description="Quaternion X component")
    qy: float = Field(..., description="Quaternion Y component")
    qz: float = Field(..., description="Quaternion Z component")
    is_metric: bool = Field(default=False, description="True if translation has been scaled into meters")


class VideoIntrinsics(BaseModel):
    """Camera intrinsics with provenance tracking."""
    fx: float = Field(..., gt=0.0, description="Focal length X in pixels")
    fy: float = Field(..., gt=0.0, description="Focal length Y in pixels")
    cx: float = Field(..., gt=0.0, description="Principal point X in pixels")
    cy: float = Field(..., gt=0.0, description="Principal point Y in pixels")
    width: int = Field(..., gt=0, description="Sensor width in pixels")
    height: int = Field(..., gt=0, description="Sensor height in pixels")
    provenance: str = Field(..., description="Source of intrinsics: video_metadata, sfm_self_calibration, default_fov")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Confidence in intrinsics accuracy")


class SfMReconstructionReport(BaseModel):
    """Statistical summary of visual SfM camera pose reconstruction."""
    capture_id: str
    total_keyframes: int
    registered_keyframes: int
    registration_ratio: float = Field(..., ge=0.0, le=1.0)
    sparse_point_count: int
    mean_reprojection_error: float
    track_length_mean: float
    status: VideoReconstructionStatus
    reconstruction_time_seconds: float
    warnings: List[str] = Field(default_factory=list)


class MetricScaleResult(BaseModel):
    """Absolute metric scale recovery result relating arbitrary SfM to meters."""
    scale_factor: float = Field(..., gt=0.0, description="Global multiplier converting SfM units to meters")
    supporting_frames: int = Field(..., ge=0, description="Number of keyframes contributing valid depth correspondences")
    supporting_points: int = Field(..., ge=0, description="Total 3D point-to-depth correspondences evaluated")
    median_ratio: float = Field(..., gt=0.0, description="Median scale ratio")
    mad: float = Field(..., ge=0.0, description="Median Absolute Deviation of inlier scale ratios")
    relative_scale_uncertainty: float = Field(..., ge=0.0, description="Relative scale uncertainty (sigma_s / s)")
    status: VideoReconstructionStatus = Field(..., description="Quality status (GOOD, PROVISIONAL, FAILED)")
    inlier_ratio: float = Field(..., ge=0.0, le=1.0, description="Fraction of correspondences retained after outlier rejection")
