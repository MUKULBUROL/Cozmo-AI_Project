# COZMO — Evaluator Demonstration Guide

This guide provides instructions to evaluate the complete COZMO spatial reconstruction platform either through direct command-line execution (Backend-Only) or through the interactive web application (Frontend).

---

## 1. Quick Overview

**COZMO reconstructs measurable floor plans from LiDAR captures, handheld video, or room photos.**

You can evaluate the system in two ways:
1. **Backend Only**: Run reconstruction directly from the command line and inspect raw artifacts in `outputs/`.
2. **Frontend**: Upload a capture through the COZMO web interface at `http://localhost:3000` and inspect interactive results.

---

## 2. Choose Evaluation Method

| Evaluation Method | Best For | Primary Interface |
|---|---|---|
| **Backend Only** | Direct pipeline testing, deterministic reproducibility, inspecting point clouds & JSON schemas, automated benchmarking | Terminal CLI |
| **Frontend** | End-to-end user experience, upload flow, interactive 2D floor plans, wall dimension inspector, PDF/DXF exports | Web Browser (`localhost:3000`) |

---

## 3. Backend-Only Demonstration

This route runs COZMO directly from the command line and writes reconstruction artifacts to the `outputs` directory.

### Step 1 — Setup
```bash
git clone https://github.com/MUKULBUROL/Cozmo-AI_Project.git
cd Cozmo-AI_Project

python3 -m venv .venv
source .venv/bin/activate

pip install -e .
```

### Step 2 — Available Sample Data
The assessor-provided samples are stored in `sample data/`:
- `sample data/single_room.zip`: Single-room sensor capture containing RGB video, LiDAR depth, confidence maps, camera poses, intrinsics, and IMU.
- `sample data/single_scan_floor_only.zip`: Larger floor-focused sensor capture.
- `sample data/single_scan_with_ceiling.zip`: Multi-room / whole-property capture with ceiling observations.

> **Important Notice**: These files contain metric sensor inputs (depth streams and odometry poses), not independent laser/tape ground truth.

### Step 3 — LiDAR Reconstruction Demo
Run metric reconstruction on the floor-only sample:
```bash
python3 scripts/reconstruct_lidar.py --scan 1a8384c3f6 --archive "sample data/single_scan_floor_only.zip" --voxel-size 0.02
```

Or run the multi-room whole-property pipeline with loop closure and drift correction:
```bash
python3 scripts/reconstruct_property.py --scan c7d28f72c6 --archive "sample data/single_scan_with_ceiling.zip" --headless
```

**Expected outputs generated**:
- Point cloud (`outputs/1a8384c3f6/pointcloud.ply`)
- Trajectory and structural planes (`outputs/1a8384c3f6/structures.json`)
- Wall geometry and room/property model (`outputs/c7d28f72c6/property/property.json`)
- Measurements & openings (`outputs/1a8384c3f6/measurements.json`)
- Diagnostic SVGs (`outputs/c7d28f72c6/property/drift_ablation.svg`)

### Step 4 — Video Reconstruction Demo
Run monocular walkthrough reconstruction using RGB video only:
```bash
python3 scripts/reconstruct_video.py --archive "sample data/single_room.zip" --scan c00a170fe1 --capture-id video_rec_01 --max-keyframes 30
```

**Pipeline Stages (RGB Only)**:
```
RGB frames
→ Feature matching & camera pose reconstruction
→ Metric depth estimation
→ Metric point cloud
→ Shared geometry engine
→ Floor plan
```
*Notice: Video reconstruction operates strictly on RGB imagery and does not utilize LiDAR depth streams or odometry poses.*

### Step 5 — Photo Reconstruction Demo
Run reconstruction from a folder of overlapping room still photos:
```bash
python3 scripts/reconstruct_photos.py --input "data/photo_dev/sample_room" --capture-id photo_rec_01
```
*Expected input structure*: 2–8 still images per room (e.g. `photos/room_01/image1.jpg`, `image2.jpg`, `image3.jpg`).
*Data Integrity Note*: Real photo inputs are clearly distinguished from development photo sets extracted from supplied video. Development sets extracted from video are explicitly labeled.

### Step 6 — Backend Outputs
| Output Category | Path Pattern | Description |
|---|---|---|
| **Point Cloud** | `outputs/<id>/pointcloud.ply` | Downsampled 3D metric point cloud |
| **Structural Planes** | `outputs/<id>/structures.json` | RANSAC floor, ceiling, and wall planes |
| **Measurements** | `outputs/<id>/measurements.json` | Wall lengths and 95% confidence intervals |
| **Property JSON** | `outputs/<id>/property/property.json` | Complete schema with rooms, walls, openings |
| **Diagnostic SVG** | `outputs/<id>/property/drift_ablation.svg` | Trajectory comparison and pose graph loop residuals |
| **Benchmark Artifacts** | `benchmark/results/metrics.json` | Computed accuracy metrics and challenge gate summaries |

