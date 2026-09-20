"""Ground-Truth Import Contract and Loader for Benchmark Evaluation.

Purpose:
    Defines the standard ingestion schema and loader for independent physical ground-truth
    measurements (wall lengths, door/window openings, ceiling heights, damage extents).
    Safeguards against fabricating synthetic reference data when true physical measurements
    are absent, strictly returning GROUND_TRUTH_NOT_AVAILABLE.

Stage:
    Stage 10 (Frozen System Benchmark + Development Evaluation)

Inputs:
    Optional directory path pointing to ground-truth CSV files:
      - measurements.csv
      - openings.csv
      - damage.csv

Outputs:
    GroundTruthContract dataclass containing parsed ground-truth records or an explicit
    GROUND_TRUTH_NOT_AVAILABLE indicator.

Units & Coordinate Systems:
    Lengths in meters (m), Areas in square meters (m^2).

Dependencies:
    csv, os, typing, dataclasses, backend.app.benchmark.models.

Assumptions:
    If ground-truth files do not exist on disk, no values are hallucinated or zero-filled.

Failure Modes:
    Malformed CSV files raise descriptive ValueError; missing directories cleanly produce
    GROUND_TRUTH_NOT_AVAILABLE.

First Debugging Points:
    Check file headers match: measurement_id,room_id,measurement_type,value,unit,source,notes.
"""

import csv
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from backend.app.benchmark.models import EvidenceLevel


VALID_MEASUREMENT_TYPES = {
    "wall_length",
    "door_width",
    "window_width",
    "ceiling_height",
    "floor_area",
    "perimeter",
    "damage_area",
    "damage_length",
}


@dataclass
class GroundTruthRecord:
    """Individual physical ground-truth record.

    Attributes:
        measurement_id: Unique identifier for the measurement.
        room_id: Target room or zone identifier.
        measurement_type: Standardized type key (e.g. wall_length, door_width).
        value: Physical ground-truth value.
        unit: Unit of measurement (m, m2).
        source: Verification method (e.g., laser_disto, tape_measure).
        notes: Contextual documentation or host wall identifier.
    """
    measurement_id: str
    room_id: str
    measurement_type: str
    value: float
    unit: str
    source: str
    notes: str = ""


@dataclass
class GroundTruthContract:
    """Import contract container representing available physical ground truth.

    Attributes:
        status: GROUND_TRUTH_AVAILABLE or GROUND_TRUTH_NOT_AVAILABLE.
        has_ground_truth: Boolean flag indicating if valid physical GT was imported.
        measurements: Dictionary of records keyed by (room_id, measurement_type, measurement_id).
        openings: List of ground-truth opening records.
        damage: List of ground-truth damage records.
        source_dir: Directory path from which records were read (if any).
    """
    status: str
    has_ground_truth: bool
    measurements: List[GroundTruthRecord] = field(default_factory=list)
    openings: List[GroundTruthRecord] = field(default_factory=list)
    damage: List[GroundTruthRecord] = field(default_factory=list)
    source_dir: Optional[str] = None

    def get_measurements_by_room(self, room_id: str) -> List[GroundTruthRecord]:
        """Filter imported ground-truth records by room identifier.

        Parameters:
            room_id: String room identifier.

        Returns:
            List of GroundTruthRecord objects matching the room.

        Units:
            Meters and square meters.

        Assumptions:
            room_id comparison is case-insensitive.

        Failure Conditions:
            Returns empty list if no records match.

        Dependencies:
            None.

        Debugging Clues:
            Verify room_id naming conventions (e.g. room_01 vs Room1).
        """
        target = room_id.lower()
        return [r for r in self.measurements if r.room_id.lower() == target]


def load_ground_truth_contract(ground_truth_dir: Optional[str] = None) -> GroundTruthContract:
    """Load physical ground-truth records from a standardized folder contract.

    Parameters:
        ground_truth_dir: Optional filesystem path to ground-truth directory.

    Returns:
        GroundTruthContract with loaded records or status='GROUND_TRUTH_NOT_AVAILABLE'.

    Units:
        Values parsed as floats in meters (m) or square meters (m^2).

    Assumptions:
        If directory is None or empty or missing, returns GROUND_TRUTH_NOT_AVAILABLE.

    Failure Conditions:
        Missing columns in existing CSV file raises ValueError with clear error message.

    Dependencies:
        csv, os, GroundTruthRecord, GroundTruthContract.

    Debugging Clues:
        Check existence of measurements.csv, openings.csv, or damage.csv in ground_truth_dir.
    """
    if not ground_truth_dir or not os.path.exists(ground_truth_dir) or not os.path.isdir(ground_truth_dir):
        return GroundTruthContract(
            status="GROUND_TRUTH_NOT_AVAILABLE",
            has_ground_truth=False,
            source_dir=ground_truth_dir,
        )

    measurements: List[GroundTruthRecord] = []
    openings: List[GroundTruthRecord] = []
    damage: List[GroundTruthRecord] = []

    def parse_csv(filepath: str) -> List[GroundTruthRecord]:
        records: List[GroundTruthRecord] = []
        if not os.path.exists(filepath):
            return records
        with open(filepath, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            required_cols = {"measurement_id", "room_id", "measurement_type", "value", "unit"}
            if not reader.fieldnames or not required_cols.issubset(set(reader.fieldnames)):
                raise ValueError(
                    f"Ground-truth file '{filepath}' missing required headers {required_cols}. "
                    f"Found: {reader.fieldnames}"
                )
            for row in reader:
                val = float(row["value"])
                m_type = row["measurement_type"].strip().lower()
                records.append(
                    GroundTruthRecord(
                        measurement_id=row["measurement_id"].strip(),
                        room_id=row["room_id"].strip(),
                        measurement_type=m_type,
                        value=val,
                        unit=row["unit"].strip(),
                        source=row.get("source", "physical_audit").strip(),
                        notes=row.get("notes", "").strip(),
                    )
                )
        return records

    m_path = os.path.join(ground_truth_dir, "measurements.csv")
    o_path = os.path.join(ground_truth_dir, "openings.csv")
    d_path = os.path.join(ground_truth_dir, "damage.csv")

    if os.path.exists(m_path):
        measurements.extend(parse_csv(m_path))
    if os.path.exists(o_path):
        openings.extend(parse_csv(o_path))
    if os.path.exists(d_path):
        damage.extend(parse_csv(d_path))

    has_gt = bool(measurements or openings or damage)
    status = "GROUND_TRUTH_AVAILABLE" if has_gt else "GROUND_TRUTH_NOT_AVAILABLE"

    return GroundTruthContract(
        status=status,
        has_ground_truth=has_gt,
        measurements=measurements,
        openings=openings,
        damage=damage,
        source_dir=ground_truth_dir,
    )
