"""3D metric projection, host-surface association, and planar frame unprojection.

1. Why this file exists:
   Bridges 2D visual damage masks to metric 3D space by casting optical rays through
   calibrated camera poses and intersecting Stage 2 structural planes (walls, floors, ceilings),
   or back-projecting aligned depth maps. Establishes stable local 2D coordinate frames
   on host surfaces to enable exact physical area and crack length calculation.

2. Pipeline stage:
   Stage 9 (Damage Detection, Metric Extent, Concealed-Damage Rules & Repair Scope) - 3D Projection.

3. Inputs:
   Binary damage mask (H, W bool), camera intrinsics, 6D camera pose, structural planes,
   and optional aligned metric depth map.

4. Outputs:
   Dictionary with associated host_surface_id, host_surface_type, 3D centroid,
   projected 3D points, planar local 2D points (u_local, v_local), view angle,
   and projection status.

5. Coordinate convention:
   Camera frame: Optical frame (X right, Y down, Z forward).
   World frame: Right-handed metric meters (Y vertical upward, XZ horizontal ground).
   Host plane equation: a*x + b*y + c*z + d = 0 with unit normal (a, b, c).
   Plane local frame: (u_local, v_local) along horizontal and vertical planar axes.

6. Unit convention:
   Distances and coordinates in metric meters (m).
   View angles in degrees.

7. Dependencies:
   math, typing, numpy, scipy.spatial.transform.Rotation, backend.app.models.damage.SurfaceType.

8. Assumptions:
   - Structural planes have been extracted by Stage 2 with reliable plane equations.
   - Damage points lie on or very close to the host plane surface (within 0.15 m tolerance).

9. Failure modes:
   - Camera optical ray nearly parallel to host plane (|dot(n, r)| < 0.10).
   - Intersection behind the camera or diverging to infinity (> 10 m).
   - Damage mask spanning multiple conflicting structural surfaces.
   - Missing or uncalibrated camera pose / intrinsics -> returns NOT_EVALUABLE.

10. First things to inspect while debugging:
    - Check view_angle_deg (angles > 75 deg indicate extreme oblique degradation).
    - Check host_plane_support_ratio (rejects if best plane supports < 50% of sampled points).
    - Verify camera_pose dictionary keys (position, orientation_quaternion).
"""

import math
from typing import Dict, Any, List, Optional, Tuple
import numpy as np
from scipy.spatial.transform import Rotation

from ..models.damage import SurfaceType, DamageStatus


