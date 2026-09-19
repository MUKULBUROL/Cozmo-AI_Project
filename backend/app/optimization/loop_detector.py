"""Stage 6 Loop Closure Candidate Search.

1. Why this file exists:
    Identifies candidate pairs of non-consecutive keyframe nodes that are physically
    proximate in space but separated by significant capture time, representing potential
    revisits of corridors, doorways, or rooms.

2. Pipeline stage:
    Stage 6 — Loop Candidate Proposal.

3. Inputs:
    List of KeyframeNode objects with poses, timestamps, and optional local point clouds.

4. Outputs:
    List of LoopCandidate objects and serialized loop_candidates.json documenting proposal rationale.

5. Coordinate conventions:
    Horizontal XZ plane proximity, Y vertical height proximity. Metric meters.

6. Unit assumptions:
    Distances in meters (m), elapsed time in seconds (s).

7. Important dependencies:
    numpy, json, pathlib, backend.app.optimization.keyframes.

8. What is most likely to break:
    Too wide proximity threshold proposing hundreds of distant pairs, overwhelming ICP registration.

9. What a developer should inspect first:
    Verify candidate spatial_distance_m is within reasonable scanner range (< 2.0 m).
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Any, Optional
import numpy as np

from backend.app.optimization.keyframes import KeyframeNode


@dataclass
class LoopCandidate:
    """Represents a proposed loop closure pairing between two keyframes.

    Attributes:
        candidate_id: Unique string identifier (e.g. 'cand_005_078').
        node_i: Index of source keyframe node.
        node_j: Index of target keyframe node.
        frame_i: Raw frame index of source node.
        frame_j: Raw frame index of target node.
        time_delta_s: Temporal separation in seconds between frames.
        spatial_distance_m: Euclidean distance between camera origins.
        reasons: List of explanatory justification strings.
    """
    candidate_id: str
    node_i: int
    node_j: int
    frame_i: int
    frame_j: int
    time_delta_s: float
    spatial_distance_m: float
    reasons: List[str] = field(default_factory=list)


def detect_loop_candidates(
    keyframes: List[KeyframeNode],
    max_proximity_m: float = 1.6,
    min_time_gap_s: float = 18.0,
    min_node_gap: int = 12,
    max_candidates: int = 30,
) -> List[LoopCandidate]:
    """Finds plausible non-sequential keyframe pairs based on spatio-temporal cues.

    Purpose:
        Restricts expensive 3D geometric ICP registration to high-probability revisit areas.

    Parameters:
        keyframes: List of KeyframeNode instances.
        max_proximity_m: Maximum Euclidean distance in meters between camera centers.
        min_time_gap_s: Minimum elapsed time in seconds between candidate keyframes.
        min_node_gap: Minimum difference in node indices to prevent adjacent loop proposals.
        max_candidates: Maximum number of candidate pairs to retain.

    Returns:
        List of LoopCandidate objects sorted by spatial proximity.

    Assumptions:
        Node indices reflect monotonic time sequence.

    Failure conditions:
        Returns empty list if no pairs satisfy the spatio-temporal constraints.

    Debugging:
        Inspect len(candidates) and spatial_distance_m distribution.
    """
    n = len(keyframes)
    if n < min_node_gap + 1:
        return []

    positions = np.array([k.matrix[:3, 3] for k in keyframes], dtype=np.float64)
    timestamps = np.array([k.timestamp for k in keyframes], dtype=np.float64)

    candidates: List[LoopCandidate] = []

    for i in range(n):
        for j in range(i + min_node_gap, n):
            dt = float(timestamps[j] - timestamps[i])
            if dt < min_time_gap_s:
                continue

            dist = float(np.linalg.norm(positions[i] - positions[j]))
            if dist <= max_proximity_m:
                reasons = ["spatial_proximity", f"temporal_gap_{dt:.1f}s"]

                # Optional bounding box overlap check if point clouds are present
                if keyframes[i].local_pcd is not None and keyframes[j].local_pcd is not None:
                    # Check if bounding boxes in world space overlap
                    pcd_i_world = keyframes[i].local_pcd.clone().transform(keyframes[i].matrix)
                    pcd_j_world = keyframes[j].local_pcd.clone().transform(keyframes[j].matrix)
                    box_i = pcd_i_world.get_axis_aligned_bounding_box()
                    box_j = pcd_j_world.get_axis_aligned_bounding_box()

                    min_i, max_i = box_i.get_min_bound(), box_i.get_max_bound()
                    min_j, max_j = box_j.get_min_bound(), box_j.get_max_bound()

                    overlap = np.all(min_i <= max_j) and np.all(min_j <= max_i)
                    if overlap:
                        reasons.append("point_cloud_bounding_overlap")

                cand = LoopCandidate(
                    candidate_id=f"cand_{keyframes[i].node_id:03d}_{keyframes[j].node_id:03d}",
                    node_i=keyframes[i].node_id,
                    node_j=keyframes[j].node_id,
                    frame_i=keyframes[i].frame_id,
                    frame_j=keyframes[j].frame_id,
                    time_delta_s=round(dt, 2),
                    spatial_distance_m=round(dist, 4),
                    reasons=reasons,
                )
                candidates.append(cand)

    # Sort candidates by spatial proximity (closest pairs first)
    candidates.sort(key=lambda c: c.spatial_distance_m)
    return candidates[:max_candidates]


def export_loop_candidates_json(candidates: List[LoopCandidate], output_path: Path) -> None:
    """Exports proposed loop closure candidates to a machine-readable JSON file.

    Purpose:
        Provides clear audit trail of why candidates were selected prior to registration.

    Parameters:
        candidates: List of LoopCandidate objects.
        output_path: File destination Path.

    Returns:
        None.

    Assumptions:
        Destination directory is writable.

    Failure conditions:
        OSError on disk write failure.

    Debugging:
        Verify candidate node IDs match keyframe indices.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "candidate_count": len(candidates),
        "candidates": [
            {
                "candidate_id": c.candidate_id,
                "node_i": c.node_i,
                "node_j": c.node_j,
                "frame_i": c.frame_i,
                "frame_j": c.frame_j,
                "time_delta_s": c.time_delta_s,
                "spatial_distance_meters": c.spatial_distance_m,
                "reasons": c.reasons,
            }
            for c in candidates
        ],
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
