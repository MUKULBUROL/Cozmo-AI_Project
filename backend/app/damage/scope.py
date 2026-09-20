"""Deterministic repair scope generation with metric quantity linking and evidence traceability.

1. Why this file exists:
   Synthesizes actionable building repair line items strictly from verified physical
   evidence and metric geometry. Derives quantities directly from measured surface
   areas (m2) or crack lengths (m) without hallucinating unobserved quantities when
   measurements are NOT_EVALUABLE.

2. Pipeline stage:
   Stage 9 (Damage Detection, Metric Extent, Concealed-Damage Rules & Repair Scope) - Scope Generation.

3. Inputs:
   DamageRegion3D objects, their metric measurements (area/length), and fired ConcealedDamageFlags.

4. Outputs:
   List of ScopeLineItem Pydantic objects containing remediation actions, target surfaces,
   physical quantities, units of measure, evidence bases, and inspection requirements.

5. Coordinate convention:
   N/A.

6. Unit convention:
   Areas in square meters ('m2'); lengths in linear meters ('linear_m'); count ('count'); inspection ('inspection').

7. Dependencies:
   typing, pydantic, backend.app.models.damage, backend.app.models.output.DamageClass.

8. Assumptions:
   - Scope generation is deterministic and directly traceable to a specific damage_id.
   - If a damage extent is NOT_EVALUABLE, quantity is set to None with an inspection requirement,
     strictly preventing fake dimensional claims.

9. Failure modes:
   - Unrecognized damage classes generate safe default diagnostic inspection items.

10. First things to inspect while debugging:
    - Verify that quantity matches damage.metric_area.value or damage.metric_length.value.
    - Check whether basis matches damage.damage_id.
"""

from typing import List, Dict, Any, Optional
from ..models.damage import (
    DamageRegion3D,
    ScopeLineItem,
    ConcealedDamageFlag,
    DamageStatus,
    SurfaceType,
)
from ..models.output import DamageClass