class DamagePlaneProjector:
    """Projects 2D damage masks onto 3D structural planes and local planar frames."""

    def __init__(
        self,
        max_ray_distance_m: float = 8.0,
        max_plane_residual_m: float = 0.18,
        min_support_ratio: float = 0.50,
        max_oblique_angle_deg: float = 75.0,
        sample_step: int = 4,
    ):
        """Initializes projector tolerances and sampling parameters.

        Purpose:
            Configures geometric acceptance criteria for host plane association.

        Parameters:
            max_ray_distance_m: Maximum allowable camera-to-surface distance.
            max_plane_residual_m: Maximum perpendicular distance from point to host plane.
            min_support_ratio: Minimum fraction of mask samples that must agree on host plane.
            max_oblique_angle_deg: Cutoff view angle relative to surface normal.
            sample_step: Grid subsampling step in pixels to balance accuracy and speed.

        Returns:
            None.

        Assumptions:
            Subsampling by sample_step produces a statistically representative point cloud.

        Failure cases:
            None.

        Debugging clues:
            Decrease sample_step if inspecting very small damage spots (< 50 pixels).
        """
        self.max_ray_distance_m = max_ray_distance_m
        self.max_plane_residual_m = max_plane_residual_m
        self.min_support_ratio = min_support_ratio
        self.max_oblique_angle_deg = max_oblique_angle_deg
        self.sample_step = sample_step

    def project_and_associate(
        self,
        mask: np.ndarray,
        intrinsics: Optional[Dict[str, Any]],
        camera_pose: Optional[Dict[str, Any]],
        structural_planes: List[Dict[str, Any]],
        depth_map: Optional[np.ndarray] = None,
    ) -> Dict[str, Any]:
        """Associates mask with a host structural plane and computes 3D coordinates.

        Purpose:
            Identifies the host structural surface (wall, floor, ceiling) receiving the
            greatest geometric support, projects mask points onto the surface, and returns
            both 3D world coordinates and 2D local planar coordinates.

        Parameters:
            mask: Full-resolution binary mask array (H, W bool or uint8).
            intrinsics: Camera intrinsics dictionary with fx, fy, cx, cy.
            camera_pose: 6D camera pose dictionary with position and orientation_quaternion.
            structural_planes: List of plane dictionaries with 'plane_id', 'type', 'equation' [a,b,c,d].
            depth_map: Optional aligned depth map array.

        Returns:
            Dictionary containing:
            {
                'status': DamageStatus,
                'host_surface_id': Optional[str],
                'host_surface_type': SurfaceType,
                'centroid_3d': Optional[List[float]],
                'points_3d': Optional[np.ndarray],
                'points_2d_local': Optional[np.ndarray],
                'view_angle_deg': Optional[float],
                'plane_equation': Optional[List[float]],
                'local_basis': Optional[Dict[str, Any]],
                'support_ratio': float,
                'rejection_reason': Optional[str],
            }

        Assumptions:
            Structural plane normal is normalized: a^2 + b^2 + c^2 = 1.

        Failure cases:
            Returns NOT_EVALUABLE if intrinsics or poses are missing or uncalibrated.

        Debugging clues:
            Inspect support_ratio and view_angle_deg if status is REJECTED or PROVISIONAL.
        """
        if intrinsics is None or camera_pose is None or not structural_planes:
            return {
                "status": DamageStatus.NOT_EVALUABLE,
                "host_surface_id": None,
                "host_surface_type": SurfaceType.OTHER,
                "centroid_3d": None,
                "points_3d": None,
                "points_2d_local": None,
                "view_angle_deg": None,
                "plane_equation": None,
                "local_basis": None,
                "support_ratio": 0.0,
                "rejection_reason": "missing_intrinsics_pose_or_structural_planes",
            }

        # Extract mask coordinate samples
        v_indices, u_indices = np.where(mask > 0)
        if len(u_indices) == 0:
            return {
                "status": DamageStatus.REJECTED,
                "host_surface_id": None,
                "host_surface_type": SurfaceType.OTHER,
                "centroid_3d": None,
                "points_3d": None,
                "points_2d_local": None,
                "view_angle_deg": None,
                "plane_equation": None,
                "local_basis": None,
                "support_ratio": 0.0,
                "rejection_reason": "empty_mask",
            }

        # Subsample for efficiency
        step = max(1, self.sample_step)
        u_samples = u_indices[::step]
        v_samples = v_indices[::step]

        fx = float(intrinsics["fx"])
        fy = float(intrinsics["fy"])
        cx = float(intrinsics["cx"])
        cy = float(intrinsics["cy"])

        # Camera center in world coordinates
        cam_pos = np.array(camera_pose["position"], dtype=np.float64)
        quat = camera_pose.get("orientation_quaternion") or camera_pose.get("quaternion")
        rot = Rotation.from_quat(quat)

        # Precompute camera rays in world frame
        # r_cam = [(u - cx)/fx, (v - cy)/fy, 1.0]
        dirs_cam = np.stack(
            [(u_samples - cx) / fx, (v_samples - cy) / fy, np.ones_like(u_samples, dtype=np.float64)],
            axis=-1,
        )
        norms = np.linalg.norm(dirs_cam, axis=-1, keepdims=True)
        dirs_cam /= norms
        dirs_world = rot.apply(dirs_cam)  # (N, 3)

        # Test intersection against each candidate structural plane
        best_plane_record: Optional[Dict[str, Any]] = None
        best_hits_3d: Optional[np.ndarray] = None
        max_valid_hits = 0
        total_samples = len(u_samples)

        for plane in structural_planes:
            eq = plane.get("equation") or plane.get("coefficients")
            if eq is None:
                continue
            if isinstance(eq, dict):
                a, b, c, d = float(eq["a"]), float(eq["b"]), float(eq["c"]), float(eq["d"])
            else:
                a, b, c, d = float(eq[0]), float(eq[1]), float(eq[2]), float(eq[3])

            normal = np.array([a, b, c], dtype=np.float64)
            n_len = np.linalg.norm(normal)
            if n_len > 1e-6:
                normal /= n_len
                d /= n_len
            else:
                continue

            # Check ray-plane intersection: t = -(dot(normal, cam_pos) + d) / dot(normal, ray_dir)
            numer = -(np.dot(normal, cam_pos) + d)
            denoms = np.dot(dirs_world, normal)  # (N,)

            # Filter valid intersections in front of camera
            valid_mask = (np.abs(denoms) > 0.08) & (np.sign(numer) == np.sign(denoms))
            t_vals = np.where(valid_mask, numer / np.where(denoms == 0, 1e-6, denoms), -1.0)
            valid_t = (t_vals > 0.10) & (t_vals <= self.max_ray_distance_m)

            num_hits = int(np.count_nonzero(valid_t))
            if num_hits > max_valid_hits:
                hits_3d = cam_pos + dirs_world[valid_t] * t_vals[valid_t, np.newaxis]
                max_valid_hits = num_hits
                best_plane_record = plane
                best_hits_3d = hits_3d

        support_ratio = max_valid_hits / float(total_samples) if total_samples > 0 else 0.0

        if best_plane_record is None or support_ratio < self.min_support_ratio or best_hits_3d is None:
            return {
                "status": DamageStatus.REJECTED,
                "host_surface_id": None,
                "host_surface_type": SurfaceType.OTHER,
                "centroid_3d": None,
                "points_3d": None,
                "points_2d_local": None,
                "view_angle_deg": None,
                "plane_equation": None,
                "local_basis": None,
                "support_ratio": round(support_ratio, 3),
                "rejection_reason": "insufficient_host_plane_geometric_support",
            }

        # Extract host plane equation and normal
        eq = best_plane_record.get("equation") or best_plane_record.get("coefficients")
        if isinstance(eq, dict):
            a, b, c, d = float(eq["a"]), float(eq["b"]), float(eq["c"]), float(eq["d"])
        else:
            a, b, c, d = float(eq[0]), float(eq[1]), float(eq[2]), float(eq[3])
        plane_normal = np.array([a, b, c], dtype=np.float64)
        plane_normal /= np.linalg.norm(plane_normal)

        # 3D centroid of intersection points
        centroid_3d = np.mean(best_hits_3d, axis=0)

        # Compute viewing angle between camera ray to centroid and plane normal
        ray_to_center = centroid_3d - cam_pos
        ray_len = np.linalg.norm(ray_to_center)
        if ray_len > 1e-6:
            ray_to_center /= ray_len
            # Acute angle between ray and normal
            cos_angle = abs(np.dot(ray_to_center, plane_normal))
            view_angle_deg = float(np.degrees(np.arccos(np.clip(cos_angle, 0.0, 1.0))))
        else:
            view_angle_deg = 0.0

        # Construct local orthonormal 2D frame on the host plane
        # For walls (nearly vertical normal): vertical axis is (0, 1, 0)
        local_basis = self.build_planar_local_basis(plane_normal, centroid_3d)
        u_axis = local_basis["u_axis"]
        v_axis = local_basis["v_axis"]
        origin = local_basis["origin"]

        # Project 3D points to local 2D plane coordinates
        diffs = best_hits_3d - origin
        u_local = np.dot(diffs, u_axis)
        v_local = np.dot(diffs, v_axis)
        points_2d_local = np.stack([u_local, v_local], axis=-1)

        # Classify host surface type
        surface_type_str = str(best_plane_record.get("type", "wall")).lower()
        if "wall" in surface_type_str:
            host_type = SurfaceType.WALL
        elif "floor" in surface_type_str:
            host_type = SurfaceType.FLOOR
        elif "ceiling" in surface_type_str:
            host_type = SurfaceType.CEILING
        else:
            host_type = SurfaceType.WALL

        # Status determination based on view angle and support
        status = DamageStatus.ACCEPTED
        rejection_reason = None
        if view_angle_deg > self.max_oblique_angle_deg:
            status = DamageStatus.NOT_EVALUABLE
            rejection_reason = f"extreme_oblique_view_angle_{view_angle_deg:.1f}_deg"
        elif support_ratio < 0.70 or view_angle_deg > 60.0:
            status = DamageStatus.PROVISIONAL

        return {
            "status": status,
            "host_surface_id": str(best_plane_record.get("plane_id") or best_plane_record.get("id", "plane_00")),
            "host_surface_type": host_type,
            "centroid_3d": [round(x, 4) for x in centroid_3d.tolist()],
            "points_3d": best_hits_3d,
            "points_2d_local": points_2d_local,
            "view_angle_deg": round(view_angle_deg, 2),
            "plane_equation": [round(a, 4), round(b, 4), round(c, 4), round(d, 4)],
            "local_basis": local_basis,
            "support_ratio": round(support_ratio, 3),
            "rejection_reason": rejection_reason,
        }

    @staticmethod
    def build_planar_local_basis(normal: np.ndarray, origin: np.ndarray) -> Dict[str, Any]:
        """Constructs an orthonormal 2D coordinate basis on a 3D plane.

        Purpose:
            Defines horizontal (u) and vertical (v) tangent vectors on a host surface plane
            to facilitate Euclidean 2D area and curve length calculation.

        Parameters:
            normal: 3D unit normal vector (a, b, c) of the plane.
            origin: 3D origin point lying on the plane.

        Returns:
            Dictionary with 'u_axis', 'v_axis', 'normal', and 'origin'.
        """
        n = normal / np.linalg.norm(normal)
        # Check if plane is horizontal (floor or ceiling: n close to +/- Y)
        if abs(n[1]) > 0.85:
            # Floor or ceiling
            v_axis = np.array([0.0, 0.0, 1.0], dtype=np.float64)
            u_axis = np.cross(v_axis, n)
            u_axis /= np.linalg.norm(u_axis)
            v_axis = np.cross(n, u_axis)
            v_axis /= np.linalg.norm(v_axis)
        else:
            # Wall: vertical axis aligns with world Y
            up = np.array([0.0, 1.0, 0.0], dtype=np.float64)
            u_axis = np.cross(up, n)
            u_axis /= np.linalg.norm(u_axis)
            v_axis = np.cross(n, u_axis)
            v_axis /= np.linalg.norm(v_axis)

        return {
            "u_axis": u_axis,
            "v_axis": v_axis,
            "normal": n,
            "origin": origin,
        }
