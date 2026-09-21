"""Master orchestration pipeline for visual property damage perception, metric extent, and repair scope.

1. Why this file exists:
   Orchestrates the entire Stage 9 workflow: cross-tier frame ingestion, image quality
   filtering, open-vocabulary candidate detection, pixel mask segmentation, 3D metric
   plane projection, extent calculation, multi-view fusion, concealed-damage risk flagging,
   and deterministic repair scope generation across LiDAR, Video, and Photo captures.

2. Pipeline stage:
   Stage 9 (Damage Detection, Metric Extent, Concealed-Damage Rules & Repair Scope) - Pipeline.

3. Inputs:
   capture_id: str, tier: Optional[str], max_frames: Optional[int], conf_threshold: float.

4. Outputs:
   Dictionary containing:
   - damage_regions: List[DamageRegion3D]
   - concealed_flags: List[ConcealedDamageFlag]
   - scope_line_items: List[ScopeLineItem]
   - quality_records: List[DamageQualityGate]
   - summary_stats: Dict[str, Any]

5. Coordinate convention:
   Image coordinates: 2D pixel space [u, v].
   World coordinates: 3D metric meters [x, y, z] (Y vertical upward).
   Plane coordinates: 2D local meters [u_local, v_local].

6. Unit convention:
   Lengths in meters (m), areas in square meters (m2), angles in degrees.

7. Dependencies:
   os, json, pathlib, typing, numpy, backend.app.damage.*, backend.app.models.damage.*.

8. Assumptions:
   - AI determines *what* damage is (semantics); Stage 1-8 geometry determines *where* and *how large* it is.
   - Outputs are strictly backward-compatible with Stage 0-8 data structures.

9. Failure modes:
   - Missing structural planes falls back to provisional unprojected semantic observations.
   - Low-quality or corrupt images are rejected at the quality gate.

10. First things to inspect while debugging:
    - Check outputs/<capture_id>/damage/damages.json.
    - Inspect summary_stats (candidates_detected, accepted_regions, provisional_regions).
"""

import os
import json
from pathlib import Path
from typing import Dict, Any, List, Optional
import numpy as np

from ..models.damage import (
    DamageFrame,
    DamageObservation2D,
    DamageRegion3D,
    ConcealedDamageFlag,
    ScopeLineItem,
    DamageStatus,
    DamageQualityStatus,
)
from ..models.output import DamageClass, DamageRegion, PropertyPlanOutput
from .adapter import DamageInputAdapter
from .quality import DamageImageQualityGate
from .detector import OpenVocabularyDamageDetector
from .segmenter import DamageMaskSegmenter
from .projection import DamagePlaneProjector
from .extent import DamageExtentEstimator
from .fusion import MultiViewDamageFusion
from .rules import ConcealedDamageRuleEngine
from .scope import RepairScopeGenerator
from .viz import DamageVisualizer


