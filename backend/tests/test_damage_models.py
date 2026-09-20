"""Unit tests for Stage 9 damage data models, adapters, and quality gate.

1. Why this file exists:
   Verifies Pydantic model validity, serialization contracts, quality gating,
   and cross-tier RGB frame ingestion for Stage 9 damage inspection.

2. Pipeline stage:
   Stage 9 (Damage Detection, Metric Extent, Concealed-Damage Rules & Repair Scope) - Testing.

3. Inputs:
   Synthetic model instances, test image buffers, and keyframe paths.

4. Outputs:
   Pytest assertion results verifying data integrity and serialization.

5. Coordinate convention:
   N/A (model assertions).

6. Unit convention:
   Lengths: meters (m), Areas: square meters (m2), scores: [0, 1].

7. Dependencies:
   unittest, numpy, backend.app.models.damage, backend.app.damage.quality, backend.app.damage.adapter.

8. Assumptions:
   - Tests execute deterministically without downloading external model weights.

9. Failure modes:
   - Schema validation errors on invalid field types or inverted bounds.

10. First things to inspect while debugging:
    - Check Pydantic validation tracebacks for missing mandatory fields.
"""

import unittest
import numpy as np
from pathlib import Path

from backend.app.models.damage import (
    DamageStatus,
    DamageQualityStatus,
    DamageQualityGate,
    DamageFrame,
    DamageObservation2D,
    ConcealedDamageFlag,
    ScopeLineItem,
    DamageRegion3D,
    SurfaceType,
)
from backend.app.models.output import (
    Measurement,
    DamageClass,
    DamageRegion,
    PropertyPlanOutput,
)
from backend.app.models.capture import CaptureTier
from backend.app.models.floorplan import Point2D
from backend.app.damage.quality import DamageImageQualityGate
from backend.app.damage.adapter import DamageInputAdapter
from backend.app.damage.detector import DEFAULT_DAMAGE_TAXONOMY


