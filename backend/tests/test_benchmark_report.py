"""Unit Tests for Benchmark Report Generation and Artifact Integrity.

Purpose:
    Validates end-to-end benchmark reporting:
      - Baseline commit is recorded accurately.
      - Failed reconstructions and gates are preserved rather than excluded.
      - Mandatory disclaimers (CROSS-TIER AGREEMENT, NOT GROUND-TRUTH ACCURACY) are present.
      - Incumbent comparison correctly reflects NOT_EVALUABLE without fake results.
      - Worst system failure candidate is ranked and nominated for Stage 11 without code modification.

Stage:
    Stage 10 (Frozen System Benchmark + Development Evaluation)

Inputs:
    Mock benchmark run outputs and populated tier containers.

Outputs:
    Assertions verifying Markdown report sections, CSV rows, and worst failure nomination.

Units & Coordinate Systems:
    Report strings and file paths.

Dependencies:
    pytest, os, backend.app.benchmark.report, backend.app.benchmark.models,
    backend.app.benchmark.damage_metrics, backend.app.benchmark.repeatability,
    backend.app.benchmark.incumbent.

Assumptions:
    Report generation is deterministic and reproducible given identical inputs.

Failure Modes:
    Assertion failure if mandatory disclaimers or baseline commits are omitted.

First Debugging Points:
    Check generate_benchmark_markdown and identify_worst_failure in backend.app.benchmark.report.
"""

import os
import pytest
from backend.app.benchmark.damage_metrics import DamageBenchmarkResult
from backend.app.benchmark.gate_evaluator import BenchmarkGateResult
from backend.app.benchmark.incumbent import IncumbentComparisonResult
from backend.app.benchmark.models import (
    EvidenceLevel,
    FailureCategory,
    GateStatus,
    SystemStatus,
    TierBenchmarkResult,
)
from backend.app.benchmark.repeatability import RepeatabilityResult
from backend.app.benchmark.report import (
    generate_benchmark_markdown,
    identify_worst_failure,
)
from backend.app.benchmark.tier_comparison import CrossTierComparisonResult
from backend.app.benchmark.uncertainty import UncertaintyAuditSummary


def test_worst_failure_candidate_identification():
    """Verify objective identification and nomination of Stage 11 fix candidate.

    Parameters:
        None.

    Returns:
        None.

    Units:
        Unitless candidate ranking.

    Assumptions:
        Video registration failure on multi-room scan is ranked as top critical candidate.

    Failure Conditions:
        Fails if critical registration failure is overlooked.

    Dependencies:
        identify_worst_failure, TierBenchmarkResult, FailureCategory, SystemStatus.

    Debugging Clues:
        Check ranking weights in identify_worst_failure.
    """
    tier_results = {
        "video": TierBenchmarkResult(
            capture_id="video_multi_room",
            tier="video",
            status=SystemStatus.PROVISIONAL,
            failures=[FailureCategory.REGISTRATION_FAILURE.value, FailureCategory.NOT_EVALUABLE.value],
            coverage=0.45,
        ),
        "lidar": TierBenchmarkResult(
            capture_id="c00a170fe1",
            tier="lidar",
            status=SystemStatus.WORKING,
            failures=[],
            coverage=1.0,
        ),
    }

    worst = identify_worst_failure(tier_results=tier_results, gate_results=[])
    assert worst["nominated_candidate"] == "VIDEO_MULTIROOM_SFM_REGISTRATION_FAILURE"
    assert worst["tier"] == "video"
    assert worst["severity"] == "CRITICAL"
    assert "4 of 40 keyframes" in worst["evidence"]


def test_benchmark_report_content_and_disclaimers():
    """Verify that generated Markdown report contains all mandatory sections and disclaimers.

    Parameters:
        None.

    Returns:
        None.

    Units:
        Markdown string formatting.

    Assumptions:
        Report must include baseline commit, cross-tier disclaimer, and Stage 11 recommendation.

    Failure Conditions:
        Fails if any mandatory disclaimer or baseline commit string is missing.

    Dependencies:
        generate_benchmark_markdown.

    Debugging Clues:
        Check section titles in generate_benchmark_markdown.
    """
    commit_sha = "98aea6f73270c05048b1ec85feb02479cadc20d8"
    tier_results = {
        "lidar": TierBenchmarkResult("lidar_scan", "lidar", SystemStatus.WORKING, [], [], 22.2, 1.0),
        "video": TierBenchmarkResult("video_scan", "video", SystemStatus.PROVISIONAL, [], [FailureCategory.REGISTRATION_FAILURE.value], 24.4, 0.45),
        "photo": TierBenchmarkResult("photo_scan", "photo", SystemStatus.PROVISIONAL, [], [FailureCategory.TOPOLOGY_FAILURE.value], 23.7, 0.55),
        "damage": TierBenchmarkResult("damage_dev", "damage", SystemStatus.WORKING, [], [], 4.4, 1.0),
    }
    ct_res = [
        CrossTierComparisonResult("lidar", "video", [], 0, 4, 0, 1, 0, {})
    ]
    gates = [
        BenchmarkGateResult("GATE_DRIFT_ABLATION", "Drift ablation", GateStatus.PASS, 1.0, 1.0, "req", EvidenceLevel.INTERNAL_CONSISTENCY),
        BenchmarkGateResult("GATE_OPENING_WIDTH", "Opening width", GateStatus.NOT_EVALUABLE, None, None, "<= 0.02m", EvidenceLevel.NOT_EVALUABLE, ["No physical GT"]),
    ]
    uncertainty_audits = {
        "lidar": UncertaintyAuditSummary("lidar", 5, 5, [], 0.05, 0.03, 0.08, False, "CALIBRATION_NOT_EVALUABLE"),
    }
    repeatability = RepeatabilityResult("lidar", "s1", "s1", "REPEATABILITY_NOT_EVALUABLE", reasons=["No repeats"])
    incumbent = IncumbentComparisonResult("INCUMBENT_COMPARISON_NOT_EVALUABLE", reasons=["No incumbent export"])
    damage_res = DamageBenchmarkResult(class_accuracy=1.0, mean_area_relative_error=0.04, mean_length_relative_error=0.02)
    worst = {
        "nominated_candidate": "VIDEO_MULTIROOM_SFM_REGISTRATION_FAILURE",
        "tier": "video",
        "severity": "CRITICAL",
        "frequency": "High",
        "blocking_effect": "Blocks multiroom floorplan",
        "evidence": "4/40 registered",
        "likely_root_cause": "Visual feature drift",
    }

    md_report = generate_benchmark_markdown(
        baseline_commit=commit_sha,
        tier_results=tier_results,
        cross_tier_results=ct_res,
        gate_results=gates,
        uncertainty_audits=uncertainty_audits,
        repeatability=repeatability,
        incumbent=incumbent,
        damage_result=damage_res,
        runtimes={},
        worst_failure=worst,
    )

    assert commit_sha in md_report
    assert "CROSS-TIER AGREEMENT, NOT GROUND-TRUTH ACCURACY" in md_report
    assert "CALIBRATION_NOT_EVALUABLE" in md_report
    assert "REPEATABILITY_NOT_EVALUABLE" in md_report
    assert "INCUMBENT_COMPARISON_NOT_EVALUABLE" in md_report
    assert "DO NOT FIX THIS FAILURE IN STAGE 10" in md_report
    assert "VIDEO_MULTIROOM_SFM_REGISTRATION_FAILURE" in md_report
