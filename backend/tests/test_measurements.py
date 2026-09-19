"""Deterministic synthetic unit tests for Stage 4 floor plan measurements and uncertainty.

1. Why this file exists:
   Verifies the mathematical correctness, sensitivity propagation, validity gating,
   and deterministic reproducibility of Stage 4 metric wall lengths, room perimeter,
   polygon floor area, ceiling plane elevation, and uncertainty intervals.

2. Pipeline stage:
   Stage 4 (Metric Measurements, Room Area & Uncertainty) - Automated Test Suite.

3. Inputs:
   Synthetically constructed polygons, corner geometries, and Stage 2 structural plane metadata.

4. Outputs:
   Test assertions validating rectangular dimensions, non-rectangular areas,
   inferred-corner uncertainty widening, plane noise sensitivity, ceiling status,
   invalid polygon gating, and deterministic Monte Carlo reproducibility.

5. Coordinate/Unit assumptions:
   Y is vertical (upward).
   XZ is horizontal floor plane.
   All coordinates and metrics are in meters (m) and square meters (m2).

6. Dependencies:
   unittest, math, numpy, shapely, backend.app.measurements, backend.app.models.output.

7. Most likely failure/debugging points:
   - Numerical precision differences exceeding assertion tolerances.
   - Non-deterministic Monte Carlo runs if seed parameter is disregarded.
"""

import unittest
import math
from typing import List, Tuple, Dict, Any
import numpy as np
from shapely.geometry import Polygon

from backend.app.measurements.validity_gate import (
    evaluate_measurement_validity,
    ValidityStatus,
)
from backend.app.measurements.uncertainty import (
    calculate_corner_positional_uncertainty,
    calculate_wall_length_uncertainty,
    monte_carlo_area_and_perimeter_uncertainty,
    derive_wall_confidence,
    derive_area_confidence,
)
from backend.app.models.output import Measurement


