"""Benchmark Data Models for Stage 10 System Evaluation.

Purpose:
    Defines standardized enums, dataclasses, and schema contracts for evaluating
    multi-modal architectural reconstruction (LiDAR, Video, Photo) and damage analysis.
    Encapsulates evidence levels, failure categorizations, gate results, measurement
    comparisons, and tier-level benchmark outputs.

Stage:
    Stage 10 (Frozen System Benchmark + Development Evaluation)

Inputs:
    Reconstruction artifacts, geometric metrics, and ground-truth/reference records.

Outputs:
    Structured benchmark data containers serializable to JSON/CSV.

Units & Coordinate Systems:
    Length: meters (m), Area: square meters (m^2), Angle: degrees, Time: seconds (s).
    Coordinate frames follow standard floorplan conventions (+X East/Right, +Y North/Up, +Z Up).

Dependencies:
    Python standard library (dataclasses, enum, typing).

Assumptions:
    Measurements without valid ground-truth comparisons default strictly to NOT_EVALUABLE
    rather than fabricating synthetic or zero errors.

Failure Modes:
    Serialization error if custom non-primitive types are added to details dictionary.

First Debugging Points:
    Verify that evidence_level reflects the true source of reference (GROUND_TRUTH vs CROSS_TIER).
"""

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Dict, List, Optional


class EvidenceLevel(str, Enum):
    """Hierarchy of benchmark reference evidence levels."""
    GROUND_TRUTH = "GROUND_TRUTH"
    CROSS_TIER_REFERENCE = "CROSS_TIER_REFERENCE"
    SYNTHETIC_GROUND_TRUTH = "SYNTHETIC_GROUND_TRUTH"
    INTERNAL_CONSISTENCY = "INTERNAL_CONSISTENCY"
    NOT_EVALUABLE = "NOT_EVALUABLE"


class FailureCategory(str, Enum):
    """Standardized failure categories across all reconstruction and analysis tiers."""
    MISSED = "MISSED"
    PHANTOM = "PHANTOM"
    NOT_EVALUABLE = "NOT_EVALUABLE"
    UNMATCHED = "UNMATCHED"
    INVALID_GEOMETRY = "INVALID_GEOMETRY"
    INSUFFICIENT_COVERAGE = "INSUFFICIENT_COVERAGE"
    REGISTRATION_FAILURE = "REGISTRATION_FAILURE"
    SCALE_FAILURE = "SCALE_FAILURE"
    TOPOLOGY_FAILURE = "TOPOLOGY_FAILURE"
    NONE = "NONE"


class GateStatus(str, Enum):
    """Evaluation status for official assessment challenge gates."""
    PASS = "PASS"
    FAIL = "FAIL"
    NOT_EVALUABLE = "NOT_EVALUABLE"


class SystemStatus(str, Enum):
    """Operational status of a pipeline tier or major functional module."""
    WORKING = "WORKING"
    PROVISIONAL = "PROVISIONAL"
    NOT_EVALUABLE = "NOT_EVALUABLE"
    FAILED = "FAILED"


@dataclass
class BenchmarkMeasurement:
    """Individual geometric or semantic measurement comparison.

    Attributes:
        measurement_id: Unique identifier for the measurement.
        room_id: Room or space identifier associated with the measurement.
        type: Measurement type (e.g., wall_length, door_width, ceiling_height, floor_area).
        predicted_value: Metric value estimated by the reconstruction pipeline.
        reference_value: Ground-truth or cross-tier reference value (if available).
        unit: Unit of measurement (m, m2, count).
        absolute_error: Absolute difference |predicted - reference| (None if reference missing).
        relative_error: Fractional difference |predicted - reference| / reference.
        evidence_level: Source level of the reference value.
        status: Measurement status (e.g., EVALUATED, NOT_EVALUABLE, UNMATCHED, MISSED, PHANTOM).
        uncertainty_lower: Lower bound of 90%/95% confidence interval.
        uncertainty_upper: Upper bound of 90%/95% confidence interval.
        details: Additional contextual metadata (e.g. wall normal, host surface, coordinates).
    """
    measurement_id: str
    room_id: str
    type: str
    predicted_value: Optional[float]
    reference_value: Optional[float]
    unit: str
    absolute_error: Optional[float]
    relative_error: Optional[float]
    evidence_level: EvidenceLevel
    status: str
    uncertainty_lower: Optional[float] = None
    uncertainty_upper: Optional[float] = None
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize measurement to a dictionary."""
        d = asdict(self)
        d["evidence_level"] = self.evidence_level.value
        return d


@dataclass
class BenchmarkGateResult:
    """Evaluation result for an official challenge gate.

    Attributes:
        gate_id: Unique gate identifier (e.g. GATE_OPENING_WIDTH).
        description: Plain-text explanation of the gate criteria.
        result: Gate outcome (PASS, FAIL, NOT_EVALUABLE).
        numerator: Passed observations or actual metric value.
        denominator: Total valid eligible observations or baseline target.
        threshold: Target criterion threshold string.
        evidence_level: Evidence basis supporting the gate decision.
        reasons: Bulleted justification or failure explanations.
    """
    gate_id: str
    description: str
    result: GateStatus
    numerator: Optional[float]
    denominator: Optional[float]
    threshold: Optional[str]
    evidence_level: EvidenceLevel
    reasons: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize gate result to a dictionary."""
        d = asdict(self)
        d["result"] = self.result.value
        d["evidence_level"] = self.evidence_level.value
        return d


@dataclass
class TierBenchmarkResult:
    """Benchmark evaluation summary for a specific reconstruction tier.

    Attributes:
        capture_id: Scan or capture identifier.
        tier: Modality name (lidar, video, photo, damage).
        status: Overall tier operational status.
        measurements: List of individual benchmark measurements.
        failures: List of failure categories encountered.
        runtime: Execution runtime in seconds.
        coverage: Ratio of applicable structural elements successfully produced (0.0 to 1.0).
        gates: List of evaluated challenge gates applicable to this tier.
        details: Stage-by-stage runtime, feature counts, and diagnostic telemetry.
    """
    capture_id: str
    tier: str
    status: SystemStatus
    measurements: List[BenchmarkMeasurement] = field(default_factory=list)
    failures: List[str] = field(default_factory=list)
    runtime: float = 0.0
    coverage: float = 0.0
    gates: List[BenchmarkGateResult] = field(default_factory=list)
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize tier benchmark result to a dictionary."""
        return {
            "capture_id": self.capture_id,
            "tier": self.tier,
            "status": self.status.value,
            "measurements": [m.to_dict() for m in self.measurements],
            "failures": self.failures,
            "runtime": self.runtime,
            "coverage": self.coverage,
            "gates": [g.to_dict() for g in self.gates],
            "details": self.details,
        }
