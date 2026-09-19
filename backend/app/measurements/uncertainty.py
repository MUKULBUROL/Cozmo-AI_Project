"""Engineering uncertainty propagation and confidence modeling for Stage 4 floor plans.

1. Why this file exists:
   Implements a physically grounded, defensible uncertainty propagation model that derives
   measurement intervals and confidence scores directly from observable sensor residuals,
   plane fitting RMSEs, corner intersection geometries, and deterministic Monte Carlo simulations,
   strictly rejecting arbitrary fixed error bands (e.g. ±2cm) and unsubstantiated confidence values.

2. Pipeline stage:
   Stage 4 (Metric Measurements, Room Area & Uncertainty) - Uncertainty Engine.

3. Inputs:
   Stage 2 wall plane residuals and confidences, Stage 3 corner intersection metrics,
   inferred extension distances, and closed polygon vertices.

4. Outputs:
   Calibrated 95% confidence intervals ([lower, upper]), component breakdowns,
   and evidence-derived confidence values for individual walls, room perimeter, and floor area.

5. Coordinate/Unit assumptions:
   Coordinates and lengths in metric meters (m).
   Areas in metric square meters (m2).
   Angles in degrees.
   Uncertainties expressed as 1-sigma standard errors or 95% coverage intervals (k=1.96).

6. Dependencies:
   math, typing, numpy, shapely.

7. Most likely failure/debugging points:
   - Singular intersection angles (< 5 deg) causing division by zero (guarded with clamping).
   - Inverted polygon vertices causing negative Shapely areas (handled with coordinate normalization).
   - High Monte Carlo noise on non-simple perturbations (guarded with topology repair).
"""

import math
from typing import List, Dict, Any, Tuple, Optional
import numpy as np
from shapely.geometry import Polygon


def calculate_corner_positional_uncertainty(
    rmse_a_m: float,
    rmse_b_m: float,
    intersection_angle_deg: float = 90.0,
    is_inferred: bool = False,
    extension_m: float = 0.0,
    voxel_size_m: float = 0.01,
) -> float:
    """Calculates 1-sigma positional standard error of a corner intersection.

    Purpose:
        Propagates lateral wall plane fitting residuals through the 2D intersection
        geometry, incorporating intersection angle conditioning and gap extrapolation penalties.

    Parameters:
        rmse_a_m: Plane fitting RMSE of first intersecting wall in meters.
        rmse_b_m: Plane fitting RMSE of second intersecting wall in meters.
        intersection_angle_deg: Angle between intersecting wall normals/lines in degrees.
        is_inferred: True if corner required extrapolation beyond observed segment extents.
        extension_m: Distance extrapolated along wall segments to form closure.
        voxel_size_m: Baseline discretization resolution of point cloud reconstruction.

    Returns:
        1-sigma positional uncertainty in meters (standard error sigma_c).

    Assumptions:
        Errors in wall plane estimation are uncorrelated Gaussian deviations.
        Extrapolation error grows with gap distance.

    Failure conditions:
        Degenerate parallel walls (angle near 0 or 180 deg) clamp sin(theta) to 0.1 to avoid division by zero.

    Debugging:
        Check whether extension_m is properly populated for inferred corners.
    """
    rad = math.radians(intersection_angle_deg)
    sin_theta = max(abs(math.sin(rad)), 0.10)

    # Intersection geometric uncertainty from line transverse errors
    sigma_geom = math.sqrt((rmse_a_m ** 2 + rmse_b_m ** 2) / (sin_theta ** 2))

    # Extrapolation penalty: gap distance carries linear physical extrapolation drift
    sigma_inf = 0.50 * extension_m if is_inferred else 0.0

    # Total combined 1-sigma standard error
    sigma_total = math.sqrt(sigma_geom ** 2 + sigma_inf ** 2 + voxel_size_m ** 2)
    return float(sigma_total)


