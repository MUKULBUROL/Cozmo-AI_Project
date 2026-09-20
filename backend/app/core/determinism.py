"""Centralized determinism configuration utility for reproducible reconstruction.

1. Purpose:
    Provides a single, centralized entry point to configure random number generators
    across all core computational and geometric libraries utilized by the pipeline,
    specifically Python's internal random module, NumPy, and Open3D's C++ RANSAC RNG.
    Eliminates stochastic plane segmentation variance in iterative RANSAC algorithms.

2. Stage:
    Stage 10.2 (Deterministic LiDAR Reconstruction & Reproducibility).

3. Inputs:
    Integer seed value (default: 42).

4. Outputs:
    Configures internal RNG state across Python random, NumPy, and Open3D.
    Sets PYTHONHASHSEED environment variable if not already fixed.

5. Coordinate systems / units:
    Dimensionless RNG seed scalar.

6. Dependencies:
    os, random, numpy, open3d (optional/conditional if installed).

7. Assumptions:
    Open3D version exposes `open3d.utility.random.seed` for C++ RANSAC random number generation.
    Seed must be an integer representable in standard 32-bit/64-bit unsigned integers.

8. Failure modes:
    Passing non-integer seed or types that cannot be coerced to integer.
    Open3D missing `utility.random` module attribute in incompatible versions.

9. First debugging points:
    Check `hasattr(open3d.utility, "random")` and `o3d.__version__`.
    Verify `np.random.get_state()` and test single plane RANSAC repeatability.
"""

import os
import random
from typing import Optional
import numpy as np

try:
    import open3d as o3d
    _HAS_OPEN3D = True
except ImportError:
    o3d = None
    _HAS_OPEN3D = False


DEFAULT_SEED: int = 42


def configure_determinism(seed: int = DEFAULT_SEED) -> None:
    """Initializes all relevant random number generators used in the pipeline.

    Purpose:
        Enforces identical, bit-level deterministic execution across repeated runs
        of point cloud processing, RANSAC plane fitting, and probabilistic geometry routines.

    Parameters:
        seed: int
            Integer seed value to initialize RNGs (default: 42).

    Returns:
        None.

    Units / coordinates:
        Dimensionless integer seed.

    Assumptions:
        Open3D random utilities accept integer seed.
        Runs on single process or before worker initialization.

    Failure conditions:
        TypeError if seed is not an integer or cannot be converted to int.
        RuntimeError if underlying Open3D utility raises during seeding.

    Dependencies:
        Python standard library `random` and `os`, `numpy`, and `open3d.utility.random`.

    Debugging clues:
        Inspect `python3 -c "import open3d as o3d; print(dir(o3d.utility.random))"`
        if Open3D seeding fails. Verify repeated calls to `o3d.geometry.PointCloud.segment_plane`
        yield identical plane equations and inlier arrays for the same point set.
    """
    if not isinstance(seed, (int, np.integer)):
        raise TypeError(f"Seed must be an integer, got {type(seed).__name__}: {seed}")

    int_seed = int(seed)

    # 1. Standard Python random
    random.seed(int_seed)

    # 2. Python hash seed & OpenMP environment variables (single thread to eliminate race conditions)
    os.environ["PYTHONHASHSEED"] = str(int_seed)
    os.environ["OMP_NUM_THREADS"] = "1"
    os.environ["OPENBLAS_NUM_THREADS"] = "1"
    os.environ["MKL_NUM_THREADS"] = "1"

    # 3. NumPy RNG
    np.random.seed(int_seed)

    # 4. Open3D RNG and Threading (controls RANSAC sampling in segment_plane)
    if _HAS_OPEN3D and hasattr(o3d, "utility"):
        if hasattr(o3d.utility, "random") and hasattr(o3d.utility.random, "seed"):
            o3d.utility.random.seed(int_seed)
        # Pin Open3D threads to 1 to eliminate multi-threaded RANSAC race non-determinism
        if hasattr(o3d.utility, "set_max_threads"):
            o3d.utility.set_max_threads(1)


def get_default_seed() -> int:
    """Returns the canonical project default random seed.

    Purpose:
        Provides single source of truth for pipeline default seed value (42).

    Parameters:
        None.

    Returns:
        int: Canonical default seed (42).

    Units / coordinates:
        Dimensionless integer.

    Assumptions:
        Default seed remains 42 throughout project lifecycle.

    Failure conditions:
        None.

    Dependencies:
        DEFAULT_SEED module constant.

    Debugging clues:
        Inspect DEFAULT_SEED if tests report seed mismatches.
    """
    return DEFAULT_SEED
