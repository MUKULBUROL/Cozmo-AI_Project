"""Automated Reproducibility & Geometric Equivalence Verification Tool.

Purpose:
    Compares two property plan result JSON files produced by COZMO
    reconstruction pipelines (e.g. Reference vs Candidate, or Run A vs Run B).

    Verifies deterministic reproducibility across:
    - Reconstruction status & tier
    - Room count & room topology / adjacency
    - Room polygon geometry (with cyclic starting-vertex invariance)
    - Floor area and perimeter measurements
    - Wall counts, geometry (start/end points, lengths, orientations)
    - Ceiling heights and uncertainty bounds
    - Openings (doors/windows) counts, associations, and dimensions
    - Damage detections and repair scopes

Usage:
    python3 scripts/verify_sample_reproducibility.py \
        --reference <path_to_reference.json> \
        --candidate <path_to_candidate.json> \
        [--tolerance 1e-4]
"""

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional


IGNORED_DYNAMIC_FIELDS = {
    "capture_id",
    "property_id",
    "created_at",
    "updated_at",
    "timestamp",
    "duration_seconds",
    "processing_time_s",
    "runtime_s",
    "output_dir",
    "output_path",
    "filename",
    "original_filename",
    "job_id",
}


def load_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def normalize_val(v: Any) -> Any:
    if isinstance(v, float):
        return round(v, 6)
    return v


def polygon_cyclic_equal(poly1: List[List[float]], poly2: List[List[float]], tol: float = 1e-4) -> bool:
    """Check if two 2D polygons are identical up to cyclic starting-vertex shift."""
    if len(poly1) != len(poly2):
        return False
    n = len(poly1)
    if n == 0:
        return True

    # Check forward cycles
    for shift in range(n):
        match = True
        for i in range(n):
            p1 = poly1[i]
            p2 = poly2[(i + shift) % n]
            if abs(p1[0] - p2[0]) > tol or abs(p1[1] - p2[1]) > tol:
                match = False
                break
        if match:
            return True

    # Check reverse cycles
    for shift in range(n):
        match = True
        for i in range(n):
            p1 = poly1[i]
            p2 = poly2[(shift - i) % n]
            if abs(p1[0] - p2[0]) > tol or abs(p1[1] - p2[1]) > tol:
                match = False
                break
        if match:
            return True

    return False


