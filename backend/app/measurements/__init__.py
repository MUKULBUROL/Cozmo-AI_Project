"""Stage 4 measurement and uncertainty module.

1. Why this file exists:
   Exposes high-level interfaces for Stage 4 metric measurement computation,
   validity gating, uncertainty propagation, and visual artifact generation.

2. Pipeline stage:
   Stage 4 (Metric Measurements, Room Area & Uncertainty) - Package Entry Point.

3. Inputs:
   Stage 3 room polygon geometry, polygon validation statistics, and Stage 2 structural planes.

4. Outputs:
   Calibrated metric wall dimensions, room perimeter, polygon floor area,
   optional clear ceiling height, uncertainty intervals, confidence scores,
   and validity gating status.

5. Coordinate/Unit assumptions:
   Horizontal ground plane: XZ coordinates in meters (m).
   Vertical elevation: Y coordinate in meters (m).
   Floor area: square meters (m2).

6. Dependencies:
   backend.app.measurements.validity_gate, backend.app.measurements.uncertainty,
   backend.app.measurements.engine, backend.app.measurements.svg_render.

7. Most likely failure/debugging points:
   - Module import failures if downstream geometry modules are missing.
   - Pydantic schema validation errors when passing raw JSON dictionaries.
"""

from .validity_gate import evaluate_measurement_validity, ValidityStatus, ValidityReport
from .uncertainty import (
    calculate_corner_positional_uncertainty,
    calculate_wall_length_uncertainty,
    monte_carlo_area_and_perimeter_uncertainty,
    derive_wall_confidence,
    derive_area_confidence,
)
from .engine import compute_room_measurements, MeasurementReport
from .svg_render import render_dimensioned_debug_svg

__all__ = [
    "evaluate_measurement_validity",
    "ValidityStatus",
    "ValidityReport",
    "calculate_corner_positional_uncertainty",
    "calculate_wall_length_uncertainty",
    "monte_carlo_area_and_perimeter_uncertainty",
    "derive_wall_confidence",
    "derive_area_confidence",
    "compute_room_measurements",
    "MeasurementReport",
    "render_dimensioned_debug_svg",
]
