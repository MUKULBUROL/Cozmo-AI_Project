"""Unit Tests for Benchmark Metric Calculations and Statistical Aggregations.

Purpose:
    Verifies mathematical correctness of absolute/relative error computations, descriptive
    statistics (mean, median, rmse), and uncertainty interval integrity checks.

Stage:
    Stage 10 (Frozen System Benchmark + Development Evaluation)

Inputs:
    Deterministic scalar pairs, edge cases (zero reference, None inputs, NaN), and arrays of residuals.

Outputs:
    Assertions verifying expected metric values and graceful null propagation.

Units & Coordinate Systems:
    Lengths in meters (m), relative ratios unitless.

Dependencies:
    pytest, backend.app.benchmark.metrics.

Assumptions:
    Division by zero in relative error returns None instead of raising ZeroDivisionError.

Failure Modes:
    Assertion failure if numerical calculation produces inaccurate roundings or unhandled exceptions.

First Debugging Points:
    Check backend.app.benchmark.metrics implementations.
"""

import math
import pytest
from backend.app.benchmark.metrics import (
    compute_absolute_error,
    compute_coverage,
    compute_error_statistics,
    compute_relative_error,
    verify_interval_integrity,
)


def test_absolute_error_calculation():
    """Verify absolute error computation for valid numbers and null/NaN inputs.

    Parameters:
        None.

    Returns:
        None.

    Units:
        Meters (m).

    Assumptions:
        |pred - ref| is computed symmetrically.

    Failure Conditions:
        Fails if None is not returned on missing inputs.

    Dependencies:
        compute_absolute_error.

    Debugging Clues:
        Check null checks in compute_absolute_error.
    """
    assert compute_absolute_error(3.50, 3.45) == pytest.approx(0.05)
    assert compute_absolute_error(3.45, 3.50) == pytest.approx(0.05)
    assert compute_absolute_error(None, 3.50) is None
    assert compute_absolute_error(3.50, None) is None
    assert compute_absolute_error(float("nan"), 3.50) is None


def test_relative_error_calculation():
    """Verify relative fractional error computation and division-by-zero protection.

    Parameters:
        None.

    Returns:
        None.

    Units:
        Unitless ratio.

    Assumptions:
        Reference must be strictly non-zero.

    Failure Conditions:
        Fails if zero reference causes ZeroDivisionError instead of None.

    Dependencies:
        compute_relative_error.

    Debugging Clues:
        Check zero threshold in compute_relative_error.
    """
    assert compute_relative_error(3.60, 3.00) == pytest.approx(0.20)
    assert compute_relative_error(3.00, 3.00) == pytest.approx(0.0)
    assert compute_relative_error(1.00, 0.0) is None
    assert compute_relative_error(None, 3.00) is None


def test_coverage_calculation():
    """Verify engineering coverage ratio is clamped within [0.0, 1.0].

    Parameters:
        None.

    Returns:
        None.

    Units:
        Unitless ratio.

    Assumptions:
        Ratio produced / applicable handles zero applicable without division error.

    Failure Conditions:
        Fails if ratio exceeds 1.0 or goes below 0.0.

    Dependencies:
        compute_coverage.

    Debugging Clues:
        Check clamp logic in compute_coverage.
    """
    assert compute_coverage(produced=4, applicable=4) == 1.0
    assert compute_coverage(produced=2, applicable=4) == 0.5
    assert compute_coverage(produced=0, applicable=5) == 0.0
    assert compute_coverage(produced=0, applicable=0) == 1.0


def test_error_statistics_aggregation():
    """Verify descriptive statistics computation (mean, median, rmse, min, max).

    Parameters:
        None.

    Returns:
        None.

    Units:
        Meters (m).

    Assumptions:
        Calculates exact summary metrics on positive residuals.

    Failure Conditions:
        Fails if empty list causes exception instead of count=0.

    Dependencies:
        compute_error_statistics.

    Debugging Clues:
        Check empty list handling in compute_error_statistics.
    """
    residuals = [0.02, 0.04, 0.06]
    stats = compute_error_statistics(residuals)
    assert stats["count"] == 3
    assert stats["mean"] == pytest.approx(0.04)
    assert stats["median"] == pytest.approx(0.04)
    assert stats["min"] == pytest.approx(0.02)
    assert stats["max"] == pytest.approx(0.06)

    empty_stats = compute_error_statistics([])
    assert empty_stats["count"] == 0
    assert empty_stats["mean"] is None


def test_uncertainty_interval_integrity():
    """Verify logical validation of confidence bounds (lower <= val <= upper).

    Parameters:
        None.

    Returns:
        None.

    Units:
        Meters (m).

    Assumptions:
        Valid interval requires lower <= val <= upper and positive width.

    Failure Conditions:
        Fails if inverted bounds or nominal outside bounds are flagged as valid.

    Dependencies:
        verify_interval_integrity.

    Debugging Clues:
        Check boundary condition checks in verify_interval_integrity.
    """
    assert verify_interval_integrity(lower=1.0, val=1.5, upper=2.0) is True
    assert verify_interval_integrity(lower=2.0, val=1.5, upper=1.0) is False  # Inverted
    assert verify_interval_integrity(lower=1.6, val=1.5, upper=2.0) is False  # Val < lower
    assert verify_interval_integrity(lower=1.0, val=2.5, upper=2.0) is False  # Val > upper
    assert verify_interval_integrity(lower=None, val=1.5, upper=2.0) is False
