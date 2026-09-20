"""Unit Tests for Uncertainty Interval Audits and Empirical Calibration.

Purpose:
    Validates uncertainty interval integrity checking and empirical calibration behavior:
      - Violations (lower > upper or val outside bounds) are detected and logged.
      - Absence of physical GT strictly sets calibration_status to CALIBRATION_NOT_EVALUABLE.
      - Empirical coverage (% of GT inside intervals) evaluates correctly when GT is provided.

Stage:
    Stage 10 (Frozen System Benchmark + Development Evaluation)

Inputs:
    Synthetic BenchmarkMeasurement items with valid and corrupt bounds, and GroundTruthRecord lists.

Outputs:
    Assertions verifying audit counts, violation messages, and calibration status flags.

Units & Coordinate Systems:
    Lengths in meters (m), relative widths unitless.

Dependencies:
    pytest, backend.app.benchmark.uncertainty, backend.app.benchmark.models,
    backend.app.benchmark.ground_truth.

Assumptions:
    Confidence intervals without physical GT must NEVER be claimed as calibrated.

Failure Modes:
    Assertion failure if calibration is marked True without physical GT records.

First Debugging Points:
    Check audit_uncertainty_intervals in backend.app.benchmark.uncertainty.
"""

import pytest
from backend.app.benchmark.ground_truth import GroundTruthRecord
from backend.app.benchmark.models import BenchmarkMeasurement, EvidenceLevel
from backend.app.benchmark.uncertainty import audit_uncertainty_intervals


def test_uncertainty_integrity_and_violations():
    """Verify detection of valid intervals and logging of inverted or corrupt bounds.

    Parameters:
        None.

    Returns:
        None.

    Units:
        Meters (m).

    Assumptions:
        Valid bounds require lower <= nominal <= upper and span >= 0.

    Failure Conditions:
        Fails if corrupt bound is counted in valid_integrity_count.

    Dependencies:
        BenchmarkMeasurement, audit_uncertainty_intervals.

    Debugging Clues:
        Check violation detection in audit_uncertainty_intervals.
    """
    measurements = [
        # Valid interval
        BenchmarkMeasurement(
            "m1", "room_01", "wall_length", 3.0, None, "m", None, None,
            EvidenceLevel.NOT_EVALUABLE, "EVALUATED", uncertainty_lower=2.8, uncertainty_upper=3.2
        ),
        # Inverted interval (lower > upper)
        BenchmarkMeasurement(
            "m2", "room_01", "wall_length", 3.0, None, "m", None, None,
            EvidenceLevel.NOT_EVALUABLE, "EVALUATED", uncertainty_lower=3.5, uncertainty_upper=2.5
        ),
        # Nominal outside interval (val < lower)
        BenchmarkMeasurement(
            "m3", "room_01", "wall_length", 2.0, None, "m", None, None,
            EvidenceLevel.NOT_EVALUABLE, "EVALUATED", uncertainty_lower=2.5, uncertainty_upper=3.0
        ),
    ]

    audit = audit_uncertainty_intervals(tier="lidar", measurements=measurements, ground_truth=None)
    assert audit.total_intervals_checked == 3
    assert audit.valid_integrity_count == 1
    assert len(audit.integrity_violations) == 2
    assert audit.is_calibrated is False
    assert audit.calibration_status == "CALIBRATION_NOT_EVALUABLE"


def test_empirical_calibration_with_ground_truth():
    """Verify empirical calibration coverage when independent physical GT is provided.

    Parameters:
        None.

    Returns:
        None.

    Units:
        Meters (m).

    Assumptions:
        Coverage reflects fraction of GT records that lie within predicted [lower, upper].

    Failure Conditions:
        Fails if empirical coverage is miscalculated.

    Dependencies:
        BenchmarkMeasurement, GroundTruthRecord, audit_uncertainty_intervals.

    Debugging Clues:
        Check ground truth matching in audit_uncertainty_intervals.
    """
    measurements = [
        # GT = 3.05 -> inside [2.9, 3.1]
        BenchmarkMeasurement(
            "wall_01", "room_01", "wall_length", 3.0, None, "m", None, None,
            EvidenceLevel.NOT_EVALUABLE, "EVALUATED", uncertainty_lower=2.9, uncertainty_upper=3.1
        ),
        # GT = 4.30 -> outside [3.8, 4.2]
        BenchmarkMeasurement(
            "wall_02", "room_01", "wall_length", 4.0, None, "m", None, None,
            EvidenceLevel.NOT_EVALUABLE, "EVALUATED", uncertainty_lower=3.8, uncertainty_upper=4.2
        ),
    ]
    gt = [
        GroundTruthRecord("wall_01", "room_01", "wall_length", 3.05, "m", "disto"),
        GroundTruthRecord("wall_02", "room_01", "wall_length", 4.30, "m", "disto"),
    ]

    audit = audit_uncertainty_intervals(tier="lidar", measurements=measurements, ground_truth=gt)
    assert audit.is_calibrated is True
    assert audit.calibration_status == "CALIBRATED"
    assert audit.empirical_coverage == pytest.approx(0.5)  # 1 of 2 inside interval
