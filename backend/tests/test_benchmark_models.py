"""Unit Tests for Benchmark Data Models and Serialization Contracts.

Purpose:
    Validates data structures, enums, evidence levels, failure categories, and serialization
    fidelity for BenchmarkMeasurement, BenchmarkGateResult, and TierBenchmarkResult.

Stage:
    Stage 10 (Frozen System Benchmark + Development Evaluation)

Inputs:
    Instantiated benchmark models with diverse evidence and failure parameters.

Outputs:
    Assertions verifying enum consistency, dictionary conversion, and null handling.

Units & Coordinate Systems:
    Lengths in meters (m), Areas in square meters (m^2).

Dependencies:
    pytest, backend.app.benchmark.models.

Assumptions:
    Data models preserve exact metric precision and evidence level strings.

Failure Modes:
    Assertion failure if serialization alters enum values or drops metadata keys.

First Debugging Points:
    Check to_dict() implementation in backend.app.benchmark.models.
"""

import pytest
from backend.app.benchmark.models import (
    BenchmarkGateResult,
    BenchmarkMeasurement,
    EvidenceLevel,
    FailureCategory,
    GateStatus,
    SystemStatus,
    TierBenchmarkResult,
)


def test_evidence_level_hierarchy():
    """Verify enum members and string values for EvidenceLevel hierarchy.

    Parameters:
        None.

    Returns:
        None.

    Units:
        Unitless string enumeration.

    Assumptions:
        GROUND_TRUTH, CROSS_TIER_REFERENCE, SYNTHETIC_GROUND_TRUTH, INTERNAL_CONSISTENCY,
        NOT_EVALUABLE must exist without alteration.

    Failure Conditions:
        Fails if any required evidence level is missing.

    Dependencies:
        EvidenceLevel.

    Debugging Clues:
        Check EvidenceLevel definition in backend.app.benchmark.models.
    """
    assert EvidenceLevel.GROUND_TRUTH.value == "GROUND_TRUTH"
    assert EvidenceLevel.CROSS_TIER_REFERENCE.value == "CROSS_TIER_REFERENCE"
    assert EvidenceLevel.SYNTHETIC_GROUND_TRUTH.value == "SYNTHETIC_GROUND_TRUTH"
    assert EvidenceLevel.INTERNAL_CONSISTENCY.value == "INTERNAL_CONSISTENCY"
    assert EvidenceLevel.NOT_EVALUABLE.value == "NOT_EVALUABLE"


def test_benchmark_measurement_serialization():
    """Verify BenchmarkMeasurement serialization retains numerical bounds and evidence level.

    Parameters:
        None.

    Returns:
        None.

    Units:
        Meters (m).

    Assumptions:
        Dictionary conversion produces primitive types compatible with JSON.

    Failure Conditions:
        Fails if fields are missing or if evidence level is not converted to string.

    Dependencies:
        BenchmarkMeasurement, EvidenceLevel.

    Debugging Clues:
        Inspect to_dict output dictionary.
    """
    m = BenchmarkMeasurement(
        measurement_id="wall_01",
        room_id="room_01",
        type="wall_length",
        predicted_value=3.45,
        reference_value=3.50,
        unit="m",
        absolute_error=0.05,
        relative_error=0.0143,
        evidence_level=EvidenceLevel.GROUND_TRUTH,
        status="EVALUATED",
        uncertainty_lower=3.35,
        uncertainty_upper=3.55,
        details={"corner_start": "c1", "corner_end": "c2"},
    )
    d = m.to_dict()
    assert d["measurement_id"] == "wall_01"
    assert d["evidence_level"] == "GROUND_TRUTH"
    assert d["absolute_error"] == 0.05
    assert d["uncertainty_lower"] == 3.35
    assert d["details"]["corner_start"] == "c1"


def test_tier_benchmark_result_serialization():
    """Verify TierBenchmarkResult serialization preserves gate and failure lists.

    Parameters:
        None.

    Returns:
        None.

    Units:
        Seconds (s) for runtime.

    Assumptions:
        Nested lists of measurements and gates are serialized recursively.

    Failure Conditions:
        Fails if nested models fail to serialize to dicts.

    Dependencies:
        TierBenchmarkResult, BenchmarkGateResult, GateStatus, EvidenceLevel, SystemStatus.

    Debugging Clues:
        Check TierBenchmarkResult.to_dict().
    """
    gate = BenchmarkGateResult(
        gate_id="GATE_DRIFT_ABLATION",
        description="Loop closure drift ablation",
        result=GateStatus.PASS,
        numerator=1.0,
        denominator=1.0,
        threshold="required",
        evidence_level=EvidenceLevel.INTERNAL_CONSISTENCY,
        reasons=["Pose graph optimization reduced endpoint drift."],
    )
    tier_res = TierBenchmarkResult(
        capture_id="c7d28f72c6",
        tier="lidar",
        status=SystemStatus.WORKING,
        measurements=[],
        failures=[FailureCategory.NONE.value],
        runtime=22.5,
        coverage=1.0,
        gates=[gate],
        details={"rooms": 4},
    )
    d = tier_res.to_dict()
    assert d["tier"] == "lidar"
    assert d["status"] == "WORKING"
    assert len(d["gates"]) == 1
    assert d["gates"][0]["result"] == "PASS"
    assert d["gates"][0]["evidence_level"] == "INTERNAL_CONSISTENCY"
