"""Trajectory and odometry drift analysis for ARKit captures."""

import json
from typing import List, Dict, Any, Optional
import numpy as np

from backend.app.models.capture import Pose6D


def analyze_trajectory(poses: List[Pose6D], is_loop_scan: Optional[bool] = None) -> Dict[str, Any]:
    """Computes trajectory length, bounds, start-end displacement, and drift metrics.

    Args:
        poses: Chronological list of Pose6D records.
        is_loop_scan: If True, indicates the capture trajectory was intended to return to origin.
    """
    if not poses:
        return {"error": "Empty trajectory"}

    coords = np.array([[p.x, p.y, p.z] for p in poses], dtype=np.float64)
    timestamps = [p.timestamp for p in poses]

    start_pos = coords[0].tolist()
    end_pos = coords[-1].tolist()
    start_end_displacement = float(np.linalg.norm(coords[-1] - coords[0]))

    # Step-by-step increments
    diffs = coords[1:] - coords[:-1]
    step_distances = np.linalg.norm(diffs, axis=1)
    total_path_length_m = float(np.sum(step_distances))

    duration_s = float(timestamps[-1] - timestamps[0]) if len(timestamps) > 1 else 0.0
    avg_speed_mps = total_path_length_m / duration_s if duration_s > 0 else 0.0

    # Bounding box of trajectory
    min_bounds = coords.min(axis=0).tolist()
    max_bounds = coords.max(axis=0).tolist()

    # Loop drift assessment
    # Note: displacement equals drift ONLY when the physical capture returned to start.
    drift_note = (
        "Start-end displacement represents accumulated loop closure drift if the user walked in a loop."
        if is_loop_scan
        else "Start-end displacement is distance between first and last pose (not necessarily closed loop)."
    )

    stats = {
        "total_poses": len(poses),
        "duration_seconds": round(duration_s, 2),
        "total_path_length_meters": round(total_path_length_m, 3),
        "start_position_meters": [round(v, 4) for v in start_pos],
        "end_position_meters": [round(v, 4) for v in end_pos],
        "start_end_displacement_meters": round(start_end_displacement, 4),
        "average_speed_mps": round(avg_speed_mps, 3),
        "trajectory_bounds_meters": {
            "x": [round(min_bounds[0], 3), round(max_bounds[0], 3)],
            "y": [round(min_bounds[1], 3), round(max_bounds[1], 3)],
            "z": [round(min_bounds[2], 3), round(max_bounds[2], 3)],
        },
        "is_loop_scan": is_loop_scan,
        "estimated_loop_drift_meters": round(start_end_displacement, 4) if is_loop_scan else None,
        "drift_interpretation_note": drift_note,
    }
    return stats


def save_trajectory_json(stats: Dict[str, Any], output_path: str):
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2)
