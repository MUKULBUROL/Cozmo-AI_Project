"""2D line intersection, distance, and geometric projection mathematics.

1. Why this file exists:
   Provides robust, coordinate-system-agnostic 2D linear algebra utilities for
   intersecting lines, computing point-to-segment distances, evaluating segment
   extensions, and determining line angles in the horizontal XZ floor plane.

2. Pipeline stage:
   Stage 3 (2D Wall Projection & Room Polygon Extraction) - Foundation math.

3. Inputs:
   Normalized 2D lines (A*x + B*z + C = 0), points, and finite segments.

4. Outputs:
   2D intersection coordinates, Euclidean distances, projection parameters,
   and angular metrics.

5. Coordinate/Unit assumptions:
   Coordinates (x, z) are in meters.
   Angles are returned in degrees unless explicitly stated.

6. Dependencies:
   numpy, typing.

7. Most likely failure/debugging points:
   - Singular matrix when solving for intersection of parallel lines.
   - Zero-length segments in distance_to_segment calculation.
"""

from typing import Optional, Tuple
import numpy as np


def intersect_2d_lines(
    line1: Tuple[float, float, float] | np.ndarray,
    line2: Tuple[float, float, float] | np.ndarray,
    min_angle_deg: float = 10.0,
) -> Optional[np.ndarray]:
    """Computes the 2D intersection of two lines in A*x + B*z + C = 0 form.

    Purpose:
        Finds the unique meeting point of two non-parallel wall lines in the XZ plane.

    Parameters:
        line1: (A1, B1, C1) coefficients of the first line.
        line2: (A2, B2, C2) coefficients of the second line.
        min_angle_deg: Minimum angle threshold in degrees to reject near-parallel lines.

    Returns:
        np.ndarray([x, z]) intersection coordinates, or None if lines are nearly parallel.

    Assumptions:
        Line coefficients (A, B) are normalized such that A^2 + B^2 == 1.

    Failure conditions:
        Returns None if determinant |A1*B2 - A2*B1| < sin(radians(min_angle_deg)).

    Debugging:
        If expected corners are missing, inspect whether min_angle_deg rejected them.
    """
    A1, B1, C1 = float(line1[0]), float(line1[1]), float(line1[2])
    A2, B2, C2 = float(line2[0]), float(line2[1]), float(line2[2])

    det = A1 * B2 - A2 * B1
    sin_thresh = float(np.sin(np.radians(min_angle_deg)))

    if abs(det) < sin_thresh:
        return None  # Lines are parallel or nearly parallel

    # Solve linear system:
    # A1*x + B1*z = -C1
    # A2*x + B2*z = -C2
    x = (-C1 * B2 - (-C2) * B1) / det
    z = (A1 * (-C2) - A2 * (-C1)) / det

    return np.array([x, z], dtype=np.float64)


def compute_segment_extension_distance(
    pt_xz: np.ndarray,
    origin_pt: np.ndarray,
    tangent_xz: np.ndarray,
    s_min: float,
    s_max: float,
) -> float:
    """Computes how far a candidate corner point lies outside observed wall extents.

    Purpose:
        Distinguishes between corners that sit on the observed wall (extension = 0.0m)
        versus corners that require geometric gap bridging (extension > 0.0m).

    Parameters:
        pt_xz: np.ndarray([x, z]) candidate intersection point.
        origin_pt: np.ndarray([x0, z0]) closest point on line to origin.
        tangent_xz: np.ndarray([tx, tz]) unit tangent vector.
        s_min: Observed minimum extent along tangent.
        s_max: Observed maximum extent along tangent.

    Returns:
        Extension distance in meters (0.0 if point falls within [s_min, s_max]).

    Assumptions:
        tangent_xz is unit length.

    Failure conditions:
        Returns 0.0 if s_min <= s <= s_max.

    Debugging:
        High extension distance indicates intersection is far beyond physical scan observation.
    """
    proj_s = float((pt_xz - origin_pt) @ tangent_xz)
    if proj_s < s_min:
        return float(s_min - proj_s)
    elif proj_s > s_max:
        return float(proj_s - s_max)
    else:
        return 0.0


def point_to_segment_distance(
    pt: np.ndarray,
    p_start: np.ndarray,
    p_end: np.ndarray,
) -> float:
    """Computes Euclidean distance from a point to a finite 2D line segment.

    Purpose:
        Evaluates physical proximity of candidate corners to observed wall ends.

    Parameters:
        pt: np.ndarray([x, z]) test point.
        p_start: np.ndarray([x, z]) start of segment.
        p_end: np.ndarray([x, z]) end of segment.

    Returns:
        Shortest Euclidean distance in meters.

    Assumptions:
        Coordinates are metric.

    Failure conditions:
        If p_start == p_end, returns distance to that single point.

    Debugging:
        Verify segment endpoints if returned distance is unexpectedly large.
    """
    seg = p_end - p_start
    seg_len_sq = float(seg @ seg)
    if seg_len_sq < 1e-10:
        return float(np.linalg.norm(pt - p_start))

    t = max(0.0, min(1.0, float((pt - p_start) @ seg / seg_len_sq)))
    proj = p_start + t * seg
    return float(np.linalg.norm(pt - proj))


def angle_between_lines_deg(
    line1: Tuple[float, float, float] | np.ndarray,
    line2: Tuple[float, float, float] | np.ndarray,
) -> float:
    """Computes acute angle in degrees between two 2D lines.

    Purpose:
        Determines orthogonality or obliqueness between adjacent room walls.

    Parameters:
        line1: (A1, B1, C1) normalized line.
        line2: (A2, B2, C2) normalized line.

    Returns:
        Acute angle in degrees [0.0, 90.0].

    Assumptions:
        Line normals are unit vectors.

    Failure conditions:
        Clips dot product to [-1.0, 1.0] to avoid numerical arccos NaNs.

    Debugging:
        Check whether dot product magnitude is close to 0 (orthogonal) or 1 (parallel).
    """
    n1 = np.array([line1[0], line1[1]], dtype=np.float64)
    n2 = np.array([line2[0], line2[1]], dtype=np.float64)
    dot = float(abs(n1 @ n2))
    dot = max(0.0, min(1.0, dot))
    # Angle between normal vectors is the angle between lines
    # For acute angle: arccos(dot)
    return float(np.degrees(np.arccos(dot)))