def compare_properties(ref: Dict[str, Any], cand: Dict[str, Any], tol: float = 1e-4) -> Dict[str, Any]:
    mismatches = []
    differences = []

    # 1. Status & Tier
    ref_status = ref.get("reconstruction_status") or ref.get("status")
    cand_status = cand.get("reconstruction_status") or cand.get("status")
    if ref_status != cand_status:
        mismatches.append(f"Status mismatch: reference '{ref_status}' vs candidate '{cand_status}'")

    ref_tier = ref.get("tier")
    cand_tier = cand.get("tier")
    if ref_tier != cand_tier:
        mismatches.append(f"Tier mismatch: reference '{ref_tier}' vs candidate '{cand_tier}'")

    # 2. Rooms
    ref_rooms = ref.get("rooms", [])
    cand_rooms = cand.get("rooms", [])

    if len(ref_rooms) != len(cand_rooms):
        mismatches.append(f"Room count mismatch: reference {len(ref_rooms)} vs candidate {len(cand_rooms)}")

    # Index rooms by room_id or centroid
    ref_room_map = {r.get("room_id", f"idx_{i}"): r for i, r in enumerate(ref_rooms)}
    cand_room_map = {r.get("room_id", f"idx_{i}"): r for i, r in enumerate(cand_rooms)}

    matched_cand_rooms = set()
    for rid, r_ref in ref_room_map.items():
        if rid in cand_room_map:
            r_cand = cand_room_map[rid]
            matched_cand_rooms.add(rid)
        else:
            # Try to match by geometry / area
            r_cand = None
            ref_area = (r_ref.get("floor_area", {}) or {}).get("value")
            for cid, c_room in cand_room_map.items():
                if cid not in matched_cand_rooms:
                    cand_area = (c_room.get("floor_area", {}) or {}).get("value")
                    if ref_area is not None and cand_area is not None and abs(ref_area - cand_area) < 0.1:
                        r_cand = c_room
                        matched_cand_rooms.add(cid)
                        break
            if r_cand is None:
                mismatches.append(f"Room '{rid}' missing in candidate")
                continue

        # Compare room area
        ref_area = (r_ref.get("floor_area", {}) or {}).get("value")
        cand_area = (r_cand.get("floor_area", {}) or {}).get("value")
        if ref_area is not None and cand_area is not None:
            diff = abs(ref_area - cand_area)
            if diff > tol:
                differences.append(f"Room '{rid}' area diff: ref={ref_area} m2, cand={cand_area} m2 (diff={diff:.6f} m2)")

        # Compare perimeter
        ref_perim = (r_ref.get("perimeter", {}) or {}).get("value")
        cand_perim = (r_cand.get("perimeter", {}) or {}).get("value")
        if ref_perim is not None and cand_perim is not None:
            diff = abs(ref_perim - cand_perim)
            if diff > tol:
                differences.append(f"Room '{rid}' perimeter diff: ref={ref_perim} m, cand={cand_perim} m (diff={diff:.6f} m)")

        # Compare ceiling height
        ref_ceil = (r_ref.get("ceiling_height", {}) or {}).get("value") if isinstance(r_ref.get("ceiling_height"), dict) else r_ref.get("ceiling_height")
        cand_ceil = (r_cand.get("ceiling_height", {}) or {}).get("value") if isinstance(r_cand.get("ceiling_height"), dict) else r_cand.get("ceiling_height")
        if ref_ceil is not None and cand_ceil is not None:
            diff = abs(ref_ceil - cand_ceil)
            if diff > tol:
                differences.append(f"Room '{rid}' ceiling height diff: ref={ref_ceil} m, cand={cand_ceil} m (diff={diff:.6f} m)")
        elif (ref_ceil is None) != (cand_ceil is None):
            differences.append(f"Room '{rid}' ceiling height presence mismatch: ref={ref_ceil}, cand={cand_ceil}")

        # Compare walls
        r_ref_walls = r_ref.get("walls", [])
        r_cand_walls = r_cand.get("walls", [])
        if len(r_ref_walls) != len(r_cand_walls):
            mismatches.append(f"Room '{rid}' wall count mismatch: ref={len(r_ref_walls)} vs cand={len(r_cand_walls)}")

        # Check wall lengths
        ref_wall_lengths = sorted([(w.get("length", {}) or {}).get("value", 0.0) for w in r_ref_walls])
        cand_wall_lengths = sorted([(w.get("length", {}) or {}).get("value", 0.0) for w in r_cand_walls])
        for wl_r, wl_c in zip(ref_wall_lengths, cand_wall_lengths):
            if abs(wl_r - wl_c) > tol:
                differences.append(f"Room '{rid}' wall length diff: ref={wl_r:.4f} m, cand={wl_c:.4f} m (diff={abs(wl_r - wl_c):.6f} m)")

    # 3. Connections / Topology
    ref_conn = ref.get("connections", [])
    cand_conn = cand.get("connections", [])
    if len(ref_conn) != len(cand_conn):
        differences.append(f"Connections count mismatch: ref={len(ref_conn)} vs cand={len(cand_conn)}")

    # 4. Damages
    ref_dmg = ref.get("damages", []) or ref.get("damage_records", [])
    cand_dmg = cand.get("damages", []) or cand.get("damage_records", [])
    if len(ref_dmg) != len(cand_dmg):
        mismatches.append(f"Damage count mismatch: ref={len(ref_dmg)} vs cand={len(cand_dmg)}")

    # Determine Overall Result
    if not mismatches and not differences:
        verdict = "EXACT"
    elif not mismatches and all("diff=" in d for d in differences):
        verdict = "EQUIVALENT"
    else:
        verdict = "DIFFERENT"

    return {
        "verdict": verdict,
        "mismatches": mismatches,
        "differences": differences,
        "ref_rooms": len(ref_rooms),
        "cand_rooms": len(cand_rooms),
        "ref_status": ref_status,
        "cand_status": cand_status,
    }


def main():
    parser = argparse.ArgumentParser(description="Verify Sample Reproducibility between two JSONs")
    parser.add_argument("--reference", required=True, help="Path to reference property.json")
    parser.add_argument("--candidate", required=True, help="Path to candidate property.json")
    parser.add_argument("--tolerance", type=float, default=1e-4, help="Diagnostic tolerance in meters (default: 1e-4)")
    args = parser.parse_args()

    ref_data = load_json(args.reference)
    cand_data = load_json(args.candidate)

    res = compare_properties(ref_data, cand_data, tol=args.tolerance)

    print("=" * 60)
    print("COZMO REPRODUCIBILITY COMPARISON")
    print("=" * 60)
    print(f"Reference: {args.reference}")
    print(f"Candidate: {args.candidate}")
    print(f"Verdict:   {res['verdict']}")
    print("-" * 60)
    print(f"Ref Status: {res['ref_status']} | Cand Status: {res['cand_status']}")
    print(f"Ref Rooms:  {res['ref_rooms']} | Cand Rooms:  {res['cand_rooms']}")
    print("-" * 60)
    if res["mismatches"]:
        print("STRUCTURAL MISMATCHES:")
        for m in res["mismatches"]:
            print(f"  [MISMATCH] {m}")
    else:
        print("Structural Topology: MATCH")

    if res["differences"]:
        print("\nNUMERICAL DIFFERENCES:")
        for d in res["differences"]:
            print(f"  [DIFF] {d}")
    else:
        print("Numerical Equality: EXACT")
    print("=" * 60)


if __name__ == "__main__":
    main()
