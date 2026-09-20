"""Unit tests for Stage 9 damage segmentation and 3D plane projection.

1. Why this file exists:
   Verifies pixel mask segmentation within candidate bounding boxes, analytical
   ray-plane unprojection to 3D world space, host structural plane association,
   and view angle degradation checks.

2. Pipeline stage:
   Stage 9 (Damage Detection, Metric Extent, Concealed-Damage Rules & Repair Scope) - Testing.

3. Inputs:
   Synthetic images with painted damage, analytical camera poses, and structural planes.

4. Outputs:
   Pytest assertion results confirming geometric projection accuracy and status gating.

5. Coordinate convention:
   Camera optical frame and world metric frame.

6. Unit convention:
   Meters (m), degrees, pixels.

7. Dependencies:
   unittest, numpy, backend.app.damage.segmenter, backend.app.damage.projection.

8. Assumptions:
   - Synthetic geometry tests verify exact mathematical correctness without neural dependencies.

9. Failure modes:
   - Inaccurate ray intersection math or sign flips in plane equations.

10. First things to inspect while debugging:
    - Check plane normal normalization and distance sign.
"""

import math
import unittest
import numpy as np

from backend.app.models.output import DamageClass
from backend.app.models.damage import DamageStatus, SurfaceType
from backend.app.damage.segmenter import DamageMaskSegmenter
from backend.app.damage.projection import DamagePlaneProjector


class TestDamageProjection(unittest.TestCase):
    """Verifies segmentation and 3D metric host-surface projection."""

    def setUp(self):
        self.segmenter = DamageMaskSegmenter(min_mask_pixels=10)
        self.projector = DamagePlaneProjector()

    def test_segmenter_stain_extraction(self):
        # Create a synthetic white wall with a dark circular water stain
        img = np.full((300, 400, 3), 220, dtype=np.uint8)
        # Draw stain in region [50, 50, 150, 150]
        y, x = np.ogrid[:300, :400]
        mask_circle = ((x - 100) ** 2 + (y - 100) ** 2) <= 30 ** 2
        img[mask_circle] = [110, 95, 80]  # dark brownish stain

        bbox = [60.0, 60.0, 140.0, 140.0]
        result = self.segmenter.segment_candidate(img, bbox, DamageClass.WATER_STAIN)

        self.assertIn("mask", result)
        self.assertGreater(result["mask_area_pixels"], 100)
        self.assertGreater(len(result["boundary_polygon"]), 3)
        self.assertFalse(result["is_fallback"])

    def test_segmenter_crack_extraction(self):
        # Create a synthetic image with a thin diagonal line (crack)
        img = np.full((200, 200, 3), 230, dtype=np.uint8)
        for i in range(40, 160):
            img[i, i] = [40, 40, 40]
            img[i, min(199, i + 1)] = [60, 60, 60]

        bbox = [35.0, 35.0, 165.0, 165.0]
        result = self.segmenter.segment_candidate(img, bbox, DamageClass.SURFACE_CRACK)
        self.assertGreater(result["mask_area_pixels"], 20)
        self.assertGreaterEqual(len(result["boundary_polygon"]), 2)

    def test_projector_wall_association(self):
        # Camera at (0, 1.5, 0) looking forward along +Z
        # Camera quaternion: identity [0, 0, 0, 1]
        camera_pose = {
            "position": [0.0, 1.5, 0.0],
            "orientation_quaternion": [0.0, 0.0, 0.0, 1.0],
        }
        # Intrinsics: fx=1000, fy=1000, cx=500, cy=500, width=1000, height=1000
        intrinsics = {
            "fx": 1000.0,
            "fy": 1000.0,
            "cx": 500.0,
            "cy": 500.0,
            "width": 1000,
            "height": 1000,
        }
        # Wall at Z = 3.0 m (Plane: 0*x + 0*y + 1*z - 3.0 = 0 -> normal [0, 0, -1], d=3 or [0, 0, 1], d=-3)
        structural_planes = [
            {
                "plane_id": "wall_front",
                "type": "wall",
                "equation": [0.0, 0.0, 1.0, -3.0],
            },
            {
                "plane_id": "wall_side",
                "type": "wall",
                "equation": [1.0, 0.0, 0.0, -4.0],
            },
        ]

        # Mask symmetrically centered around image center (u=500, v=500)
        mask = np.zeros((1000, 1000), dtype=bool)
        mask[480:521, 480:521] = True

        res = self.projector.project_and_associate(
            mask, intrinsics, camera_pose, structural_planes
        )

        self.assertEqual(res["status"], DamageStatus.ACCEPTED)
        self.assertEqual(res["host_surface_id"], "wall_front")
        self.assertEqual(res["host_surface_type"], SurfaceType.WALL)
        # Ray through (500, 500) hits exactly (0, 1.5, 3.0)
        centroid = res["centroid_3d"]
        self.assertAlmostEqual(centroid[0], 0.0, places=1)
        self.assertAlmostEqual(centroid[1], 1.5, places=1)
        self.assertAlmostEqual(centroid[2], 3.0, places=1)
        self.assertLess(res["view_angle_deg"], 10.0)

    def test_projector_oblique_angle_degradation(self):
        # Camera at (0, 1.5, 0) looking nearly parallel to wall at X = 0.2
        camera_pose = {
            "position": [0.0, 1.5, 0.0],
            "orientation_quaternion": [0.0, 0.0, 0.0, 1.0],
        }
        intrinsics = {
            "fx": 1000.0,
            "fy": 1000.0,
            "cx": 500.0,
            "cy": 500.0,
            "width": 1000,
            "height": 1000,
        }
        # Wall is at X = 0.5 (normal [1, 0, 0], d = -0.5)
        # Looking along +Z gives view angle ~ 90 deg (extreme grazing)
        structural_planes = [
            {
                "plane_id": "wall_grazing",
                "type": "wall",
                "equation": [1.0, 0.0, 0.0, -0.5],
            }
        ]

        mask = np.zeros((1000, 1000), dtype=bool)
        mask[480:520, 480:520] = True

        res = self.projector.project_and_associate(
            mask, intrinsics, camera_pose, structural_planes
        )
        # Should be NOT_EVALUABLE or REJECTED due to extreme angle or parallel ray
        self.assertIn(res["status"], [DamageStatus.NOT_EVALUABLE, DamageStatus.REJECTED])

    def test_projector_missing_geometry_not_evaluable(self):
        mask = np.ones((50, 50), dtype=bool)
        res = self.projector.project_and_associate(mask, None, None, [])
        self.assertEqual(res["status"], DamageStatus.NOT_EVALUABLE)


if __name__ == "__main__":
    unittest.main()
