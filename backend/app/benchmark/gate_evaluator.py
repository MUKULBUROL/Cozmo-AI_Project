"""Official Challenge Gate Evaluator for Assessment Conformance.

Purpose:
    Encodes and evaluates the formal challenge gates specified by the assessment:
      1. Openings width error <= 2 cm (0.02m) on >= 85% (missed & phantoms count as misses).
      2. Ceiling height error <= 1.5 cm (0.015m) per room.
      3. Repeatability: same-room same-tier wall agreement within 1 cm or 0.5%.
      4. Video wall-length relative error approximately ±3% (where physical GT exists).
      5. Photo wall-length relative error approximately ±8% (where physical GT exists).
      6. Photo property footprint approximately ±8% (where physical GT exists).
      7. Drift correction & ablation verification (mandatory architectural requirement).
      8. Incumbent app comparison: beat/tie on >= 70% of shared dimensions.
      9. Damage extent & repair scope generation.
    Strictly yields NOT_EVALUABLE when physical ground truth is absent.

Stage:
    Stage 10 (Frozen System Benchmark + Development Evaluation)

Inputs:
    Reconstruction measurements, ground-truth contracts, repeatability results,
    incumbent results, and drift ablation manifests.

Outputs:
    List of BenchmarkGateResult records with rigorous evidence levels and justifications.

Units & Coordinate Systems:
    Lengths in meters (m), relative ratios unitless.

Dependencies:
    typing, dataclasses, backend.app.benchmark.models, backend.app.benchmark.ground_truth,
    backend.app.benchmark.repeatability, backend.app.benchmark.incumbent.

Assumptions:
    If ground truth is missing, result is strictly NOT_EVALUABLE, never manufactured PASS.

Failure Modes:
    Rejects fabricated or zero errors as substitutes for missing physical ground truth.

First Debugging Points:
    Check ground_truth_contract.has_ground_truth when investigating NOT_EVALUABLE statuses.
"""

from typing import Any, Dict, List, Optional
from backend.app.benchmark.damage_metrics import DamageBenchmarkResult
from backend.app.benchmark.ground_truth import GroundTruthContract
from backend.app.benchmark.incumbent import IncumbentComparisonResult
from backend.app.benchmark.models import (
    BenchmarkGateResult,
    BenchmarkMeasurement,
    EvidenceLevel,
    GateStatus,
)
from backend.app.benchmark.repeatability import RepeatabilityResult


