"""3D ray-plane intersection and metric camera unprojection for architectural openings.

1. Why this file exists:
   Converts 2D pixel coordinates of detected door and window jambs into physical 3D world coordinates
   by casting perspective camera rays through 6D camera poses and solving exact analytical
   intersections with 3D structural wall planes, eliminating pixel-based heuristic scaling.

2. Pipeline stage:
   Stage 5 (Door/Window Detection & Metric Opening Measurement) - 3D Geometric Projection.

3. Inputs:
   2D pixel coordinates (u, v), CameraIntrinsics, 6D camera pose (position, quaternion),
   and 3D wall plane coefficients (a, b, c, d).

4. Outputs:
   Exact 3D metric world coordinates (x, y, z) lying on the structural wall plane.

5. Coordinate/Unit assumptions:
   Camera frame: right-handed optical frame (X right, Y down, Z forward).
   World frame: metric meters (Y vertical upward, XZ horizontal floor plane).
   Wall planes: normalized a*x + b*y + c*z + d = 0 where ||(a, b, c)|| = 1.

6. Dependencies:
   math, typing, numpy, scipy.spatial.transform.Rotation.

7. Most likely failure/debugging points:
   - Ray parallel to wall plane (denom near zero).
   - Intersection behind the camera (t_hit < 0).
   - Inverted quaternion order (qx, qy, qz, qw vs qw, qx, qy, qz).
"""

import math
from typing import Dict, Any, Tuple, Optional, List
import numpy as np
from scipy.spatial.transform import Rotation


def project_ray_to_wall_plane(
    pixel_uv: Tuple[float, float],
    intrinsics: Dict[str, Any],
    camera_pose: Dict[str, Any],
    wall_plane: Dict[str, float],
    max_distance_m: float = 8.0,
) -> Optional[np.ndarray]:
    """Casts a perspective optical ray from a pixel through camera pose to intersect a 3D wall plane.

    Purpose:
        Computes the exact physical 3D world intersection point of a pixel onto a planar surface.

    Parameters:
        pixel_uv: 2-tuple (u, v) in image pixel coordinates.
        intrinsics: Dictionary with fx, fy, cx, cy camera intrinsics.
        camera_pose: Dictionary with 'position' [x, y, z] and 'orientation_quaternion' [qx, qy, qz, qw].
        wall_plane: Dictionary with plane coefficients 'a', 'b', 'c', 'd' (a*x + b*y + c*z + d = 0).
        max_distance_m: Maximum acceptable distance along ray to discard diverging intersections.

    Returns:
        3D numpy array [x, y, z] in metric world coordinates, or None if no valid forward intersection.

    Assumptions:
        Plane normal (a, b, c) is normalized to unit length.
        Quaternion is formatted as [qx, qy, qz, qw].

    Failure conditions:
        Returns None if ray is parallel to plane (|dot| < 1e-4) or intersection is behind camera (t <= 0).

    Debugging:
        Check sign of t_hit if intersection points diverge.
    """
    u, v = pixel_uv
    fx = float(intrinsics["fx"])
    fy = float(intrinsics["fy"])
    cx = float(intrinsics["cx"])
    cy = float(intrinsics["cy"])

    # 1. Optical ray in camera coordinate system (Z forward, X right, Y down)
    r_cam = np.array([(u - cx) / fx, (v - cy) / fy, 1.0], dtype=np.float64)
    r_cam /= np.linalg.norm(r_cam)

    # 2. Camera pose in world space
    pos = np.array(camera_pose["position"], dtype=np.float64)
    quat = camera_pose.get("orientation_quaternion") or camera_pose.get("quaternion")
    rot = Rotation.from_quat(quat)

    # Transform ray direction to world frame
    r_world = rot.apply(r_cam)

    # 3. Wall plane equation: a*x + b*y + c*z + d = 0
    if isinstance(wall_plane, (list, tuple)):
        a, b, c, d = float(wall_plane[0]), float(wall_plane[1]), float(wall_plane[2]), float(wall_plane[3])
    else:
        a = float(wall_plane["a"])
        b = float(wall_plane["b"])
        c = float(wall_plane["c"])
        d = float(wall_plane["d"])
    normal = np.array([a, b, c], dtype=np.float64)

    denom = np.dot(normal, r_world)
    if abs(denom) < 1e-4:
        # Ray is parallel to wall plane
        return None

    # Solve for distance along ray: dot(normal, pos + t * r_world) + d = 0
    t_hit = -(np.dot(normal, pos) + d) / denom

    if t_hit <= 0.10 or t_hit > max_distance_m:
        # Intersection is behind camera or exceeds range
        return None

    p_world = pos + t_hit * r_world
    return p_world