class TestDamageModels(unittest.TestCase):
    """Verifies schemas and operational logic of Stage 9 damage models."""

    def test_damage_observation_2d_serialization(self):
        obs = DamageObservation2D(
            observation_id="obs_01",
            image_id="frame_000000.jpg",
            capture_id="c00a170fe1",
            tier="lidar",
            class_name="water stain",
            canonical_class=DamageClass.WATER_STAIN,
            class_confidence=0.88,
            bbox=[100.0, 150.0, 400.0, 500.0],
            mask_area_pixels=45200,
            segmentation_confidence=0.92,
            boundary_polygon=[[100.0, 150.0], [400.0, 150.0], [400.0, 500.0], [100.0, 500.0]],
            is_clipped_by_border=False,
            view_angle_deg=18.5,
        )
        data = obs.model_dump()
        self.assertEqual(data["observation_id"], "obs_01")
        self.assertEqual(data["canonical_class"], "water_stain")
        self.assertEqual(data["mask_area_pixels"], 45200)
        self.assertFalse(data["is_clipped_by_border"])

    def test_damage_region_3d_serialization(self):
        reg = DamageRegion3D(
            damage_id="damage_01",
            damage_class=DamageClass.WATER_STAIN,
            class_confidence=0.89,
            host_surface_id="wall_002",
            host_surface_type=SurfaceType.WALL,
            host_room_id="room_01",
            centroid_3d=[1.25, 1.40, -2.10],
            polygon_on_surface=[Point2D(x=0.2, y=0.5), Point2D(x=0.8, y=0.5), Point2D(x=0.5, y=1.2)],
            metric_area=Measurement[float](
                value=0.45,
                unit="m2",
                lower_bound=0.41,
                upper_bound=0.49,
                confidence=0.90,
                method="plane_raster_integration",
            ),
            status=DamageStatus.ACCEPTED,
            supporting_observations=["obs_01", "obs_04"],
            supporting_images=["frame_000000.jpg", "frame_000056.jpg"],
            measurement_spread_m2=0.03,
            best_image_id="frame_000000.jpg",
        )
        dump = reg.model_dump()
        self.assertEqual(dump["damage_id"], "damage_01")
        self.assertEqual(dump["status"], "ACCEPTED")
        self.assertEqual(dump["metric_area"]["value"], 0.45)
        self.assertEqual(len(dump["supporting_images"]), 2)

    def test_concealed_flag_and_scope_models(self):
        flag = ConcealedDamageFlag(
            rule_id="RULE_WATER_STAIN_CAVITY",
            damage_id="damage_01",
            suspected_issue="possible concealed moisture behind finish",
            evidence="visible water stain of 0.45 m2 on drywall wall",
            confidence=0.85,
            requires_inspection=True,
            inspection_recommendation="Perform invasive or pinless moisture meter probing",
            is_risk_flag_only=True,
        )
        self.assertTrue(flag.requires_inspection)
        self.assertTrue(flag.is_risk_flag_only)

        scope = ScopeLineItem(
            line_item_id="scope_01",
            damage_id="damage_01",
            action="Remove affected drywall finish and inspect framing cavity",
            target_surface="wall_002",
            quantity=0.45,
            unit="m2",
            basis="damage_01",
            confidence=0.85,
            inspection_required=True,
        )
        self.assertEqual(scope.quantity, 0.45)
        self.assertEqual(scope.unit, "m2")

    def test_quality_gate_evaluations(self):
        gate = DamageImageQualityGate(
            min_width=100,
            min_height=100,
            min_sharpness_usable=50.0,
            min_sharpness_provisional=20.0,
            min_brightness=30.0,
            max_brightness=230.0,
        )

        # 1. Sharp high-contrast image -> USABLE
        sharp_img = np.zeros((200, 200, 3), dtype=np.uint8)
        sharp_img[:, :100] = 50
        sharp_img[:, 100:] = 200
        q_sharp = gate.assess_image(sharp_img, image_id="sharp_test")
        self.assertEqual(q_sharp.status, DamageQualityStatus.USABLE)

        # 2. Extreme darkness -> REJECTED
        dark_img = np.full((200, 200, 3), 10, dtype=np.uint8)
        q_dark = gate.assess_image(dark_img, image_id="dark_test")
        self.assertEqual(q_dark.status, DamageQualityStatus.REJECTED)
        self.assertTrue(any("extreme_darkness" in r for r in q_dark.rejection_reasons))

        # 3. Blurry low-texture image -> REJECTED or PROVISIONAL
        flat_img = np.full((200, 200, 3), 128, dtype=np.uint8)
        q_flat = gate.assess_image(flat_img, image_id="flat_test")
        self.assertIn(q_flat.status, [DamageQualityStatus.PROVISIONAL, DamageQualityStatus.REJECTED])

        # 4. Tiny image -> REJECTED
        tiny_img = np.zeros((50, 50, 3), dtype=np.uint8)
        q_tiny = gate.assess_image(tiny_img, image_id="tiny_test")
        self.assertEqual(q_tiny.status, DamageQualityStatus.REJECTED)

    def test_damage_adapter_lidar_discovery(self):
        adapter = DamageInputAdapter(workspace_root=".")
        frames = adapter.load_frames(capture_id="c00a170fe1", tier="lidar", max_frames=5)
        self.assertGreater(len(frames), 0)
        first = frames[0]
        self.assertEqual(first.tier, "lidar")
        self.assertTrue(Path(first.image_path).exists() or Path("outputs/c00a170fe1").exists())

    def test_backward_compatibility_property_plan_output(self):
        wall_damage = DamageRegion(
            damage_id="dmg_legacy_01",
            surface_id="wall_01",
            damage_class=DamageClass.WATER_STAIN,
            extent_area=Measurement[float](
                value=1.2,
                unit="m2",
                lower_bound=1.1,
                upper_bound=1.3,
                confidence=0.90,
                method="lidar_projection",
            ),
        )
        self.assertEqual(wall_damage.damage_id, "dmg_legacy_01")
        self.assertEqual(wall_damage.status, "ACCEPTED")

        plan = PropertyPlanOutput(
            property_id="prop_01",
            capture_id="c00a170fe1",
            tier=CaptureTier.LIDAR,
            total_floor_area=Measurement[float](
                value=24.0,
                unit="m2",
                lower_bound=23.5,
                upper_bound=24.5,
                confidence=0.95,
                method="room_sum",
            ),
            reconstruction_method="ARKit_LiDAR",
            damage_regions=[wall_damage],
        )
        plan_json = plan.model_dump_json()
        self.assertIn("dmg_legacy_01", plan_json)
        self.assertIn("damage_regions", plan_json)


if __name__ == "__main__":
    unittest.main()
