"""Deterministic synthetic unit tests for Stage 3 room polygon extraction pipeline.

1. Why this file exists:
   Verifies 2D wall projection, quality filtering, duplicate line merging,
   candidate corner discovery, gap inference, polygon closure, and validity
   checks against deterministic synthetic benchmarks without sensor noise.

2. Pipeline stage:
   Stage 3 (2D Wall Projection & Room Polygon Extraction) - Automated Test Suite.

3. Inputs:
   Synthetically constructed 3D wall plane dictionaries and point bounds.

4. Outputs:
   Test assertions verifying polygon validity, area, corner count, merge behavior,
   furniture rejection, and honest failure reporting.

5. Coordinate/Unit assumptions:
   Y is vertical (upward), XZ is horizontal floor plane. Units are meters.

6. Dependencies:
   unittest, numpy, backend.app.geometry.

7. Most likely failure/debugging points:
   - Threshold mismatches causing synthetic test walls to be filtered prematurely.
   - Numerical rounding errors in line intersection solvers.
"""

import unittest
import numpy as np
from typing import Dict, Any, List

from backend.app.geometry.wall_quality import evaluate_wall_quality
from backend.app.geometry.projection_2d import (
    project_walls_to_2d,
    merge_near_duplicate_2d_lines,
    project_plane_to_2d_line,
)
from backend.app.geometry.line_geometry import (
    intersect_2d_lines,
    angle_between_lines_deg,
    compute_segment_extension_distance,
)
from backend.app.geometry.corner_detection import detect_candidate_corners
from backend.app.geometry.polygon_builder import (
    build_connectivity_graph,
    find_simple_cycles,
    extract_room_polygon,
)
from backend.app.geometry.polygon_validation import (
    validate_room_polygon,
    compute_polygon_quality_metrics,
)