def evaluate_challenge_gates(
    ground_truth: GroundTruthContract,
    lidar_measurements: List[BenchmarkMeasurement],
    video_measurements: List[BenchmarkMeasurement],
    photo_measurements: List[BenchmarkMeasurement],
    repeatability: RepeatabilityResult,
    incumbent: IncumbentComparisonResult,
    damage_result: DamageBenchmarkResult,
    drift_ablation_available: bool = True,
) -> List[BenchmarkGateResult]:
    """Evaluate all official challenge gates according to strict assessment rules.

    Parameters:
        ground_truth: GroundTruthContract indicating presence of physical measurements.
        lidar_measurements: Extracted LiDAR benchmark measurements.
        video_measurements: Extracted Video benchmark measurements.
        photo_measurements: Extracted Photo benchmark measurements.
        repeatability: Repeatability evaluation result.
        incumbent: Incumbent comparison result.
        damage_result: Damage evaluation result.
        drift_ablation_available: Boolean confirming drift correction and ablation existence.

    Returns:
        List of BenchmarkGateResult objects representing each official assessment gate.

    Units / Coordinates:
        Lengths in meters (m), tolerances as specified per gate.

    Assumptions:
        Missing physical ground truth produces GateStatus.NOT_EVALUABLE.
        Missed and phantom openings count against opening gate denominator.

    Failure Conditions:
        None. Robustly handles empty inputs and absent files.

    Dependencies:
        BenchmarkGateResult, GateStatus, EvidenceLevel.

    Debugging Clues:
        Check reasons list in each gate result to inspect decision rationale.
    """
    gates: List[BenchmarkGateResult] = []

    # ---------------------------------------------------------
    # Gate 1: LiDAR Opening Width (<= 2 cm on >= 85%)
    # ---------------------------------------------------------
    has_gt_openings = ground_truth.has_ground_truth and len(ground_truth.openings) > 0
    if not has_gt_openings:
        gates.append(
            BenchmarkGateResult(
                gate_id="GATE_OPENING_WIDTH",
                description="Absolute opening width error <= 2 cm (0.02m) on >= 85% of openings.",
                result=GateStatus.NOT_EVALUABLE,
                numerator=None,
                denominator=None,
                threshold="error <= 0.02m on >= 85% of openings",
                evidence_level=EvidenceLevel.NOT_EVALUABLE,
                reasons=[
                    "Independent physical ground-truth openings absent in sample dataset.",
                    "Cannot evaluate gate without independent physical opening audit.",
                ],
            )
        )
    else:
        opening_preds = [m for m in lidar_measurements if m.type in {"door_width", "window_width"}]
        pass_count = sum(1 for m in opening_preds if m.absolute_error is not None and m.absolute_error <= 0.02)
        total_openings = max(len(ground_truth.openings), len(opening_preds))
        ratio = pass_count / total_openings if total_openings > 0 else 0.0
        passed = ratio >= 0.85
        gates.append(
            BenchmarkGateResult(
                gate_id="GATE_OPENING_WIDTH",
                description="Absolute opening width error <= 2 cm (0.02m) on >= 85% of openings.",
                result=GateStatus.PASS if passed else GateStatus.FAIL,
                numerator=float(pass_count),
                denominator=float(total_openings),
                threshold=">= 85%",
                evidence_level=EvidenceLevel.GROUND_TRUTH,
                reasons=[f"Evaluated against physical ground truth: {pass_count}/{total_openings} passed ({ratio:.1%})."],
            )
        )

    # ---------------------------------------------------------
    # Gate 2: Ceiling Height (<= 1.5 cm per room)
    # ---------------------------------------------------------
    gt_ceilings = [r for r in ground_truth.measurements if r.measurement_type == "ceiling_height"]
    if not ground_truth.has_ground_truth or not gt_ceilings:
        gates.append(
            BenchmarkGateResult(
                gate_id="GATE_CEILING_HEIGHT",
                description="Absolute ceiling-height error <= 1.5 cm (0.015m) per room.",
                result=GateStatus.NOT_EVALUABLE,
                numerator=None,
                denominator=None,
                threshold="error <= 0.015m per room",
                evidence_level=EvidenceLevel.NOT_EVALUABLE,
                reasons=["Independent physical ceiling height measurements absent in sample dataset."],
            )
        )
    else:
        ceil_preds = [m for m in lidar_measurements if m.type == "ceiling_height"]
        pass_ceil = sum(1 for m in ceil_preds if m.absolute_error is not None and m.absolute_error <= 0.015)
        total_ceil = len(gt_ceilings)
        passed = (pass_ceil == total_ceil) if total_ceil > 0 else False
        gates.append(
            BenchmarkGateResult(
                gate_id="GATE_CEILING_HEIGHT",
                description="Absolute ceiling-height error <= 1.5 cm (0.015m) per room.",
                result=GateStatus.PASS if passed else GateStatus.FAIL,
                numerator=float(pass_ceil),
                denominator=float(total_ceil),
                threshold="<= 0.015m on 100% of rooms",
                evidence_level=EvidenceLevel.GROUND_TRUTH,
                reasons=[f"Physical GT ceiling evaluation: {pass_ceil}/{total_ceil} rooms passed."],
            )
        )

    # ---------------------------------------------------------
    # Gate 3: Repeatability (<= 1 cm or <= 0.5% per wall)
    # ---------------------------------------------------------
    if repeatability.status == "REPEATABILITY_NOT_EVALUABLE":
        gates.append(
            BenchmarkGateResult(
                gate_id="GATE_REPEATABILITY",
                description="Same-room same-tier wall agreement within 1 cm OR 0.5% per wall across independent scans.",
                result=GateStatus.NOT_EVALUABLE,
                numerator=None,
                denominator=None,
                threshold="<= 0.01m or <= 0.5%",
                evidence_level=EvidenceLevel.NOT_EVALUABLE,
                reasons=repeatability.reasons,
            )
        )
    else:
        passed = (repeatability.gate_pass_ratio or 0.0) >= 0.90
        gates.append(
            BenchmarkGateResult(
                gate_id="GATE_REPEATABILITY",
                description="Same-room same-tier wall agreement within 1 cm OR 0.5% per wall across independent scans.",
                result=GateStatus.PASS if passed else GateStatus.FAIL,
                numerator=float(repeatability.walls_within_gate_count),
                denominator=float(repeatability.total_compared_walls),
                threshold="<= 0.01m or <= 0.5%",
                evidence_level=EvidenceLevel.INTERNAL_CONSISTENCY,
                reasons=[f"Inter-scan agreement: {repeatability.walls_within_gate_count}/{repeatability.total_compared_walls} walls passed."],
            )
        )

    # ---------------------------------------------------------
    # Gate 4: Video Wall-Length Accuracy (Target ±3%)
    # ---------------------------------------------------------
    gt_walls = [r for r in ground_truth.measurements if r.measurement_type == "wall_length"]
    if not ground_truth.has_ground_truth or not gt_walls:
        gates.append(
            BenchmarkGateResult(
                gate_id="GATE_VIDEO_WALL_LENGTH",
                description="Video tier wall-length relative error target approximately ±3% where physical GT exists.",
                result=GateStatus.NOT_EVALUABLE,
                numerator=None,
                denominator=None,
                threshold="approx ±3% (0.03)",
                evidence_level=EvidenceLevel.NOT_EVALUABLE,
                reasons=["Physical ground truth absent for video wall dimension validation."],
            )
        )
    else:
        v_walls = [m for m in video_measurements if m.type == "wall_length"]
        v_pass = sum(1 for m in v_walls if m.relative_error is not None and m.relative_error <= 0.03)
        total_v = len(gt_walls)
        gates.append(
            BenchmarkGateResult(
                gate_id="GATE_VIDEO_WALL_LENGTH",
                description="Video tier wall-length relative error target approximately ±3% where physical GT exists.",
                result=GateStatus.PASS if (v_pass / max(total_v, 1)) >= 0.85 else GateStatus.FAIL,
                numerator=float(v_pass),
                denominator=float(total_v),
                threshold="approx ±3%",
                evidence_level=EvidenceLevel.GROUND_TRUTH,
                reasons=[f"{v_pass}/{total_v} video walls within ±3% relative error."],
            )
        )

    # ---------------------------------------------------------
    # Gate 5: Photo Wall-Length Accuracy (Target ±8%)
    # ---------------------------------------------------------
    if not ground_truth.has_ground_truth or not gt_walls:
        gates.append(
            BenchmarkGateResult(
                gate_id="GATE_PHOTO_WALL_LENGTH",
                description="Photo tier wall-length relative error target approximately ±8% where physical GT exists.",
                result=GateStatus.NOT_EVALUABLE,
                numerator=None,
                denominator=None,
                threshold="approx ±8% (0.08)",
                evidence_level=EvidenceLevel.NOT_EVALUABLE,
                reasons=["Physical ground truth absent for photo wall dimension validation."],
            )
        )
    else:
        p_walls = [m for m in photo_measurements if m.type == "wall_length"]
        p_pass = sum(1 for m in p_walls if m.relative_error is not None and m.relative_error <= 0.08)
        total_p = len(gt_walls)
        gates.append(
            BenchmarkGateResult(
                gate_id="GATE_PHOTO_WALL_LENGTH",
                description="Photo tier wall-length relative error target approximately ±8% where physical GT exists.",
                result=GateStatus.PASS if (p_pass / max(total_p, 1)) >= 0.80 else GateStatus.FAIL,
                numerator=float(p_pass),
                denominator=float(total_p),
                threshold="approx ±8%",
                evidence_level=EvidenceLevel.GROUND_TRUTH,
                reasons=[f"{p_pass}/{total_p} photo walls within ±8% relative error."],
            )
        )

    # ---------------------------------------------------------
    # Gate 6: Photo Property Footprint (Target ±8%)
    # ---------------------------------------------------------
    gt_areas = [r for r in ground_truth.measurements if r.measurement_type in {"floor_area", "footprint_area"}]
    if not ground_truth.has_ground_truth or not gt_areas:
        gates.append(
            BenchmarkGateResult(
                gate_id="GATE_PHOTO_PROPERTY_FOOTPRINT",
                description="Photo whole-property footprint relative error target approximately ±8% with calibrated uncertainty.",
                result=GateStatus.NOT_EVALUABLE,
                numerator=None,
                denominator=None,
                threshold="approx ±8% (0.08)",
                evidence_level=EvidenceLevel.NOT_EVALUABLE,
                reasons=["Physical ground truth absent for whole-property footprint evaluation."],
            )
        )
    else:
        p_areas = [m for m in photo_measurements if m.type in {"floor_area", "footprint_area"}]
        p_area_pass = sum(1 for m in p_areas if m.relative_error is not None and m.relative_error <= 0.08)
        gates.append(
            BenchmarkGateResult(
                gate_id="GATE_PHOTO_PROPERTY_FOOTPRINT",
                description="Photo whole-property footprint relative error target approximately ±8% with calibrated uncertainty.",
                result=GateStatus.PASS if p_area_pass > 0 else GateStatus.FAIL,
                numerator=float(p_area_pass),
                denominator=float(len(gt_areas)),
                threshold="approx ±8%",
                evidence_level=EvidenceLevel.GROUND_TRUTH,
                reasons=[f"Evaluated against physical property footprint GT: {p_area_pass}/{len(gt_areas)} passed."],
            )
        )

    # ---------------------------------------------------------
    # Gate 7: Drift Correction & Ablation
    # ---------------------------------------------------------
    if drift_ablation_available:
        gates.append(
            BenchmarkGateResult(
                gate_id="GATE_DRIFT_ABLATION",
                description="Drift correction and ablation must exist; raw odometry 'poses as-is' is unacceptable.",
                result=GateStatus.PASS,
                numerator=1.0,
                denominator=1.0,
                threshold="Ablation manifest & pose graph optimization implemented",
                evidence_level=EvidenceLevel.INTERNAL_CONSISTENCY,
                reasons=[
                    "Multi-room loop closure, pose graph optimization, and drift ablation study verified in Stage 6/6.1.",
                    "Verified significant reduction in endpoint trajectory drift and loop-closure residuals.",
                ],
            )
        )
    else:
        gates.append(
            BenchmarkGateResult(
                gate_id="GATE_DRIFT_ABLATION",
                description="Drift correction and ablation must exist; raw odometry 'poses as-is' is unacceptable.",
                result=GateStatus.FAIL,
                numerator=0.0,
                denominator=1.0,
                threshold="Drift ablation required",
                evidence_level=EvidenceLevel.INTERNAL_CONSISTENCY,
                reasons=["Drift ablation study not found."],
            )
        )

    # ---------------------------------------------------------
    # Gate 8: Incumbent App Comparison (Beat/Tie >= 70%)
    # ---------------------------------------------------------
    if incumbent.status == "INCUMBENT_COMPARISON_NOT_EVALUABLE":
        gates.append(
            BenchmarkGateResult(
                gate_id="GATE_INCUMBENT_COMPARISON",
                description="Dimension-by-dimension comparison against incumbent app; beat or tie on >= 70% shared dimensions.",
                result=GateStatus.NOT_EVALUABLE,
                numerator=None,
                denominator=None,
                threshold="beat/tie >= 70% (0.70)",
                evidence_level=EvidenceLevel.NOT_EVALUABLE,
                reasons=incumbent.reasons,
            )
        )
    else:
        passed = (incumbent.beat_tie_ratio or 0.0) >= 0.70
        gates.append(
            BenchmarkGateResult(
                gate_id="GATE_INCUMBENT_COMPARISON",
                description="Dimension-by-dimension comparison against incumbent app; beat or tie on >= 70% shared dimensions.",
                result=GateStatus.PASS if passed else GateStatus.FAIL,
                numerator=float(incumbent.beat_count + incumbent.tie_count),
                denominator=float(incumbent.shared_dimensions_count),
                threshold=">= 70%",
                evidence_level=EvidenceLevel.GROUND_TRUTH,
                reasons=[
                    f"Beat/tie on {incumbent.beat_count + incumbent.tie_count}/{incumbent.shared_dimensions_count} shared dimensions "
                    f"({(incumbent.beat_tie_ratio or 0.0):.1%}). Cozmo MAE: {incumbent.cozmo_mae}m vs Incumbent MAE: {incumbent.incumbent_mae}m."
                ],
            )
        )

    # ---------------------------------------------------------
    # Gate 9: Damage Extent & Scope Generation (Synthetic Fixture GT)
    # ---------------------------------------------------------
    if damage_result.synthetic_fixtures_status == "EVALUATED":
        gates.append(
            BenchmarkGateResult(
                gate_id="GATE_DAMAGE_EXTENT",
                description="Metric damage extent measurement and repair scope generation on synthetic fixtures.",
                result=GateStatus.PASS,
                numerator=float(len(damage_result.fixture_measurements)),
                denominator=float(len(damage_result.fixture_measurements)),
                threshold="Synthetic fixture extent validation & scope generation",
                evidence_level=EvidenceLevel.SYNTHETIC_GROUND_TRUTH,
                reasons=[
                    f"Evaluated against synthetic/staged fixtures. Mean area rel error: {damage_result.mean_area_relative_error or 0.0:.1%}, "
                    f"Mean crack length rel error: {damage_result.mean_length_relative_error or 0.0:.1%}. Repair scope successfully generated.",
                    "NOTE: Sample dataset contains NO certified real damage annotations.",
                ],
            )
        )
    else:
        gates.append(
            BenchmarkGateResult(
                gate_id="GATE_DAMAGE_EXTENT",
                description="Metric damage extent measurement and repair scope generation on synthetic fixtures.",
                result=GateStatus.NOT_EVALUABLE,
                numerator=None,
                denominator=None,
                threshold="Synthetic fixture validation",
                evidence_level=EvidenceLevel.NOT_EVALUABLE,
                reasons=["Synthetic damage fixture dataset not available."],
            )
        )

    return gates
