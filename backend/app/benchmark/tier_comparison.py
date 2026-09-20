"""Cross-Tier Comparison Engine for Multi-Modal Reconstruction Pipelines.

Purpose:
    Compares reconstructed geometry and measurements across modalities (LiDAR ↔ Video,
    LiDAR ↔ Photo, Video ↔ Photo). Explicitly labels all comparisons as CROSS-TIER AGREEMENT
    and NOT GROUND-TRUTH ACCURACY to prevent false evaluation claims.

Stage:
    Stage 10 (Frozen System Benchmark + Development Evaluation)

Inputs:
    Measurement candidate sets from two distinct tiers (e.g., LiDAR vs Video).

Outputs:
    CrossTierComparisonResult container detailing shared matched dimensions, absolute/relative
    differences, room count consistency, and unmatched feature counts.

Units & Coordinate Systems:
    Lengths in meters (m), Areas in square meters (m^2), Discrepancies in meters or fractional ratios.

Dependencies:
    dataclasses, typing, backend.app.benchmark.models, backend.app.benchmark.matcher,
    backend.app.benchmark.metrics.

Assumptions:
    Cross-tier comparisons evaluate inter-pipeline concordance, not physical ground-truth accuracy.

Failure Modes:
    Zero matched dimensions cleanly returns count=0 and status='INSUFFICIENT_OVERLAP'.

First Debugging Points:
    Verify candidates from both tiers are expressed in metric scale (meters).
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
class CrossTierComparisonResult:
    """Comprehensive cross-tier geometric agreement summary.

    Attributes:
        tier_a: Name of first pipeline tier (e.g., 'lidar').
        tier_b: Name of second pipeline tier (e.g., 'video').
        matched_measurements: List of individual matched BenchmarkMeasurement records.
        shared_dimensions_count: Total number of successfully matched dimensions.
        unmatched_a_count: Number of candidate features unique to tier A.
        unmatched_b_count: Number of candidate features unique to tier B.
        room_count_a: Room count reported by tier A.
        room_count_b: Room count reported by tier B.
        statistics: Error statistics (mean, median, rmse, min, max) of absolute discrepancies.
        disclaimer: Mandatory notice emphasizing cross-tier nature of evaluation.
    """
    tier_a: str
    tier_b: str
    matched_measurements: List[BenchmarkMeasurement] = field(default_factory=list)
    shared_dimensions_count: int = 0
    unmatched_a_count: int = 0
    unmatched_b_count: int = 0
    room_count_a: int = 0
    room_count_b: int = 0
    statistics: Dict[str, Optional[float]] = field(default_factory=dict)
    disclaimer: str = "CROSS-TIER AGREEMENT, NOT GROUND-TRUTH ACCURACY"

    def to_dict(self) -> Dict[str, Any]:
        """Serialize comparison result to dictionary format."""
        return {
            "tier_a": self.tier_a,
            "tier_b": self.tier_b,
            "disclaimer": self.disclaimer,
            "shared_dimensions_count": self.shared_dimensions_count,
            "unmatched_a_count": self.unmatched_a_count,
            "unmatched_b_count": self.unmatched_b_count,
            "room_count_a": self.room_count_a,
            "room_count_b": self.room_count_b,
            "statistics": self.statistics,
            "matched_measurements": [m.to_dict() for m in self.matched_measurements],
        }


def compare_tiers(
    tier_a_name: str,
    tier_b_name: str,
    candidates_a: List[MeasurementCandidate],
    candidates_b: List[MeasurementCandidate],
    room_count_a: int = 1,
    room_count_b: int = 1,
) -> CrossTierComparisonResult:
    """Execute pairwise geometric comparison between two pipeline reconstruction tiers.

    Parameters:
        tier_a_name: String name of baseline tier (e.g. 'lidar').
        tier_b_name: String name of comparison tier (e.g. 'video').
        candidates_a: List of MeasurementCandidate items from tier A.
        candidates_b: List of MeasurementCandidate items from tier B.
        room_count_a: Total room count identified by tier A.
        room_count_b: Total room count identified by tier B.

    Returns:
        CrossTierComparisonResult with matched dimensions and residual discrepancy metrics.

    Units / Coordinates:
        Meters (m) for linear features, square meters (m^2) for planar areas.

    Assumptions:
        Tier A acts as reference basis for delta computation, but evidence level is strictly
        CROSS_TIER_REFERENCE.

    Failure Conditions:
        If no candidates match, statistics have count=0 and shared_dimensions_count=0.

    Dependencies:
        match_measurements, compute_absolute_error, compute_relative_error, compute_error_statistics.

    Debugging Clues:
        Check unmatched counts to evaluate coverage divergence between tiers.
    """
    pairs = match_measurements(predictions=candidates_b, references=candidates_a)

    matched_records: List[BenchmarkMeasurement] = []
    abs_errors: List[float] = []
    unmatched_a = 0
    unmatched_b = 0

    for idx, pair in enumerate(pairs):
        if pair.status == "MATCHED" and pair.candidate_a and pair.candidate_b:
            val_b = pair.candidate_a.value
            val_a = pair.candidate_b.value
            abs_err = compute_absolute_error(val_b, val_a)
            rel_err = compute_relative_error(val_b, val_a)
            if abs_err is not None:
                abs_errors.append(abs_err)

            m_record = BenchmarkMeasurement(
                measurement_id=f"cross_{tier_a_name}_{tier_b_name}_{idx}",
                room_id=pair.candidate_a.room_id,
                type=pair.candidate_a.measurement_type,
                predicted_value=val_b,
                reference_value=val_a,
                unit="m" if "area" not in pair.candidate_a.measurement_type else "m2",
                absolute_error=round(abs_err, 4) if abs_err is not None else None,
                relative_error=round(rel_err, 4) if rel_err is not None else None,
                evidence_level=EvidenceLevel.CROSS_TIER_REFERENCE,
                status="EVALUATED",
                details={
                    "tier_a": tier_a_name,
                    "tier_b": tier_b_name,
                    "candidate_a_id": pair.candidate_b.entity_id,
                    "candidate_b_id": pair.candidate_a.entity_id,
                },
            )
            matched_records.append(m_record)
        elif pair.candidate_a is not None and pair.candidate_b is None:
            unmatched_b += 1
        elif pair.candidate_a is None and pair.candidate_b is not None:
            unmatched_a += 1

    stats = compute_error_statistics(abs_errors)

    return CrossTierComparisonResult(
        tier_a=tier_a_name,
        tier_b=tier_b_name,
        matched_measurements=matched_records,
        shared_dimensions_count=len(matched_records),
        unmatched_a_count=unmatched_a,
        unmatched_b_count=unmatched_b,
        room_count_a=room_count_a,
        room_count_b=room_count_b,
        statistics=stats,
        disclaimer="CROSS-TIER AGREEMENT, NOT GROUND-TRUTH ACCURACY",
    )
