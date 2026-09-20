"""CLI verification tool comparing multiple reconstruction runs for determinism.

1. Purpose:
    Forensically validates deterministic replay across multiple execution runs of the same
    LiDAR capture, verifying byte-level identity or exact floating-point equality across
    all pipeline artifacts (Stage 1 to Stage 5).

2. Stage:
    Stage 10.2 (Deterministic LiDAR Reconstruction Verification).

3. Inputs:
    List of run directory paths specified via `--runs run1_dir run2_dir [run3_dir ...]`.
    Example: `python -m scripts.verify_determinism --runs outputs/run1/c00a170fe1 outputs/run2/c00a170fe1`

4. Outputs:
    Formatted console report table comparing Stage 1 point clouds, Stage 2 structural planes,
    Stage 3 room polygon, Stage 4 measurements, and Stage 5 openings.
    Exits with code 0 (PASS) or code 1 (FAIL).

5. Coordinate systems / units:
    Metric units (meters), areas in m^2, SHA-256 file hashes.

6. Dependencies:
    argparse, sys, os, json, hashlib, math, typing, pathlib.

7. Assumptions:
    Each specified directory contains standard pipeline output folders:
    structure/, floorplan_geometry/, measurements/, openings/, and root PLY/trajectory files.

8. Failure modes:
    Missing artifact files across runs.
    Mismatch in plane models, inlier counts, vertex sequences, areas, or opening metrics.

9. First debugging points:
    Inspect printed diff sections to identify the exact stage where divergence initiated.
"""

import argparse
import hashlib
import json
import math
import os
import sys
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional


def compute_file_sha256(filepath: str) -> Optional[str]:
    """Computes SHA-256 hex digest of a file.

    Purpose:
        Enables byte-for-byte verification of raw point clouds, filtered PLYs, and JSON artifacts.

    Parameters:
        filepath: str
            Path to file.

    Returns:
        Optional[str]: 64-character hex digest, or None if file does not exist.

    Units / coordinates:
        Cryptographic hex hash.

    Assumptions:
        File can be read in chunks.

    Failure conditions:
        Returns None if file cannot be opened.

    Dependencies:
        hashlib.sha256.

    Debugging clues:
        Verify filepath existence and read permissions.
    """
    if not os.path.exists(filepath):
        return None
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def compare_stage1(run_dirs: List[Path]) -> Tuple[bool, List[str], Dict[str, Any]]:
    """Compares Stage 1 raw point clouds, filtered point clouds, and trajectories.

    Purpose:
        Verifies that Stage 1 sensor unprojection and voxel filtering are byte-identical across runs.

    Parameters:
        run_dirs: List[Path]
            List of run directory paths for the scan.

    Returns:
        Tuple[bool, List[str], Dict[str, Any]]:
            (pass_status, diff_messages, summary_data)

    Units / coordinates:
        Point counts and cryptographic file hashes.

    Assumptions:
        baseline_raw.ply, baseline_filtered.ply, and trajectory.json exist in each directory.

    Failure conditions:
        Missing files or non-identical SHA-256 digests.

    Dependencies:
        compute_file_sha256.

    Debugging clues:
        If hashes differ, check if unprojection was performed on identical depth frames.
    """
    diffs = []
    summary = {}
    files_to_check = ["baseline_raw.ply", "baseline_filtered.ply", "trajectory.json"]

    for fname in files_to_check:
        hashes = [compute_file_sha256(str(rd / fname)) for rd in run_dirs]
        if any(h is None for h in hashes):
            diffs.append(f"Stage 1: File {fname} missing in at least one run directory.")
            continue
        if len(set(hashes)) > 1:
            diffs.append(f"Stage 1: Hash mismatch on {fname}: {hashes}")
        summary[fname] = {
            "identical": len(set(hashes)) == 1,
            "hash": hashes[0] if hashes else None,
        }

    return len(diffs) == 0, diffs, summary


