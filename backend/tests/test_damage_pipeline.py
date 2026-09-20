"""Comprehensive integration tests for Stage 9 damage pipeline, extent, rules, and scope.

1. Why this file exists:
   Implements end-to-end integration and safety verification for all 18 mandatory
   requirements specified in Stage 9 Step 30. Verifies deterministic execution of
   pipeline orchestration, multi-tier provenance, rule safety, and schema compatibility.

2. Pipeline stage:
   Stage 9 (Damage Detection, Metric Extent, Concealed-Damage Rules & Repair Scope) - Testing.

3. Inputs:
   Synthetic frames, analytical structural geometry, multi-view observations, and schema objects.

4. Outputs:
   Pytest assertion results confirming complete compliance with the Stage 9 Definition of Done.

5. Coordinate convention:
   Metric world meters, image pixel coordinates, surface local coordinates.

6. Unit convention:
   Meters (m), square meters (m2).

7. Dependencies:
   unittest, numpy, backend.app.damage.*, backend.app.models.damage.*, backend.app.models.output.*.

8. Assumptions:
   - All tests run deterministically without neural network downloads during CI.

9. Failure modes:
   - Failure of any of the 18 architectural guarantees.

10. First things to inspect while debugging:
    - Inspect failing test method name corresponding to Step 30 requirements.
"""

import unittest
import numpy as np
from pathlib import Path

from backend.app.models.damage import (
    DamageFrame,
    DamageObservation2D,
    DamageRegion3D,
    ConcealedDamageFlag,
    ScopeLineItem,
    DamageStatus,
    DamageQualityStatus,
    SurfaceType,
)
from backend.app.models.output import (
    DamageClass,
    Measurement,
    DamageRegion,
    PropertyPlanOutput,
)
from backend.app.models.capture import CaptureTier
from backend.app.damage.adapter import DamageInputAdapter
from backend.app.damage.quality import DamageImageQualityGate
from backend.app.damage.segmenter import DamageMaskSegmenter
from backend.app.damage.projection import DamagePlaneProjector
from backend.app.damage.extent import DamageExtentEstimator
from backend.app.damage.fusion import MultiViewDamageFusion
from backend.app.damage.rules import ConcealedDamageRuleEngine
from backend.app.damage.scope import RepairScopeGenerator
from backend.app.damage.pipeline import DamageAssessmentPipeline


