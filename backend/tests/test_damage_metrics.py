"""Unit Tests for Damage Metrics and Synthetic Development Fixtures.

Purpose:
    Validates damage evaluation separation:
      - Real sample rooms report NO ANNOTATED REAL DAMAGE AVAILABLE without fabricating metrics.
      - Synthetic fixture evaluation is strictly labeled SYNTHETIC_GROUND_TRUTH.
      - Classification accuracy, metric extent errors, and scope generation are evaluated.

Stage:
    Stage 10 (Frozen System Benchmark + Development Evaluation)

Inputs:
    Synthetic fixture JSON definitions and test prediction dictionaries.

Outputs:
    Assertions verifying evidence levels, classification rates, and metric relative errors.

Units & Coordinate Systems:
    Areas in square meters (m^2), lengths in meters (m).

Dependencies:
    pytest, backend.app.benchmark.damage_metrics, backend.app.benchmark.models.

Assumptions:
    Synthetic damage evaluation evaluates code paths and metric sizing on staged targets only.

Failure Modes:
    Assertion failure if real sample data is falsely credited with annotated ground truth.

First Debugging Points:
    Check evaluate_damage_benchmarks in backend.app.benchmark.damage_metrics.
"""

import pytest
from backend.app.benchmark.damage_metrics import evaluate_damage_benchmarks
from backend.app.benchmark.models import EvidenceLevel


def test_damage_sample_data_unannotated_status():
    """Verify that sample dataset damage is reported as NO ANNOTATED REAL DAMAGE AVAILABLE.

    Parameters:
        None.

    Returns:
        None.

    Units:
        Unitless status check.

    Assumptions:
        Sample scans contain no certified forensic annotations.

    Failure Conditions:
        Fails if sample data status indicates ground-truth accuracy.

    Dependencies:
        evaluate_damage_benchmarks.

    Debugging Clues:
        Check sample_data_status field in DamageBenchmarkResult.
    """
    res = evaluate_damage_benchmarks(sample_damage_outputs=None)
    assert res.sample_data_status == "NO ANNOTATED REAL DAMAGE AVAILABLE"
    assert "REAL SAMPLE ROOMS CONTAIN NO CERTIFIED FORENSIC DAMAGE LABELS" in res.disclaimer


def test_synthetic_damage_fixture_evaluation():
    """Verify deterministic metric sizing and class matching against synthetic fixture GT.

    Parameters:
        None.

    Returns:
        None.

    Units:
        Square meters (m^2), meters (m).

    Assumptions:
        Evidence level is strictly SYNTHETIC_GROUND_TRUTH.

    Failure Conditions:
        Fails if evidence level is not SYNTHETIC_GROUND_TRUTH or if errors are inaccurate.

    Dependencies:
        evaluate_damage_benchmarks, EvidenceLevel.

    Debugging Clues:
        Check fixture JSON at data/damage_dev/SYNTHETIC_DEVELOPMENT_DAMAGE_SET.json.
    """
    # Supply known test predictions for fixtures
    preds = {
        "dev_water_stain_01": {"class": "water_stain", "area_m2": 1.20, "length_m": None},
        "dev_crack_01": {"class": "surface_crack", "area_m2": None, "length_m": 1.50},
        "dev_hole_01": {"class": "hole_or_missing_material", "area_m2": 0.35, "length_m": None},
        "dev_mold_01": {"class": "mold_like_discoloration", "area_m2": 0.60, "length_m": None},
    }

    res = evaluate_damage_benchmarks(
        sample_damage_outputs=None,
        synthetic_fixture_json_path="data/damage_dev/SYNTHETIC_DEVELOPMENT_DAMAGE_SET.json",
        predictions_map=preds,
    )

    assert res.synthetic_fixtures_status == "EVALUATED"
    assert res.evidence_level == EvidenceLevel.SYNTHETIC_GROUND_TRUTH
    assert res.class_accuracy == pytest.approx(1.0)
    assert res.mean_area_relative_error == pytest.approx(0.0)
    assert res.mean_length_relative_error == pytest.approx(0.0)
    assert res.concealed_risk_evaluated is True
    assert res.scope_generated is True