def project_opening_to_wall(
    boundary_pixels: Dict[str, Any],
    intrinsics: Dict[str, Any],
    camera_pose: Dict[str, Any],
    wall_plane: Dict[str, float],
) -> Optional[Dict[str, Any]]:
    """Projects left and right jambs, header, and sill of an opening onto a physical wall plane.

    Purpose:
        Constructs full 3D metric opening geometry anchored to a specific Stage 2 wall plane.

    Parameters:
        boundary_pixels: Dictionary containing left_jamb_pixel, right_jamb_pixel, etc.
        intrinsics: Camera intrinsics dictionary.
        camera_pose: Camera 6D pose dictionary.
        wall_plane: Stage 2 plane equation coefficients.

    Returns:
        Dictionary with left_jamb_3d, right_jamb_3d, opening_width_m, and 3D centroid,
        or None if projection fails.

    Assumptions:
        Left and right jambs must both successfully project onto the wall.

    Failure conditions:
        Returns None if either jamb fails forward ray-plane intersection.

    Debugging:
        Verify distance between 3D jambs falls within sensible architectural dimensions.
    """
    # Determine camera orientation relative to world gravity (Y is vertical)
    quat = camera_pose.get("orientation_quaternion") or camera_pose.get("quaternion")
    rot = Rotation.from_quat(quat)
    R = rot.as_matrix()
    u_world = R[:, 0]  # camera X axis in world
    v_world = R[:, 1]  # camera Y axis in world
    u_vert = abs(u_world[1])
    v_vert = abs(v_world[1])

    bbox = boundary_pixels.get("refined_bbox") or boundary_pixels.get("bbox")
    if bbox and len(bbox) == 4 and u_vert > v_vert:
        # Portrait orientation: camera Y axis (rows, v) is horizontal in world!
        x1, y1, x2, y2 = bbox
        xmid = (x1 + x2) / 2.0
        p_left_2d = (xmid, float(y1))
        p_right_2d = (xmid, float(y2))
    else:
        p_left_2d = boundary_pixels.get("left_jamb_pixel")
        p_right_2d = boundary_pixels.get("right_jamb_pixel")

    if not p_left_2d or not p_right_2d:
        return None

    p_left_3d = project_ray_to_wall_plane(tuple(p_left_2d), intrinsics, camera_pose, wall_plane)
    p_right_3d = project_ray_to_wall_plane(tuple(p_right_2d), intrinsics, camera_pose, wall_plane)

    if p_left_3d is None or p_right_3d is None:
        return None

    # Calculate metric width in horizontal XZ plane
    dx = p_right_3d[0] - p_left_3d[0]
    dz = p_right_3d[2] - p_left_3d[2]
    horizontal_width_m = float(math.hypot(dx, dz))

    centroid_3d = (p_left_3d + p_right_3d) / 2.0

    return {
        "left_jamb_3d": [round(float(v), 4) for v in p_left_3d],
        "right_jamb_3d": [round(float(v), 4) for v in p_right_3d],
        "centroid_3d": [round(float(v), 4) for v in centroid_3d],
        "width_m": round(horizontal_width_m, 4),
        "ray_distance_m": round(float(np.linalg.norm(centroid_3d - np.array(camera_pose["position"]))), 3),
    }
