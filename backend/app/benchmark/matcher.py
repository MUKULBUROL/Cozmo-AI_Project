"""Robust Measurement and Geometric Feature Matcher for Benchmark Evaluation.

Purpose:
    Establishes rigorous correspondence between predicted geometric elements (walls,
    openings, room dimensions) and reference elements (ground-truth records or cross-tier
    reconstructions). Rejects ambiguous matches rather than forcing erroneous correspondences.

Stage:
    Stage 10 (Frozen System Benchmark + Development Evaluation)

Inputs:
    Candidate measurement collections with spatial metadata (orientation angle, centroid,
    length, host wall identifier, room ID).

Outputs:
    List of matched pairs, unmatched predictions (potential phantoms), and unmatched
    references (potential misses) with diagnostic matching metrics.

Units & Coordinate Systems:
    Lengths in meters (m), Angles in degrees, Coordinates in meters (+X East, +Y North).

Dependencies:
    math, typing, dataclasses, backend.app.benchmark.models.

Assumptions:
    Wall directions are symmetric modulo 180 degrees.
    Singletons per room (floor area, ceiling height) match directly on room identity.

Failure Modes:
    Ambiguous candidates within match tolerance are marked UNMATCHED to prevent biased metrics.

First Debugging Points:
    Check candidate room_id normalization and orientation alignment tolerance.
"""

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from backend.app.benchmark.models import FailureCategory


@dataclass
class MeasurementCandidate:
    """Standardized representation of a geometric entity for correspondence matching.

    Attributes:
        entity_id: Unique identifier of entity (e.g., wall_0, door_1, room_area).
        room_id: Room or zone identifier.
        measurement_type: Geometric type (wall_length, door_width, floor_area, ceiling_height).
        value: Scalar measurement value in metric units.
        orientation_deg: Primary orientation angle in degrees [0, 360), if applicable.
        centroid: 2D or 3D centroid coordinates [x, y] or [x, y, z] in meters.
        host_surface_id: Associated host surface or parent wall ID (for openings).
        details: Additional metadata dictionary.
    """
    entity_id: str
    room_id: str
    measurement_type: str
    value: float
    orientation_deg: Optional[float] = None
    centroid: Optional[Tuple[float, ...]] = None
    host_surface_id: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MatchedPair:
    """Correspondence result between two measurement candidates.

    Attributes:
        candidate_a: First candidate (typically prediction).
        candidate_b: Second candidate (reference or cross-tier counterpart).
        score: Geometric alignment score (lower is closer/better).
        status: Match state ('MATCHED', 'UNMATCHED', 'AMBIGUOUS').
        failure_category: Categorized failure reason if unmatched.
    """
    candidate_a: Optional[MeasurementCandidate]
    candidate_b: Optional[MeasurementCandidate]
    score: float
    status: str
    failure_category: FailureCategory = FailureCategory.NONE


def compute_angle_difference_deg(deg_a: float, deg_b: float, symmetric: bool = True) -> float:
    """Calculate the minimal angular difference between two orientations.

    Parameters:
        deg_a: First orientation in degrees.
        deg_b: Second orientation in degrees.
        symmetric: If True, treats angles as bidirectional lines modulo 180 degrees.

    Returns:
        Minimal angular difference in degrees [0.0, 90.0] if symmetric, else [0.0, 180.0].

    Units / Coordinates:
        Degrees.

    Assumptions:
        Wall lines have orientation invariance up to 180 degree flips.

    Failure Conditions:
        Handles inputs outside [0, 360] via modular arithmetic.

    Dependencies:
        math.

    Debugging Clues:
        Check if symmetric is set correctly for directed vectors vs undirected wall segments.
    """
    diff = abs(deg_a - deg_b) % 360.0
    if diff > 180.0:
        diff = 360.0 - diff
    if symmetric and diff > 90.0:
        diff = 180.0 - diff
    return diff


