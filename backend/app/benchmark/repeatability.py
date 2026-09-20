"""Repeatability Evaluation Framework for Identical-Room Multi-Scan Consistency.

Purpose:
    Evaluates geometric consistency between two genuinely independent physical scans
    of the same room acquired using the same pipeline tier. Explicitly decouples
    repeatability (scan A vs scan B) from measurement bias (scan vs physical ground truth)
    and refuses to fabricate repeatability from re-processing the same raw capture.

Stage:
    Stage 10 (Frozen System Benchmark + Development Evaluation)

Inputs:
    Paired measurement candidates from two separate captures of identical space.

Outputs:
    RepeatabilityResult container detailing wall-by-wall discrepancies, pass ratio for
    the official repeatability gate (<= 1 cm or <= 0.5%), and descriptive spread statistics.

Units & Coordinate Systems:
    Discrepancies in meters (m), relative ratios unitless.

Dependencies:
    dataclasses, typing, backend.app.benchmark.models, backend.app.benchmark.matcher,
    backend.app.benchmark.metrics.

Assumptions:
    Re-running the pipeline on identical raw scan data is NOT repeatability. Two distinct
    physical captures are strictly required.

Failure Modes:
    Missing or identical captures return status='REPEATABILITY_NOT_EVALUABLE' with explicit reasons.

First Debugging Points:
    Verify capture_a != capture_b to ensure distinct independent acquisitions.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from backend.app.benchmark.matcher import MeasurementCandidate, match_measurements
from backend.app.benchmark.metrics import (
    compute_absolute_error,
    compute_error_statistics,
    compute_relative_error,
)
from backend.app.benchmark.models import BenchmarkMeasurement, EvidenceLevel


@dataclass
class RepeatabilityResult:
    """Evaluation container for intra-tier repeatability across multiple physical scans.

    Attributes:
        tier: Pipeline tier evaluated (e.g., 'lidar', 'photo').
        capture_a: Identifier of first independent capture.
        capture_b: Identifier of second independent capture.
        status: 'EVALUATED' or 'REPEATABILITY_NOT_EVALUABLE'.
        wall_differences: List of matched wall comparison records.
        walls_within_gate_count: Count of walls satisfying <= 1cm OR <= 0.5% difference.
        total_compared_walls: Total matched walls between captures.
        gate_pass_ratio: Fraction of walls satisfying repeatability threshold (0.0 to 1.0).
        summary_statistics: Residual error statistics (mean, median, rmse, min, max).
        reasons: Diagnostic explanations for status.
        note: Permanent disclaimer differentiating repeatability from accuracy.
    """
    tier: str
    capture_a: Optional[str]
    capture_b: Optional[str]
    status: str
    wall_differences: List[BenchmarkMeasurement] = field(default_factory=list)
    walls_within_gate_count: int = 0
    total_compared_walls: int = 0
    gate_pass_ratio: Optional[float] = None
    summary_statistics: Dict[str, Optional[float]] = field(default_factory=dict)
    reasons: List[str] = field(default_factory=list)
    note: str = (
        "REPEATABILITY EVALUATES INTER-SCAN STABILITY, NOT PHYSICAL ACCURACY. "
        "REPEATABILITY DOES NOT MEASURE ABSOLUTE BIAS."
    )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize repeatability evaluation to dictionary format."""
        return {
            "tier": self.tier,
            "capture_a": self.capture_a,
            "capture_b": self.capture_b,
            "status": self.status,
            "note": self.note,
            "walls_within_gate_count": self.walls_within_gate_count,
            "total_compared_walls": self.total_compared_walls,
            "gate_pass_ratio": self.gate_pass_ratio,
            "summary_statistics": self.summary_statistics,
            "reasons": self.reasons,
            "wall_differences": [m.to_dict() for m in self.wall_differences],
        }