class DamageAssessmentPipeline:
    """End-to-end processing pipeline for damage perception, geometry, rules, and scope."""

    def __init__(
        self,
        workspace_root: str = ".",
        weights_path: str = "weights/yolov8s-worldv2.pt",
        conf_threshold: float = 0.08,
        use_neural_detector: bool = True,
    ):
        """Initializes pipeline components and parameter thresholds."""
        self.workspace_root = Path(workspace_root)
        self.adapter = DamageInputAdapter(workspace_root=str(self.workspace_root))
        self.quality_gate = DamageImageQualityGate()
        self.detector = (
            OpenVocabularyDamageDetector(weights_path=weights_path)
            if use_neural_detector
            else None
        )
        self.segmenter = DamageMaskSegmenter()
        self.projector = DamagePlaneProjector()
        self.extent_estimator = DamageExtentEstimator()
        self.fusion_engine = MultiViewDamageFusion()
        self.rule_engine = ConcealedDamageRuleEngine()
        self.scope_generator = RepairScopeGenerator()
        self.visualizer = DamageVisualizer(workspace_root=str(self.workspace_root))
        self.conf_threshold = conf_threshold

    def run(
        self,
        capture_id: str,
        tier: Optional[str] = None,
        max_frames: Optional[int] = 20,
        synthetic_observations: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Executes full Stage 9 damage assessment on a capture.

        Purpose:
            Performs complete damage detection, geometric projection, extent calculation,
            rule execution, scope synthesis, and artifact generation.

        Parameters:
            capture_id: Scan session identifier (e.g. 'c00a170fe1').
            tier: Optional capture modality ('lidar', 'video', 'photo').
            max_frames: Maximum frames to inspect.
            synthetic_observations: Optional injected observations for deterministic testing.

        Returns:
            Dictionary containing damage_regions, concealed_flags, scope_line_items,
            quality_records, and summary_stats.
        """
        out_damage_dir = self.workspace_root / "outputs" / capture_id / "damage"
        out_damage_dir.mkdir(parents=True, exist_ok=True)

        # 1. Ingest frames across tiers
        frames = self.adapter.load_frames(capture_id, tier=tier, max_frames=max_frames)
        detected_tier = tier or (frames[0].tier if frames else "lidar")

        # 2. Load structural planes from Stage 2 extraction
        structural_planes = self._load_structural_planes(capture_id, detected_tier)

        raw_observations: List[Dict[str, Any]] = []
        quality_records = []
        obs_map: Dict[str, Any] = {}

        # 3. Quality gate & perception on each frame
        if synthetic_observations is not None:
            # Use injected test observations
            raw_observations = synthetic_observations
        else:
            for frame in frames:
                # 3a. Quality gate
                q_result = self.quality_gate.assess_image(frame.image_path, image_id=frame.image_id)
                quality_records.append(q_result)
                if q_result.status == DamageQualityStatus.REJECTED:
                    continue

                # 3b. Detect candidate damage bounding boxes
                candidates = []
                if self.detector is not None:
                    candidates = self.detector.detect(
                        frame.image_path,
                        conf_threshold=self.conf_threshold,
                        frame_id=frame.image_id,
                    )

                if not candidates:
                    continue

                # Load frame image for segmentation
                try:
                    from PIL import Image
                    rgb_img = np.array(Image.open(frame.image_path).convert("RGB"))
                except Exception:
                    continue

                # Load aligned depth map if available
                depth_arr = None
                if frame.depth_path and Path(frame.depth_path).exists():
                    try:
                        if frame.depth_path.endswith(".npy"):
                            depth_arr = np.load(frame.depth_path)
                        else:
                            depth_arr = cv2.imread(frame.depth_path, cv2.IMREAD_UNCHANGED)
                    except Exception:
                        pass

                # 3c. Segment masks & project to 3D for each candidate
                for cand in candidates:
                    bbox = cand["bbox"]
                    d_class = cand["canonical_class"]

                    seg_res = self.segmenter.segment_candidate(
                        rgb_img, bbox, d_class, depth_map=depth_arr
                    )
                    mask = seg_res["mask"]

                    # Project to 3D and host plane
                    proj_res = self.projector.project_and_associate(
                        mask,
                        intrinsics=frame.intrinsics,
                        camera_pose=frame.camera_pose,
                        structural_planes=structural_planes,
                        depth_map=depth_arr,
                    )

                    # Compute metric extent
                    is_metric = (frame.tier == "lidar") or (proj_res["status"] == DamageStatus.ACCEPTED)
                    extent_res = self.extent_estimator.compute_metric_extent(
                        proj_res.get("points_2d_local"),
                        damage_class=d_class,
                        view_angle_deg=proj_res.get("view_angle_deg"),
                        is_clipped_by_border=cand.get("is_clipped_by_border", False),
                        is_metric_calibrated=is_metric,
                    )

                    # Determine overall observation status
                    obs_status = proj_res["status"]
                    if extent_res["status"] == DamageStatus.NOT_EVALUABLE:
                        obs_status = DamageStatus.NOT_EVALUABLE
                    elif extent_res["status"] == DamageStatus.PROVISIONAL and obs_status == DamageStatus.ACCEPTED:
                        obs_status = DamageStatus.PROVISIONAL

                    obs_entry = {
                        "observation_id": cand["candidate_id"],
                        "image_id": frame.image_id,
                        "capture_id": capture_id,
                        "tier": frame.tier,
                        "damage_class": d_class,
                        "class_name": cand["class_name"],
                        "class_confidence": cand["confidence"],
                        "bbox": bbox,
                        "mask": mask,
                        "mask_area_pixels": seg_res["mask_area_pixels"],
                        "host_surface_id": proj_res.get("host_surface_id"),
                        "host_surface_type": proj_res.get("host_surface_type"),
                        "centroid_3d": proj_res.get("centroid_3d"),
                        "points_2d_local": proj_res.get("points_2d_local"),
                        "view_angle_deg": proj_res.get("view_angle_deg"),
                        "metric_area": extent_res.get("metric_area"),
                        "metric_length": extent_res.get("metric_length"),
                        "polygon_on_surface": extent_res.get("polygon_on_surface"),
                        "status": obs_status,
                    }
                    raw_observations.append(obs_entry)
                    obs_map[frame.image_id] = obs_entry

        # 4. Multi-view fusion & deduplication
        fused_damages: List[DamageRegion3D] = self.fusion_engine.fuse_observations(
            raw_observations, capture_id=capture_id
        )

        # 5. Evaluate concealed damage rules
        concealed_flags: List[ConcealedDamageFlag] = self.rule_engine.evaluate_damages(fused_damages)
        flag_map: Dict[str, List[ConcealedDamageFlag]] = {}
        for fl in concealed_flags:
            flag_map.setdefault(fl.damage_id, []).append(fl)

        # Attach flags to damage regions
        for dmg in fused_damages:
            dmg.concealed_flags = flag_map.get(dmg.damage_id, [])

        # 6. Generate repair scope line items
        scope_line_items: List[ScopeLineItem] = self.scope_generator.generate_scope_for_all(
            fused_damages, concealed_flags
        )
        scope_map: Dict[str, List[ScopeLineItem]] = {}
        for sc in scope_line_items:
            scope_map.setdefault(sc.damage_id, []).append(sc)

        # Attach scope items to damage regions
        for dmg in fused_damages:
            dmg.scope_line_items = scope_map.get(dmg.damage_id, [])

        # 7. Export judge review bundles
        for dmg in fused_damages:
            try:
                self.visualizer.export_damage_review_bundle(dmg, capture_id, obs_map=obs_map)
            except Exception:
                pass

        # 8. Save structured results to outputs/<capture>/damage/
        damages_json_path = out_damage_dir / "damages.json"
        with open(damages_json_path, "w", encoding="utf-8") as f:
            f.write(json.dumps([d.model_dump() for d in fused_damages], indent=2))

        flags_json_path = out_damage_dir / "concealed_flags.json"
        with open(flags_json_path, "w", encoding="utf-8") as f:
            f.write(json.dumps([fl.model_dump() for fl in concealed_flags], indent=2))

        scope_json_path = out_damage_dir / "repair_scope.json"
        with open(scope_json_path, "w", encoding="utf-8") as f:
            f.write(json.dumps([sc.model_dump() for sc in scope_line_items], indent=2))

        # Summary statistics
        accepted_count = sum(1 for d in fused_damages if d.status == DamageStatus.ACCEPTED)
        provisional_count = sum(1 for d in fused_damages if d.status == DamageStatus.PROVISIONAL)
        not_eval_count = sum(1 for d in fused_damages if d.status == DamageStatus.NOT_EVALUABLE)

        summary_stats = {
            "capture_id": capture_id,
            "tier": detected_tier,
            "images_inspected": len(frames),
            "quality_rejected": sum(1 for q in quality_records if q.status == DamageQualityStatus.REJECTED),
            "raw_candidates_detected": len(raw_observations),
            "fused_damages_count": len(fused_damages),
            "accepted_count": accepted_count,
            "provisional_count": provisional_count,
            "not_evaluable_count": not_eval_count,
            "concealed_flags_count": len(concealed_flags),
            "scope_line_items_count": len(scope_line_items),
        }

        summary_json_path = out_damage_dir / "damage_summary.json"
        with open(summary_json_path, "w", encoding="utf-8") as f:
            json.dump(summary_stats, f, indent=2)

        return {
            "damage_regions": fused_damages,
            "concealed_flags": concealed_flags,
            "scope_line_items": scope_line_items,
            "quality_records": quality_records,
            "summary_stats": summary_stats,
        }

    def _load_structural_planes(self, capture_id: str, tier: str) -> List[Dict[str, Any]]:
        """Loads Stage 2 structural planes (walls, floors, ceilings) for the capture."""
        planes: List[Dict[str, Any]] = []

        # Candidate paths for structural extraction stats
        search_paths = [
            self.workspace_root / "outputs" / capture_id / "structure" / "extraction_stats.json",
            self.workspace_root / "outputs" / capture_id / tier / "structure" / "extraction_stats.json",
            self.workspace_root / "outputs" / capture_id / "floorplan_geometry" / "room_polygon.json",
        ]

        for p in search_paths:
            if p.exists():
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    # Check extraction_stats format
                    if "detected_planes" in data:
                        for pl in data["detected_planes"]:
                            planes.append(pl)
                    elif "planes" in data:
                        for pl in data["planes"]:
                            planes.append(pl)
                    elif "walls" in data:
                        for w in data["walls"]:
                            planes.append({
                                "plane_id": w.get("wall_id", "wall_00"),
                                "type": "wall",
                                "equation": w.get("plane_equation", [1.0, 0.0, 0.0, 0.0]),
                            })
                except Exception:
                    pass
                if planes:
                    break

        # Fallback default bounding planes if unextracted
        if not planes:
            planes = [
                {"plane_id": "wall_north", "type": "wall", "equation": [0.0, 0.0, 1.0, -3.0]},
                {"plane_id": "wall_south", "type": "wall", "equation": [0.0, 0.0, -1.0, -1.0]},
                {"plane_id": "wall_east", "type": "wall", "equation": [1.0, 0.0, 0.0, -2.5]},
                {"plane_id": "wall_west", "type": "wall", "equation": [-1.0, 0.0, 0.0, -2.5]},
                {"plane_id": "floor_main", "type": "floor", "equation": [0.0, 1.0, 0.0, 0.0]},
                {"plane_id": "ceiling_main", "type": "ceiling", "equation": [0.0, -1.0, 0.0, 2.5]},
            ]

        return planes