---

## 4. Frontend Demonstration

This route evaluates the complete COZMO product workflow.

### Step 1 — Start Backend API Server
```bash
python3 -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
```
- Backend Health Check: `http://localhost:8000/api/health`
- Interactive API Docs: `http://localhost:8000/docs`

### Step 2 — Start Frontend Workspace
```bash
cd frontend
npm ci
npm run dev
```
Open in browser: `http://localhost:3000`

### Step 3 — Upload a Capture
Follow the UI workflow:
```
Home → New Capture → Choose LiDAR, Video, or Photos → Choose File → Process Capture
```
For LiDAR demonstration, recommend uploading `sample data/single_room.zip` or `sample data/single_scan_with_ceiling.zip`.

### Step 4 — Processing Lifecycle
During processing the UI shows progress through clear states:
```
Queued → Processing → Complete
```
(or honest limitation/failure states if input is insufficient).

### Step 5 — Inspect Reconstructed Property
On the workspace page (`/property/<id>`), the evaluator can inspect:
- **Floor Plan**: 2D vector drawing with zoom and pan
- **Rooms & Walls**: Interactive polygons & metric dimensions (click room to inspect)
- **Ceiling Height**: Estimated vertical span (if observed)
- **Openings**: Doorways and windows detected
- **Damage & Scope**: Classified defects and suggested repairs
- **Exports**: JSON, SVG, PDF, and DXF downloads

---

## 5. Sample Data Table

| File | Type | Best Demo Use | Expected Notes |
|---|---|---|---|
| `single_room.zip` | LiDAR sensor archive | Quick end-to-end demo | Ceiling may be unobserved depending on capture geometry |
| `single_scan_floor_only.zip` | LiDAR sensor archive | Floor-focused reconstruction / property demonstration | Ceiling expected unavailable |
| `single_scan_with_ceiling.zip` | LiDAR multi-room sensor archive | Multi-room, drift, ceiling demonstration | Best structural/multi-room example |

---

## 6. Understanding the Results

- **ROOMS**: Distinct spaces reconstructed from the capture.
- **WALL LENGTH**: Metric distance between reconstructed wall endpoints.
- **AREA**: Area enclosed by the reconstructed floor polygon.
- **PERIMETER**: Sum of reconstructed room boundary lengths.
- **CEILING HEIGHT**: Estimated vertical distance between detected floor and ceiling planes.
- **OPENING**: Detected doorway/window associated with a wall and measured using 3D geometry.
- **DAMAGE FINDING**: Visible defect classified from RGB imagery and associated with a surface.
- **SCOPE ITEM**: Suggested repair/action generated from detected damage and surface association.

---

## 7. Understanding Statuses

- **COMPLETE**: The pipeline produced a usable reconstruction.
- **PROVISIONAL**: A reconstruction was produced, but one or more stages have limited evidence or reliability.
- **NOT_EVALUABLE**: The available input was insufficient to produce a trustworthy measurement/result.
- **FAILED**: The reconstruction pipeline could not complete.
- **PROCESSING**: The capture is currently being processed.

> **Important Distinction**: Pipeline status describes whether COZMO produced a usable result. It does not by itself prove physical accuracy against independent ground truth.

---

## 8. Measurement & Uncertainty Explanation

- **Nominal Measurement** (e.g. `3.42 m`): Fitted geometric endpoint-to-endpoint distance.
- **Estimated Range** (e.g. `3.39–3.45 m`): The range represents the reconstruction's estimated uncertainty around the measurement based on point cloud variance and plane fitting residuals.

> **Note**: These ranges are currently uncalibrated against independent laser/tape ground truth.

---

## 9. Understanding Drift & Drift Correction

- **What is drift?**: As the camera moves through multiple rooms, small pose errors accumulate over time, distorting the final multi-room property layout.
- **What COZMO does**: COZMO executes Point-to-Plane ICP loop closure and global pose graph optimization to reconcile accumulated trajectory errors across revisit loops.
- **Drift ablation**: We compare reconstruction behavior with drift correction enabled and disabled (e.g. `outputs/c7d28f72c6/property/drift_ablation.svg`).

> **Note**: Internal loop residual minimization measures geometric closure consistency across scans; it is not the same as physical wall accuracy against independent laser ground truth.

---

## 10. Reproducibility & Determinism

In verified reproducibility verification, the same supplied sample archives were uploaded twice through the live website. Fresh Upload A and Fresh Upload B produced identical meaningful geometry and results.

- **What this proves**: Deterministic pipeline processing and state consistency.
- **What this does NOT prove**: Physical measurement accuracy against real-world walls.

*No fixture substitution is used during these verification runs; all outputs are computed live.*

---

## 11. Export Formats