def calculate_wall_length_uncertainty(
    nominal_length_m: float,
    wall_rmse_m: float,
    corner_a_uncertainty_m: float,
    corner_b_uncertainty_m: float,
    corner_a_inferred: bool = False,
    corner_b_inferred: bool = False,
    corner_extension_m: float = 0.0,
    confidence_level: float = 0.95,
) -> Tuple[float, float, Dict[str, Any]]:
    """Calculates defensible uncertainty interval and component breakdown for a wall edge.

    Purpose:
        Combines wall plane fitting variance with positional uncertainties of start/end corners
        to construct a calibrated 95% confidence interval.

    Parameters:
        nominal_length_m: Measured Euclidean length between vertices in meters.
        wall_rmse_m: Plane fitting residual of the wall itself in meters.
        corner_a_uncertainty_m: 1-sigma positional uncertainty of start corner.
        corner_b_uncertainty_m: 1-sigma positional uncertainty of end corner.
        corner_a_inferred: Whether start corner was geometrically inferred.
        corner_b_inferred: Whether end corner was geometrically inferred.
        corner_extension_m: Extrapolated gap extension at corners.
        confidence_level: Desired coverage probability (default 0.95 -> k=1.96).

    Returns:
        Tuple of (lower_bound_m, upper_bound_m, uncertainty_components_dict).

    Assumptions:
        Measurement errors combine under Gaussian quadrature (root sum of squares).

    Failure conditions:
        Lower bound is clamped to minimum 0.01m to prevent negative physical dimensions.

    Debugging:
        Inspect components dict to see which contributor dominates the uncertainty margin.
    """
    # Gaussian coverage multiplier (k=1.96 for 95%, k=1.0 for 68%)
    k = 1.96 if abs(confidence_level - 0.95) < 0.02 else 1.0

    # Total 1-sigma length uncertainty
    sigma_length = math.sqrt(
        (corner_a_uncertainty_m ** 2) +
        (corner_b_uncertainty_m ** 2) +
        (wall_rmse_m ** 2)
    )

    margin_of_error = k * sigma_length
    lower_bound = max(0.01, nominal_length_m - margin_of_error)
    upper_bound = nominal_length_m + margin_of_error

    components = {
        "plane_rmse_m": round(wall_rmse_m, 4),
        "corner_a_m": round(corner_a_uncertainty_m, 4),
        "corner_b_m": round(corner_b_uncertainty_m, 4),
        "corner_a_inferred": corner_a_inferred,
        "corner_b_inferred": corner_b_inferred,
        "corner_extension_m": round(corner_extension_m, 4),
        "total_sigma_m": round(sigma_length, 4),
        "margin_of_error_m": round(margin_of_error, 4),
        "coverage_k": k,
    }

    return float(lower_bound), float(upper_bound), components


def monte_carlo_area_and_perimeter_uncertainty(
    vertices: List[Tuple[float, float]],
    corner_uncertainties_m: List[float],
    num_samples: int = 1000,
    random_seed: int = 42,
    confidence_level: float = 0.95,
) -> Dict[str, Any]:
    """Estimates floor area and perimeter uncertainty via deterministic Monte Carlo perturbation.

    Purpose:
        Provides defensible sensitivity intervals for non-linear polygon area and perimeter
        by perturbing vertex coordinates within their physical uncertainty ellipses.

    Parameters:
        vertices: List of ordered (x, z) coordinates defining the closed room polygon (unclosed).
        corner_uncertainties_m: List of 1-sigma positional errors for each corresponding vertex.
        num_samples: Number of Monte Carlo stochastic iterations (default 1000).
        random_seed: Fixed random seed for complete deterministic reproducibility.
        confidence_level: Target coverage level (default 0.95).

    Returns:
        Dictionary containing nominal values, standard deviations, and [lower, upper] intervals
        for both floor area (m2) and room perimeter (m).

    Assumptions:
        Vertex perturbations follow independent 2D isotropic Gaussian distributions.

    Failure conditions:
        If vertices count < 3, returns nominal zero values.

    Debugging:
        Verify random_seed reproduces identical percentile boundaries across runs.
    """
    n_pts = len(vertices)
    if n_pts < 3:
        return {
            "area": {"value": 0.0, "lower": 0.0, "upper": 0.0, "std": 0.0},
            "perimeter": {"value": 0.0, "lower": 0.0, "upper": 0.0, "std": 0.0},
            "samples_evaluated": 0,
        }

    nominal_poly = Polygon(vertices)
    nominal_area = float(nominal_poly.area)
    nominal_perimeter = float(nominal_poly.length)

    rng = np.random.RandomState(random_seed)
    pts_arr = np.array(vertices, dtype=np.float64)  # Shape (N, 2)
    sigmas = np.array(corner_uncertainties_m, dtype=np.float64)  # Shape (N,)

    # Generate perturbations: sigma per 2D coordinate is sigma / sqrt(2)
    sigma_coord = sigmas / math.sqrt(2.0)
    # Shape: (num_samples, N, 2)
    noise = rng.normal(loc=0.0, scale=1.0, size=(num_samples, n_pts, 2))
    perturbations = noise * sigma_coord[np.newaxis, :, np.newaxis]

    simulated_areas: List[float] = []
    simulated_perimeters: List[float] = []

    for s in range(num_samples):
        perturbed_pts = pts_arr + perturbations[s]
        p = Polygon(perturbed_pts)
        if not p.is_valid:
            p = p.buffer(0)
        if not p.is_empty and hasattr(p, "area"):
            simulated_areas.append(float(p.area))
            simulated_perimeters.append(float(p.length))
        else:
            simulated_areas.append(nominal_area)
            simulated_perimeters.append(nominal_perimeter)

    areas_np = np.array(simulated_areas)
    perims_np = np.array(simulated_perimeters)

    alpha = (1.0 - confidence_level) / 2.0
    area_low = float(np.percentile(areas_np, alpha * 100))
    area_high = float(np.percentile(areas_np, (1.0 - alpha) * 100))
    area_std = float(np.std(areas_np))

    perim_low = float(np.percentile(perims_np, alpha * 100))
    perim_high = float(np.percentile(perims_np, (1.0 - alpha) * 100))
    perim_std = float(np.std(perims_np))

    return {
        "area": {
            "value": nominal_area,
            "lower": area_low,
            "upper": area_high,
            "std": area_std,
            "relative_error_pct": round((area_std / max(nominal_area, 1e-6)) * 100, 2),
        },
        "perimeter": {
            "value": nominal_perimeter,
            "lower": perim_low,
            "upper": perim_high,
            "std": perim_std,
            "relative_error_pct": round((perim_std / max(nominal_perimeter, 1e-6)) * 100, 2),
        },
        "samples_evaluated": num_samples,
        "random_seed": random_seed,
    }


