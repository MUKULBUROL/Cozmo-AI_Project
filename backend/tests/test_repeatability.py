"""Unit Tests for Repeatability Evaluation Framework.

Purpose:
    Validates repeatability evaluation across independent scans:
      - Processing the same raw capture twice strictly yields REPEATABILITY_NOT_EVALUABLE.
      - Official repeatability gate (<= 1cm or <= 0.5%) evaluates accurately across independent pairs.
      - Disclaimers strictly separate repeatability from absolute accuracy/bias.

Stage:
    Stage 10 (Frozen System Benchmark + Development Evaluation)

Inputs:
    Paired wall measurement candidates across identical and distinct capture identifiers.

Outputs:
    Assertions verifying repeatability status, pass ratio, and disclaimer messages.

Units & Coordinate Systems:
    Lengths in meters (m), relative ratios unitless.

Dependencies:
    pytest, backend.app.benchmark.repeatability, backend.app.benchmark.matcher.

Assumptions:
    Repeatability measures inter-scan stability, never absolute physical accuracy.

Failure Modes:
    Assertion failure if identical capture names are allowed to produce an EVALUATED status.

First Debugging Points:
    Check evaluate_repeatability in backend.app.benchmark.repeatability.
"""

import pytest
from backend.app.benchmark.matcher import MeasurementCandidate
from backend.app.benchmark.repeatability import evaluate_repeatability


def test_repeatability_rejects_identical_captures():
    """Verify that using the same capture twice produces REPEATABILITY_NOT_EVALUABLE.

    Parameters:
        None.

    Returns:
        None.

    Units:
        Unitless status check.

    Assumptions:
        Re-running the same raw capture does not constitute repeatability.

    Failure Conditions:
        Fails if capture_a == capture_b evaluates to EVALUATED.

    Dependencies:
        evaluate_repeatability.

    Debugging Clues:
        Check capture name check in evaluate_repeatability.
    """
    candidates = [
        MeasurementCandidate("w1", "room_01", "wall_length", 3.0, 0.0, (0.0, 1.5))
    ]
    res = evaluate_repeatability(
        capture_a_name="scan_01",
        capture_b_name="scan_01",  # Same capture
        candidates_a=candidates,
        candidates_b=candidates,
        tier="lidar",
    )
    assert res.status == "REPEATABILITY_NOT_EVALUABLE"
    assert "Independent repeat physical scans do not exist" in res.reasons[0]
    assert "REPEATABILITY DOES NOT MEASURE ABSOLUTE BIAS" in res.note


def test_repeatability_evaluates_independent_scans():
    """Verify that two distinct independent captures evaluate wall-by-wall repeatability.

    Parameters:
        None.

    Returns:
        None.

    Units:
        Meters (m).

    Assumptions:
        Walls differing by <= 1 cm (0.01m) or <= 0.5% (0.005) pass the gate threshold.

    Failure Conditions:
        Fails if wall difference exceeding threshold is counted as passing.

    Dependencies:
        MeasurementCandidate, evaluate_repeatability.

    Debugging Clues:
        Check gate condition check in evaluate_repeatability.
    """
    c_a = [
        MeasurementCandidate("w1_a", "room_01", "wall_length", 3.000, 0.0, (0.0, 1.5)),
        MeasurementCandidate("w2_a", "room_01", "wall_length", 4.000, 90.0, (2.0, 3.0)),
    ]
    # w1 differs by 0.005m (0.5cm <= 1cm -> PASS)
    # w2 differs by 0.050m (5cm > 1cm and 5cm/4m=1.25% > 0.5% -> FAIL)
    c_b = [
        MeasurementCandidate("w1_b", "room_01", "wall_length", 3.005, 0.0, (0.0, 1.5)),
        MeasurementCandidate("w2_b", "room_01", "wall_length", 4.050, 90.0, (2.0, 3.0)),
    ]

    res = evaluate_repeatability(
        capture_a_name="scan_pass1",
        capture_b_name="scan_pass2",
        candidates_a=c_a,
        candidates_b=c_b,
        tier="lidar",
    )

    assert res.status == "EVALUATED"
    assert res.total_compared_walls == 2
    assert res.walls_within_gate_count == 1
    assert res.gate_pass_ratio == pytest.approx(0.5)
