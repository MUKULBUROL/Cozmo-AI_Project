"""Unit tests for Stage 9 repair scope generation and geometric quantity derivation.

1. Why this file exists:
   Verifies that remediation scope line items derive quantities directly from measured
   geometry, maintain 100% evidence linkage back to damage_id, and strictly refrain
   from hallucinating quantities when measurements are NOT_EVALUABLE.

2. Pipeline stage:
   Stage 9 (Damage Detection, Metric Extent, Concealed-Damage Rules & Repair Scope) - Testing.

3. Inputs:
   Synthetic DamageRegion3D instances with measured, provisional, and NOT_EVALUABLE states.

4. Outputs:
   Pytest assertion results confirming quantity correctness, unit matching, and evidence traceability.

5. Coordinate convention:
   N/A.

6. Unit convention:
   Quantities in m2 or linear m; units match geometry.

7. Dependencies:
   unittest, backend.app.damage.scope, backend.app.models.damage, backend.app.models.output.

8. Assumptions:
   - Quantities are strictly deterministic.

9. Failure modes:
   - Fabricating quantities for unmeasured defects.

10. First things to inspect while debugging:
    - Check quantity and unit fields on generated ScopeLineItem records.
"""

import unittest

from backend.app.models.output import DamageClass, Measurement
from backend.app.models.damage import (
    DamageRegion3D,
    DamageStatus,
    SurfaceType,
)
from backend.app.damage.scope import RepairScopeGenerator


class TestScopeGeneration(unittest.TestCase):
    """Verifies deterministic generation of repair scope line items."""

    def setUp(self):
        self.generator = RepairScopeGenerator()

    def test_scope_quantity_derives_from_metric_area(self):
        damage = DamageRegion3D(
            damage_id="dmg_drywall_01",
            damage_class=DamageClass.WATER_STAIN,
            class_confidence=0.88,
            host_surface_id="wall_01",
            host_surface_type=SurfaceType.WALL,
            centroid_3d=[1.0, 1.5, 2.0],
            metric_area=Measurement[float](
                value=2.45, unit="m2", lower_bound=2.30, upper_bound=2.60, confidence=0.9, method="test"
            ),
            status=DamageStatus.ACCEPTED,
        )

        items = self.generator.generate_scope_for_damage(damage)
        self.assertGreater(len(items), 0)

        # Check evidence traceability
        for it in items:
            self.assertEqual(it.damage_id, "dmg_drywall_01")
            self.assertIn("dmg_drywall_01", it.basis)

        # Find removal and finish items
        remed_item = [it for it in items if "remed" in it.line_item_id][0]
        finish_item = [it for it in items if "finish" in it.line_item_id][0]

        self.assertEqual(remed_item.quantity, 2.45)
        self.assertEqual(remed_item.unit, "m2")
        self.assertEqual(finish_item.quantity, 2.45)
        self.assertEqual(finish_item.unit, "m2")

    def test_scope_quantity_derives_from_linear_crack_length(self):
        damage = DamageRegion3D(
            damage_id="dmg_crack_02",
            damage_class=DamageClass.SURFACE_CRACK,
            class_confidence=0.85,
            host_surface_id="wall_02",
            host_surface_type=SurfaceType.WALL,
            centroid_3d=[0.5, 1.2, 1.0],
            metric_length=Measurement[float](
                value=1.85, unit="m", lower_bound=1.70, upper_bound=2.00, confidence=0.9, method="test"
            ),
            status=DamageStatus.ACCEPTED,
        )

        items = self.generator.generate_scope_for_damage(damage)
        remed_item = [it for it in items if "remed" in it.line_item_id][0]

        self.assertEqual(remed_item.quantity, 1.85)
        self.assertEqual(remed_item.unit, "linear_m")

    def test_unmeasurable_extent_does_not_invent_quantity(self):
        # Damage where measurement failed / is NOT_EVALUABLE
        damage = DamageRegion3D(
            damage_id="dmg_unmeasurable_01",
            damage_class=DamageClass.WATER_STAIN,
            class_confidence=0.75,
            host_surface_id="wall_03",
            host_surface_type=SurfaceType.WALL,
            centroid_3d=[1.0, 1.0, 1.0],
            metric_area=None,
            status=DamageStatus.NOT_EVALUABLE,
        )

        items = self.generator.generate_scope_for_damage(damage)
        remed_item = [it for it in items if "remed" in it.line_item_id][0]

        # Crucial safety rule: no invented quantity!
        self.assertIsNone(remed_item.quantity)
        self.assertTrue(remed_item.inspection_required)


if __name__ == "__main__":
    unittest.main()
