"""Deterministic rule engine for concealed property damage risk flags.

1. Why this file exists:
   Evaluates visible surface damages against deterministic domain rules to emit
   standardized ConcealedDamageFlag alerts. Ordinary RGB and LiDAR sensors cannot
   penetrate physical building assemblies; therefore, this module strictly generates
   actionable inspection risk flags rather than empirical diagnoses of unseen conditions.

2. Pipeline stage:
   Stage 9 (Damage Detection, Metric Extent, Concealed-Damage Rules & Repair Scope) - Concealed Damage Rules.

3. Inputs:
   DamageRegion3D objects or individual damage observation parameters (class, host surface, extent).

4. Outputs:
   List of ConcealedDamageFlag Pydantic models containing suspected issues, observable evidence,
   rule IDs, and mandatory physical inspection protocols.

5. Coordinate convention:
   N/A (rule evaluations operate on semantic and metric properties).

6. Unit convention:
   Area extents in m2; linear lengths in m; confidence scores in [0.0, 1.0].

7. Dependencies:
   typing, pydantic, backend.app.models.damage, backend.app.models.output.DamageClass.

8. Assumptions:
   - Rules are 100% deterministic, auditable, and configurable.
   - Concealed damage outputs are risk warnings requiring qualified professional inspection.
   - An LLM prompt is never used to fabricate unobserved physical defects.

9. Failure modes:
   - Unrecognized damage classes or missing surface types default safely without raising exceptions.

10. First things to inspect while debugging:
    - Inspect rules trigger table in ConcealedDamageRuleEngine.
    - Check whether requires_inspection and is_risk_flag_only remain strictly True.
"""

from typing import List, Dict, Any, Optional
from ..models.damage import (
    DamageRegion3D,
    ConcealedDamageFlag,
    SurfaceType,
)
from ..models.output import DamageClass


class ConcealedDamageRule:
    """Represents an individual deterministic building forensic rule."""

    def __init__(
        self,
        rule_id: str,
        name: str,
        trigger_classes: List[DamageClass],
        surface_types: List[SurfaceType],
        min_extent: float = 0.0,
        suspected_issue: str = "",
        recommendation: str = "",
        rule_confidence: float = 0.85,
    ):
        self.rule_id = rule_id
        self.name = name
        self.trigger_classes = trigger_classes
        self.surface_types = surface_types
        self.min_extent = min_extent
        self.suspected_issue = suspected_issue
        self.recommendation = recommendation
        self.rule_confidence = rule_confidence

    def evaluate(self, damage: DamageRegion3D) -> Optional[ConcealedDamageFlag]:
        """Evaluates whether the damage region triggers this rule."""
        if damage.damage_class not in self.trigger_classes:
            return None

        if self.surface_types and damage.host_surface_type not in self.surface_types:
            return None

        # Check extent threshold if applicable
        extent_val = 0.0
        if damage.metric_area is not None:
            extent_val = damage.metric_area.value
        elif damage.metric_length is not None:
            extent_val = damage.metric_length.value

        if extent_val < self.min_extent:
            return None

        evidence_str = (
            f"Observed {damage.damage_class.value} on {damage.host_surface_type.value} "
            f"({damage.host_surface_id})"
        )
        if damage.metric_area:
            evidence_str += f" spanning {damage.metric_area.value:.2f} m²"
        elif damage.metric_length:
            evidence_str += f" spanning {damage.metric_length.value:.2f} m"

        return ConcealedDamageFlag(
            rule_id=self.rule_id,
            damage_id=damage.damage_id,
            suspected_issue=self.suspected_issue,
            evidence=evidence_str,
            confidence=self.rule_confidence,
            requires_inspection=True,
            inspection_recommendation=self.recommendation,
            is_risk_flag_only=True,
        )


