"""Automated determinism unit tests for structural RANSAC plane fitting and extraction.

1. Purpose:
    Validates that random number generation in Open3D and NumPy is strictly deterministic
    when configured with a fixed seed. Verifies that synthetic point clouds produce identical
    plane coefficients, inlier sets, wall counts, wall ordering, and metadata across repeated runs.

2. Stage:
    Stage 10.2 (Deterministic LiDAR Reconstruction & Reproducibility Tests).

3. Inputs:
    Lightweight synthetically generated point clouds (planes with controlled Gaussian noise).

4. Outputs:
    Pytest test assertions and verification results.

5. Coordinate systems / units:
    Metric units (meters). Standard camera/world coordinates with Y upward.

6. Dependencies:
    pytest, numpy, open3d, os, json, tempfile,
    backend.app.core (configure_determinism, DEFAULT_SEED),
    backend.app.geometry (fit_single_plane_ransac, extract_planes_iterative,
                          StructuralConfig, extract_structure).

7. Assumptions:
    Tests run rapidly (<2 seconds) without requiring full 15M-point scan files.
    Open3D exposes utility.random.seed in the installed environment.

8. Failure modes:
    Test failure indicates unseeded random state, non-deterministic iteration order,
    or regression in RANSAC parameter configuration.

9. First debugging points:
    Check `o3d.utility.random.seed` execution; check if NumPy random state was altered
    between test runs.
"""

import json
import os
import tempfile
import numpy as np
import open3d as o3d
import pytest

from backend.app.core import configure_determinism, DEFAULT_SEED
from backend.app.geometry import (
    fit_single_plane_ransac,
    extract_planes_iterative,
    StructuralConfig,
    extract_structure,
)


def _generate_synthetic_plane(
    num_points: int = 1500,
    normal: tuple = (0.0, 1.0, 0.0),
    offset: float = 0.0,
    noise_std: float = 0.005,
    seed: int = 12345,
) -> np.ndarray:
    """Generates synthetic 3D points distributed along a noisy plane.

    Purpose:
        Creates a lightweight deterministic planar point cloud for fast unit testing.

    Parameters:
        num_points: int
            Number of points to generate.
        normal: tuple
            Plane normal unit vector (a, b, c).
        offset: float
            Plane d parameter such that a*x + b*y + c*z + d = 0.
        noise_std: float
            Standard deviation of perpendicular Gaussian noise in meters.
        seed: int
            Local seed used to generate synthetic points deterministically.

    Returns:
        np.ndarray: (N, 3) float64 array of points.

    Units / coordinates:
        Metric coordinates in meters.

    Assumptions:
        Normal has unit length.

    Failure conditions:
        None under standard parameters.

    Dependencies:
        numpy.random.RandomState.

    Debugging clues:
        Verify points satisfy dot(p, normal) + offset ~= 0.
    """
    rng = np.random.RandomState(seed)
    u = rng.uniform(-2.0, 2.0, num_points)
    v = rng.uniform(-2.0, 2.0, num_points)

    nx, ny, nz = normal
    if abs(ny) > 0.5:
        # Normal largely in Y: plane is horizontal (XZ)
        x = u
        z = v
        y = -(nx * x + nz * z + offset) / ny
    elif abs(nx) > 0.5:
        # Normal largely in X: plane is vertical (YZ)
        y = u
        z = v
        x = -(ny * y + nz * z + offset) / nx
    else:
        # Normal largely in Z: plane is vertical (XY)
        x = u
        y = v
        z = -(nx * x + ny * y + offset) / nz

    pts = np.column_stack([x, y, z])
    noise = rng.normal(0.0, noise_std, (num_points, 3))
    return pts + noise


def test_fit_single_plane_ransac_determinism() -> None:
    """Tests that same synthetic cloud and same seed produce identical plane coefficients and inliers.

    Purpose:
        Validates the fundamental determinism fix for Open3D segment_plane RANSAC.

    Parameters:
        None (pytest test case).

    Returns:
        None.

    Units / coordinates:
        Meters for distances and plane models.

    Assumptions:
        configure_determinism properly sets Open3D RNG state.

    Failure conditions:
        Asserts fail if plane models or inlier indices differ across repeated runs with seed 42.

    Dependencies:
        fit_single_plane_ransac, open3d.geometry.PointCloud.

    Debugging clues:
        Inspect differences between plane1 and plane2; check if Open3D random seed was applied.
    """
    pts = _generate_synthetic_plane(num_points=2000, normal=(0.0, 1.0, 0.0), offset=-1.0, seed=100)
    pcd = o3d.geometry.PointCloud()
    pcd.points = o3d.utility.Vector3dVector(pts)

    # Run 1 with seed 42
    configure_determinism(42)
    res1 = fit_single_plane_ransac(pcd, distance_threshold_m=0.02, ransac_n=3, num_iterations=500)
    assert res1 is not None
    model1, inliers1 = res1

    # Run 2 with seed 42
    configure_determinism(42)
    res2 = fit_single_plane_ransac(pcd, distance_threshold_m=0.02, ransac_n=3, num_iterations=500)
    assert res2 is not None
    model2, inliers2 = res2

    # Verify exact equality between Run 1 and Run 2
    assert np.allclose(model1, model2, atol=1e-12), f"Plane coefficients differed: {model1} vs {model2}"
    assert np.array_equal(inliers1, inliers2), "Inlier indices differed between identical seed runs"
    assert len(inliers1) == len(inliers2)


