"""Wall quality evaluation and clutter rejection filter.

1. Why this file exists:
   Stage 2 plane fitting can fit planes to large furniture items (wardrobes,
   bed headboards, table tops) as well as true architectural walls. This module
   evaluates measurable quality signals (RMSE, confidence, height span, inliers)
   to ensure non-wall planes (such as the known Wall 09 clutter) are rejected
   before they can corrupt the room boundary polygon.

2. Pipeline stage:
   Stage 3 (2D Wall Projection & Room Polygon Extraction) - Step 1.

3. Inputs:
   List of wall dictionaries parsed from outputs/<scan_id>/structure/structure.json.

4. Outputs:
   Categorized lists of wall dictionaries: accepted, uncertain, and rejected,
   accompanied by explicit human-readable diagnostic rejection reasons.

5. Coordinate/Unit assumptions:
   Coordinates are in meters. Y is the vertical axis.
   Heights and RMSE values are metric (meters).

6. Dependencies:
   numpy, typing.

7. Most likely failure/debugging points:
   - Setting max_rmse_m too strictly may reject noisy but legitimate walls.
   - Setting min_height_span_m too high may reject walls under sloped ceilings.
   - Inspect wall_quality.json if a legitimate room boundary wall is missing.
"""

from typing import List, Dict, Any, Tuple
import numpy as np


def evaluate_wall_quality(
    walls: List[Dict[str, Any]],
    max_rmse_m: float = 0.15,
    min_confidence: float = 0.40,
    min_height_span_m: float = 1.00,
    min_inliers: int = 4000,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Evaluates measurable quality signals for each detected 3D wall plane.

    Purpose:
        Separates genuine architectural room walls from interior clutter,
        furniture, or bad RANSAC fits before 2D projection.

    Parameters:
        walls: List of wall dictionaries from structure.json.
        max_rmse_m: Maximum acceptable plane fitting RMSE in meters.
        min_confidence: Minimum acceptable structural quality confidence in [0.0, 1.0].
        min_height_span_m: Minimum vertical height span required for a wall in meters.
        min_inliers: Minimum number of supporting 3D points.

    Returns:
        (accepted_walls, uncertain_walls, rejected_walls)
        Each rejected wall entry includes a 'rejection_reasons' list.

    Assumptions:
        Assumes Y is the vertical axis and spans_m['height_y'] reflects vertical extent.

    Failure conditions:
        Returns empty accepted list if all walls fail criteria; check threshold calibration.

    Debugging:
        If Wall 09 is not rejected, check whether max_rmse_m or min_confidence was altered.
    """
    accepted = []
    uncertain = []
    rejected = []

    for w in walls:
        wall_id = w.get("id", "unknown_wall")
        rmse = float(w.get("rmse_m", 0.0))
        conf = float(w.get("confidence", 0.0))
        inliers = int(w.get("inlier_count", 0))
        spans = w.get("spans_m", {})
        height = float(spans.get("height_y", 0.0))

        reasons = []

        if rmse > max_rmse_m:
            reasons.append(f"high_fitting_rmse_{rmse:.3f}m_exceeds_{max_rmse_m}m")
        if conf < min_confidence:
            reasons.append(f"low_confidence_{conf:.3f}_below_{min_confidence}")
        if height < min_height_span_m:
            reasons.append(f"insufficient_height_{height:.2f}m_below_{min_height_span_m}m")
        if inliers < min_inliers:
            reasons.append(f"insufficient_inliers_{inliers}_below_{min_inliers}")

        w_record = dict(w)
        if reasons:
            w_record["status"] = "rejected"
            w_record["rejection_reasons"] = reasons
            rejected.append(w_record)
        else:
            w_record["status"] = "accepted"
            w_record["rejection_reasons"] = []
            accepted.append(w_record)

    return accepted, uncertain, rejected
