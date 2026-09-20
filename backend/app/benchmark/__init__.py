"""Benchmark and Systematic Evaluation Package for Cozmo AI Project.

Purpose:
    Provides standardized benchmark evaluation routines, ground truth import contracts,
    geometric measurement matching, cross-tier comparison, uncertainty audits,
    repeatability checks, and challenge gate evaluation for Stage 10.

Stage:
    Stage 10 (Frozen System Benchmark + Development Evaluation)

Inputs:
    Reconstructed floorplan artifacts, geometric models, damage assessment outputs,
    and optional physical ground-truth specifications.

Outputs:
    Benchmark metrics, gate results, CSV summaries, and comprehensive Markdown reports.

Units:
    Meters, square meters, degrees, seconds.

Dependencies:
    backend.app.benchmark.models
    backend.app.benchmark.ground_truth
    backend.app.benchmark.matcher
    backend.app.benchmark.metrics
    backend.app.benchmark.tier_comparison
    backend.app.benchmark.uncertainty
    backend.app.benchmark.repeatability
    backend.app.benchmark.gate_evaluator
    backend.app.benchmark.damage_metrics
    backend.app.benchmark.incumbent
    backend.app.benchmark.report

Assumptions:
    Follows frozen pipeline execution; does not mutate production reconstruction logic.

Failure Modes:
    Gracefully produces NOT_EVALUABLE when evidence or inputs are absent.

First Debugging Points:
    Verify model imports and evidence level mappings.
"""

from backend.app.benchmark.models import (
    BenchmarkGateResult,
    BenchmarkMeasurement,
    EvidenceLevel,
    FailureCategory,
    GateStatus,
    SystemStatus,
    TierBenchmarkResult,
)

__all__ = [
    "BenchmarkGateResult",
    "BenchmarkMeasurement",
    "EvidenceLevel",
    "FailureCategory",
    "GateStatus",
    "SystemStatus",
    "TierBenchmarkResult",
]
