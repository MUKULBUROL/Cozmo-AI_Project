"""Multi-view observation clustering, spatial deduplication, and fused 3D damage region synthesis.

1. Why this file exists:
   Prevents duplicate reporting of the same physical damage seen across multiple
   video keyframes, LiDAR sweeps, or photo stills. Clusters observations by host
   surface and 3D metric proximity, computes fused extent with measurement spread,
   and selects the best viewing angle for judge review.

2. Pipeline stage:
   Stage 9 (Damage Detection, Metric Extent, Concealed-Damage Rules & Repair Scope) - Multi-View Fusion.

3. Inputs:
   List of unprojected damage observation dictionaries containing 3D centroids,
   local planar points, metric extents, host plane IDs, image IDs, and view angles.

4. Outputs:
   List of fused DamageRegion3D Pydantic objects with consolidated measurements,
   supporting image lists, and measurement variance metrics.

5. Coordinate convention:
   3D world coordinates [x, y, z] in metric meters.
   2D surface local coordinates (u_local, v_local) in meters.

6. Unit convention:
   Distances and coordinates in meters (m); areas in square meters (m2).
   Spread in square meters or meters.

7. Dependencies:
   math, typing, numpy, backend.app.models.damage.DamageRegion3D, backend.app.models.output.DamageClass.

8. Assumptions:
   - Observations on different structural planes represent distinct physical damages.
   - Observations on the same plane within 0.35 m centroid distance represent the same defect.

9. Failure modes:
   - Two distinct damages located immediately adjacent to each other (< 0.20 m).
   - Incompatible semantic classes detected for the same spatial region.

10. First things to inspect while debugging:
    - Inspect cluster distance threshold (default max_cluster_dist_m = 0.35).
    - Check measurement_spread_m2 across supporting frames.
    - Check supporting_images and best_image_id assignments.
"""

import math
from typing import List, Dict, Any, Optional
import numpy as np

from ..models.damage import (
    DamageRegion3D,
    DamageStatus,
    SurfaceType,
)
from ..models.output import DamageClass, Measurement
from ..models.floorplan import Point2D