def compare_stage2(run_dirs: List[Path]) -> Tuple[bool, List[str], Dict[str, Any]]:
    """Compares Stage 2 structural planes (floor, ceiling, walls, inlier counts).

    Purpose:
        Verifies that plane extraction, RANSAC fitting, and wall merging are identical.

    Parameters:
        run_dirs: List[Path]
            Run directories to compare.

    Returns:
        Tuple[bool, List[str], Dict[str, Any]]:
            (pass_status, diff_messages, summary_data)

    Units / coordinates:
        Plane equations in meters: a*x + b*y + c*z + d = 0. Inlier counts.

    Assumptions:
        structure/structure.json exists in each run directory.

    Failure conditions:
        Floor detection status differs, inlier counts differ, or wall counts/coefficients differ.

    Dependencies:
        json, math.

    Debugging clues:
        Inspect structure.json and extraction_stats.json in divergent runs.
    """
    diffs = []
    summary = {"runs": []}
    parsed = []

    for rd in run_dirs:
        s_path = rd / "structure" / "structure.json"
        if not s_path.exists():
            diffs.append(f"Stage 2: structure.json missing at {s_path}")
            continue
        with open(s_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            parsed.append(data)

    if len(parsed) < len(run_dirs):
        return False, diffs, summary

    base = parsed[0]
    base_floor_inliers = base.get("floor", {}).get("inlier_count", 0)
    base_wall_count = len(base.get("walls", []))
    base_wall_ids = [w["id"] for w in base.get("walls", [])]

    summary["floor_inliers"] = [p.get("floor", {}).get("inlier_count", 0) for p in parsed]
    summary["wall_count"] = [len(p.get("walls", [])) for p in parsed]

    for idx, p in enumerate(parsed[1:], start=2):
        # Floor
        f_inliers = p.get("floor", {}).get("inlier_count", 0)
        if f_inliers != base_floor_inliers:
            diffs.append(f"Stage 2: Floor inlier mismatch: Run 1={base_floor_inliers}, Run {idx}={f_inliers}")

        bp = base.get("floor", {}).get("plane")
        cp = p.get("floor", {}).get("plane")
        if bp and cp:
            for k in ["a", "b", "c", "d"]:
                if abs(bp[k] - cp[k]) > 1e-5:
                    diffs.append(f"Stage 2: Floor plane coeff {k} mismatch: Run 1={bp[k]}, Run {idx}={cp[k]}")

        # Walls count & ordering
        walls = p.get("walls", [])
        if len(walls) != base_wall_count:
            diffs.append(f"Stage 2: Wall count mismatch: Run 1={base_wall_count}, Run {idx}={len(walls)}")
        else:
            w_ids = [w["id"] for w in walls]
            if w_ids != base_wall_ids:
                diffs.append(f"Stage 2: Wall sequence mismatch: Run 1={base_wall_ids}, Run {idx}={w_ids}")

            for w_idx in range(len(walls)):
                bw = base["walls"][w_idx]
                cw = walls[w_idx]
                if bw["inlier_count"] != cw["inlier_count"]:
                    diffs.append(f"Stage 2: Wall {bw['id']} inliers mismatch: Run 1={bw['inlier_count']}, Run {idx}={cw['inlier_count']}")
                for k in ["a", "b", "c", "d"]:
                    if abs(bw["plane"][k] - cw["plane"][k]) > 1e-5:
                        diffs.append(f"Stage 2: Wall {bw['id']} plane coeff {k} mismatch: Run 1={bw['plane'][k]}, Run {idx}={cw['plane'][k]}")

    return len(diffs) == 0, diffs, summary


def compare_stage3(run_dirs: List[Path]) -> Tuple[bool, List[str], Dict[str, Any]]:
    """Compares Stage 3 room polygon geometry, vertices, area, and perimeter.

    Purpose:
        Verifies that 2D projection, corner intersection, and polygon extraction match identically.

    Parameters:
        run_dirs: List[Path]
            Run directories to compare.

    Returns:
        Tuple[bool, List[str], Dict[str, Any]]:
            (pass_status, diff_messages, summary_data)

    Units / coordinates:
        Metric coordinates (meters), area in m^2, perimeter in meters.

    Assumptions:
        floorplan_geometry/room_polygon.json exists in each run directory.

    Failure conditions:
        Vertex count, vertex positions, area, or perimeter differ across runs.

    Dependencies:
        json, math.

    Debugging clues:
        Inspect floorplan_geometry/polygon_stats.json and corners.json.
    """
    diffs = []
    summary = {}
    parsed = []

    for rd in run_dirs:
        p_path = rd / "floorplan_geometry" / "room_polygon.json"
        if not p_path.exists():
            diffs.append(f"Stage 3: room_polygon.json missing at {p_path}")
            continue
        with open(p_path, "r", encoding="utf-8") as f:
            parsed.append(json.load(f))

    if len(parsed) < len(run_dirs):
        return False, diffs, summary

    base = parsed[0]
    base_poly = base.get("polygon", {})
    base_valid = base_poly.get("valid", base.get("is_valid", False))
    base_verts = base_poly.get("vertices", base.get("vertices", []))
    base_area = base_poly.get("area_sqm", base.get("area_m2", 0.0))
    base_perim = base_poly.get("perimeter_m", 0.0)
    base_wall_ids = base_poly.get("wall_ids", [])

    summary["vertices"] = [len(p.get("polygon", {}).get("vertices", [])) for p in parsed]
    summary["area_m2"] = [p.get("polygon", {}).get("area_sqm", 0.0) for p in parsed]
    summary["perimeter_m"] = [p.get("polygon", {}).get("perimeter_m", 0.0) for p in parsed]

    for idx, p in enumerate(parsed[1:], start=2):
        poly = p.get("polygon", {})
        c_valid = poly.get("valid", p.get("is_valid", False))
        c_verts = poly.get("vertices", p.get("vertices", []))
        c_area = poly.get("area_sqm", p.get("area_m2", 0.0))
        c_perim = poly.get("perimeter_m", 0.0)
        c_wall_ids = poly.get("wall_ids", [])

        if c_valid != base_valid:
            diffs.append(f"Stage 3: Polygon validity mismatch: Run 1={base_valid}, Run {idx}={c_valid}")
        if c_wall_ids != base_wall_ids:
            diffs.append(f"Stage 3: Polygon wall sequence mismatch: Run 1={base_wall_ids}, Run {idx}={c_wall_ids}")
        if len(c_verts) != len(base_verts):
            diffs.append(f"Stage 3: Vertex count mismatch: Run 1={len(base_verts)}, Run {idx}={len(c_verts)}")
        else:
            for v_idx, (bv, cv) in enumerate(zip(base_verts, c_verts)):
                if abs(bv[0] - cv[0]) > 1e-5 or abs(bv[1] - cv[1]) > 1e-5:
                    diffs.append(f"Stage 3: Vertex {v_idx} coords mismatch: Run 1={bv}, Run {idx}={cv}")
        if abs(c_area - base_area) > 1e-5:
            diffs.append(f"Stage 3: Area mismatch: Run 1={base_area}, Run {idx}={c_area}")
        if abs(c_perim - base_perim) > 1e-5:
            diffs.append(f"Stage 3: Perimeter mismatch: Run 1={base_perim}, Run {idx}={c_perim}")

    return len(diffs) == 0, diffs, summary


def compare_stage4(run_dirs: List[Path]) -> Tuple[bool, List[str], Dict[str, Any]]:
    """Compares Stage 4 room metric measurements and confidence intervals.

    Purpose:
        Verifies that wall lengths, area, perimeter, and Monte Carlo uncertainty intervals match.

    Parameters:
        run_dirs: List[Path]
            Run directories to compare.

    Returns:
        Tuple[bool, List[str], Dict[str, Any]]:
            (pass_status, diff_messages, summary_data)

    Units / coordinates:
        Meters (m) and square meters (m^2).

    Assumptions:
        measurements/measurements.json exists in each directory.

    Failure conditions:
        Discrepancy in point estimates or uncertainty intervals.

    Dependencies:
        json, math.

    Debugging clues:
        Check mc_samples and random_seed used in measure_room execution.
    """
    diffs = []
    summary = {}
    parsed = []

    for rd in run_dirs:
        m_path = rd / "measurements" / "measurements.json"
        if not m_path.exists():
            diffs.append(f"Stage 4: measurements.json missing at {m_path}")
            continue
        with open(m_path, "r", encoding="utf-8") as f:
            parsed.append(json.load(f))

    if len(parsed) < len(run_dirs):
        return False, diffs, summary

    base = parsed[0]
    base_status = base.get("status", base.get("validity_status"))
    base_area_val = base.get("floor_area", {}).get("value", base.get("floor_area", {}).get("mean_m2", 0.0))
    base_area_ci = base.get("floor_area", {}).get("interval", [])
    base_perim_val = base.get("perimeter", {}).get("value", base.get("perimeter", {}).get("mean_m", 0.0))
    base_perim_ci = base.get("perimeter", {}).get("interval", [])

    summary["floor_area"] = [p.get("floor_area", {}).get("value", 0.0) for p in parsed]
    summary["perimeter"] = [p.get("perimeter", {}).get("value", 0.0) for p in parsed]

    for idx, p in enumerate(parsed[1:], start=2):
        c_status = p.get("status", p.get("validity_status"))
        if c_status != base_status:
            diffs.append(f"Stage 4: Validity status mismatch: Run 1={base_status}, Run {idx}={c_status}")

        ca = p.get("floor_area", {}).get("value", p.get("floor_area", {}).get("mean_m2", 0.0))
        ca_ci = p.get("floor_area", {}).get("interval", [])
        if abs(base_area_val - ca) > 1e-5:
            diffs.append(f"Stage 4: Floor area mismatch: Run 1={base_area_val}, Run {idx}={ca}")
        if base_area_ci and ca_ci:
            if abs(base_area_ci[0] - ca_ci[0]) > 1e-5 or abs(base_area_ci[1] - ca_ci[1]) > 1e-5:
                diffs.append(f"Stage 4: Floor area 95% CI mismatch: Run 1={base_area_ci}, Run {idx}={ca_ci}")

        cp = p.get("perimeter", {}).get("value", p.get("perimeter", {}).get("mean_m", 0.0))
        cp_ci = p.get("perimeter", {}).get("interval", [])
        if abs(base_perim_val - cp) > 1e-5:
            diffs.append(f"Stage 4: Perimeter mismatch: Run 1={base_perim_val}, Run {idx}={cp}")
        if base_perim_ci and cp_ci:
            if abs(base_perim_ci[0] - cp_ci[0]) > 1e-5 or abs(base_perim_ci[1] - cp_ci[1]) > 1e-5:
                diffs.append(f"Stage 4: Perimeter 95% CI mismatch: Run 1={base_perim_ci}, Run {idx}={cp_ci}")

    return len(diffs) == 0, diffs, summary


def compare_stage5(run_dirs: List[Path]) -> Tuple[bool, List[str], Dict[str, Any]]:
    """Compares Stage 5 opening detections, host wall assignments, and clearance widths.

    Purpose:
        Verifies that door and window detection, jamb projection, and fusion match across runs.

    Parameters:
        run_dirs: List[Path]
            Run directories to compare.

    Returns:
        Tuple[bool, List[str], Dict[str, Any]]:
            (pass_status, diff_messages, summary_data)

    Units / coordinates:
        Clearance widths in meters.

    Assumptions:
        openings/openings.json exists in each directory.

    Failure conditions:
        Opening count, host wall associations, or measured widths differ.

    Dependencies:
        json, math.

    Debugging clues:
        Inspect openings/opening_stats.json and keyframe extraction order.
    """
    diffs = []
    summary = {}
    parsed = []

    for rd in run_dirs:
        o_path = rd / "openings" / "openings.json"
        if not o_path.exists():
            diffs.append(f"Stage 5: openings.json missing at {o_path}")
            continue
        with open(o_path, "r", encoding="utf-8") as f:
            parsed.append(json.load(f))

    if len(parsed) < len(run_dirs):
        return False, diffs, summary

    base = parsed[0]
    base_openings = base.get("openings", [])
    summary["openings_count"] = [len(p.get("openings", [])) for p in parsed]

    for idx, p in enumerate(parsed[1:], start=2):
        ops = p.get("openings", [])
        if len(ops) != len(base_openings):
            diffs.append(f"Stage 5: Opening count mismatch: Run 1={len(base_openings)}, Run {idx}={len(ops)}")
        else:
            for op_idx, (bo, co) in enumerate(zip(base_openings, ops)):
                b_wall = bo.get("wall_id", bo.get("host_wall_id"))
                c_wall = co.get("wall_id", co.get("host_wall_id"))
                if b_wall != c_wall:
                    diffs.append(f"Stage 5: Opening {op_idx} host wall mismatch: Run 1={b_wall}, Run {idx}={c_wall}")

                bw = bo.get("width", {}).get("value", bo.get("clearance_width_m", 0.0))
                cw = co.get("width", {}).get("value", co.get("clearance_width_m", 0.0))
                if abs(bw - cw) > 1e-4:
                    diffs.append(f"Stage 5: Opening {op_idx} width mismatch: Run 1={bw} m, Run {idx}={cw} m")

    return len(diffs) == 0, diffs, summary


def main() -> None:
    """CLI orchestrator comparing completed reconstruction runs for determinism.

    Purpose:
        Executes multi-stage forensic comparisons across 2 or more run directories,
        printing a detailed comparison matrix and exiting code 0 (PASS) or 1 (FAIL).

    Parameters:
        None (uses sys.argv).

    Returns:
        None (exits system).

    Units / coordinates:
        Metric coordinates in meters, file hashes.

    Assumptions:
        Target run paths point to scan directories with standard artifact structure.

    Failure conditions:
        Exits with code 1 if any stage comparison fails.

    Dependencies:
        argparse, sys, Path.

    Debugging clues:
        Inspect printed difference lists for exact non-matching numerical values.
    """
    parser = argparse.ArgumentParser(description="Forensically verify reconstruction determinism across multiple runs.")
    parser.add_argument(
        "--runs",
        nargs="+",
        required=True,
        help="List of run directories to compare (e.g. outputs/run1/c00a170fe1 outputs/run2/c00a170fe1)",
    )
    args = parser.parse_args()

    run_dirs = [Path(r).resolve() for r in args.runs]
    if len(run_dirs) < 2:
        print("Error: Must specify at least two run directories with --runs", file=sys.stderr)
        sys.exit(1)

    print("=" * 75)
    print("DETERMINISM VERIFICATION SUITE")
    print(f"Comparing {len(run_dirs)} runs:")
    for i, rd in enumerate(run_dirs, 1):
        print(f"  Run {i}: {rd}")
    print("=" * 75)

    all_pass = True
    all_diffs = []

    # 1. Stage 1
    s1_pass, s1_diffs, s1_data = compare_stage1(run_dirs)
    all_diffs.extend(s1_diffs)
    if not s1_pass:
        all_pass = False

    # 2. Stage 2
    s2_pass, s2_diffs, s2_data = compare_stage2(run_dirs)
    all_diffs.extend(s2_diffs)
    if not s2_pass:
        all_pass = False

    # 3. Stage 3
    s3_pass, s3_diffs, s3_data = compare_stage3(run_dirs)
    all_diffs.extend(s3_diffs)
    if not s3_pass:
        all_pass = False

    # 4. Stage 4
    s4_pass, s4_diffs, s4_data = compare_stage4(run_dirs)
    all_diffs.extend(s4_diffs)
    if not s4_pass:
        all_pass = False

    # 5. Stage 5
    s5_pass, s5_diffs, s5_data = compare_stage5(run_dirs)
    all_diffs.extend(s5_diffs)
    if not s5_pass:
        all_pass = False

    # Print summary table
    print("\nSTAGE-BY-STAGE DETERMINISM SUMMARY:")
    print("-" * 75)
    print(f"Stage 1 (Raw/Filtered Cloud & Trajectory):  {'PASS' if s1_pass else 'FAIL'}")
    print(f"Stage 2 (Floor, Walls, Inliers, Ordering): {'PASS' if s2_pass else 'FAIL'}")
    print(f"Stage 3 (Polygon, Vertices, Area, Perim):  {'PASS' if s3_pass else 'FAIL'}")
    print(f"Stage 4 (Measurements & Uncertainty):      {'PASS' if s4_pass else 'FAIL'}")
    print(f"Stage 5 (Openings & Clearance Widths):     {'PASS' if s5_pass else 'FAIL'}")
    print("-" * 75)

    if all_diffs:
        print("\nDISCREPANCIES DETECTED:")
        for d in all_diffs:
            print(f"  [X] {d}")
        print("\n" + "=" * 75)
        print("DETERMINISTIC REPLAY: FAIL")
        print("=" * 75)
        sys.exit(1)
    else:
        print("\nALL STAGES IDENTICAL ACROSS RUNS.")
        print("=" * 75)
        print("DETERMINISTIC REPLAY: PASS")
        print("=" * 75)
        sys.exit(0)


if __name__ == "__main__":
    main()