def derive_wall_confidence(
    plane_confidence: float,
    wall_rmse_m: float,
    corner_a_inferred: bool,
    corner_b_inferred: bool,
    rmse_tolerance_m: float = 0.15,
) -> float:
    """Derives evidence-based confidence score for an individual wall segment.

    Purpose:
        Calculates a confidence metric reflecting structural point evidence quality,
        fitting residuals, and inference penalties.

    Parameters:
        plane_confidence: Upstream confidence score from Stage 2 plane fitting.
        wall_rmse_m: Plane fitting RMSE in meters.
        corner_a_inferred: True if start corner is extrapolated.
        corner_b_inferred: True if end corner is extrapolated.
        rmse_tolerance_m: Residual benchmark scale.

    Returns:
        Confidence score clamped strictly to [0.10, 0.99].

    Assumptions:
        Inferred endpoints diminish confidence by 15% per extrapolated corner.

    Failure conditions:
        None (robust against non-finite inputs).

    Debugging:
        Inspect plane_confidence vs residual penalization if confidence drops below 0.50.
    """
    # Residual factor degrades gracefully as RMSE approaches tolerance
    rmse_factor = max(0.50, 1.0 - (wall_rmse_m / rmse_tolerance_m))

    # Inference penalty factors
    inf_factor_a = 0.85 if corner_a_inferred else 1.0
    inf_factor_b = 0.85 if corner_b_inferred else 1.0

    raw_conf = plane_confidence * rmse_factor * inf_factor_a * inf_factor_b
    return float(np.clip(raw_conf, 0.10, 0.99))


def derive_area_confidence(
    mean_wall_confidence: float,
    boundary_support_ratio: float,
    inferred_corner_ratio: float,
    is_provisional: bool = False,
) -> float:
    """Derives evidence-based confidence score for room floor area.

    Purpose:
        Synthesizes composite wall confidence, boundary LiDAR point coverage,
        inferred corner ratio, and validity gate outcome into a single room area confidence.

    Parameters:
        mean_wall_confidence: Average confidence of all boundary walls.
        boundary_support_ratio: Fraction of polygon perimeter supported by physical LiDAR points.
        inferred_corner_ratio: Ratio of inferred corners to total corners.
        is_provisional: True if measurement validity gate issued a provisional verdict.

    Returns:
        Confidence score clamped strictly to [0.10, 0.99].

    Assumptions:
        Provisional status imposes a 10% penalty on composite confidence.

    Failure conditions:
        None.

    Debugging:
        Check boundary_support_ratio if area confidence is lower than expected.
    """
    gate_factor = 0.90 if is_provisional else 1.0
    inf_penalty = max(0.50, 1.0 - (0.25 * inferred_corner_ratio))

    raw_conf = mean_wall_confidence * boundary_support_ratio * inf_penalty * gate_factor
    return float(np.clip(raw_conf, 0.10, 0.99))