class MultiViewDamageFusion:
    """Clusters multi-view 2D observations into unified 3D damage regions."""

    def __init__(
        self,
        max_cluster_dist_m: float = 0.35,
        min_fused_observations: int = 1,
    ):
        """Initializes fusion clustering thresholds.

        Purpose:
            Configures spatial proximity tolerances for associating observations.

        Parameters:
            max_cluster_dist_m: Maximum Euclidean 3D distance between observation centroids to merge.
            min_fused_observations: Minimum supporting observations to accept a fused damage.

        Returns:
            None.

        Assumptions:
            Multi-view captures have consistent 3D global coordinate registration.

        Failure cases:
            None.

        Debugging clues:
            Increase max_cluster_dist_m if camera pose drift causes duplicate centroids.
        """
        self.max_cluster_dist_m = max_cluster_dist_m
        self.min_fused_observations = min_fused_observations

    def fuse_observations(
        self,
        observations: List[Dict[str, Any]],
        capture_id: str = "capture_01",
    ) -> List[DamageRegion3D]:
        """Fuses raw unprojected observations into consolidated 3D damage regions.

        Purpose:
            Clusters observations by host surface and 3D centroid distance, eliminating
            duplicate detections and calculating multi-view measurement variance.

        Parameters:
            observations: List of observation dictionaries from projector and extent estimator.
            capture_id: Capture session identifier for prefixing damage IDs.

        Returns:
            List of consolidated DamageRegion3D models.

        Assumptions:
            Each observation has valid host_surface_id, centroid_3d, and damage_class.

        Failure cases:
            Returns empty list if input observations are empty or unassociated.

        Debugging clues:
            Check whether observations share the exact same host_surface_id.
        """
        valid_obs = [
            o for o in observations
            if o.get("host_surface_id") is not None and o.get("centroid_3d") is not None
        ]
        if not valid_obs:
            return []

        # Group observations by host_surface_id
        by_surface: Dict[str, List[Dict[str, Any]]] = {}
        for obs in valid_obs:
            sid = obs["host_surface_id"]
            by_surface.setdefault(sid, []).append(obs)

        clusters: List[List[Dict[str, Any]]] = []

        # Cluster within each surface by 3D centroid distance
        for sid, surface_obs in by_surface.items():
            assigned = [False] * len(surface_obs)
            for i in range(len(surface_obs)):
                if assigned[i]:
                    continue
                current_cluster = [surface_obs[i]]
                assigned[i] = True
                c_i = np.array(surface_obs[i]["centroid_3d"], dtype=float)

                for j in range(i + 1, len(surface_obs)):
                    if assigned[j]:
                        continue
                    c_j = np.array(surface_obs[j]["centroid_3d"], dtype=float)
                    dist = float(np.linalg.norm(c_i - c_j))
                    if dist <= self.max_cluster_dist_m:
                        current_cluster.append(surface_obs[j])
                        assigned[j] = True

                clusters.append(current_cluster)

        # Synthesize each cluster into a DamageRegion3D
        fused_regions: List[DamageRegion3D] = []

        for idx, cluster in enumerate(clusters):
            region = self._synthesize_cluster(cluster, f"dmg_{capture_id}_{idx+1:02d}")
            if region is not None:
                fused_regions.append(region)

        return fused_regions

    def _synthesize_cluster(
        self, cluster: List[Dict[str, Any]], damage_id: str
    ) -> Optional[DamageRegion3D]:
        """Consolidates a group of matching observations into one DamageRegion3D."""
        if not cluster:
            return None

        # Voting / priority for semantic damage class
        class_votes: Dict[DamageClass, float] = {}
        for o in cluster:
            cls = o.get("damage_class", DamageClass.OTHER_VISIBLE_DAMAGE)
            conf = float(o.get("class_confidence", 0.5))
            class_votes[cls] = class_votes.get(cls, 0.0) + conf

        winning_class = max(class_votes.keys(), key=lambda k: class_votes[k])
        total_conf = sum(o.get("class_confidence", 0.5) for o in cluster)
        mean_conf = round(total_conf / len(cluster), 3)

        # Centroid is weighted average of 3D centroids
        centroids = [np.array(o["centroid_3d"], dtype=float) for o in cluster]
        weights = [float(o.get("class_confidence", 1.0)) for o in cluster]
        w_sum = sum(weights) or 1.0
        fused_centroid = np.sum([c * w for c, w in zip(centroids, weights)], axis=0) / w_sum

        host_surface_id = cluster[0]["host_surface_id"]
        host_surface_type = cluster[0].get("host_surface_type", SurfaceType.WALL)
        host_room_id = cluster[0].get("host_room_id")

        # Select best observation frame (minimum view angle and highest sharpness)
        best_obs = min(cluster, key=lambda o: o.get("view_angle_deg", 90.0))
        best_image_id = best_obs.get("image_id")

        supporting_obs_ids = [o.get("observation_id", f"obs_{i}") for i, o in enumerate(cluster)]
        supporting_images = list(dict.fromkeys(o.get("image_id", "") for o in cluster if o.get("image_id")))

        # Check metric extents across supporting observations
        area_measurements: List[Measurement[float]] = [
            o["metric_area"] for o in cluster if o.get("metric_area") is not None
        ]
        length_measurements: List[Measurement[float]] = [
            o["metric_length"] for o in cluster if o.get("metric_length") is not None
        ]

        fused_area: Optional[Measurement[float]] = None
        fused_length: Optional[Measurement[float]] = None
        spread_m2: Optional[float] = None
        fused_polygon_surface: Optional[List[Point2D]] = best_obs.get("polygon_on_surface")

        if area_measurements:
            vals = [m.value for m in area_measurements]
            mean_val = float(np.mean(vals))
            spread_m2 = round(float(np.std(vals)), 4) if len(vals) > 1 else 0.0

            # Confidence interval
            lowers = [m.lower_bound for m in area_measurements]
            uppers = [m.upper_bound for m in area_measurements]
            fused_lower = round(float(np.mean(lowers)), 3)
            fused_upper = round(float(np.mean(uppers)), 3)

            fused_area = Measurement[float](
                value=round(mean_val, 3),
                unit="m2",
                lower_bound=fused_lower,
                upper_bound=fused_upper,
                confidence=round(np.mean([m.confidence for m in area_measurements]), 2),
                method="multi_view_fused_surface_area",
            )
        elif length_measurements:
            vals = [m.value for m in length_measurements]
            mean_val = float(np.mean(vals))
            spread_m2 = round(float(np.std(vals)), 4) if len(vals) > 1 else 0.0

            lowers = [m.lower_bound for m in length_measurements]
            uppers = [m.upper_bound for m in length_measurements]
            fused_lower = round(float(np.mean(lowers)), 3)
            fused_upper = round(float(np.mean(uppers)), 3)

            fused_length = Measurement[float](
                value=round(mean_val, 3),
                unit="m",
                lower_bound=fused_lower,
                upper_bound=fused_upper,
                confidence=round(np.mean([m.confidence for m in length_measurements]), 2),
                method="multi_view_fused_crack_length",
            )

        # Status resolution
        statuses = [o.get("status", DamageStatus.ACCEPTED) for o in cluster]
        if all(s == DamageStatus.ACCEPTED for s in statuses):
            final_status = DamageStatus.ACCEPTED
        elif any(s == DamageStatus.ACCEPTED for s in statuses):
            final_status = DamageStatus.ACCEPTED
        elif all(s == DamageStatus.NOT_EVALUABLE for s in statuses):
            final_status = DamageStatus.NOT_EVALUABLE
        elif any(s == DamageStatus.PROVISIONAL for s in statuses):
            final_status = DamageStatus.PROVISIONAL
        else:
            final_status = DamageStatus.UNCERTAIN

        return DamageRegion3D(
            damage_id=damage_id,
            damage_class=winning_class,
            class_confidence=mean_conf,
            host_surface_id=host_surface_id,
            host_surface_type=host_surface_type,
            host_room_id=host_room_id,
            centroid_3d=[round(float(x), 4) for x in fused_centroid.tolist()],
            polygon_on_surface=fused_polygon_surface,
            metric_area=fused_area,
            metric_length=fused_length,
            status=final_status,
            supporting_observations=supporting_obs_ids,
            supporting_images=supporting_images,
            measurement_spread_m2=spread_m2,
            best_image_id=best_image_id,
        )