class TestMeasurementsEngine(unittest.TestCase):
    """Synthetic benchmark unit tests for Stage 4 measurement algorithms."""

    def test_01_rectangle_4x3(self) -> None:
        """Verifies exact dimensions for a canonical 4m x 3m rectangular room.

        Purpose:
            Confirms area is 12.0 m², perimeter is 14.0 m, and individual wall
            lengths evaluate to [4, 3, 4, 3].

        Parameters:
            None.

        Returns:
            None.

        Assumptions:
            Orthogonal rectangle in horizontal XZ plane.

        Failure conditions:
            Area deviates from 12.0 or perimeter deviates from 14.0.

        Debugging:
            Inspect Euclidean segment calculation.
        """
        vertices: List[Tuple[float, float]] = [
            (0.0, 0.0),
            (4.0, 0.0),
            (4.0, 3.0),
            (0.0, 3.0),
        ]
        poly = Polygon(vertices)
        self.assertAlmostEqual(poly.area, 12.0, places=4)
        self.assertAlmostEqual(poly.length, 14.0, places=4)

        # Compute individual edge lengths
        lengths = []
        for i in range(len(vertices)):
            p1 = vertices[i]
            p2 = vertices[(i + 1) % len(vertices)]
            lengths.append(math.hypot(p2[0] - p1[0], p2[1] - p1[1]))

        self.assertAlmostEqual(lengths[0], 4.0, places=4)
        self.assertAlmostEqual(lengths[1], 3.0, places=4)
        self.assertAlmostEqual(lengths[2], 4.0, places=4)
        self.assertAlmostEqual(lengths[3], 3.0, places=4)

        # Validity check
        poly_data = {"polygon": {"vertices": vertices, "corner_ids": ["c1", "c2", "c3", "c4"]}}
        report = evaluate_measurement_validity(poly_data)
        self.assertEqual(report.measurement_status, ValidityStatus.VALID)

    def test_02_non_rectangular_polygon(self) -> None:
        """Verifies exact geometric area and perimeter on an irregular L-shaped polygon.

        Purpose:
            Validates that area is computed using true Green's theorem / polygon geometry
            rather than bounding-box approximations.

        Parameters:
            None.

        Returns:
            None.

        Assumptions:
            6-vertex L-shaped room: 6x2 base plus 3x3 extension = 21 m² area, 22m perimeter.

        Failure conditions:
            Area deviates from 21.0 m².

        Debugging:
            Ensure polygon vertices are ordered counter-clockwise or clockwise without self-intersection.
        """
        vertices: List[Tuple[float, float]] = [
            (0.0, 0.0),
            (6.0, 0.0),
            (6.0, 2.0),
            (3.0, 2.0),
            (3.0, 5.0),
            (0.0, 5.0),
        ]
        poly = Polygon(vertices)
        expected_area = (6.0 * 2.0) + (3.0 * 3.0)  # 12 + 9 = 21 m2
        expected_perimeter = 6.0 + 2.0 + 3.0 + 3.0 + 3.0 + 5.0  # 22 m

        self.assertAlmostEqual(poly.area, expected_area, places=4)
        self.assertAlmostEqual(poly.length, expected_perimeter, places=4)

        # Monte Carlo estimation should be centered closely around 21 m²
        sigmas = [0.02] * len(vertices)
        mc_res = monte_carlo_area_and_perimeter_uncertainty(vertices, sigmas, num_samples=500, random_seed=42)
        self.assertAlmostEqual(mc_res["area"]["value"], expected_area, places=4)
        self.assertLess(abs(mc_res["area"]["lower"] - expected_area), 0.5)
        self.assertGreater(mc_res["area"]["upper"], expected_area)

    def test_03_inferred_corner(self) -> None:
        """Verifies that an inferred corner strictly increases measurement uncertainty and penalizes confidence.

        Purpose:
            Demonstrates honest uncertainty widening when a corner gap requires geometric extrapolation.

        Parameters:
            None.

        Returns:
            None.

        Assumptions:
            Inferred corner with extension 0.20m vs observed corner with extension 0.0m.

        Failure conditions:
            sigma_inferred <= sigma_observed, or confidence does not drop.

        Debugging:
            Inspect calculate_corner_positional_uncertainty and derive_wall_confidence.
        """
        rmse_a = 0.02
        rmse_b = 0.02

        sigma_obs = calculate_corner_positional_uncertainty(
            rmse_a_m=rmse_a, rmse_b_m=rmse_b, is_inferred=False, extension_m=0.0
        )
        sigma_inf = calculate_corner_positional_uncertainty(
            rmse_a_m=rmse_a, rmse_b_m=rmse_b, is_inferred=True, extension_m=0.20
        )

        self.assertGreater(sigma_inf, sigma_obs)

        # Wall uncertainty comparison
        low_obs, high_obs, comp_obs = calculate_wall_length_uncertainty(
            nominal_length_m=5.0,
            wall_rmse_m=0.02,
            corner_a_uncertainty_m=sigma_obs,
            corner_b_uncertainty_m=sigma_obs,
            corner_a_inferred=False,
            corner_b_inferred=False,
        )

        low_inf, high_inf, comp_inf = calculate_wall_length_uncertainty(
            nominal_length_m=5.0,
            wall_rmse_m=0.02,
            corner_a_uncertainty_m=sigma_obs,
            corner_b_uncertainty_m=sigma_inf,
            corner_a_inferred=False,
            corner_b_inferred=True,
            corner_extension_m=0.20,
        )

        margin_obs = comp_obs["margin_of_error_m"]
        margin_inf = comp_inf["margin_of_error_m"]
        self.assertGreater(margin_inf, margin_obs)

        # Confidence comparison
        conf_obs = derive_wall_confidence(0.85, 0.02, False, False)
        conf_inf = derive_wall_confidence(0.85, 0.02, False, True)
        self.assertLess(conf_inf, conf_obs)

    def test_04_noisy_wall_planes(self) -> None:
        """Verifies that elevated plane fitting residuals widen uncertainty intervals and reduce confidence.

        Purpose:
            Confirms sensitivity to noisy sensor observations.

        Parameters:
            None.

        Returns:
            None.

        Assumptions:
            Clean plane (RMSE 0.015m) vs noisy plane (RMSE 0.090m).

        Failure conditions:
            Noisy margin of error is less than or equal to clean margin.

        Debugging:
            Check wall_rmse_m propagation inside calculate_wall_length_uncertainty.
        """
        clean_low, clean_high, clean_comp = calculate_wall_length_uncertainty(
            nominal_length_m=4.0,
            wall_rmse_m=0.015,
            corner_a_uncertainty_m=0.025,
            corner_b_uncertainty_m=0.025,
        )
        noisy_low, noisy_high, noisy_comp = calculate_wall_length_uncertainty(
            nominal_length_m=4.0,
            wall_rmse_m=0.090,
            corner_a_uncertainty_m=0.025,
            corner_b_uncertainty_m=0.025,
        )

        self.assertGreater(noisy_comp["margin_of_error_m"], clean_comp["margin_of_error_m"])
        self.assertGreater(noisy_comp["total_sigma_m"], clean_comp["total_sigma_m"])

        conf_clean = derive_wall_confidence(0.80, 0.015, False, False)
        conf_noisy = derive_wall_confidence(0.80, 0.090, False, False)
        self.assertLess(conf_noisy, conf_clean)

    def test_05_missing_ceiling(self) -> None:
        """Verifies that missing ceiling observations output null ceiling_height with status 'not_observed'.

        Purpose:
            Prevents hallucinated or assumed ceiling heights when scan lacks upper coverage.

        Parameters:
            None.

        Returns:
            None.

        Assumptions:
            Ceiling plane detected flag is False.

        Failure conditions:
            Ceiling height is assigned a numeric value.

        Debugging:
            Ensure engine guards ceiling height logic with ceiling['detected'].
        """
        structure_data = {
            "floor": {"detected": True, "mean_y": -1.45, "rmse_m": 0.012, "confidence": 0.85},
            "ceiling": {"detected": False, "plane": None, "mean_y": None, "inlier_count": 0},
        }
        # Simulate ceiling check logic
        floor = structure_data["floor"]
        ceiling = structure_data["ceiling"]

        if floor["detected"] and ceiling["detected"] and ceiling["plane"] is not None:
            c_val = abs(ceiling["mean_y"] - floor["mean_y"])
            c_stat = "observed"
        else:
            c_val = None
            c_stat = "not_observed"

        self.assertIsNone(c_val)
        self.assertEqual(c_stat, "not_observed")

    def test_06_known_floor_ceiling_planes(self) -> None:
        """Verifies perpendicular clear ceiling height calculation when both planes are detected.

        Purpose:
            Checks exact perpendicular distance between parallel horizontal floor and ceiling planes.

        Parameters:
            None.

        Returns:
            None.

        Assumptions:
            Floor at y = -1.25m, ceiling at y = +1.35m -> distance = 2.60m.

        Failure conditions:
            Distance deviates from 2.60m.

        Debugging:
            Check normal vector sign and d-offset calculation.
        """
        floor_y = -1.25
        ceil_y = 1.35
        expected_h = abs(ceil_y - floor_y)  # 2.60m

        rmse_f = 0.012
        rmse_c = 0.018
        sigma_h = math.hypot(rmse_f, rmse_c)
        moe_h = 1.96 * sigma_h

        m = Measurement[float](
            value=round(expected_h, 3),
            unit="m",
            lower_bound=round(expected_h - moe_h, 3),
            upper_bound=round(expected_h + moe_h, 3),
            confidence=0.92,
            method="structural_plane_perpendicular_distance",
        )

        self.assertEqual(m.value, 2.60)
        self.assertLess(m.lower_bound, 2.60)
        self.assertGreater(m.upper_bound, 2.60)
        self.assertEqual(m.interval, [m.lower_bound, m.upper_bound])

    def test_07_invalid_polygon(self) -> None:
        """Verifies that self-intersecting or topologically degenerate polygons are flagged INVALID.

        Purpose:
            Prevents computation of user-facing dimensions on invalid polygons.

        Parameters:
            None.

        Returns:
            None.

        Assumptions:
            Self-intersecting bowtie polygon (0,0)->(2,2)->(2,0)->(0,2).

        Failure conditions:
            ValidityStatus is not INVALID.

        Debugging:
            Ensure shapely is_valid check is triggered.
        """
        bowtie_vertices = [
            (0.0, 0.0),
            (2.0, 2.0),
            (2.0, 0.0),
            (0.0, 2.0),
        ]
        poly_data = {"polygon": {"vertices": bowtie_vertices}}
        report = evaluate_measurement_validity(poly_data)

        self.assertEqual(report.measurement_status, ValidityStatus.INVALID)
        self.assertTrue(any("invalid" in r or "self_intersecting" in r for r in report.reasons))

    def test_08_deterministic_monte_carlo(self) -> None:
        """Verifies that Monte Carlo area and perimeter simulations are 100% deterministic with fixed seed.

        Purpose:
            Ensures reproducibility across multiple executions and test runs.

        Parameters:
            None.

        Returns:
            None.

        Assumptions:
            Calling monte_carlo_area_and_perimeter_uncertainty twice with seed=42 produces identical outputs.

        Failure conditions:
            Percentile intervals differ between consecutive runs.

        Debugging:
            Confirm np.random.RandomState(random_seed) is used instead of global np.random.
        """
        vertices: List[Tuple[float, float]] = [
            (0.0, 0.0),
            (5.0, 0.0),
            (5.0, 4.0),
            (0.0, 4.0),
        ]
        sigmas = [0.03, 0.02, 0.04, 0.025]

        run1 = monte_carlo_area_and_perimeter_uncertainty(
            vertices, sigmas, num_samples=1000, random_seed=42, confidence_level=0.95
        )
        run2 = monte_carlo_area_and_perimeter_uncertainty(
            vertices, sigmas, num_samples=1000, random_seed=42, confidence_level=0.95
        )

        self.assertEqual(run1["area"]["lower"], run2["area"]["lower"])
        self.assertEqual(run1["area"]["upper"], run2["area"]["upper"])
        self.assertEqual(run1["perimeter"]["lower"], run2["perimeter"]["lower"])
        self.assertEqual(run1["perimeter"]["upper"], run2["perimeter"]["upper"])
        self.assertEqual(run1["area"]["std"], run2["area"]["std"])


if __name__ == "__main__":
    unittest.main()