def match_measurements(
    predictions: List[MeasurementCandidate],
    references: List[MeasurementCandidate],
    angle_tolerance_deg: float = 20.0,
    distance_tolerance_m: float = 1.5,
    ambiguity_threshold: float = 0.15,
) -> List[MatchedPair]:
    """Match predicted measurement candidates to reference candidates using geometric evidence.

    Parameters:
        predictions: List of estimated measurement candidates from reconstruction.
        references: List of reference candidates from GT or another pipeline tier.
        angle_tolerance_deg: Maximum allowable orientation discrepancy for wall matching.
        distance_tolerance_m: Maximum allowable centroid distance for spatial matching.
        ambiguity_threshold: Score gap below which multiple potential matches trigger AMBIGUOUS.

    Returns:
        List of MatchedPair objects detailing matched correspondences and unmatched items.

    Units / Coordinates:
        Lengths and distances in meters (m), angles in degrees.

    Assumptions:
        Candidates must match on room_id and measurement_type before geometric comparison.

    Failure Conditions:
        When two reference candidates have nearly identical alignment scores to a prediction,
        both are left UNMATCHED with failure category FailureCategory.UNMATCHED.

    Dependencies:
        compute_angle_difference_deg, MatchedPair, FailureCategory.

    Debugging Clues:
        Inspect centroid coordinates and orientation_deg populated on MeasurementCandidate.
    """
    results: List[MatchedPair] = []

    # Partition candidates by (room_id, measurement_type)
    groups: Dict[Tuple[str, str], Tuple[List[MeasurementCandidate], List[MeasurementCandidate]]] = {}
    for p in predictions:
        key = (p.room_id.strip().lower(), p.measurement_type.strip().lower())
        if key not in groups:
            groups[key] = ([], [])
        groups[key][0].append(p)

    for r in references:
        key = (r.room_id.strip().lower(), r.measurement_type.strip().lower())
        if key not in groups:
            groups[key] = ([], [])
        groups[key][1].append(r)

    for (room_id, m_type), (preds, refs) in groups.items():
        # Case 1: Room-level singletons (floor_area, perimeter, ceiling_height)
        if m_type in {"floor_area", "perimeter", "ceiling_height"}:
            if len(preds) == 1 and len(refs) == 1:
                results.append(
                    MatchedPair(
                        candidate_a=preds[0],
                        candidate_b=refs[0],
                        score=abs(preds[0].value - refs[0].value),
                        status="MATCHED",
                        failure_category=FailureCategory.NONE,
                    )
                )
            elif len(preds) > 0 and len(refs) == 0:
                for p in preds:
                    results.append(
                        MatchedPair(
                            candidate_a=p,
                            candidate_b=None,
                            score=float("inf"),
                            status="UNMATCHED",
                            failure_category=FailureCategory.PHANTOM,
                        )
                    )
            elif len(preds) == 0 and len(refs) > 0:
                for r in refs:
                    results.append(
                        MatchedPair(
                            candidate_a=None,
                            candidate_b=r,
                            score=float("inf"),
                            status="UNMATCHED",
                            failure_category=FailureCategory.MISSED,
                        )
                    )
            else:
                # Multiple singletons in same room is an anomaly: mark ambiguous
                for p in preds:
                    results.append(
                        MatchedPair(
                            candidate_a=p,
                            candidate_b=None,
                            score=float("inf"),
                            status="AMBIGUOUS",
                            failure_category=FailureCategory.UNMATCHED,
                        )
                    )
                for r in refs:
                    results.append(
                        MatchedPair(
                            candidate_a=None,
                            candidate_b=r,
                            score=float("inf"),
                            status="AMBIGUOUS",
                            failure_category=FailureCategory.UNMATCHED,
                        )
                    )
            continue

        # Case 2: Multi-instance geometric features (walls, openings)
        used_refs = set()
        for p in preds:
            scored_candidates: List[Tuple[float, int, MeasurementCandidate]] = []
            for idx, r in enumerate(refs):
                if idx in used_refs:
                    continue

                # Check host surface for openings
                if p.host_surface_id and r.host_surface_id:
                    if p.host_surface_id.lower() != r.host_surface_id.lower():
                        continue

                # Angular similarity
                angle_cost = 0.0
                if p.orientation_deg is not None and r.orientation_deg is not None:
                    ang_diff = compute_angle_difference_deg(p.orientation_deg, r.orientation_deg, symmetric=True)
                    if ang_diff > angle_tolerance_deg:
                        continue
                    angle_cost = ang_diff / angle_tolerance_deg

                # Spatial distance similarity
                dist_cost = 0.0
                if p.centroid and r.centroid and len(p.centroid) == len(r.centroid):
                    euclid = math.sqrt(sum((c1 - c2) ** 2 for c1, c2 in zip(p.centroid, r.centroid)))
                    if euclid > distance_tolerance_m:
                        continue
                    dist_cost = euclid / distance_tolerance_m

                # Dimensional length similarity
                length_diff = abs(p.value - r.value)
                denom = max(p.value, r.value, 0.1)
                dim_cost = length_diff / denom

                total_cost = 0.4 * angle_cost + 0.4 * dist_cost + 0.2 * dim_cost
                scored_candidates.append((total_cost, idx, r))

            scored_candidates.sort(key=lambda x: x[0])

            if not scored_candidates:
                results.append(
                    MatchedPair(
                        candidate_a=p,
                        candidate_b=None,
                        score=float("inf"),
                        status="UNMATCHED",
                        failure_category=FailureCategory.PHANTOM,
                    )
                )
            elif len(scored_candidates) > 1 and (scored_candidates[1][0] - scored_candidates[0][0]) < ambiguity_threshold:
                # Ambiguity detected: do not force match
                results.append(
                    MatchedPair(
                        candidate_a=p,
                        candidate_b=None,
                        score=scored_candidates[0][0],
                        status="AMBIGUOUS",
                        failure_category=FailureCategory.UNMATCHED,
                    )
                )
            else:
                best_score, best_idx, best_ref = scored_candidates[0]
                used_refs.add(best_idx)
                results.append(
                    MatchedPair(
                        candidate_a=p,
                        candidate_b=best_ref,
                        score=best_score,
                        status="MATCHED",
                        failure_category=FailureCategory.NONE,
                    )
                )

        # Record unmatched references as MISSED
        for idx, r in enumerate(refs):
            if idx not in used_refs:
                results.append(
                    MatchedPair(
                        candidate_a=None,
                        candidate_b=r,
                        score=float("inf"),
                        status="UNMATCHED",
                        failure_category=FailureCategory.MISSED,
                    )
                )

    return results