def test_extract_planes_iterative_determinism() -> None:
    """Tests that iterative RANSAC plane extraction produces identical planes and inlier counts.

    Purpose:
        Validates that sequential iterative plane extraction remains deterministic across stages.

    Parameters:
        None (pytest test case).

    Returns:
        None.

    Units / coordinates:
        Meters.

    Assumptions:
        Two distinct planes are present with sufficient separation.

    Failure conditions:
        Asserts fail if detected plane models, inlier counts, or remaining points differ.

    Dependencies:
        extract_planes_iterative, open3d.geometry.PointCloud.

    Debugging clues:
        Check order of detected planes and inlier counts per plane.
    """
    plane_a = _generate_synthetic_plane(num_points=1500, normal=(0.0, 1.0, 0.0), offset=0.0, seed=101)
    plane_b = _generate_synthetic_plane(num_points=1500, normal=(1.0, 0.0, 0.0), offset=1.5, seed=102)
    combined = np.vstack([plane_a, plane_b])

    pcd = o3d.geometry.PointCloud()
    pcd.points = o3d.utility.Vector3dVector(combined)

    configure_determinism(42)
    planes1, rem1 = extract_planes_iterative(pcd, distance_threshold_m=0.02, min_inliers=500, max_planes=3)

    configure_determinism(42)
    planes2, rem2 = extract_planes_iterative(pcd, distance_threshold_m=0.02, min_inliers=500, max_planes=3)

    assert len(planes1) == len(planes2), f"Extracted plane count differed: {len(planes1)} vs {len(planes2)}"
    for idx, (p1, p2) in enumerate(zip(planes1, planes2)):
        assert np.allclose(p1.plane_model, p2.plane_model, atol=1e-10), f"Plane {idx} model mismatch"
        assert p1.inlier_count == p2.inlier_count, f"Plane {idx} inlier count mismatch"
        assert np.array_equal(p1.inlier_indices, p2.inlier_indices), f"Plane {idx} inlier indices mismatch"

    assert len(rem1.points) == len(rem2.points)


def test_structural_extraction_synthetic_determinism() -> None:
    """Tests end-to-end structural extraction repeatability on synthetic room geometry.

    Purpose:
        Validates that extract_structure produces identical floor plane, wall planes,
        inlier counts, and wall ordering when run repeatedly with the same seed.

    Parameters:
        None (pytest test case).

    Returns:
        None.

    Units / coordinates:
        Meters for coordinates and bounding box dimensions.

    Assumptions:
        Synthetic room consists of a floor and four surrounding vertical walls.

    Failure conditions:
        Asserts fail if floor inliers, wall count, wall coefficients, or wall ordering differ.

    Dependencies:
        StructuralConfig, extract_structure, open3d.

    Debugging clues:
        Check extraction_stats.json in temporary directories.
    """
    # Create a synthetic room: Floor at Y=0, 4 walls at X=+-1.5, Z=+-1.5
    floor = _generate_synthetic_plane(num_points=3000, normal=(0.0, 1.0, 0.0), offset=0.0, seed=201)
    wall_x_pos = _generate_synthetic_plane(num_points=2500, normal=(1.0, 0.0, 0.0), offset=-1.5, seed=202)
    wall_x_neg = _generate_synthetic_plane(num_points=2500, normal=(1.0, 0.0, 0.0), offset=1.5, seed=203)
    wall_z_pos = _generate_synthetic_plane(num_points=2500, normal=(0.0, 0.0, 1.0), offset=-1.5, seed=204)
    wall_z_neg = _generate_synthetic_plane(num_points=2500, normal=(0.0, 0.0, 1.0), offset=1.5, seed=205)

    room_pts = np.vstack([floor, wall_x_pos, wall_x_neg, wall_z_pos, wall_z_neg])

    with tempfile.TemporaryDirectory() as tmp_dir:
        ply_path = os.path.join(tmp_dir, "synthetic_filtered.ply")
        pcd = o3d.geometry.PointCloud()
        pcd.points = o3d.utility.Vector3dVector(room_pts)
        o3d.io.write_point_cloud(ply_path, pcd, write_ascii=True)

        out_dir1 = os.path.join(tmp_dir, "run1")
        out_dir2 = os.path.join(tmp_dir, "run2")

        cfg1 = StructuralConfig(
            scan_id="synthetic_test",
            ply_path=ply_path,
            output_dir=out_dir1,
            distance_threshold_m=0.03,
            min_floor_inliers=1000,
            min_wall_inliers=800,
            min_height_span_m=0.3,
            min_horizontal_span_m=0.3,
            random_seed=42,
            deterministic_mode=True,
        )

        cfg2 = StructuralConfig(
            scan_id="synthetic_test",
            ply_path=ply_path,
            output_dir=out_dir2,
            distance_threshold_m=0.03,
            min_floor_inliers=1000,
            min_wall_inliers=800,
            min_height_span_m=0.3,
            min_horizontal_span_m=0.3,
            random_seed=42,
            deterministic_mode=True,
        )

        stats1 = extract_structure(cfg1)
        stats2 = extract_structure(cfg2)

        # Assert statistics match identically
        assert stats1["floor_detected"] == stats2["floor_detected"] == True
        assert stats1["floor_inliers"] == stats2["floor_inliers"]
        assert stats1["walls_accepted"] == stats2["walls_accepted"]
        assert stats1["walls_final_merged"] == stats2["walls_final_merged"]

        # Read structure.json to compare planes and ordering
        with open(os.path.join(out_dir1, "structure.json"), "r") as f1, open(os.path.join(out_dir2, "structure.json"), "r") as f2:
            struct1 = json.load(f1)
            struct2 = json.load(f2)

        assert struct1["random_seed"] == 42
        assert struct2["random_seed"] == 42
        assert struct1["deterministic_mode"] is True

        # Floor plane match
        fp1 = struct1["floor"]["plane"]
        fp2 = struct2["floor"]["plane"]
        for k in ["a", "b", "c", "d"]:
            assert pytest.approx(fp1[k], abs=1e-6) == fp2[k]

        # Walls match and ordering
        assert len(struct1["walls"]) == len(struct2["walls"])
        for idx in range(len(struct1["walls"])):
            w1 = struct1["walls"][idx]
            w2 = struct2["walls"][idx]
            assert w1["id"] == w2["id"], f"Wall ordering mismatch at index {idx}"
            assert w1["inlier_count"] == w2["inlier_count"]
            for k in ["a", "b", "c", "d"]:
                assert pytest.approx(w1["plane"][k], abs=1e-6) == w2["plane"][k]


