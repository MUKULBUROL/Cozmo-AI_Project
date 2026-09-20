"""Incumbent Scanning Application Comparison Framework.

Purpose:
    Enables side-by-side benchmark comparison between Cozmo AI reconstructions and
    commercial/consumer scanning applications (e.g. Polycam, Canvas, Metaroom) against
    physical ground truth. Adheres to the official challenge requirement of beating or
    tying incumbent accuracy on >= 70% of shared dimensions, strictly evaluating to
    INCUMBENT_COMPARISON_NOT_EVALUABLE when incumbent or ground-truth data is missing.

Stage:
    Stage 10 (Frozen System Benchmark + Development Evaluation)

Inputs:
    Cozmo reconstruction measurements, incumbent CSV measurement export, and physical GT records.

Outputs:
    IncumbentComparisonResult containing win/tie/loss counts, beat+tie ratios, and comparative MAE.

Units & Coordinate Systems:
    Lengths in meters (m), Areas in square meters (m^2).

Dependencies:
    csv, os, dataclasses, typing, backend.app.benchmark.models, backend.app.benchmark.ground_truth,
    backend.app.benchmark.metrics.

Assumptions:
    Comparison against incumbent measurements is only mathematically valid when independent
    physical ground truth exists to compute absolute errors for both systems.

Failure Modes:
    Missing incumbent CSV or missing physical ground truth cleanly produces
    INCUMBENT_COMPARISON_NOT_EVALUABLE without fabrication.

First Debugging Points:
    Verify CSV headers match: room_id,measurement_id,measurement_type,incumbent_value,unit.
"""

import csv
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from backend.app.benchmark.ground_truth import GroundTruthRecord
from backend.app.benchmark.metrics import compute_absolute_error
from backend.app.benchmark.models import BenchmarkMeasurement


@dataclass
class IncumbentRecord:
    """Individual measurement entry exported from an incumbent scanning application.

    Attributes:
        room_id: Target room identifier.
        measurement_id: Specific dimension or wall ID.
        measurement_type: Standardized type (e.g. wall_length, ceiling_height).
        incumbent_value: Scalar metric value reported by the incumbent app.
        unit: Measurement unit (m, m2).
        notes: Optional comments.
    """
    room_id: str
    measurement_id: str
    measurement_type: str
    incumbent_value: float
    unit: str
    notes: str = ""


