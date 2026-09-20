# Stage 10.2 Deterministic Reconstruction & Baseline Freezing Report

## 1. Purpose

In structural engineering, robotic reconstruction, and automated damage assessment, deterministic replay is a fundamental prerequisite for regression testing, validation gating, and scientific credibility. Given identical sensor input:
```
SAME RAW INPUT
       ↓
SAME RECONSTRUCTION
       ↓
SAME WALLS
       ↓
SAME POLYGON
       ↓
SAME MEASUREMENTS
       ↓
SAME OPENINGS
```
Without deterministic replay, architectural geometries, surface inlier counts, wall segment counts, room polygons, and computed clearances fluctuate between consecutive runs of the exact same sensor data, corrupting downstream evaluations and rendering automated benchmark suites inconclusive.

---

## 2. Root Cause Analysis

Forensic investigation in Stage 10.1 and confirmed in Stage 10.2 identified two compounded sources of non-determinism during Stage 2 structural plane extraction:

1. **Unseeded Random Number Generation in Open3D C++ RANSAC**:
   `backend/app/geometry/plane_detection.py` invokes `pcd.segment_plane(...)`. Open3D implements random sample consensus (RANSAC) via an internal pseudorandom number generator. Because no random seed was initialized prior to extraction, different random triplets were selected across runs, yielding varying plane inliers.

2. **OpenMP Multi-Threaded Candidate Race Conditions**:
   Open3D's C++ RANSAC implementation evaluates hypotheses across an OpenMP thread pool (defaulting to the host CPU core count, e.g., 12 threads). Non-deterministic thread scheduling, work-stealing, and thread completion order caused different hypotheses to be evaluated in different sequences, creating variance even when pseudorandom seeds were partially initialized.

Because structural plane extraction is iterative (each detected plane has its inliers subtracted before the next plane search), small perturbations in the first RANSAC fit cascade into:
- different remaining point clouds
- different wall candidates
- different parallel wall merges
- different 2D corner graph topology
- different closed room cycles
- different room polygon vertices, area, and perimeter

---

## 3. Centralized Fix Implementation