def test_seed_recorded_in_metadata() -> None:
    """Verifies that seed and deterministic_mode are persisted to output JSON metadata.

    Purpose:
        Ensures auditability and provenance tracking of random seeds in pipeline outputs.

    Parameters:
        None (pytest test case).

    Returns:
        None.

    Units / coordinates:
        Metadata keys.

    Assumptions:
        extract_structure writes extraction_stats.json and structure.json.

    Failure conditions:
        Asserts fail if random_seed or deterministic_mode keys are missing or mismatch config.

    Dependencies:
        StructuralConfig, extract_structure.

    Debugging clues:
        Inspect json serialization in extract_structure().
    """
    pts = _generate_synthetic_plane(num_points=1200, normal=(0.0, 1.0, 0.0), offset=0.0, seed=301)
    with tempfile.TemporaryDirectory() as tmp_dir:
        ply_path = os.path.join(tmp_dir, "test.ply")
        pcd = o3d.geometry.PointCloud()
        pcd.points = o3d.utility.Vector3dVector(pts)
        o3d.io.write_point_cloud(ply_path, pcd, write_ascii=True)

        out_dir = os.path.join(tmp_dir, "out")
        cfg = StructuralConfig(
            scan_id="meta_test",
            ply_path=ply_path,
            output_dir=out_dir,
            min_floor_inliers=500,
            min_wall_inliers=500,
            random_seed=77,
            deterministic_mode=True,
        )
        stats = extract_structure(cfg)

        assert stats["random_seed"] == 77
        assert stats["deterministic_mode"] is True

        with open(os.path.join(out_dir, "structure.json"), "r") as f:
            s_data = json.load(f)
        assert s_data["random_seed"] == 77
        assert s_data["deterministic_mode"] is True


def test_default_configuration_uses_deterministic_seed() -> None:
    """Verifies that default StructuralConfig initializes with canonical seed 42.

    Purpose:
        Guarantees that invoking extraction without explicit CLI flags remains deterministic.

    Parameters:
        None (pytest test case).

    Returns:
        None.

    Units / coordinates:
        Dimensionless seed scalar.

    Assumptions:
        DEFAULT_SEED is 42.

    Failure conditions:
        Asserts fail if default random_seed != 42 or deterministic_mode is False.

    Dependencies:
        StructuralConfig, DEFAULT_SEED.

    Debugging clues:
        Inspect default argument in StructuralConfig dataclass definition.
    """
    cfg = StructuralConfig(scan_id="default_test")
    assert cfg.random_seed == 42
    assert cfg.random_seed == DEFAULT_SEED
    assert cfg.deterministic_mode is True