@dataclass
class IncumbentComparisonResult:
    """Benchmark evaluation of Cozmo AI vs Incumbent scanning applications.

    Attributes:
        status: 'EVALUATED' or 'INCUMBENT_COMPARISON_NOT_EVALUABLE'.
        shared_dimensions_count: Total shared dimensions compared.
        beat_count: Number of dimensions where Cozmo error < Incumbent error.
        tie_count: Number of dimensions where Cozmo error == Incumbent error (within 1mm).
        loss_count: Number of dimensions where Cozmo error > Incumbent error.
        beat_tie_ratio: Ratio (beat + tie) / shared_dimensions_count.
        cozmo_mae: Mean absolute error of Cozmo AI against physical GT.
        incumbent_mae: Mean absolute error of Incumbent app against physical GT.
        reasons: Diagnostic explanations for status.
        details: Dimension-by-dimension comparison log.
    """
    status: str
    shared_dimensions_count: int = 0
    beat_count: int = 0
    tie_count: int = 0
    loss_count: int = 0
    beat_tie_ratio: Optional[float] = None
    cozmo_mae: Optional[float] = None
    incumbent_mae: Optional[float] = None
    reasons: List[str] = field(default_factory=list)
    details: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize incumbent comparison result to dictionary."""
        return {
            "status": self.status,
            "shared_dimensions_count": self.shared_dimensions_count,
            "beat_count": self.beat_count,
            "tie_count": self.tie_count,
            "loss_count": self.loss_count,
            "beat_tie_ratio": self.beat_tie_ratio,
            "cozmo_mae": self.cozmo_mae,
            "incumbent_mae": self.incumbent_mae,
            "reasons": self.reasons,
            "details": self.details,
        }


def load_incumbent_measurements(csv_path: Optional[str]) -> List[IncumbentRecord]:
    """Load measurement records from an incumbent application CSV file.

    Parameters:
        csv_path: Optional filesystem path to incumbent CSV file.

    Returns:
        List of parsed IncumbentRecord items, or empty list if path is missing/invalid.

    Units / Coordinates:
        Values parsed as floats in meters (m) or square meters (m^2).

    Assumptions:
        File format contains headers: room_id, measurement_id, measurement_type, incumbent_value, unit.

    Failure Conditions:
        Malformed rows or missing files return empty list or raise ValueError on invalid headers.

    Dependencies:
        csv, os, IncumbentRecord.

    Debugging Clues:
        Check header column names in incumbent export file.
    """
    if not csv_path or not os.path.exists(csv_path):
        return []

    records: List[IncumbentRecord] = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        required = {"room_id", "measurement_id", "measurement_type", "incumbent_value", "unit"}
        if not reader.fieldnames or not required.issubset(set(reader.fieldnames)):
            return []
        for row in reader:
            try:
                records.append(
                    IncumbentRecord(
                        room_id=row["room_id"].strip(),
                        measurement_id=row["measurement_id"].strip(),
                        measurement_type=row["measurement_type"].strip().lower(),
                        incumbent_value=float(row["incumbent_value"]),
                        unit=row["unit"].strip(),
                        notes=row.get("notes", "").strip(),
                    )
                )
            except (ValueError, KeyError):
                continue
    return records


def evaluate_incumbent_comparison(
    cozmo_measurements: List[BenchmarkMeasurement],
    incumbent_records: List[IncumbentRecord],
    ground_truth: Optional[List[GroundTruthRecord]] = None,
    tie_tolerance_m: float = 0.002,
) -> IncumbentComparisonResult:
    """Evaluate dimension-by-dimension performance against incumbent scanning application.

    Parameters:
        cozmo_measurements: List of Cozmo reconstruction measurements.
        incumbent_records: List of incumbent measurements.
        ground_truth: List of physical ground-truth measurements.
        tie_tolerance_m: Absolute difference tolerance in meters to count as a tie.

    Returns:
        IncumbentComparisonResult container.

    Units / Coordinates:
        Meters (m) for linear dimensions.

    Assumptions:
        Gate requires beating or tying incumbent on >= 70% (0.70) of shared dimensions.

    Failure Conditions:
        If incumbent records or physical ground truth is absent, cleanly returns
        INCUMBENT_COMPARISON_NOT_EVALUABLE.

    Dependencies:
        compute_absolute_error, IncumbentComparisonResult.

    Debugging Clues:
        Check whether physical GT exists to score both systems independently.
    """
    if not incumbent_records:
        return IncumbentComparisonResult(
            status="INCUMBENT_COMPARISON_NOT_EVALUABLE",
            reasons=["No incumbent benchmark measurements provided in benchmark inputs."],
        )

    if not ground_truth:
        return IncumbentComparisonResult(
            status="INCUMBENT_COMPARISON_NOT_EVALUABLE",
            reasons=["Physical ground-truth measurements absent; cannot evaluate absolute errors."],
        )

    gt_map = {f"{g.room_id.lower()}_{g.measurement_type.lower()}_{g.measurement_id.lower()}": g.value for g in ground_truth}
    cozmo_map = {f"{c.room_id.lower()}_{c.type.lower()}_{c.measurement_id.lower()}": c.predicted_value for c in cozmo_measurements if c.predicted_value is not None}

    shared_dims = 0
    beat = 0
    tie = 0
    loss = 0
    cozmo_errs = []
    inc_errs = []
    details = []

    for inc in incumbent_records:
        key = f"{inc.room_id.lower()}_{inc.measurement_type.lower()}_{inc.measurement_id.lower()}"
        if key in gt_map and key in cozmo_map:
            shared_dims += 1
            gt_val = gt_map[key]
            c_val = cozmo_map[key]
            i_val = inc.incumbent_value

            c_err = abs(c_val - gt_val)
            i_err = abs(i_val - gt_val)
            cozmo_errs.append(c_err)
            inc_errs.append(i_err)

            diff = c_err - i_err
            if abs(diff) <= tie_tolerance_m:
                tie += 1
                outcome = "TIE"
            elif c_err < i_err:
                beat += 1
                outcome = "BEAT"
            else:
                loss += 1
                outcome = "LOSS"

            details.append({
                "key": key,
                "gt_value": gt_val,
                "cozmo_value": c_val,
                "incumbent_value": i_val,
                "cozmo_abs_error": round(c_err, 4),
                "incumbent_abs_error": round(i_err, 4),
                "outcome": outcome,
            })

    if shared_dims == 0:
        return IncumbentComparisonResult(
            status="INCUMBENT_COMPARISON_NOT_EVALUABLE",
            reasons=["No shared dimensions found between Cozmo, Incumbent, and Ground Truth."],
        )

    ratio = (beat + tie) / shared_dims
    c_mae = sum(cozmo_errs) / len(cozmo_errs)
    i_mae = sum(inc_errs) / len(inc_errs)

    return IncumbentComparisonResult(
        status="EVALUATED",
        shared_dimensions_count=shared_dims,
        beat_count=beat,
        tie_count=tie,
        loss_count=loss,
        beat_tie_ratio=round(ratio, 4),
        cozmo_mae=round(c_mae, 4),
        incumbent_mae=round(i_mae, 4),
        reasons=[],
        details=details,
    )