def evaluate_repeatability(
    capture_a_name: Optional[str],
    capture_b_name: Optional[str],
    candidates_a: Optional[List[MeasurementCandidate]],
    candidates_b: Optional[List[MeasurementCandidate]],
    tier: str = "lidar",
) -> RepeatabilityResult:
    """Evaluate geometric repeatability across two independent physical captures.

    Parameters:
        capture_a_name: Name/ID of first capture.
        capture_b_name: Name/ID of second capture.
        candidates_a: Geometric candidates extracted from capture A.
        candidates_b: Geometric candidates extracted from capture B.
        tier: String modality name.

    Returns:
        RepeatabilityResult container detailing wall concordance or non-evaluable status.

    Units / Coordinates:
        Lengths in meters (m).

    Assumptions:
        Official challenge gate criterion: wall dimension agreement within 1 cm (0.01m)
        OR 0.5% (0.005) relative difference.

    Failure Conditions:
        If capture_a_name == capture_b_name or either candidate list is missing/empty,
        returns REPEATABILITY_NOT_EVALUABLE.

    Dependencies:
        match_measurements, compute_absolute_error, compute_relative_error, compute_error_statistics.

    Debugging Clues:
        Check sample dataset audit to confirm if separate independent repeat acquisitions exist.
    """
    if not capture_a_name or not capture_b_name or capture_a_name == capture_b_name:
        return RepeatabilityResult(
            tier=tier,
            capture_a=capture_a_name,
            capture_b=capture_b_name,
            status="REPEATABILITY_NOT_EVALUABLE",
            reasons=[
                "Independent repeat physical scans do not exist in current sample dataset.",
                "Processing the same raw capture twice does not constitute repeatability.",
            ],
        )

    if not candidates_a or not candidates_b:
        return RepeatabilityResult(
            tier=tier,
            capture_a=capture_a_name,
            capture_b=capture_b_name,
            status="REPEATABILITY_NOT_EVALUABLE",
            reasons=["One or both candidate sets are empty."],
        )

    # Filter to wall_length measurements
    walls_a = [c for c in candidates_a if c.measurement_type == "wall_length"]
    walls_b = [c for c in candidates_b if c.measurement_type == "wall_length"]

    pairs = match_measurements(predictions=walls_b, references=walls_a)

    differences: List[BenchmarkMeasurement] = []
    abs_errors: List[float] = []
    within_gate = 0

    for idx, pair in enumerate(pairs):
        if pair.status == "MATCHED" and pair.candidate_a and pair.candidate_b:
            val_b = pair.candidate_a.value
            val_a = pair.candidate_b.value
            abs_err = compute_absolute_error(val_b, val_a)
            rel_err = compute_relative_error(val_b, val_a)
            if abs_err is not None:
                abs_errors.append(abs_err)
                # Gate: within 1 cm (0.01m) OR within 0.5% (0.005)
                is_within = (abs_err <= 0.01) or (rel_err is not None and rel_err <= 0.005)
                if is_within:
                    within_gate += 1

            m = BenchmarkMeasurement(
                measurement_id=f"rep_{tier}_{idx}",
                room_id=pair.candidate_a.room_id,
                type="wall_length",
                predicted_value=val_b,
                reference_value=val_a,
                unit="m",
                absolute_error=round(abs_err, 4) if abs_err is not None else None,
                relative_error=round(rel_err, 4) if rel_err is not None else None,
                evidence_level=EvidenceLevel.INTERNAL_CONSISTENCY,
                status="EVALUATED",
                details={"candidate_a": pair.candidate_b.entity_id, "candidate_b": pair.candidate_a.entity_id},
            )
            differences.append(m)

    total_matched = len(differences)
    pass_ratio = (within_gate / total_matched) if total_matched > 0 else 0.0
    stats = compute_error_statistics(abs_errors)

    return RepeatabilityResult(
        tier=tier,
        capture_a=capture_a_name,
        capture_b=capture_b_name,
        status="EVALUATED" if total_matched > 0 else "REPEATABILITY_NOT_EVALUABLE",
        wall_differences=differences,
        walls_within_gate_count=within_gate,
        total_compared_walls=total_matched,
        gate_pass_ratio=round(pass_ratio, 4) if total_matched > 0 else None,
        summary_statistics=stats,
        reasons=[] if total_matched > 0 else ["No corresponding walls could be matched between captures."],
    )