A centralized determinism infrastructure was introduced in [`backend/app/core/determinism.py`](file:///wsl.localhost/Ubuntu/home/devcontainers/Projects/Active/CosmoAIProject/backend/app/core/determinism.py):

1. **RNG Seeding**:
   - Python `random.seed(seed)`
   - NumPy `np.random.seed(seed)`
   - Open3D RNG `open3d.utility.random.seed(seed)`
   - Environment variable `PYTHONHASHSEED = str(seed)`

2. **Thread Pinning**:
   - Open3D thread pool pinned to single-thread execution: `open3d.utility.set_max_threads(1)`
   - Environment variables set: `OMP_NUM_THREADS=1`, `OPENBLAS_NUM_THREADS=1`, `MKL_NUM_THREADS=1`

3. **Pipeline Integration**:
   - `StructuralConfig` updated with `random_seed: int = 42` and `deterministic_mode: bool = True`.
   - `extract_structure` calls `configure_determinism(config.random_seed)` before any RANSAC extraction begins.
   - CLI script `scripts/extract_structure.py` updated with `--seed 42` (default 42).
   - Artifacts `structure.json` and `extraction_stats.json` record `random_seed` and `deterministic_mode`.

4. **Zero Algorithm Tuning**:
   - No RANSAC distance thresholds, normal radii, minimum inlier thresholds, angular merge limits, or polygon scoring heuristics were altered.
   - Seed 42 was predeclared and frozen without seed-shopping.

---

## 4. Reproduction Commands

All three runs were executed completely independently from `sample data/single_room.zip` for scan `c00a170fe1`:

```bash
# Stage 1: LiDAR Reconstruction
python3 -m scripts.reconstruct_lidar \
    --scan c00a170fe1 \
    --archive "sample data/single_room.zip" \
    --output-dir outputs/determinism_run_X/c00a170fe1

# Stage 2: Structural Plane Extraction (Deterministic Seed 42)
python3 -m scripts.extract_structure \
    --scan c00a170fe1 \
    --ply-path outputs/determinism_run_X/c00a170fe1/baseline_filtered.ply \
    --output-dir outputs/determinism_run_X/c00a170fe1/structure \
    --seed 42

# Stage 3: 2D Wall Projection & Room Polygon Extraction
python3 -m scripts.build_room_polygon \
    --scan c00a170fe1 \
    --outputs-root outputs/determinism_run_X

# Stage 4: Metric Measurements & Uncertainty Propagation
python3 -m scripts.measure_room \
    --scan c00a170fe1 \
    --outputs-root outputs/determinism_run_X \
    --seed 42

# Stage 5: Structural Opening Detection & Clearance Measurement
python3 -m scripts.detect_openings \
    --scan c00a170fe1 \
    --outputs-root outputs/determinism_run_X
```

---

## 5. Three-Run Verification Results

Automated comparison across all three fresh runs using [`scripts/verify_determinism.py`](file:///wsl.localhost/Ubuntu/home/devcontainers/Projects/Active/CosmoAIProject/scripts/verify_determinism.py):

```bash
python3 -m scripts.verify_determinism \
    --runs \
      outputs/determinism_run_1/c00a170fe1 \
      outputs/determinism_run_2/c00a170fe1 \
      outputs/determinism_run_3/c00a170fe1
```

### Forensic Comparison Matrix

| Metric / Artifact | Run 1 | Run 2 | Run 3 | Match Status |
|---|---:|---:|---:|---|
| **Raw Fused Points** | 15,189,493 | 15,189,493 | 15,189,493 | **PASS** (Exact) |
| **Filtered Cloud Points** | 408,108 | 408,108 | 408,108 | **PASS** (Exact) |
| **Trajectory Length** | 14.404 m | 14.404 m | 14.404 m | **PASS** (Exact) |
| **Floor Detected** | True | True | True | **PASS** (Exact) |
| **Floor Inliers** | 68,652 | 68,652 | 68,652 | **PASS** (Exact) |
| **Floor RMSE** | 0.0129 m | 0.0129 m | 0.0129 m | **PASS** (Exact) |
| **Ceiling Detected** | False | False | False | **PASS** (Exact) |
| **Raw Vertical Planes** | 14 | 14 | 14 | **PASS** (Exact) |
| **Accepted Walls** | 14 | 14 | 14 | **PASS** (Exact) |
| **Consolidated Walls** | 10 | 10 | 10 | **PASS** (Exact) |
| **Wall IDs Sequence** | wall_01 .. wall_10 | wall_01 .. wall_10 | wall_01 .. wall_10 | **PASS** (Exact) |
| **Polygon Validity** | Valid & Closed | Valid & Closed | Valid & Closed | **PASS** (Exact) |
| **Polygon Vertices** | 8 | 8 | 8 | **PASS** (Exact) |
| **Polygon Area** | 7.554 m² | 7.554 m² | 7.554 m² | **PASS** (Exact) |
| **Polygon Perimeter** | 11.055 m | 11.055 m | 11.055 m | **PASS** (Exact) |
| **Measured Floor Area** | 7.554 m² | 7.554 m² | 7.554 m² | **PASS** (Exact) |
| **Floor Area 95% CI** | [7.349, 7.784] m² | [7.349, 7.784] m² | [7.349, 7.784] m² | **PASS** (Exact) |
| **Measured Perimeter** | 11.055 m | 11.055 m | 11.055 m | **PASS** (Exact) |
| **Perimeter 95% CI** | [10.907, 11.298] m | [10.907, 11.298] m | [10.907, 11.298] m | **PASS** (Exact) |
| **Measurement Status** | Provisional | Provisional | Provisional | **PASS** (Exact) |
| **Accepted Openings** | 1 | 1 | 1 | **PASS** (Exact) |
| **Opening 1 Wall Assignment** | wall_02 | wall_02 | wall_02 | **PASS** (Exact) |
| **Opening 1 Clearance Width**| 1.5682 m | 1.5682 m | 1.5682 m | **PASS** (Exact) |
| **Opening 1 95% CI** | [1.4949, 1.6415] m | [1.4949, 1.6415] m | [1.4949, 1.6415] m | **PASS** (Exact) |

---

## 6. Critical Engineering Distinction

> [!IMPORTANT]
> ### DETERMINISTIC REPLAY vs. PHYSICAL REPEATABILITY
>
> - **DETERMINISTIC REPLAY (`PASS`)**:
>   Processing the **exact same raw capture** repeatedly with fixed configuration produces byte-identical point clouds, identical plane extractions, identical room polygons, and identical measurements.
>
> - **PHYSICAL REPEATABILITY (`NOT_EVALUABLE`)**:
>   Processing **independent physical captures** of the same real-world room (e.g., Scan A vs. Scan B taken on different walks) produces measurements within the challenge's 1 cm / 0.5% tolerance gate.
>
> Stage 10.2 definitively solves and verifies **DETERMINISTIC REPLAY**.
> It does **NOT** claim the official challenge physical repeatability gate, which remains `NOT_EVALUABLE` until independent duplicate captures with ground-truth laser measurements are provided.

---

## 7. Canonical Baseline Freezing

In accordance with Stage 10.2 acceptance criteria:
- `outputs/determinism_run_1/c00a170fe1` is selected as the canonical baseline because it represents the first execution using the predeclared canonical seed (42).
- The resulting canonical metrics (Area: 7.554 m², Perimeter: 11.055 m, 10 merged walls, Doorway: 1.568 m on wall_02) are frozen into `outputs/c00a170fe1/` and benchmark provenance documentation.
- The previous unseeded stochastic numbers (6.998 m², 7.296 m², 3.392 m²) are superseded by the canonical seeded baseline.
