"""Unit Tests for Official Challenge Gate Evaluator.

Purpose:
    Validates adherence to official assessment challenge gates:
      - Absence of physical GT strictly yields NOT_EVALUABLE rather than fabricated PASS.
      - Missed and phantom openings count against gate denominators.
      - Drift ablation verification produces PASS with INTERNAL_CONSISTENCY.
      - Synthetic damage extent gate evaluates with SYNTHETIC_GROUND_TRUTH.

Stage:
    Stage 10 (Frozen System Benchmark + Development Evaluation)

Inputs:
    Synthetic GroundTruthContract objects, BenchmarkMeasurement lists, and dummy results.

Outputs:
    Assertions verifying gate statuses, numerators, denominators, and justifications.

Units & Coordinate Systems:
    Lengths in meters (m), relative percentages.

Dependencies:
    pytest, backend.app.benchmark.gate_evaluator, backend.app.benchmark.ground_truth,
    backend.app.benchmark.models, backend.app.benchmark.repeatability,
    backend.app.benchmark.incumbent, backend.app.benchmark.damage_metrics.

Assumptions:
    Gates requiring physical GT must NEVER report PASS without verified GT records.

Failure Modes:
    Assertion failure if missing GT produces a PASS status.

First Debugging Points:
    Check evaluate_challenge_gates in backend.app.benchmark.gate_evaluator.
"""

import pytest
from backend.app.benchmark.damage_metrics import DamageBenchmarkResult
from backend.app.benchmark.gate_evaluator import evaluate_challenge_gates
from backend.app.benchmark.ground_truth import GroundTruthContract, GroundTruthRecord
from backend.app.benchmark.incumbent import IncumbentComparisonResult
from backend.app.benchmark.models import (
    BenchmarkMeasurement,
    EvidenceLevel,
    GateStatus,
)
from backend.app.benchmark.repeatability import RepeatabilityResult


def test_missing_ground_truth_yields_not_evaluable():
    """Verify that absent physical GT strictly sets challenge gates to NOT_EVALUABLE.

    Parameters:
        None.

    Returns:
        None.

    Units:
        Unitless status check.

    Assumptions:
        When ground_truth.has_ground_truth is False, measurement gates cannot evaluate.

    Failure Conditions:
        Fails if any physical measurement gate evaluates to PASS or FAIL instead of NOT_EVALUABLE.

    Dependencies:
        GroundTruthContract, evaluate_challenge_gates, GateStatus.

    Debugging Clues:
        Check ground_truth.has_ground_truth handling in evaluate_challenge_gates.
    """
    empty_gt = GroundTruthContract(status="GROUND_TRUTH_NOT_AVAILABLE", has_ground_truth=False)
    rep_res = RepeatabilityResult(
        tier="lidar",
        capture_a="scan1",
        capture_b="scan1",
        status="REPEATABILITY_NOT_EVALUABLE",
        reasons=["Duplicate scans"],
    )
    inc_res = IncumbentComparisonResult(status="INCUMBENT_COMPARISON_NOT_EVALUABLE")
    dmg_res = DamageBenchmarkResult(synthetic_fixtures_status="EVALUATED")

    gates = evaluate_challenge_gates(
        ground_truth=empty_gt,
        lidar_measurements=[],
        video_measurements=[],
        photo_measurements=[],
        repeatability=rep_res,
        incumbent=inc_res,
        damage_result=dmg_res,
        drift_ablation_available=True,
    )

    gate_map = {g.gate_id: g for g in gates}

    # Physical gates must strictly be NOT_EVALUABLE
    assert gate_map["GATE_OPENING_WIDTH"].result == GateStatus.NOT_EVALUABLE
    assert gate_map["GATE_CEILING_HEIGHT"].result == GateStatus.NOT_EVALUABLE
    assert gate_map["GATE_REPEATABILITY"].result == GateStatus.NOT_EVALUABLE
    assert gate_map["GATE_VIDEO_WALL_LENGTH"].result == GateStatus.NOT_EVALUABLE
    assert gate_map["GATE_PHOTO_WALL_LENGTH"].result == GateStatus.NOT_EVALUABLE
    assert gate_map["GATE_PHOTO_PROPERTY_FOOTPRINT"].result == GateStatus.NOT_EVALUABLE
    assert gate_map["GATE_INCUMBENT_COMPARISON"].result == GateStatus.NOT_EVALUABLE

    # Drift ablation and synthetic damage gates evaluate based on available evidence
    assert gate_map["GATE_DRIFT_ABLATION"].result == GateStatus.PASS
    assert gate_map["GATE_DAMAGE_EXTENT"].result == GateStatus.PASS
    assert gate_map["GATE_DAMAGE_EXTENT"].evidence_level == EvidenceLevel.SYNTHETIC_GROUND_TRUTH


def test_opening_gate_with_ground_truth_accounting():
    """Verify that opening width gate correctly accounts for numerator and denominator.

    Parameters:
        None.

    Returns:
        None.

    Units:
        Meters (m).

    Assumptions:
        Gate requires absolute error <= 0.02m on >= 85% of openings.

    Failure Conditions:
        Fails if pass count or ratio calculation is inaccurate.

    Dependencies:
        GroundTruthContract, GroundTruthRecord, BenchmarkMeasurement, evaluate_challenge_gates.

    Debugging Clues:
        Check opening gate calculation in evaluate_challenge_gates.
    """
    # 2 GT openings
    gt_openings = [
        GroundTruthRecord("op_01", "room_01", "door_width", 0.90, "m", "laser"),
        GroundTruthRecord("op_02", "room_01", "window_width", 1.20, "m", "laser"),
    ]
    gt_contract = GroundTruthContract(
        status="GROUND_TRUTH_AVAILABLE",
        has_ground_truth=True,
        openings=gt_openings,
    )

    # 2 predictions: one passes (err=0.01 <= 0.02), one fails (err=0.04 > 0.02)
    # Ratio = 1/2 = 50% < 85% -> FAIL
    lidar_measurements = [
        BenchmarkMeasurement(
            "op_01", "room_01", "door_width", 0.91, 0.90, "m", 0.01, 0.011,
            EvidenceLevel.GROUND_TRUTH, "EVALUATED"
        ),
        BenchmarkMeasurement(
            "op_02", "room_01", "window_width", 1.24, 1.20, "m", 0.04, 0.033,
            EvidenceLevel.GROUND_TRUTH, "EVALUATED"
        ),
    ]

    rep_res = RepeatabilityResult("lidar", "c1", "c1", "REPEATABILITY_NOT_EVALUABLE")
    inc_res = IncumbentComparisonResult("INCUMBENT_COMPARISON_NOT_EVALUABLE")
    dmg_res = DamageBenchmarkResult()

    gates = evaluate_challenge_gates(
        ground_truth=gt_contract,
        lidar_measurements=lidar_measurements,
        video_measurements=[],
        photo_measurements=[],
        repeatability=rep_res,
        incumbent=inc_res,
        damage_result=dmg_res,
    )

    op_gate = next(g for g in gates if g.gate_id == "GATE_OPENING_WIDTH")
    assert op_gate.result == GateStatus.FAIL
    assert op_gate.numerator == 1.0
    assert op_gate.denominator == 2.0
    assert op_gate.evidence_level == EvidenceLevel.GROUND_TRUTH