class TestRoomPolygonExtraction(unittest.TestCase):
    """Synthetic unit tests for Stage 3 geometry pipeline."""

    def _make_wall(
        self,
        wall_id: str,
        a: float,
        b: float,
        c: float,
        d: float,
        bx: List[float],
        bz: List[float],
        rmse: float = 0.02,
        conf: float = 0.85,
        inliers: int = 15000,
        height_y: float = 2.4,
    ) -> Dict[str, Any]:
        """Helper to create a well-formed Stage 2 wall dictionary."""
        return {
            "id": wall_id,
            "plane": {"a": a, "b": b, "c": c, "d": d},
            "normal": [a, b, c],
            "centroid": [(bx[0] + bx[1]) / 2, 0.0, (bz[0] + bz[1]) / 2],
            "bounds": {"x": bx, "y": [-1.2, -1.2 + height_y], "z": bz},
            "spans_m": {
                "width_x": abs(bx[1] - bx[0]),
                "height_y": height_y,
                "depth_z": abs(bz[1] - bz[0]),
            },
            "inlier_count": inliers,
            "rmse_m": rmse,
            "confidence": conf,
        }

    def test_01_synthetic_rectangle(self) -> None:
        """Tests exact 4-wall rectangular room extraction.

        Purpose:
            Verifies 4 orthogonal walls (5m x 4m) yield 4 corners and a valid closed polygon.

        Parameters:
            None.

        Returns:
            None.

        Assumptions:
            Room boundaries at x in [0, 5], z in [0, 4].

        Failure conditions:
            Fails if corner count != 4, area != 20m^2, or polygon_valid is False.

        Debugging:
            Check whether corner detection rejected any orthogonal corner.
        """
        # 4 walls: North (z=4), South (z=0), East (x=5), West (x=0)
        # z=0 -> normal (0, -1), d=0 => 0*x - 1*z + 0 = 0
        # z=4 -> normal (0, 1), d=-4 => 0*x + 1*z - 4 = 0
        # x=0 -> normal (-1, 0), d=0 => -1*x + 0*z + 0 = 0
        # x=5 -> normal (1, 0), d=-5 => 1*x + 0*z - 5 = 0
        walls = [
            self._make_wall("w_south", 0.0, 0.0, -1.0, 0.0, [0.0, 5.0], [0.0, 0.0]),
            self._make_wall("w_north", 0.0, 0.0, 1.0, -4.0, [0.0, 5.0], [4.0, 4.0]),
            self._make_wall("w_west", -1.0, 0.0, 0.0, 0.0, [0.0, 0.0], [0.0, 4.0]),
            self._make_wall("w_east", 1.0, 0.0, 0.0, -5.0, [5.0, 5.0], [0.0, 4.0]),
        ]

        accepted, _, rejected = evaluate_wall_quality(walls)
        self.assertEqual(len(accepted), 4)
        self.assertEqual(len(rejected), 0)

        projected = project_walls_to_2d(accepted)
        merged, _ = merge_near_duplicate_2d_lines(projected)
        self.assertEqual(len(merged), 4)

        corners, _ = detect_candidate_corners(merged, max_extension_m=0.35)
        self.assertEqual(len(corners), 4)

        poly_data = extract_room_polygon(corners, merged)
        self.assertTrue(poly_data["valid"])
        self.assertTrue(poly_data["closed"])
        self.assertAlmostEqual(poly_data["area_sqm"], 20.0, places=2)
        self.assertAlmostEqual(poly_data["perimeter_m"], 18.0, places=2)

        val = validate_room_polygon(poly_data)
        self.assertTrue(val["is_valid"])
        self.assertTrue(val["is_closed"])
        self.assertEqual(val["self_intersections_count"], 0)

    def test_02_noisy_rectangle(self) -> None:
        """Tests rectangular room with slightly perturbed, noisy wall coefficients.

        Purpose:
            Verifies robust corner intersection and polygon closure despite minor plane tilt.

        Parameters:
            None.

        Returns:
            None.

        Assumptions:
            Planes perturbed by up to 1.5 degrees and 2 cm offset.

        Failure conditions:
            Fails if polygon is marked invalid or area deviates > 5% from nominal.

        Debugging:
            Inspect intersection determinants and validation report.
        """
        # Slight angular perturbations (< 1.5 deg)
        # sin(1 deg) ~ 0.0175, cos(1 deg) ~ 0.9998
        walls = [
            self._make_wall("w_south_noisy", 0.015, 0.0, -0.999, 0.02, [0.0, 5.0], [0.0, 0.05]),
            self._make_wall("w_north_noisy", -0.012, 0.0, 0.999, -3.98, [0.0, 5.0], [3.95, 4.02]),
            self._make_wall("w_west_noisy", -0.999, 0.0, 0.014, 0.01, [0.0, 0.03], [0.0, 4.0]),
            self._make_wall("w_east_noisy", 0.999, 0.0, -0.011, -5.02, [4.98, 5.02], [0.0, 4.0]),
        ]

        accepted, _, _ = evaluate_wall_quality(walls)
        projected = project_walls_to_2d(accepted)
        merged, _ = merge_near_duplicate_2d_lines(projected)
        corners, _ = detect_candidate_corners(merged, max_extension_m=0.35)

        self.assertEqual(len(corners), 4)
        poly_data = extract_room_polygon(corners, merged)
        self.assertTrue(poly_data["valid"])
        self.assertTrue(poly_data["closed"])
        self.assertAlmostEqual(poly_data["area_sqm"], 20.0, delta=0.5)

    def test_03_non_orthogonal_angled_room(self) -> None:
        """Tests room with an intentional non-orthogonal (45-degree chamfered) wall.

        Purpose:
            Verifies that the pipeline preserves oblique architectural walls without
            forcing them to 90 degrees.

        Parameters:
            None.

        Returns:
            None.

        Assumptions:
            Chamfer wall cuts across corner with normal at 45 degrees.

        Failure conditions:
            Fails if angled wall is rejected or snapped to 90 degrees.

        Debugging:
            Check angle_deg on corners incident to the angled wall.
        """
        # Pentagonal room: West (x=0), South (z=0), North (z=4), East (x=5),
        # but top-right corner is chamfered at 45 deg between (4, 4) and (5, 3).
        # Line through (4, 4) and (5, 3): x + z = 8 => (1/sqrt(2))x + (1/sqrt(2))z - 8/sqrt(2) = 0
        s2 = np.sqrt(2.0)
        walls = [
            self._make_wall("w_west", -1.0, 0.0, 0.0, 0.0, [0.0, 0.0], [0.0, 4.0]),
            self._make_wall("w_south", 0.0, 0.0, -1.0, 0.0, [0.0, 5.0], [0.0, 0.0]),
            self._make_wall("w_north", 0.0, 0.0, 1.0, -4.0, [0.0, 4.0], [4.0, 4.0]),
            self._make_wall("w_east", 1.0, 0.0, 0.0, -5.0, [5.0, 5.0], [0.0, 3.0]),
            self._make_wall(
                "w_chamfer_45",
                1.0 / s2,
                0.0,
                1.0 / s2,
                -8.0 / s2,
                [4.0, 5.0],
                [3.0, 4.0],
            ),
        ]

        accepted, _, _ = evaluate_wall_quality(walls)
        projected = project_walls_to_2d(accepted)
        merged, _ = merge_near_duplicate_2d_lines(projected)
        self.assertEqual(len(merged), 5)

        corners, _ = detect_candidate_corners(merged, max_extension_m=0.35)
        self.assertEqual(len(corners), 5)

        # Verify that chamfer corners are near 45 / 135 deg (non-orthogonal)
        chamfer_corners = [c for c in corners if "w_chamfer_45" in c["wall_ids"]]
        self.assertEqual(len(chamfer_corners), 2)
        for c in chamfer_corners:
            self.assertAlmostEqual(c["angle_deg"], 45.0, delta=1.0)
            self.assertFalse(c["is_near_orthogonal"])  # Specifically non-orthogonal!

        poly_data = extract_room_polygon(corners, merged)
        self.assertTrue(poly_data["valid"])
        # Nominal area = 5*4 - 0.5*1*1 = 19.5 sqm
        self.assertAlmostEqual(poly_data["area_sqm"], 19.5, places=1)

    def test_04_duplicate_wall_fragments_merge(self) -> None:
        """Tests that collinear fragmented wall observations merge cleanly.

        Purpose:
            Verifies step 4 merges two collinear fragments of the same physical wall
            without creating duplicate lines or fake corners.

        Parameters:
            None.

        Returns:
            None.

        Assumptions:
            w_north_part1 and w_north_part2 lie along z=4 with a small gap.

        Failure conditions:
            Fails if merged wall count != 4 or merge log is empty.

        Debugging:
            Check max_offset_m and max_gap_m in merge_near_duplicate_2d_lines.
        """
        walls = [
            self._make_wall("w_south", 0.0, 0.0, -1.0, 0.0, [0.0, 5.0], [0.0, 0.0]),
            self._make_wall("w_west", -1.0, 0.0, 0.0, 0.0, [0.0, 0.0], [0.0, 4.0]),
            self._make_wall("w_east", 1.0, 0.0, 0.0, -5.0, [5.0, 5.0], [0.0, 4.0]),
            # Split North wall into two parts along z=4: [0 to 2.2] and [2.4 to 5.0]
            self._make_wall("w_north_part1", 0.0, 0.0, 1.0, -4.0, [0.0, 2.2], [4.0, 4.0], inliers=8000),
            self._make_wall("w_north_part2", 0.0, 0.0, 1.0, -4.0, [2.4, 5.0], [4.0, 4.0], inliers=8000),
        ]

        accepted, _, _ = evaluate_wall_quality(walls)
        self.assertEqual(len(accepted), 5)

        projected = project_walls_to_2d(accepted)
        merged, merge_log = merge_near_duplicate_2d_lines(projected)

        # 5 raw projected lines should merge into 4 structural walls
        self.assertEqual(len(merged), 4)
        self.assertEqual(len(merge_log), 1)
        self.assertEqual(merge_log[0]["action"], "merge")

        corners, _ = detect_candidate_corners(merged, max_extension_m=0.35)
        self.assertEqual(len(corners), 4)

        poly_data = extract_room_polygon(corners, merged)
        self.assertTrue(poly_data["valid"])
        self.assertAlmostEqual(poly_data["area_sqm"], 20.0, places=2)

    def test_05_false_furniture_plane_rejection(self) -> None:
        """Tests that a noisy interior clutter/furniture plane is strictly rejected.

        Purpose:
            Replicates known Wall 09 failure mode (RMSE=1.945m, conf=0.274, height=0.94m)
            and verifies it is rejected at the quality gate and never enters the polygon.

        Parameters:
            None.

        Returns:
            None.

        Assumptions:
            Quality gate inspects RMSE, confidence, inliers, and height span.

        Failure conditions:
            Fails if furniture wall is accepted or enters polygon.

        Debugging:
            Check evaluate_wall_quality criteria and rejection_reasons.
        """
        walls = [
            self._make_wall("w_south", 0.0, 0.0, -1.0, 0.0, [0.0, 5.0], [0.0, 0.0]),
            self._make_wall("w_north", 0.0, 0.0, 1.0, -4.0, [0.0, 5.0], [4.0, 4.0]),
            self._make_wall("w_west", -1.0, 0.0, 0.0, 0.0, [0.0, 0.0], [0.0, 4.0]),
            self._make_wall("w_east", 1.0, 0.0, 0.0, -5.0, [5.0, 5.0], [0.0, 4.0]),
            # Interior false furniture clutter plane (Wall 09 equivalent)
            self._make_wall(
                "wall_09_clutter",
                0.0,
                0.0,
                1.0,
                -2.0,
                [1.0, 4.0],
                [2.0, 2.0],
                rmse=1.945,       # High RMSE!
                conf=0.274,       # Low confidence!
                inliers=2000,     # Few inliers!
                height_y=0.85,    # Short table/bed height!
            ),
        ]

        accepted, _, rejected = evaluate_wall_quality(walls)
        self.assertEqual(len(accepted), 4)
        self.assertEqual(len(rejected), 1)

        rej = rejected[0]
        self.assertEqual(rej["id"], "wall_09_clutter")
        self.assertTrue(len(rej["rejection_reasons"]) >= 3)
        self.assertTrue(any("rmse" in r for r in rej["rejection_reasons"]))
        self.assertTrue(any("confidence" in r for r in rej["rejection_reasons"]))

        # Run rest of pipeline; polygon must only use the 4 structural walls
        projected = project_walls_to_2d(accepted)
        merged, _ = merge_near_duplicate_2d_lines(projected)
        corners, _ = detect_candidate_corners(merged)
        poly_data = extract_room_polygon(corners, merged)

        self.assertTrue(poly_data["valid"])
        self.assertNotIn("wall_09_clutter", poly_data["wall_ids"])
        self.assertAlmostEqual(poly_data["area_sqm"], 20.0, places=2)

    def test_06_missing_small_corner_observation_inferred(self) -> None:
        """Tests controlled geometric extension across a small missing corner gap.

        Purpose:
            Verifies that when two walls fall 0.15m short of their meeting point,
            the intersection is computed, closed, and marked inferred=True.

        Parameters:
            None.

        Returns:
            None.

        Assumptions:
            Gap extension is within max_extension_m (0.35m).

        Failure conditions:
            Fails if corner is rejected or not marked as inferred.

        Debugging:
            Check compute_segment_extension_distance and inferred flag in detect_candidate_corners.
        """
        # South wall ends at x=4.85 (0.15m short of East wall at x=5.0)
        # East wall starts at z=0.15 (0.15m short of South wall at z=0.0)
        walls = [
            self._make_wall("w_south", 0.0, 0.0, -1.0, 0.0, [0.0, 4.85], [0.0, 0.0]),
            self._make_wall("w_east", 1.0, 0.0, 0.0, -5.0, [5.0, 5.0], [0.15, 4.0]),
            self._make_wall("w_north", 0.0, 0.0, 1.0, -4.0, [0.0, 5.0], [4.0, 4.0]),
            self._make_wall("w_west", -1.0, 0.0, 0.0, 0.0, [0.0, 0.0], [0.0, 4.0]),
        ]

        accepted, _, _ = evaluate_wall_quality(walls)
        projected = project_walls_to_2d(accepted)
        merged, _ = merge_near_duplicate_2d_lines(projected)

        corners, _ = detect_candidate_corners(merged, max_extension_m=0.35)
        self.assertEqual(len(corners), 4)

        # Southeast corner (w_south x w_east at (5.0, 0.0)) must be inferred
        se_corner = [c for c in corners if "w_south" in c["wall_ids"] and "w_east" in c["wall_ids"]][0]
        self.assertTrue(se_corner["inferred"])
        self.assertAlmostEqual(se_corner["extension_wall_a_m"], 0.15, places=2)
        self.assertAlmostEqual(se_corner["extension_wall_b_m"], 0.15, places=2)

        poly_data = extract_room_polygon(corners, merged)
        self.assertTrue(poly_data["valid"])
        self.assertTrue(poly_data["closed"])
        self.assertAlmostEqual(poly_data["area_sqm"], 20.0, places=2)

    def test_07_impossible_open_geometry_honest_failure(self) -> None:
        """Tests that incomplete or open geometry honestly reports polygon_valid=False.

        Purpose:
            Verifies the system never hallucinates or fabricates missing walls when
            only 2 disconnected walls are present.

        Parameters:
            None.

        Returns:
            None.

        Assumptions:
            Only 2 walls provided; impossible to form a closed 2D polygon.

        Failure conditions:
            Fails if valid is True or fake vertices are fabricated.

        Debugging:
            Check extract_room_polygon failure diagnostics.
        """
        walls = [
            self._make_wall("w_south", 0.0, 0.0, -1.0, 0.0, [0.0, 5.0], [0.0, 0.0]),
            self._make_wall("w_north", 0.0, 0.0, 1.0, -4.0, [0.0, 5.0], [4.0, 4.0]),
        ]

        accepted, _, _ = evaluate_wall_quality(walls)
        projected = project_walls_to_2d(accepted)
        merged, _ = merge_near_duplicate_2d_lines(projected)
        corners, _ = detect_candidate_corners(merged)

        poly_data = extract_room_polygon(corners, merged)
        self.assertFalse(poly_data["valid"])
        self.assertFalse(poly_data["closed"])
        self.assertEqual(len(poly_data["vertices"]), 0)
        self.assertIn("reason", poly_data["diagnostics"])


if __name__ == "__main__":
    unittest.main()