class TestDamagePipeline(unittest.TestCase):
    """Verifies all 18 core requirements of Stage 9."""

    def setUp(self):
        self.projector = DamagePlaneProjector()
        self.extent_estimator = DamageExtentEstimator()
        self.fusion = MultiViewDamageFusion()
        self.rules = ConcealedDamageRuleEngine()
        self.scope = RepairScopeGenerator()

    # 1. damage mask model serialization
    def test_01_damage_mask_model_serialization(self):
        obs = DamageObservation2D(
            observation_id="obs_test_01",
            image_id="img_01.jpg",
            capture_id="cap_01",
            tier="lidar",
            class_name="water stain",
            canonical_class=DamageClass.WATER_STAIN,
            class_confidence=0.92,
            bbox=[50.0, 50.0, 250.0, 250.0],
            mask_area_pixels=32000,
            segmentation_confidence=0.88,
            boundary_polygon=[[50.0, 50.0], [250.0, 50.0], [250.0, 250.0]],
            is_clipped_by_border=False,
            view_angle_deg=12.0,
        )
        d = obs.model_dump()
        self.assertEqual(d["observation_id"], "obs_test_01")
        self.assertEqual(d["canonical_class"], "water_stain")
        self.assertEqual(d["mask_area_pixels"], 32000)

    # 2. wall-plane projection
    def test_02_wall_plane_projection(self):
        cam_pose = {"position": [0.0, 1.5, 0.0], "orientation_quaternion": [0.0, 0.0, 0.0, 1.0]}
        intr = {"fx": 1000.0, "fy": 1000.0, "cx": 500.0, "cy": 500.0, "width": 1000, "height": 1000}
        planes = [{"plane_id": "wall_01", "type": "wall", "equation": [0.0, 0.0, 1.0, -3.0]}]
        mask = np.zeros((1000, 1000), dtype=bool)
        mask[480:521, 480:521] = True

        res = self.projector.project_and_associate(mask, intr, cam_pose, planes)
        self.assertEqual(res["status"], DamageStatus.ACCEPTED)
        self.assertAlmostEqual(res["centroid_3d"][2], 3.0, places=1)

    # 3. synthetic known metric area
    def test_03_synthetic_known_metric_area(self):
        # 1.2 m x 1.0 m rectangle -> 1.20 m2
        u = np.linspace(0.0, 1.2, 25)
        v = np.linspace(0.0, 1.0, 20)
        uu, vv = np.meshgrid(u, v)
        pts = np.stack([uu.ravel(), vv.ravel()], axis=-1)

        res = self.extent_estimator.compute_metric_extent(
            pts, DamageClass.WATER_STAIN, view_angle_deg=5.0, is_clipped_by_border=False
        )
        self.assertIsNotNone(res["metric_area"])
        self.assertAlmostEqual(res["metric_area"].value, 1.20, places=1)
        self.assertEqual(res["metric_area"].unit, "m2")

    # 4. synthetic known crack length
    def test_04_synthetic_known_crack_length(self):
        # 1.80 m linear crack
        u = np.linspace(-0.9, 0.9, 40)
        v = np.zeros_like(u)
        pts = np.stack([u, v], axis=-1)

        res = self.extent_estimator.compute_metric_extent(
            pts, DamageClass.SURFACE_CRACK, view_angle_deg=10.0, is_clipped_by_border=False
        )
        self.assertIsNotNone(res["metric_length"])
        self.assertAlmostEqual(res["metric_length"].value, 1.80, places=1)
        self.assertEqual(res["metric_length"].unit, "m")

    # 5. uncertainty increases with bad depth / plane RMSE
    def test_05_uncertainty_increases_with_plane_rmse(self):
        pts = np.array([[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]])
        r_good = self.extent_estimator.compute_metric_extent(
            pts, DamageClass.WATER_STAIN, plane_rmse_m=0.01
        )
        r_bad = self.extent_estimator.compute_metric_extent(
            pts, DamageClass.WATER_STAIN, plane_rmse_m=0.08
        )
        spread_good = r_good["metric_area"].upper_bound - r_good["metric_area"].lower_bound
        spread_bad = r_bad["metric_area"].upper_bound - r_bad["metric_area"].lower_bound
        self.assertGreater(spread_bad, spread_good)

    # 6. uncertainty increases at oblique angle
    def test_06_uncertainty_increases_at_oblique_angle(self):
        pts = np.array([[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]])
        r_ortho = self.extent_estimator.compute_metric_extent(
            pts, DamageClass.WATER_STAIN, view_angle_deg=10.0
        )
        r_oblique = self.extent_estimator.compute_metric_extent(
            pts, DamageClass.WATER_STAIN, view_angle_deg=65.0
        )
        spread_ortho = r_ortho["metric_area"].upper_bound - r_ortho["metric_area"].lower_bound
        spread_oblique = r_oblique["metric_area"].upper_bound - r_oblique["metric_area"].lower_bound
        self.assertGreater(spread_oblique, spread_ortho)

    # 7. image-border clipping downgrade
    def test_07_image_border_clipping_downgrade(self):
        pts = np.array([[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]])
        r_clipped = self.extent_estimator.compute_metric_extent(
            pts, DamageClass.WATER_STAIN, is_clipped_by_border=True
        )
        self.assertEqual(r_clipped["status"], DamageStatus.PROVISIONAL)
        self.assertIn("clipped", r_clipped["rejection_reason"])

    # 8. same damage from multiple views is fused
    def test_08_same_damage_multiple_views_fused(self):
        obs1 = {
            "observation_id": "obs_1",
            "image_id": "frame_01.jpg",
            "host_surface_id": "wall_A",
            "centroid_3d": [1.0, 1.5, 2.0],
            "damage_class": DamageClass.WATER_STAIN,
            "metric_area": Measurement[float](
                value=1.1, unit="m2", lower_bound=1.0, upper_bound=1.2, confidence=0.9, method="t"
            ),
            "status": DamageStatus.ACCEPTED,
        }
        obs2 = {
            "observation_id": "obs_2",
            "image_id": "frame_02.jpg",
            "host_surface_id": "wall_A",
            "centroid_3d": [1.08, 1.52, 1.98],
            "damage_class": DamageClass.WATER_STAIN,
            "metric_area": Measurement[float](
                value=1.2, unit="m2", lower_bound=1.1, upper_bound=1.3, confidence=0.9, method="t"
            ),
            "status": DamageStatus.ACCEPTED,
        }
        fused = self.fusion.fuse_observations([obs1, obs2], capture_id="test_cap")
        self.assertEqual(len(fused), 1)
        self.assertEqual(len(fused[0].supporting_images), 2)

    # 9. different damage regions are not fused
    def test_09_different_damage_regions_not_fused(self):
        obs1 = {
            "observation_id": "obs_1",
            "image_id": "frame_01.jpg",
            "host_surface_id": "wall_A",
            "centroid_3d": [1.0, 1.5, 2.0],
            "damage_class": DamageClass.WATER_STAIN,
            "status": DamageStatus.ACCEPTED,
        }
        obs2 = {
            "observation_id": "obs_2",
            "image_id": "frame_02.jpg",
            "host_surface_id": "wall_A",
            "centroid_3d": [3.0, 1.5, 2.0],  # 2.0 meters apart
            "damage_class": DamageClass.WATER_STAIN,
            "status": DamageStatus.ACCEPTED,
        }
        fused = self.fusion.fuse_observations([obs1, obs2], capture_id="test_cap")
        self.assertEqual(len(fused), 2)

    # 10. host wall association
    def test_10_host_wall_association(self):
        cam_pose = {"position": [0.0, 1.5, 0.0], "orientation_quaternion": [0.0, 0.0, 0.0, 1.0]}
        intr = {"fx": 1000.0, "fy": 1000.0, "cx": 500.0, "cy": 500.0, "width": 1000, "height": 1000}
        planes = [
            {"plane_id": "wall_north", "type": "wall", "equation": [0.0, 0.0, 1.0, -4.0]},
            {"plane_id": "wall_south", "type": "wall", "equation": [0.0, 0.0, -1.0, -2.0]},
        ]
        mask = np.zeros((1000, 1000), dtype=bool)
        mask[490:511, 490:511] = True

        res = self.projector.project_and_associate(mask, intr, cam_pose, planes)
        self.assertEqual(res["host_surface_id"], "wall_north")
        self.assertEqual(res["host_surface_type"], SurfaceType.WALL)

    # 11. missing metric geometry -> NOT_EVALUABLE
    def test_11_missing_metric_geometry_not_evaluable(self):
        pts = np.array([[0.0, 0.0], [1.0, 1.0]])
        # is_metric_calibrated = False -> NOT_EVALUABLE
        res = self.extent_estimator.compute_metric_extent(
            pts, DamageClass.WATER_STAIN, is_metric_calibrated=False
        )
        self.assertEqual(res["status"], DamageStatus.NOT_EVALUABLE)
        self.assertIsNone(res["metric_area"])

    # 12. concealed rule fires correctly
    def test_12_concealed_rule_fires_correctly(self):
        d = DamageRegion3D(
            damage_id="dmg_c01",
            damage_class=DamageClass.WATER_STAIN,
            class_confidence=0.88,
            host_surface_id="wall_01",
            host_surface_type=SurfaceType.WALL,
            centroid_3d=[1.0, 1.5, 2.0],
            metric_area=Measurement[float](
                value=0.8, unit="m2", lower_bound=0.7, upper_bound=0.9, confidence=0.9, method="test"
            ),
            status=DamageStatus.ACCEPTED,
        )
        flags = self.rules.evaluate_damage(d)
        self.assertGreaterEqual(len(flags), 1)
        self.assertEqual(flags[0].damage_id, "dmg_c01")

    # 13. concealed rule is a FLAG, not diagnosis
    def test_13_concealed_rule_is_flag_not_diagnosis(self):
        d = DamageRegion3D(
            damage_id="dmg_c02",
            damage_class=DamageClass.MOLD_LIKE_DISCOLORATION,
            class_confidence=0.85,
            host_surface_id="ceiling_01",
            host_surface_type=SurfaceType.CEILING,
            centroid_3d=[0.0, 2.5, 1.0],
            status=DamageStatus.ACCEPTED,
        )
        flags = self.rules.evaluate_damage(d)
        for fl in flags:
            self.assertTrue(fl.is_risk_flag_only)
            self.assertTrue(fl.requires_inspection)

    # 14. scope references source damage ID
    def test_14_scope_references_source_damage_id(self):
        d = DamageRegion3D(
            damage_id="dmg_src_99",
            damage_class=DamageClass.WATER_STAIN,
            class_confidence=0.89,
            host_surface_id="wall_05",
            host_surface_type=SurfaceType.WALL,
            centroid_3d=[1.0, 1.5, 2.0],
            metric_area=Measurement[float](
                value=1.5, unit="m2", lower_bound=1.4, upper_bound=1.6, confidence=0.9, method="test"
            ),
            status=DamageStatus.ACCEPTED,
        )
        items = self.scope.generate_scope_for_damage(d)
        for it in items:
            self.assertEqual(it.damage_id, "dmg_src_99")
            self.assertIn("dmg_src_99", it.basis)

    # 15. scope quantity uses metric extent
    def test_15_scope_quantity_uses_metric_extent(self):
        d = DamageRegion3D(
            damage_id="dmg_q01",
            damage_class=DamageClass.WATER_STAIN,
            class_confidence=0.90,
            host_surface_id="wall_01",
            host_surface_type=SurfaceType.WALL,
            centroid_3d=[1.0, 1.5, 2.0],
            metric_area=Measurement[float](
                value=3.25, unit="m2", lower_bound=3.0, upper_bound=3.5, confidence=0.9, method="test"
            ),
            status=DamageStatus.ACCEPTED,
        )
        items = self.scope.generate_scope_for_damage(d)
        remed = [it for it in items if "remed" in it.line_item_id][0]
        self.assertEqual(remed.quantity, 3.25)
        self.assertEqual(remed.unit, "m2")

    # 16. no measurement -> no invented quantity
    def test_16_no_measurement_no_invented_quantity(self):
        d = DamageRegion3D(
            damage_id="dmg_none_01",
            damage_class=DamageClass.WATER_STAIN,
            class_confidence=0.80,
            host_surface_id="wall_01",
            host_surface_type=SurfaceType.WALL,
            centroid_3d=[1.0, 1.5, 2.0],
            metric_area=None,
            status=DamageStatus.NOT_EVALUABLE,
        )
        items = self.scope.generate_scope_for_damage(d)
        remed = [it for it in items if "remed" in it.line_item_id][0]
        self.assertIsNone(remed.quantity)

    # 17. LiDAR/Video/Photo provenance preserved
    def test_17_tier_provenance_preserved(self):
        adapter = DamageInputAdapter(workspace_root=".")
        # Test detection of LiDAR tier
        tier_lidar = adapter._detect_tier("c00a170fe1")
        self.assertEqual(tier_lidar, "lidar")
        # Test detection of video tier
        tier_video = adapter._detect_tier("video_single_room")
        self.assertEqual(tier_video, "video")
        # Test detection of photo tier
        tier_photo = adapter._detect_tier("photo_room_01")
        self.assertEqual(tier_photo, "photo")

    # 18. existing outputs remain backward compatible
    def test_18_existing_outputs_backward_compatible(self):
        dr = DamageRegion(
            damage_id="dmg_legacy",
            surface_id="wall_legacy",
            damage_class=DamageClass.WATER_STAIN,
            extent_area=Measurement[float](
                value=0.5, unit="m2", lower_bound=0.45, upper_bound=0.55, confidence=0.9, method="legacy"
            ),
        )
        plan = PropertyPlanOutput(
            property_id="prop_legacy",
            capture_id="c00a170fe1",
            tier=CaptureTier.LIDAR,
            total_floor_area=Measurement[float](
                value=20.0, unit="m2", lower_bound=19.5, upper_bound=20.5, confidence=0.95, method="t"
            ),
            reconstruction_method="ARKit",
            damage_regions=[dr],
        )
        dump = plan.model_dump()
        self.assertEqual(dump["property_id"], "prop_legacy")
        self.assertEqual(len(dump["damage_regions"]), 1)
        self.assertEqual(dump["damage_regions"][0]["damage_id"], "dmg_legacy")


if __name__ == "__main__":
    unittest.main()
