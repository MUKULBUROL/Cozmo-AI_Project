"""Core infrastructure and shared foundational utilities for Cozmo AI.

1. Purpose:
    Central package entry point exposing core utilities used across the reconstruction
    and evaluation stages, specifically deterministic random number generator configuration.

2. Stage:
    Stage 10.2 (Deterministic LiDAR Reconstruction & Reproducibility).

3. Inputs:
    None (module namespace aggregator).

4. Outputs:
    Exposed public symbols: configure_determinism, DEFAULT_SEED.

5. Coordinate systems / units:
    Dimensionless / abstract core utilities.

6. Dependencies:
    backend.app.core.determinism

7. Assumptions:
    Shared across geometry, perception, calibration, and benchmark execution.

8. Failure modes:
    Import errors if child modules have syntax or dependency issues.

9. First debugging points:
    Ensure backend/ is located on sys.path and child imports resolve cleanly.
"""

from .determinism import configure_determinism, DEFAULT_SEED

__all__ = [
    "configure_determinism",
    "DEFAULT_SEED",
]