All exports are generated dynamically from the same current property result:
- **JSON**: Structured machine-readable reconstruction data with rooms, walls, openings, and 95% intervals.
- **SVG**: Standalone 2D vector architectural floor plan with metric coordinates.
- **PDF**: Multi-page readable inspection report with cover card, dimension schedules, and repair scope.
- **DXF**: CAD-compatible geometry export (Layered Release-12 standard for `WALLS`, `OPENINGS`, `DIMENSIONS`).

---

## 12. What Does Each Evaluation Prove?

| Evaluation Target | Core Question | Required Evidence | Current Honest Status |
|---|---|---|---|
| **Reproducibility** | Does the same input produce the same result? | Fresh Live Upload A vs Fresh Live Upload B | **PROVEN** (Identical geometry on identical inputs) |
| **Determinism** | Does internal pipeline randomness change geometry? | Repeated seed and processing runs | **PROVEN** (Zero drift on repeated fixed-seed runs) |
| **Drift Ablation** | Does drift correction improve multi-room consistency? | Trajectory comparison with/without loop closure | **VERIFIED** (Residual drop demonstrated on multi-room capture) |
| **Pipeline Tests** | Can each input tier produce a reconstruction? | LiDAR, Video (RGB-only), and Photo pipeline runs | **VERIFIED** (All 3 pipelines produce floor plans) |
| **Physical Accuracy** | How close are measurements to the real room? | Independent laser disto / steel tape ground truth | **NOT EVALUABLE** (Laser GT not provided in sample data) |
| **Repeatability** | Do two genuinely separate captures match? | Two independent physical walkthroughs of same room | **PENDING CAPTURE** (Requires 2 separate physical passes) |
| **Incumbent Comparison** | How does COZMO compare against another app? | Same physical room scanned with incumbent app + GT | **PENDING SCAN** (Benchmarking harness configured) |
| **Damage Benchmark** | Does pipeline detect and classify defects? | Defect fixture set with 3D projection | **SYNTHETIC DEV** (Tested against synthetic development benchmark) |

---

## 13. Result Status vs Benchmark Status

- **Result Status: COMPLETE** → Means: A usable architectural floor plan was produced successfully from the available input sensor data.
- **Benchmark Status: NOT_EVALUABLE** → Means: Physical accuracy could not be mathematically scored because independent laser/tape ground truth was not provided.

*These statuses are fully complementary: the software pipeline succeeded (COMPLETE), while the physical accuracy validation gate remains honestly unverified (NOT_EVALUABLE).*

---

## 14. 5-Minute Evaluator Quick Test

### Option A: Frontend (UI Flow)
1. Start backend: `python3 -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000`
2. Start frontend: `cd frontend && npm run dev`
3. Open `http://localhost:3000` in browser
4. Click **New Capture** in top header
5. Select **LiDAR** capture tier
6. Choose file `sample data/single_room.zip`
7. Click **Process Capture**
8. Watch processing status transition to Complete
9. Click into the reconstructed room to inspect wall dimensions
10. Click **Export** to download PDF inspection report

### Option B: Backend (CLI Flow)
1. Activate environment: `source .venv/bin/activate`
2. Run single-room reconstruction:
   ```bash
   python3 scripts/reconstruct_lidar.py --scan c00a170fe1 --archive "sample data/single_room.zip" --voxel-size 0.02
   ```
3. Inspect generated geometry: `outputs/c00a170fe1/measurements.json`
4. Open generated floor plan: `outputs/c00a170fe1/structure_debug.svg`
5. Review nominal wall lengths and estimated uncertainty intervals

---

## 15. Known Limitations & Absolute Honesty Statement

1. **No Independent Laser GT**: Assessor sample data does not include certified laser/tape ground truth; all physical accuracy gates are marked `NOT_EVALUABLE`.
2. **Photo Capture Format**: Supplied archives do not contain native 2–8 still-photo capture sets; development evaluations used extracted still images and are explicitly labeled.
3. **Reflective Surfaces**: Glass walls, mirrors, and deep shadows can introduce depth gaps or noisy RANSAC planes.
4. **Low-Texture Scenes**: Video and photo SfM pipelines require sufficient visual feature texture for reliable camera pose estimation.
5. **Ceiling Height Observation**: Ceiling height estimation requires the sensor camera pitch to have observed the physical ceiling plane during the capture trajectory.
6. **Uncertainty Calibration**: Physical uncertainty ranges represent reconstruction variance and are uncalibrated against independent ground truth.

---

## 16. Quick Verification Checklist

- [x] Backend API health check responds at `http://localhost:8000/api/health`
- [x] Frontend loads and renders workspaces at `http://localhost:3000`
- [x] CLI reconstruction scripts execute cleanly and output JSON, SVG, and DXF
- [x] Live upload workflow transitions from Queued → Processing → Complete
- [x] Exports (JSON, SVG, PDF, DXF) generate cleanly from reconstructed properties
