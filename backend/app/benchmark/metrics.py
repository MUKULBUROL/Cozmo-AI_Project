"""Metric Calculation and Statistical Aggregation for Benchmark Evaluation.

Purpose:
    Provides standardized arithmetic functions for error computation (absolute and relative),
    reconstruction coverage ratios, uncertainty interval validation, and descriptive error statistics.
    Ensures null or missing references gracefully propagate as None rather than falsifying zero error.

Stage:
    Stage 10 (Frozen System Benchmark + Development Evaluation)

Inputs:
    Predicted scalar metrics, reference values, bounds, and arrays of residual errors.

Outputs:
    Absolute/relative errors, summary statistic dictionaries (RMSE, MAE, Max, Median, Std),
    and integrity validation flags.

Units & Coordinate Systems:
    Lengths in meters (m), Areas in square meters (m^2), Residuals in meters or percentage ratios.

Dependencies:
    math, statistics, typing.

Assumptions:
    Relative error is defined as |predicted - reference| / reference when reference != 0.
    Division by zero yields None.

Failure Modes:
    Passing NaN or infinite numbers handles gracefully with None or filtered statistical sets.

First Debugging Points:
    Verify reference values are positive non-zero before inspecting relative errors.
"""

import math
from typing import Any, Dict, List, Optional


def compute_absolute_error(predicted: Optional[float], reference: Optional[float]) -> Optional[float]:
    """Compute absolute error between predicted and reference values.

    Parameters:
        predicted: Estimated numerical value from pipeline.
        reference: Reference numerical value from ground truth or cross-tier source.

    Returns:
        Absolute difference |predicted - reference| as a float, or None if either input is None.

    Units / Coordinates:
        Matches input units (e.g., meters, square meters).

    Assumptions:
        Inputs are scalar floating point numbers.

    Failure Conditions:
        Returns None if predicted is None, reference is None, or either is NaN.

    Dependencies:
        math.isnan.

    Debugging Clues:
        Check if measurement was marked NOT_EVALUABLE or UNMATCHED prior to error computation.
    """
    if predicted is None or reference is None:
        return None
    if math.isnan(predicted) or math.isnan(reference):
        return None
    return abs(float(predicted) - float(reference))


def compute_relative_error(predicted: Optional[float], reference: Optional[float]) -> Optional[float]:
    """Compute relative fractional error |predicted - reference| / reference.

    Parameters:
        predicted: Estimated numerical value from pipeline.
        reference: Reference numerical value from ground truth or cross-tier source.

    Returns:
        Fractional error as float (e.g. 0.03 for 3%), or None if either input is None or reference == 0.

    Units / Coordinates:
        Unitless ratio.

    Assumptions:
        Reference must be strictly non-zero to avoid division by zero.

    Failure Conditions:
        Returns None if reference is zero, None, or inputs are NaN.

    Dependencies:
        compute_absolute_error, math.isnan.

    Debugging Clues:
        Examine if reference value is zero (e.g. zero displacement or zero angle).
    """
    abs_err = compute_absolute_error(predicted, reference)
    if abs_err is None or reference is None:
        return None
    ref_abs = abs(float(reference))
    if ref_abs < 1e-12:
        return None
    return abs_err / ref_abs


def compute_coverage(produced: int, applicable: int) -> float:
    """Calculate engineering coverage ratio between produced features and applicable features.

    Parameters:
        produced: Number of successfully produced structural/metric entities.
        applicable: Total number of expected or applicable entities in domain.

    Returns:
        Coverage ratio between 0.0 and 1.0 (float). Returns 1.0 if applicable == 0.

    Units / Coordinates:
        Unitless ratio.

    Assumptions:
        Coverage reflects engineering completeness, NOT ground-truth measurement accuracy.

    Failure Conditions:
        Clamped to [0.0, 1.0] if produced > applicable or produced < 0.

    Dependencies:
        None.

    Debugging Clues:
        Inspect count of applicable rooms/walls to understand denominator source.
    """
    if applicable <= 0:
        return 1.0 if produced >= 0 else 0.0
    ratio = float(produced) / float(applicable)
    return max(0.0, min(1.0, ratio))


def compute_error_statistics(errors: List[float]) -> Dict[str, Optional[float]]:
    """Compute descriptive statistics for a collection of numerical errors.

    Parameters:
        errors: List of positive float error residuals.

    Returns:
        Dictionary containing 'count', 'mean', 'median', 'rmse', 'std', 'min', 'max'.

    Units / Coordinates:
        Matches unit of error inputs (e.g., meters).

    Assumptions:
        Only valid finite numerical values are included in statistics.

    Failure Conditions:
        If list is empty or contains no valid numbers, returns count=0 and None for all stats.

    Dependencies:
        math.sqrt, statistics.

    Debugging Clues:
        Ensure errors list is populated with absolute errors before calling.
    """
    valid = [float(e) for e in errors if e is not None and not math.isnan(e) and not math.isinf(e)]
    if not valid:
        return {
            "count": 0,
            "mean": None,
            "median": None,
            "rmse": None,
            "std": None,
            "min": None,
            "max": None,
        }

    n = len(valid)
    mean_val = sum(valid) / n
    sorted_val = sorted(valid)
    median_val = sorted_val[n // 2] if n % 2 != 0 else (sorted_val[n // 2 - 1] + sorted_val[n // 2]) / 2.0
    rmse_val = math.sqrt(sum(e * e for e in valid) / n)
    variance = sum((e - mean_val) ** 2 for e in valid) / n if n > 1 else 0.0
    std_val = math.sqrt(variance)

    return {
        "count": n,
        "mean": round(mean_val, 5),
        "median": round(median_val, 5),
        "rmse": round(rmse_val, 5),
        "std": round(std_val, 5),
        "min": round(min(valid), 5),
        "max": round(max(valid), 5),
    }


def verify_interval_integrity(lower: Optional[float], val: Optional[float], upper: Optional[float]) -> bool:
    """Verify statistical and logical integrity of an estimated uncertainty interval.

    Parameters:
        lower: Estimated lower confidence bound.
        val: Estimated nominal scalar value.
        upper: Estimated upper confidence bound.

    Returns:
        True if lower <= val <= upper and (upper - lower) >= 0; False otherwise.

    Units / Coordinates:
        Consistent scalar units.

    Assumptions:
        Intervals must encompass the nominal prediction without inverted bounds.

    Failure Conditions:
        Returns False if any input is None, NaN, infinite, or if lower > val or val > upper.

    Dependencies:
        math.isnan, math.isinf.

    Debugging Clues:
        Check variance propagation logic if upper < lower or nominal falls outside bounds.
    """
    if lower is None or val is None or upper is None:
        return False
    if math.isnan(lower) or math.isnan(val) or math.isnan(upper):
        return False
    if math.isinf(lower) or math.isinf(val) or math.isinf(upper):
        return False
    return lower <= (val + 1e-9) and (val - 1e-9) <= upper and (upper >= lower)
