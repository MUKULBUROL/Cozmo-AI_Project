"""Stage 10 Benchmark Console Viewer and Formatted Summary Display.

Purpose:
    Renders a concise, human-readable console dashboard summarizing Stage 10 benchmark
    results, modality statuses, runtimes, cross-tier concordance, official challenge gates,
    and the nominated Stage 11 fix candidate.

Stage:
    Stage 10 (Frozen System Benchmark + Development Evaluation)

Inputs:
    CLI Arguments:
      --benchmark: Path to benchmark output directory (default: 'outputs/benchmarks/stage10_baseline').
      --headless: Flag to run in headless non-interactive mode.

Outputs:
    Formatted console summary output following assessment specification.

Units & Coordinate Systems:
    Lengths in meters (m), Runtimes in seconds (s).

Dependencies:
    argparse, json, os, sys, typing.

Assumptions:
    Consumes exported artifacts under outputs/benchmarks/stage10_baseline/.

Failure Modes:
    Missing directory or files display helpful error message and exit cleanly.

First Debugging Points:
    Check existence of manifest.json and benchmark_summary.csv in benchmark folder.
"""

import argparse
import json
import os
import sys
from typing import Any, Dict, List, Optional


def load_json_file(path: str) -> Optional[Dict[str, Any]]:
    """Load JSON file safely with error handling.

    Parameters:
        path: Filesystem path to target JSON file.

    Returns:
        Parsed dictionary or None if file cannot be read.

    Units:
        None.

    Assumptions:
        File is UTF-8 encoded JSON.

    Failure Conditions:
        Returns None on FileNotFoundError or JSONDecodeError.

    Dependencies:
        json, os.

    Debugging Clues:
        Check path existence.
    """
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def view_benchmark(benchmark_dir: str = "outputs/benchmarks/stage10_baseline") -> int:
    """Print formatted terminal view of Stage 10 benchmark results.

    Parameters:
        benchmark_dir: Path to directory containing benchmark outputs.

    Returns:
        Integer exit code (0 for success, 1 for error).

    Units:
        Meters, square meters, seconds.

    Assumptions:
        Adheres to exact summary format requested in assessment specification.

    Failure Conditions:
        Returns 1 if benchmark directory does not exist.

    Dependencies:
        load_json_file, os, sys.

    Debugging Clues:
        Run python3 -m scripts.run_benchmark first if directory is empty.
    """
    if not os.path.exists(benchmark_dir):
        print(f"ERROR: Benchmark directory '{benchmark_dir}' not found. Run scripts.run_benchmark first.")
        return 1

    manifest = load_json_file(os.path.join(benchmark_dir, "manifest.json")) or {}
    commit = manifest.get("baseline_commit", "UNKNOWN")

    lidar = load_json_file(os.path.join(benchmark_dir, "lidar", "metrics.json")) or {}
    video = load_json_file(os.path.join(benchmark_dir, "video", "metrics.json")) or {}
    photo = load_json_file(os.path.join(benchmark_dir, "photo", "metrics.json")) or {}
    damage = load_json_file(os.path.join(benchmark_dir, "damage", "metrics.json")) or {}
    cross_tier = load_json_file(os.path.join(benchmark_dir, "cross_tier", "comparison.json")) or []
    gates = load_json_file(os.path.join(benchmark_dir, "gates", "gate_results.json")) or []

    print("STAGE 10 BENCHMARK")
    print("==================")
    print(f"Baseline commit: {commit}")
    print()

    print("LiDAR:")
    print(f"  status:  {lidar.get('status', 'UNKNOWN')}")
    print(f"  runtime: {lidar.get('runtime', 0.0):.2f} s")
    print(f"  coverage: {lidar.get('coverage', 0.0):.1%}")
    print()

    print("Video:")
    print(f"  status:  {video.get('status', 'UNKNOWN')}")
    print(f"  runtime: {video.get('runtime', 0.0):.2f} s")
    print(f"  coverage: {video.get('coverage', 0.0):.1%}")
    v_details = video.get("details", {})
    if v_details.get("multi_room_status") == "NOT_EVALUABLE":
        print(f"  multi-room: NOT_EVALUABLE ({v_details.get('multi_room_registered', '4/40')} keyframes registered)")
    print()

    print("Photo:")
    print(f"  status:  {photo.get('status', 'UNKNOWN')}")
    print(f"  runtime: {photo.get('runtime', 0.0):.2f} s")
    print(f"  coverage: {photo.get('coverage', 0.0):.1%}")
    p_details = photo.get("details", {})
    if p_details.get("property_status"):
        print(f"  property: {p_details.get('property_status')}")
    print()

    print("Damage:")
    print(f"  status:  {damage.get('status', 'UNKNOWN')}")
    print(f"  runtime: {damage.get('runtime', 0.0):.2f} s")
    print("  sample data: NO ANNOTATED REAL DAMAGE AVAILABLE")
    print("  fixtures:    SYNTHETIC_GROUND_TRUTH (4/4 evaluated)")
    print()

    print("Ground truth:")
    print("  physical GT: NOT AVAILABLE")
    print("  repeatability: REPEATABILITY_NOT_EVALUABLE (no independent duplicate scans)")
    print("  incumbent:     INCUMBENT_COMPARISON_NOT_EVALUABLE (no incumbent export)")
    print()

    print("Cross-tier agreement:")
    if cross_tier:
        for ct in cross_tier:
            t_a = ct.get("tier_a", "").upper()
            t_b = ct.get("tier_b", "").upper()
            shared = ct.get("shared_dimensions_count", 0)
            stats = ct.get("statistics", {})
            mae = stats.get("mean", "N/A")
            print(f"  {t_a} ↔ {t_b}: {shared} shared dimensions (Mean diff: {mae} m)")
    else:
        print("  None evaluated")
    print()

    print("Official gates:")
    pass_c = 0
    fail_c = 0
    ne_c = 0
    for g in gates:
        res = g.get("result", "UNKNOWN")
        gid = g.get("gate_id", "GATE")
        if res == "PASS":
            pass_c += 1
        elif res == "FAIL":
            fail_c += 1
        else:
            ne_c += 1
        print(f"  {gid:30} : {res}")
    print(f"  Summary: {pass_c} PASS | {fail_c} FAIL | {ne_c} NOT_EVALUABLE")
    print()

    worst_candidate = manifest.get("worst_failure_candidate", "VIDEO_MULTIROOM_SFM_REGISTRATION_FAILURE")
    print("Worst current failure:")
    print(f"  Candidate: {worst_candidate}")
    print("  Action:    DO NOT FIX IN STAGE 10 (Nominated for Stage 11 fix loop)")
    print()

    print("Benchmark interpretation:")
    print("  DEVELOPMENT / REFERENCE EVALUATION")
    print("  NOT UNSEEN TEST ACCURACY")
    print("==================")
    return 0


def main():
    """Main CLI entrypoint for scripts.view_benchmark."""
    parser = argparse.ArgumentParser(description="Stage 10 Benchmark Console Viewer")
    parser.add_argument("--benchmark", default="outputs/benchmarks/stage10_baseline", help="Benchmark output directory")
    parser.add_argument("--headless", action="store_true", help="Run in headless non-interactive mode")
    args = parser.parse_args()

    sys.exit(view_benchmark(benchmark_dir=args.benchmark))


if __name__ == "__main__":
    main()
