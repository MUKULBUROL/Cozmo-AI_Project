"""Stage 6 Loop Closure Quality Gating & Validation.

1. Why this file exists:
    Applies strict geometric and statistical quality gates to ICP registration results,
    categorizing loop candidates into 'accepted', 'uncertain', or 'rejected' to prevent
    spurious constraints from corrupting the pose graph.

2. Pipeline stage:
    Stage 6 — Loop Closure Validation & Rejection.

3. Inputs:
    RegistrationResult from ICP registration.

4. Outputs:
    ValidationDecision object detailing acceptance status and rejection rationale,
    and serialized loop_closures.json documenting all decisions.

5. Coordinate conventions:
    Metric units: RMSE in meters, displacement delta in meters, rotation delta in degrees.

6. Unit assumptions:
    Distances in meters (m), angles in degrees.

7. Important dependencies:
    json, pathlib, typing, backend.app.optimization.registration.

8. What is most likely to break:
    Permissive gates accepting featureless wall sliding as valid loop closures.

9. What a developer should inspect first:
    Inspect loop_closures.json rejection reasons when accepted closures count is zero.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Any, Optional

from backend.app.optimization.registration import RegistrationResult


@dataclass
class ValidationDecision:
    """Stores the verification decision and diagnosis for an ICP loop candidate.

    Attributes:
        node_i: Source keyframe node index.
        node_j: Target keyframe node index.
        status: One of 'accepted', 'uncertain', or 'rejected'.
        fitness: Registration fitness achieved.
        inlier_rmse: Point-to-plane RMSE in meters.
        correspondences: Number of valid point pairings.
        translation_delta_m: Translation change from odometry in meters.
        rotation_delta_deg: Rotation change from odometry in degrees.
        rejection_reasons: List of reasons if not accepted.
    """
    node_i: int
    node_j: int
    status: str
    fitness: float
    inlier_rmse: float
    correspondences: int
    translation_delta_m: float
    rotation_delta_deg: float
    rejection_reasons: List[str] = field(default_factory=list)


def validate_loop_candidate(
    reg_result: RegistrationResult,
    min_fitness: float = 0.55,
    max_rmse_m: float = 0.055,
    min_correspondences: int = 80,
    max_translation_delta_m: float = 0.50,
    max_rotation_delta_deg: float = 22.0,
    uncertain_fitness_threshold: float = 0.45,
) -> ValidationDecision:
    """Evaluates ICP registration against strict metric criteria.

    Purpose:
        Protects the global pose graph from degenerate, planar-sliding, or mismatched loop edges.

    Parameters:
        reg_result: RegistrationResult from Point-to-Plane ICP.
        min_fitness: Minimum inlier overlap fraction for acceptance.
        max_rmse_m: Maximum acceptable inlier RMSE in meters.
        min_correspondences: Minimum point correspondences required.
        max_translation_delta_m: Maximum allowable translation jump from odometry.
        max_rotation_delta_deg: Maximum allowable rotation jump from odometry.
        uncertain_fitness_threshold: Threshold below which candidate is definitively rejected.

    Returns:
        ValidationDecision object with status ('accepted', 'uncertain', 'rejected').

    Assumptions:
        RMSE is in meters, deltas are non-negative.

    Failure conditions:
        None; handles extreme metric values safely.

    Debugging:
        Check rejection_reasons list to see which constraint failed.
    """
    reasons: List[str] = []

    if reg_result.fitness < min_fitness:
        reasons.append(f"low_fitness_{reg_result.fitness:.3f}_below_{min_fitness}")

    if reg_result.inlier_rmse > max_rmse_m:
        reasons.append(f"high_rmse_{reg_result.inlier_rmse*100:.1f}cm_above_{max_rmse_m*100:.1f}cm")

    if reg_result.correspondence_count < min_correspondences:
        reasons.append(f"insufficient_correspondences_{reg_result.correspondence_count}_below_{min_correspondences}")

    if reg_result.translation_delta_m > max_translation_delta_m:
        reasons.append(f"excessive_translation_shift_{reg_result.translation_delta_m:.2f}m_above_{max_translation_delta_m}m")

    if reg_result.rotation_delta_deg > max_rotation_delta_deg:
        reasons.append(f"excessive_rotation_shift_{reg_result.rotation_delta_deg:.1f}deg_above_{max_rotation_delta_deg}deg")

    has_unacceptable_shift = (
        reg_result.translation_delta_m > max_translation_delta_m
        or reg_result.rotation_delta_deg > max_rotation_delta_deg
    )

    if not reasons:
        status = "accepted"
    elif not has_unacceptable_shift and reg_result.fitness >= uncertain_fitness_threshold and reg_result.inlier_rmse <= max_rmse_m * 1.3:
        status = "uncertain"
    else:
        status = "rejected"

    return ValidationDecision(
        node_i=reg_result.node_i,
        node_j=reg_result.node_j,
        status=status,
        fitness=round(reg_result.fitness, 4),
        inlier_rmse=round(reg_result.inlier_rmse, 5),
        correspondences=reg_result.correspondence_count,
        translation_delta_m=round(reg_result.translation_delta_m, 4),
        rotation_delta_deg=round(reg_result.rotation_delta_deg, 2),
        rejection_reasons=reasons,
    )


def export_loop_closures_json(
    decisions: List[ValidationDecision],
    output_path: Path,
) -> None:
    """Exports loop validation outcomes to a machine-readable JSON file.

    Purpose:
        Preserves an explicit record of all validated and rejected loop closure constraints.

    Parameters:
        decisions: List of ValidationDecision objects.
        output_path: Target JSON destination Path.

    Returns:
        None.

    Assumptions:
        Destination directory is writable.

    Failure conditions:
        OSError on file write failure.

    Debugging:
        Verify accepted_count vs rejected_count in output JSON summary.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    accepted = [d for d in decisions if d.status == "accepted"]
    uncertain = [d for d in decisions if d.status == "uncertain"]
    rejected = [d for d in decisions if d.status == "rejected"]

    payload = {
        "summary": {
            "total_evaluated": len(decisions),
            "accepted_count": len(accepted),
            "uncertain_count": len(uncertain),
            "rejected_count": len(rejected),
        },
        "decisions": [
            {
                "node_i": d.node_i,
                "node_j": d.node_j,
                "status": d.status,
                "fitness": d.fitness,
                "inlier_rmse_meters": d.inlier_rmse,
                "correspondence_count": d.correspondences,
                "translation_delta_meters": d.translation_delta_m,
                "rotation_delta_degrees": d.rotation_delta_deg,
                "rejection_reasons": d.rejection_reasons,
            }
            for d in decisions
        ],
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