class ConcealedDamageRuleEngine:
    """Configurable rule engine executing deterministic forensic risk assessments."""

    def __init__(self, rules: Optional[List[ConcealedDamageRule]] = None):
        """Initializes the rule engine with default building envelope and finish rules."""
        self.rules = rules or self._get_default_rules()

    def _get_default_rules(self) -> List[ConcealedDamageRule]:
        """Defines standardized property forensic risk rules."""
        return [
            # 1. Water stain on wall -> cavity moisture
            ConcealedDamageRule(
                rule_id="RULE_WATER_STAIN_WALL_CAVITY",
                name="Water Stain on Wall Cavity",
                trigger_classes=[DamageClass.WATER_STAIN],
                surface_types=[SurfaceType.WALL],
                min_extent=0.01,
                suspected_issue="Possible concealed moisture accumulation behind wall finish and insulation dampness",
                recommendation="Perform pinless and pin-probe moisture metering of wall cavity and inspect plumbing supply/drain runs",
                rule_confidence=0.88,
            ),
            # 2. Water stain on ceiling -> overhead leak / plenum moisture
            ConcealedDamageRule(
                rule_id="RULE_WATER_STAIN_CEILING_PLENUM",
                name="Water Stain on Ceiling Plenum",
                trigger_classes=[DamageClass.WATER_STAIN],
                surface_types=[SurfaceType.CEILING],
                min_extent=0.01,
                suspected_issue="Possible active or prior overhead leak from roof assembly, HVAC pan, or upper floor plumbing",
                recommendation="Access ceiling plenum or attic space directly above staining to trace origin and check joist deflection",
                rule_confidence=0.92,
            ),
            # 3. Mold-like discoloration -> microbial growth requiring testing
            ConcealedDamageRule(
                rule_id="RULE_MOLD_DISCOLORATION_SAMPLING",
                name="Suspected Microbial Discoloration",
                trigger_classes=[
                    DamageClass.MOLD_LIKE_DISCOLORATION,
                    DamageClass.MOLD,
                ],
                surface_types=[SurfaceType.WALL, SurfaceType.CEILING, SurfaceType.FLOOR],
                min_extent=0.005,
                suspected_issue="Suspected surface microbial colony potentially indicating elevated indoor relative humidity or hidden moisture reservoir",
                recommendation="Commission certified industrial hygienist (CIH) or mold assessor for tape-lift/air sampling; do not disturb dry surface",
                rule_confidence=0.85,
            ),
            # 4. Structural crack on wall -> foundation movement or shear stress
            ConcealedDamageRule(
                rule_id="RULE_CRACK_STRUCTURAL_SHEAR",
                name="Structural Shear Crack Risk",
                trigger_classes=[DamageClass.CRACK_STRUCTURAL],
                surface_types=[SurfaceType.WALL],
                min_extent=0.25,
                suspected_issue="Potential structural settlement, foundation movement, or lateral load-bearing shear compromise",
                recommendation="Retain licensed structural engineer to evaluate foundation integrity, framing load paths, and plumbness",
                rule_confidence=0.90,
            ),
            # 5. Burn / char damage -> framing integrity compromise
            ConcealedDamageRule(
                rule_id="RULE_BURN_CHAR_FRAMING",
                name="Charred Structural Member Risk",
                trigger_classes=[DamageClass.BURN_OR_CHAR, DamageClass.FIRE_SMOKE],
                surface_types=[SurfaceType.WALL, SurfaceType.CEILING],
                min_extent=0.05,
                suspected_issue="Possible loss of structural wood member section or compromised electrical wiring inside wall cavity",
                recommendation="Expose stud cavity to inspect framing char depth and retain licensed electrical contractor to test wiring continuity",
                rule_confidence=0.95,
            ),
            # 6. Hole or missing material -> cavity exposure
            ConcealedDamageRule(
                rule_id="RULE_HOLE_CAVITY_EXPOSURE",
                name="Breached Envelope / Cavity Exposure",
                trigger_classes=[DamageClass.HOLE_OR_MISSING_MATERIAL],
                surface_types=[SurfaceType.WALL, SurfaceType.CEILING],
                min_extent=0.02,
                suspected_issue="Breached interior envelope potentially compromising air barrier, acoustic rating, or fire separation",
                recommendation="Inspect internal cavity for insulation displacement, draft penetrations, and pest intrusion before closure",
                rule_confidence=0.82,
            ),
        ]

    def evaluate_damage(self, damage: DamageRegion3D) -> List[ConcealedDamageFlag]:
        """Evaluates all rules against a single 3D damage region.

        Purpose:
            Produces all applicable ConcealedDamageFlag instances for the damage.

        Parameters:
            damage: DamageRegion3D object.

        Returns:
            List of fired ConcealedDamageFlag records.
        """
        flags: List[ConcealedDamageFlag] = []
        for rule in self.rules:
            flag = rule.evaluate(damage)
            if flag is not None:
                flags.append(flag)
        return flags

    def evaluate_damages(self, damages: List[DamageRegion3D]) -> List[ConcealedDamageFlag]:
        """Evaluates rules across all property damage regions."""
        all_flags: List[ConcealedDamageFlag] = []
        for d in damages:
            all_flags.extend(self.evaluate_damage(d))
        return all_flags
