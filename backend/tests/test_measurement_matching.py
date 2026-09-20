"""Unit Tests for Robust Measurement Matching and Correspondence Rejection.

Purpose:
    Verifies that geometric feature matching aligns corresponding walls and openings
    accurately, correctly classifies unassigned features as MISSED or PHANTOM, and
    strictly rejects ambiguous matches rather than forcing incorrect correspondences.

Stage:
    Stage 10 (Frozen System Benchmark + Development Evaluation)

Inputs:
    Synthetic measurement candidate collections with controlled spatial offsets and orientations.

Outputs:
    Assertions verifying matched pairs, ambiguous rejections, and failure categories.

Units & Coordinate Systems:
    Lengths in meters (m), angles in degrees.

Dependencies:
    pytest, backend.app.benchmark.matcher, backend.app.benchmark.models.

Assumptions:
    Candidate pairs within ambiguity tolerance are flagged as AMBIGUOUS and left UNMATCHED.

Failure Modes:
    Assertion failure if ambiguous features are forced into erroneous correspondence.

First Debugging Points:
    Check match_measurements in backend.app.benchmark.matcher.
"""

import pytest
from backend.app.benchmark.matcher import (
    MeasurementCandidate,
    compute_angle_difference_deg,
    match_measurements,
)
from backend.app.benchmark.models import FailureCategory


def test_angle_difference_symmetric():
    """Verify bidirectional angle difference calculation for wall lines.

    Parameters:
        None.

    Returns:
        None.

    Units:
        Degrees.

    Assumptions:
        Wall lines are symmetric modulo 180 degrees (e.g. 0 deg and 180 deg have 0 diff).

    Failure Conditions:
        Fails if anti-parallel walls are treated as 180 deg apart rather than 0 deg.

    Dependencies:
        compute_angle_difference_deg.

    Debugging Clues:
        Check symmetric parameter in compute_angle_difference_deg.
    """
    assert compute_angle_difference_deg(0.0, 180.0, symmetric=True) == pytest.approx(0.0)
    assert compute_angle_difference_deg(10.0, 190.0, symmetric=True) == pytest.approx(0.0)
    assert compute_angle_difference_deg(0.0, 90.0, symmetric=True) == pytest.approx(90.0)
    assert compute_angle_difference_deg(15.0, 35.0, symmetric=True) == pytest.approx(20.0)


def test_wall_correspondence_matching():
    """Verify clean geometric matching between predicted and reference walls.

    Parameters:
        None.

    Returns:
        None.

    Units:
        Meters (m), degrees.

    Assumptions:
        Distinct non-ambiguous wall pairs are successfully matched with status='MATCHED'.

    Failure Conditions:
        Fails if distinct walls fail to match.

    Dependencies:
        MeasurementCandidate, match_measurements.

    Debugging Clues:
        Check orientation and centroid distances in candidate parameters.
    """
    preds = [
        MeasurementCandidate(
            entity_id="pred_wall_0",
            room_id="room_01",
            measurement_type="wall_length",
            value=3.52,
            orientation_deg=0.0,
            centroid=(0.0, 1.76),
        ),
        MeasurementCandidate(
            entity_id="pred_wall_1",
            room_id="room_01",
            measurement_type="wall_length",
            value=4.10,
            orientation_deg=90.0,
            centroid=(2.05, 3.5),
        ),
    ]
    refs = [
        MeasurementCandidate(
            entity_id="ref_wall_0",
            room_id="room_01",
            measurement_type="wall_length",
            value=3.50,
            orientation_deg=2.0,
            centroid=(0.02, 1.75),
        ),
        MeasurementCandidate(
            entity_id="ref_wall_1",
            room_id="room_01",
            measurement_type="wall_length",
            value=4.12,
            orientation_deg=89.0,
            centroid=(2.04, 3.51),
        ),
    ]

    matches = match_measurements(preds, refs)
    matched_pairs = [m for m in matches if m.status == "MATCHED"]
    assert len(matched_pairs) == 2
    assert matched_pairs[0].candidate_a.entity_id == "pred_wall_0"
    assert matched_pairs[0].candidate_b.entity_id == "ref_wall_0"


def test_ambiguous_correspondence_rejection():
    """Verify that ambiguous candidate matches are rejected and flagged as UNMATCHED.

    Parameters:
        None.

    Returns:
        None.

    Units:
        Meters (m), degrees.

    Assumptions:
        When a prediction could equally match two equidistant identical reference walls,
        neither is matched to prevent metric distortion.

    Failure Conditions:
        Fails if an ambiguous correspondence is arbitrarily assigned.

    Dependencies:
        MeasurementCandidate, match_measurements, FailureCategory.

    Debugging Clues:
        Check ambiguity_threshold in match_measurements.
    """
    preds = [
        MeasurementCandidate(
            entity_id="pred_wall_amb",
            room_id="room_01",
            measurement_type="wall_length",
            value=3.0,
            orientation_deg=0.0,
            centroid=(0.0, 0.0),
        )
    ]
    # Two almost identical reference candidates
    refs = [
        MeasurementCandidate(
            entity_id="ref_wall_a",
            room_id="room_01",
            measurement_type="wall_length",
            value=3.01,
            orientation_deg=0.5,
            centroid=(0.01, 0.01),
        ),
        MeasurementCandidate(
            entity_id="ref_wall_b",
            room_id="room_01",
            measurement_type="wall_length",
            value=3.02,
            orientation_deg=0.8,
            centroid=(0.02, 0.02),
        ),
    ]

    matches = match_measurements(preds, refs, ambiguity_threshold=0.10)
    matched = [m for m in matches if m.status == "MATCHED"]
    assert len(matched) == 0  # Rejection of ambiguity
    ambiguous = [m for m in matches if m.status == "AMBIGUOUS"]
    assert len(ambiguous) >= 1
    assert ambiguous[0].failure_category == FailureCategory.UNMATCHED


def test_unmatched_phantom_and_missed():
    """Verify unmatched predictions count as PHANTOM and unmatched references as MISSED.

    Parameters:
        None.

    Returns:
        None.

    Units:
        Meters (m).

    Assumptions:
        Extra predictions are PHANTOM; missing expected references are MISSED.

    Failure Conditions:
        Fails if unassigned candidates are not categorized correctly.

    Dependencies:
        MeasurementCandidate, match_measurements, FailureCategory.

    Debugging Clues:
        Check failure_category assignments in match_measurements.
    """
    preds = [
        MeasurementCandidate(
            entity_id="pred_extra",
            room_id="room_01",
            measurement_type="wall_length",
            value=1.5,
            orientation_deg=45.0,
        )
    ]
    refs = [
        MeasurementCandidate(
            entity_id="ref_unseen",
            room_id="room_01",
            measurement_type="wall_length",
            value=5.0,
            orientation_deg=90.0,
        )
    ]

    matches = match_measurements(preds, refs, angle_tolerance_deg=10.0)
    phantoms = [m for m in matches if m.failure_category == FailureCategory.PHANTOM]
    misses = [m for m in matches if m.failure_category == FailureCategory.MISSED]
    assert len(phantoms) == 1
    assert len(misses) == 1
