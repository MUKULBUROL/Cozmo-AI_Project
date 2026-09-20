"""Unit tests for Stage 9 concealed-damage deterministic rule engine.

1. Why this file exists:
   Verifies that concealed property damage rules trigger strictly based on observable
   evidence, emit risk flags rather than claimed observations, enforce mandatory
   inspection requirements, and adhere to deterministic logic without LLM hallucinations.

2. Pipeline stage:
   Stage 9 (Damage Detection, Metric Extent, Concealed-Damage Rules & Repair Scope) - Testing.

3. Inputs:
   Synthetic DamageRegion3D objects with varied classes, host surfaces, and extents.

4. Outputs:
   Pytest assertion results validating rule firing, flag metadata, and safety constraints.

5. Coordinate convention:
   N/A.

6. Unit convention:
   Areas in m2; lengths in m.

7. Dependencies:
   unittest, backend.app.damage.rules, backend.app.models.damage, backend.app.models.output.

8. Assumptions:
   - Rules are 100% deterministic and reproducible.

9. Failure modes:
   - Rule asserting factual unseen reality instead of a risk notification.

10. First things to inspect while debugging:
    - Check rule trigger class and surface type lists in ConcealedDamageRuleEngine.
"""

import unittest

from backend.app.models.output import DamageClass, Measurement
from backend.app.models.damage import (
    DamageRegion3D,
    DamageStatus,
    SurfaceType,
)
from backend.app.damage.rules import ConcealedDamageRuleEngine


class TestConcealedRules(unittest.TestCase):
    """Verifies deterministic execution of concealed damage rules."""

    def setUp(self):
        self.engine = ConcealedDamageRuleEngine()

    def test_water_stain_on_wall_triggers_cavity_moisture_flag(self):
        damage = DamageRegion3D(
            damage_id="dmg_water_01",
            damage_class=DamageClass.WATER_STAIN,
            class_confidence=0.88,
            host_surface_id="wall_01",
            host_surface_type=SurfaceType.WALL,
            centroid_3d=[1.0, 1.5, 2.0],
            metric_area=Measurement[float](
                value=0.75, unit="m2", lower_bound=0.68, upper_bound=0.82, confidence=0.9, method="test"
            ),
            status=DamageStatus.ACCEPTED,
        )

        flags = self.engine.evaluate_damage(damage)
        self.assertGreaterEqual(len(flags), 1)

        flag = flags[0]
        self.assertEqual(flag.damage_id, "dmg_water_01")
        self.assertEqual(flag.rule_id, "RULE_WATER_STAIN_WALL_CAVITY")
        # Safety contract: strictly a risk flag, not a factual diagnosis
        self.assertTrue(flag.is_risk_flag_only)
        self.assertTrue(flag.requires_inspection)
        self.assertIn("moisture", flag.suspected_issue.lower())
        self.assertIn("moisture meter", flag.inspection_recommendation.lower())

    def test_water_stain_on_ceiling_triggers_plenum_leak_flag(self):
        damage = DamageRegion3D(
            damage_id="dmg_ceil_01",
            damage_class=DamageClass.WATER_STAIN,
            class_confidence=0.91,
            host_surface_id="ceiling_01",
            host_surface_type=SurfaceType.CEILING,
            centroid_3d=[0.0, 2.6, 1.0],
            metric_area=Measurement[float](
                value=1.20, unit="m2", lower_bound=1.10, upper_bound=1.30, confidence=0.9, method="test"
            ),
            status=DamageStatus.ACCEPTED,
        )

        flags = self.engine.evaluate_damage(damage)
        self.assertTrue(any(f.rule_id == "RULE_WATER_STAIN_CEILING_PLENUM" for f in flags))
        matching = [f for f in flags if f.rule_id == "RULE_WATER_STAIN_CEILING_PLENUM"][0]
        self.assertIn("overhead leak", matching.suspected_issue.lower())

    def test_mold_discoloration_triggers_hygienist_sampling_flag(self):
        damage = DamageRegion3D(
            damage_id="dmg_mold_01",
            damage_class=DamageClass.MOLD_LIKE_DISCOLORATION,
            class_confidence=0.84,
            host_surface_id="wall_03",
            host_surface_type=SurfaceType.WALL,
            centroid_3d=[0.5, 0.4, 3.0],
            metric_area=Measurement[float](
                value=0.30, unit="m2", lower_bound=0.25, upper_bound=0.35, confidence=0.9, method="test"
            ),
            status=DamageStatus.ACCEPTED,
        )

        flags = self.engine.evaluate_damage(damage)
        self.assertTrue(any("MOLD" in f.rule_id for f in flags))
        matching = [f for f in flags if "MOLD" in f.rule_id][0]
        self.assertTrue(matching.is_risk_flag_only)
        self.assertIn("sampling", matching.inspection_recommendation.lower())

    def test_structural_crack_triggers_structural_engineer_flag(self):
        damage = DamageRegion3D(
            damage_id="dmg_crack_01",
            damage_class=DamageClass.CRACK_STRUCTURAL,
            class_confidence=0.89,
            host_surface_id="wall_02",
            host_surface_type=SurfaceType.WALL,
            centroid_3d=[2.0, 1.2, 0.0],
            metric_length=Measurement[float](
                value=1.40, unit="m", lower_bound=1.25, upper_bound=1.55, confidence=0.9, method="test"
            ),
            status=DamageStatus.ACCEPTED,
        )

        flags = self.engine.evaluate_damage(damage)
        self.assertTrue(any("STRUCTURAL" in f.rule_id for f in flags))
        matching = [f for f in flags if "STRUCTURAL" in f.rule_id][0]
        self.assertIn("structural engineer", matching.inspection_recommendation.lower())


if __name__ == "__main__":
    unittest.main()
