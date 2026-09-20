"""Stage 8 deterministic tests for unordered-photo SfM policy and coverage gates.

1. Why this file exists: verifies exhaustive matching configuration and honest weak-geometry status.
2. Pipeline stage: Stage 8 photo feature matching and sparse reconstruction.
3. Inputs: synthetic contracts only; no pycolmap process runs in normal unit tests.
4. Outputs: assertions over policy and quality reason codes.
5. Coordinate system: arbitrary right-handed SfM coordinates.
6. Units: arbitrary SfM positions and pixel reprojection errors.
7. Dependencies: NumPy, pytest, and Stage 7/8 Pydantic contracts.
8. Assumptions: synthetic poses model world-from-camera centers.
9. Failure modes: score or gate regressions fail explicit assertions.
10. First debugging points: inspect the generated report fields and reason-code thresholds.
"""

from backend.app.pipelines.photo.sfm import assess_photo_geometry, photo_sfm_configuration
from backend.app.pipelines.video.contract import (
    SfMReconstructionReport,
    VideoCameraPose,
    VideoReconstructionStatus,
)


def _pose(identifier: int, x: float) -> VideoCameraPose:
    """Build one arbitrary-scale identity pose for gate tests.

    ``x`` is an arbitrary SfM coordinate, not meters. The helper returns a valid shared pose and
    assumes identity rotation; construction errors indicate a test contract regression.
    """
    return VideoCameraPose(
        keyframe_id=identifier,
        frame_index=identifier,
        timestamp_seconds=float(identifier),
        timestamp=float(identifier),
        tx=x,
        ty=0.0,
        tz=0.0,
        t_vec=[x, 0.0, 0.0],
        r_matrix=[[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
        qw=1.0,
        qx=0.0,
        qy=0.0,
        qz=0.0,
    )


def test_photo_matching_configuration_is_exhaustive() -> None:
    """Require all unordered image pairs and prohibit temporal adjacency assumptions."""
    config = photo_sfm_configuration(8)
    assert config["matching_strategy"] == "exhaustive"
    assert config["pair_count"] == 28
    assert config["uses_temporal_adjacency"] is False


def test_two_view_geometry_is_reported_provisional() -> None:
    """Keep a mathematically populated two-view model explicitly poorly constrained."""
    report = SfMReconstructionReport(
        capture_id="two_view",
        total_keyframes=2,
        registered_keyframes=2,
        registration_ratio=1.0,
        sparse_point_count=40,
        mean_reprojection_error=0.5,
        track_length_mean=2.0,
        status=VideoReconstructionStatus.PROVISIONAL,
        reconstruction_time_seconds=0.1,
    )
    points = [
        {"xyz": [float(i % 5), float((i // 5) % 4), float(i // 20)], "track": []}
        for i in range(40)
    ]
    quality = assess_photo_geometry(report, [_pose(0, 0.0), _pose(1, 1.0)], points, 1)
    assert quality.status == "PROVISIONAL"
    assert "two_view_reconstruction_poorly_constrained" in quality.failure_reasons


def test_tiny_baseline_fails_coverage_reason() -> None:
    """Flag cameras from effectively one viewpoint even when sparse point count is high."""
    report = SfMReconstructionReport(
        capture_id="tiny_baseline",
        total_keyframes=4,
        registered_keyframes=4,
        registration_ratio=1.0,
        sparse_point_count=80,
        mean_reprojection_error=0.4,
        track_length_mean=3.0,
        status=VideoReconstructionStatus.GOOD,
        reconstruction_time_seconds=0.1,
    )
    points = [{"xyz": [float(i % 10), float(i // 10), float(i % 3)], "track": []} for i in range(80)]
    poses = [_pose(index, index * 1e-5) for index in range(4)]
    quality = assess_photo_geometry(report, poses, points, 1)
    assert "insufficient_baseline" in quality.failure_reasons
    assert quality.status == "PROVISIONAL"