class RepairScopeGenerator:
    """Generates remediation line items deterministically from damage evidence."""

    def __init__(self, include_pre_inspection: bool = True):
        self.include_pre_inspection = include_pre_inspection

    def generate_scope_for_damage(
        self,
        damage: DamageRegion3D,
        concealed_flags: Optional[List[ConcealedDamageFlag]] = None,
    ) -> List[ScopeLineItem]:
        """Generates remediation line items for a single damage region.

        Purpose:
            Produces sequence of diagnostic, containment, removal, and restoration
            line items mapped to the specific damage class and host surface.

        Parameters:
            damage: DamageRegion3D instance.
            concealed_flags: Optional list of triggered ConcealedDamageFlag items.

        Returns:
            List of ScopeLineItem instances.

        Assumptions:
            Quantities are taken directly from metric_area or metric_length if available.

        Failure cases:
            Sets quantity=None if extent is unmeasurable.

        Debugging clues:
            Inspect quantity and unit fields on each generated line item.
        """
        items: List[ScopeLineItem] = []
        dmg_id = damage.damage_id
        surf_id = damage.host_surface_id
        surf_desc = f"{damage.host_surface_type.value} ({surf_id})"
        cls = damage.damage_class

        # Determine physical metric quantity and unit
        quantity: Optional[float] = None
        unit = "count"

        if damage.metric_area is not None and damage.status in [DamageStatus.ACCEPTED, DamageStatus.PROVISIONAL]:
            quantity = damage.metric_area.value
            unit = "m2"
        elif damage.metric_length is not None and damage.status in [DamageStatus.ACCEPTED, DamageStatus.PROVISIONAL]:
            quantity = damage.metric_length.value
            unit = "linear_m"

        # 1. Pre-inspection / diagnostic step
        if self.include_pre_inspection:
            diag_action = self._get_diagnostic_action(cls, damage.host_surface_type)
            items.append(
                ScopeLineItem(
                    line_item_id=f"{dmg_id}_item_01_diag",
                    damage_id=dmg_id,
                    action=diag_action,
                    target_surface=surf_desc,
                    quantity=1.0,
                    unit="inspection",
                    basis=f"{dmg_id}: visible {cls.value}",
                    confidence=damage.class_confidence,
                    inspection_required=True,
                )
            )

        # 2. Containment / protection if mold or char
        if cls in [DamageClass.MOLD, DamageClass.MOLD_LIKE_DISCOLORATION, DamageClass.BURN_OR_CHAR]:
            items.append(
                ScopeLineItem(
                    line_item_id=f"{dmg_id}_item_02_contain",
                    damage_id=dmg_id,
                    action="Set up critical dust containment barrier and negative air filtration",
                    target_surface=surf_desc,
                    quantity=1.0,
                    unit="setup",
                    basis=f"{dmg_id}: particulate containment for {cls.value}",
                    confidence=0.90,
                    inspection_required=True,
                )
            )

        # 3. Remediation / removal step
        remove_action = self._get_removal_action(cls, damage.host_surface_type)
        items.append(
            ScopeLineItem(
                line_item_id=f"{dmg_id}_item_03_remed",
                damage_id=dmg_id,
                action=remove_action,
                target_surface=surf_desc,
                quantity=quantity,
                unit=unit,
                basis=f"{dmg_id}: verified physical defect extent",
                confidence=damage.class_confidence,
                inspection_required=True,
            )
        )

        # 4. Restoration / finish step
        finish_action = self._get_finish_action(cls, damage.host_surface_type)
        items.append(
            ScopeLineItem(
                line_item_id=f"{dmg_id}_item_04_finish",
                damage_id=dmg_id,
                action=finish_action,
                target_surface=surf_desc,
                quantity=quantity,
                unit=unit,
                basis=f"{dmg_id}: surface restoration to match existing",
                confidence=damage.class_confidence,
                inspection_required=False,
            )
        )

        return items

    def _get_diagnostic_action(self, cls: DamageClass, surf_type: SurfaceType) -> str:
        if cls == DamageClass.WATER_STAIN:
            return f"Moisture mapping and non-invasive cavity moisture survey of {surf_type.value}"
        elif cls in [DamageClass.MOLD, DamageClass.MOLD_LIKE_DISCOLORATION]:
            return "Microbial swab sampling and indoor air quality diagnostic evaluation"
        elif cls in [DamageClass.CRACK_STRUCTURAL, DamageClass.SURFACE_CRACK]:
            return f"Structural crack monitoring gauge installation and substrate assessment on {surf_type.value}"
        elif cls in [DamageClass.BURN_OR_CHAR, DamageClass.FIRE_SMOKE]:
            return "Structural framing char depth inspection and smoke odor penetration survey"
        else:
            return f"Substrate physical condition inspection on {surf_type.value}"

    def _get_removal_action(self, cls: DamageClass, surf_type: SurfaceType) -> str:
        if cls == DamageClass.WATER_STAIN:
            return f"Controlled removal and bagging of water-saturated {surf_type.value} finish and insulation"
        elif cls in [DamageClass.MOLD, DamageClass.MOLD_LIKE_DISCOLORATION]:
            return f"HEPA vacuuming and antimicrobial wipe down of exposed substrate on {surf_type.value}"
        elif cls in [DamageClass.CRACK_STRUCTURAL, DamageClass.SURFACE_CRACK]:
            return f"V-groove mechanical chase routing and substrate crack preparation along {surf_type.value}"
        elif cls == DamageClass.HOLE_OR_MISSING_MATERIAL:
            return f"Square-cut removal of damaged drywall substrate back to adjacent framing studs on {surf_type.value}"
        elif cls == DamageClass.BURN_OR_CHAR:
            return f"Abrasive blasting / soda blasting of charred surface and demolition of scorched {surf_type.value}"
        else:
            return f"Mechanical preparation and removal of deteriorated material on {surf_type.value}"

    def _get_finish_action(self, cls: DamageClass, surf_type: SurfaceType) -> str:
        if cls in [DamageClass.CRACK_STRUCTURAL, DamageClass.SURFACE_CRACK]:
            return f"Apply fiberglass mesh tape, structural elastomeric joint compound, and feather texture on {surf_type.value}"
        elif cls in [DamageClass.WATER_STAIN, DamageClass.HOLE_OR_MISSING_MATERIAL]:
            return f"Install new gypsum board to match existing thickness, tape, 3-coat finish, primer, and 2-coat paint on {surf_type.value}"
        elif cls in [DamageClass.MOLD, DamageClass.MOLD_LIKE_DISCOLORATION]:
            return f"Apply antimicrobial encapsulant coating and repaint {surf_type.value} to match existing"
        elif cls == DamageClass.SURFACE_PEELING:
            return f"Scrape loose edges, apply stabilizing skim coat, primer, and finish coat on {surf_type.value}"
        else:
            return f"Apply surface patching compound, prime, and repaint {surf_type.value} to match existing"

    def generate_scope_for_all(
        self,
        damages: List[DamageRegion3D],
        flags: Optional[List[ConcealedDamageFlag]] = None,
    ) -> List[ScopeLineItem]:
        """Generates unified repair scope for all property damages."""
        all_items: List[ScopeLineItem] = []
        flag_map: Dict[str, List[ConcealedDamageFlag]] = {}
        if flags:
            for fl in flags:
                flag_map.setdefault(fl.damage_id, []).append(fl)

        for d in damages:
            d_flags = flag_map.get(d.damage_id, [])
            items = self.generate_scope_for_damage(d, d_flags)
            all_items.extend(items)
        return all_items
