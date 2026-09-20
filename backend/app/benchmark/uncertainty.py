"""Uncertainty Interval Audit and Empirical Calibration Framework.

Purpose:
    Audits the structural validity and integrity of predicted uncertainty bounds
    ([lower, upper], positive width, nominal containment). Implements empirical coverage
    evaluation against independent physical ground truth while strictly setting
    CALIBRATION_NOT_EVALUABLE when physical ground truth is absent.

Stage:
    Stage 10 (Frozen System Benchmark + Development Evaluation)

Inputs:
    Reconstruction measurements containing uncertainty bounds and optional physical GT records.

Outputs:
    UncertaintyAuditSummary container with integrity pass rates, interval width distributions,
    and ground-truth empirical coverage ratios.

Units & Coordinate Systems:
    Intervals in meters (m) or square meters (m^2), relative width unitless.

Dependencies:
    dataclasses, typing, backend.app.benchmark.models, backend.app.benchmark.metrics,
    backend.app.benchmark.ground_truth.

Assumptions:
    Intervals cannot be claimed as 'calibrated' without independent physical measurements.
    Calibrating against the pipeline's own predictions is strictly prohibited.

Failure Modes:
    Violations where lower > upper or val < lower are captured and reported in integrity_violations.

First Debugging Points:
    Inspect whether uncertainty_lower and uncertainty_upper fields were populated during measurement.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from backend.app.benchmark.ground_truth import GroundTruthRecord
from backend.app.benchmark.metrics import verify_interval_integrity
from backend.app.benchmark.models import BenchmarkMeasurement


@dataclass
class UncertaintyAuditSummary:
    """Summary record of uncertainty interval integrity and empirical calibration.

    Attributes:
        tier: Evaluated modality name (e.g. lidar, video, photo).
        total_intervals_checked: Count of measurements evaluated for bounds.
        valid_integrity_count: Count of intervals passing lower <= val <= upper and width >= 0.
        integrity_violations: Detailed log of failed interval bounds.
        average_relative_interval_width: Mean value of (upper - lower) / value.
        min_relative_interval_width: Minimum relative interval width.
        max_relative_interval_width: Maximum relative interval width.
        is_calibrated: Boolean indicating whether physical calibration was accomplished.
        calibration_status: 'CALIBRATED' or 'CALIBRATION_NOT_EVALUABLE'.
        empirical_coverage: Fraction of physical GT values falling within predicted intervals.
        notes: Contextual documentation.
    """
    tier: str
    total_intervals_checked: int = 0
    valid_integrity_count: int = 0
    integrity_violations: List[str] = field(default_factory=list)
    average_relative_interval_width: Optional[float] = None
    min_relative_interval_width: Optional[float] = None
    max_relative_interval_width: Optional[float] = None
    is_calibrated: bool = False
    calibration_status: str = "CALIBRATION_NOT_EVALUABLE"
    empirical_coverage: Optional[float] = None
    notes: str = (
        "UNCERTAINTY CALIBRATION REQUIRES INDEPENDENT PHYSICAL GROUND TRUTH. "
        "CALIBRATION NOT EVALUABLE ON UNLABELED REFERENCE DATA."
    )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize audit summary to dictionary."""
        return {
            "tier": self.tier,
            "total_intervals_checked": self.total_intervals_checked,
            "valid_integrity_count": self.valid_integrity_count,
            "integrity_violations": self.integrity_violations,
            "average_relative_interval_width": self.average_relative_interval_width,
            "min_relative_interval_width": self.min_relative_interval_width,
            "max_relative_interval_width": self.max_relative_interval_width,
            "is_calibrated": self.is_calibrated,
            "calibration_status": self.calibration_status,
            "empirical_coverage": self.empirical_coverage,
            "notes": self.notes,
        }


def audit_uncertainty_intervals(
    tier: str,
    measurements: List[BenchmarkMeasurement],
    ground_truth: Optional[List[GroundTruthRecord]] = None,
) -> UncertaintyAuditSummary:
    """Audit uncertainty intervals for logical consistency and empirical GT coverage.

    Parameters:
        tier: String modality name.
        measurements: BenchmarkMeasurement items to audit.
        ground_truth: Optional list of physical ground-truth records.

    Returns:
        UncertaintyAuditSummary documenting integrity and calibration metrics.

    Units / Coordinates:
        Intervals in meters (m) or square meters (m^2).

    Assumptions:
        Measurements without bounds (lower=None, upper=None) are omitted from interval statistics.

    Failure Conditions:
        Missing GT sets calibration_status='CALIBRATION_NOT_EVALUABLE' and is_calibrated=False.

    Dependencies:
        verify_interval_integrity, BenchmarkMeasurement, UncertaintyAuditSummary.

    Debugging Clues:
        Check measurement.uncertainty_lower and uncertainty_upper assignments.
    """
    total = 0
    valid_count = 0
    violations = []
    rel_widths = []

    for m in measurements:
        if m.uncertainty_lower is None or m.uncertainty_upper is None or m.predicted_value is None:
            continue

        total += 1
        low = m.uncertainty_lower
        up = m.uncertainty_upper
        val = m.predicted_value

        if verify_interval_integrity(low, val, up):
            valid_count += 1
            span = up - low
            if val > 1e-6:
                rel_widths.append(span / val)
        else:
            violations.append(
                f"{m.measurement_id} ({m.type}): val={val}, bounds=[{low}, {up}] violates integrity"
            )

    avg_rel = round(sum(rel_widths) / len(rel_widths), 4) if rel_widths else None
    min_rel = round(min(rel_widths), 4) if rel_widths else None
    max_rel = round(max(rel_widths), 4) if rel_widths else None

    # Evaluate empirical coverage only if independent ground truth is supplied
    coverage: Optional[float] = None
    calibrated = False
    cal_status = "CALIBRATION_NOT_EVALUABLE"

    if ground_truth and len(ground_truth) > 0:
        gt_map = {f"{r.room_id}_{r.measurement_type}_{r.measurement_id}": r.value for r in ground_truth}
        inside_count = 0
        tested_count = 0
        for m in measurements:
            key = f"{m.room_id}_{m.type}_{m.measurement_id}"
            if key in gt_map and m.uncertainty_lower is not None and m.uncertainty_upper is not None:
                gt_val = gt_map[key]
                tested_count += 1
                if m.uncertainty_lower <= gt_val <= m.uncertainty_upper:
                    inside_count += 1
        if tested_count > 0:
            coverage = round(inside_count / tested_count, 4)
            calibrated = True
            cal_status = "CALIBRATED"

    return UncertaintyAuditSummary(
        tier=tier,
        total_intervals_checked=total,
        valid_integrity_count=valid_count,
        integrity_violations=violations,
        average_relative_interval_width=avg_rel,
        min_relative_interval_width=min_rel,
        max_relative_interval_width=max_rel,
        is_calibrated=calibrated,
        calibration_status=cal_status,
        empirical_coverage=coverage,
    )
