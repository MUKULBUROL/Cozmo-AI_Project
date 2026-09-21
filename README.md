# COZMO — Spatial Intelligence Engine

AI-assisted spatial reconstruction from Photos, Video, and LiDAR into measurable floor plans.

```
Capture (Photo / Video / LiDAR)
  ↓
3D Metric Reconstruction
  ↓
Structural Geometry Engine
  ↓
2D Floor Plan & Multi-Room Topology
  ↓
Deterministic Measurements & Openings
  ↓
Forensic Damage Detection & Repair Scope
  ↓
Deliverable Exports (JSON / SVG / PDF / DXF)
```

---

## Evaluator Demonstration

### 1. Interactive Web Guide
- **Live Evaluator Guide**: [http://localhost:3000/demo](http://localhost:3000/demo) (or `/evaluator-guide`)
- **Documentation**: [docs/EVALUATOR_DEMONSTRATION.md](docs/EVALUATOR_DEMONSTRATION.md)
- **Submission Index**: [docs/SUBMISSION_INDEX.md](docs/SUBMISSION_INDEX.md)

### 2. Start Servers
```bash
# Terminal 1 — Backend API (FastAPI)
python3 -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000

# Terminal 2 — Frontend Workspace (Next.js)
cd frontend && npm run dev
```

### 3. Core CLI Commands
```bash
# LiDAR Reconstruction (Sample scan)
python3 scripts/reconstruct_lidar.py --scan 1a8384c3f6 --archive "sample data/single_scan_floor_only.zip" --voxel-size 0.02

# Monocular Video Reconstruction
python3 scripts/reconstruct_video.py --archive "sample data/single_room.zip" --scan c00a170fe1 --capture-id video_rec_01 --max-keyframes 30

# Multi-View Photo Reconstruction
python3 scripts/reconstruct_photos.py --input "data/photo_dev/single_room" --capture-id photo_rec_01

# Multi-Room Drift Optimization & Property Export
python3 scripts/reconstruct_property.py --scan c7d28f72c6 --archive "sample data/single_scan_with_ceiling.zip" --headless

# Forensic Damage & Repair Scope
python3 scripts/analyze_damage.py --capture-id c00a170fe1
```

---

## The Problem We Were Given

Reconstruct metric architectural properties from three vastly different capture tiers:

| Input Tier | Input Characteristics | Core Reconstruction Challenge |
|---|---|---|
| **PHOTO** | 2–8 still photos, no sensor depth, no poses | Extreme view disparity; metric scale is fundamentally ambiguous without reference |
| **VIDEO** | Continuous monocular RGB walkthrough | Motion blur, camera trajectory drift; metric scale must be recovered |
| **LiDAR** | Synchronized RGB + metric depth + odometry poses + camera intrinsics | Dense point clouds; sensor noise, drift across multiple rooms |

Required Outputs:
- Closed room polygons, wall vectors, and multi-room topological connectivity
- Metric room dimensions (wall lengths, floor area, perimeter, ceiling height)
- Architectural openings (doors, doorways, windows) with clearance width
- Visible damage detection, 3D extent estimation, concealed rule triggers, and itemized repair scope
- Multi-format deliverable exports: JSON, SVG, PDF, and DXF CAD

---

## The Key Architectural Principle

> **AI tells us WHAT something is.**
> **Geometry tells us WHERE it is and HOW BIG it is.**

- **YOLO-World / Neural Vision**: *"This is a doorway"* or *"This is a water stain"*.
- **Geometry Engine**: *"This doorway measures 0.80 m on Wall 3"* or *"This water stain covers 1.42 m² on the ceiling"*.

No LLM or vision model ever guesses or hallucinates physical dimensions. All numbers stem strictly from 3D point cloud rays, plane intersections, and polygon math.

---

## Why We Built One Common Geometry Engine

Instead of building three disconnected pipelines with duplicated math, COZMO standardizes on a unified representation:

```
PHOTO ──→ Multi-View SfM + Depth ───┐
                                     │
VIDEO ──→ Keyframe SfM + Depth ─────┤
                                     ├──→ UNIFIED METRIC 3D POINT CLOUD
LiDAR ──→ Depth Fusion + Odometry ──┘
                                              ↓
                                   COMMON GEOMETRY ENGINE
                                 (RANSAC Planes → Polygon Math)
                                              ↓
                                    CANONICAL PROPERTY MODEL
                                              ↓
                                  JSON / SVG / PDF / DXF EXPORTS
```

- **One Geometry Engine**: Same RANSAC wall extraction, polygon closure, and measurement routines.
- **One Output Contract**: Single data schema for UI visualization and exports.
- **Less Duplication**: Faster test cycles, zero divergence in calculation logic.

---

## How We Built It — The Project Journey

### Stage A — Inspect the Real Sensor Data
We started by inspecting the raw captures: RGB frames, synchronized metric depth, confidence masks, camera intrinsics, and 6-DoF odometry.
*Key Insight*: The provided sample data contains metric sensor readings, but does *not* include certified physical tape/laser ground truth.

### Stage B — LiDAR First
LiDAR provided the cleanest path to reliable 3D geometry: unprojecting depth pixels with camera intrinsics and fusing frames along camera trajectories into metric point clouds.

### Stage C — Structural Geometry
Using Open3D RANSAC and Shapely polygon algorithms, we extracted dominant horizontal planes (floor, ceiling) and vertical planes (walls). Projecting vertical wall planes onto the floor plane yielded 2D closed room polygons.

### Stage D — Deterministic Measurements
Wall lengths, perimeter, floor area, and ceiling heights are computed directly from polygon vertices and plane boundaries. Statistical 95% uncertainty intervals are propagated through covariance models.

### Stage E — Openings
Zero-shot YOLO-World detects candidate doors and windows in 2D keyframes. The geometry engine unprojects bounding box jambs into 3D, associates them with adjacent wall planes, and computes metric clearance widths.

### Stage F — Multi-Room Drift Optimization
Walking through multiple rooms accumulates trajectory drift. We introduced pose graph optimization with loop closure detection (ICP + spatial proximity validation), demonstrating internal loop residual reduction.

### Stage G — Handheld Video
We built an RGB-only video pipeline: motion-spaced keyframe extraction, feature matching, Structure-from-Motion (SfM), and monocular metric depth estimation, feeding the shared geometry engine.

### Stage H — Room Photos
With only 2–8 still photos, photos represent the hardest challenge due to metric scale ambiguity. The photo pipeline performs feature matching, sparse SfM, and relative-to-metric scaling prior to polygon extraction.

### Stage I — Forensic Damage & Repair Scope
YOLO-World identifies defect candidates (cracks, water stains, mold, holes). 3D plane projection measures damaged surface area. A deterministic rule engine checks for concealed damage (e.g. electrical/insulation risks behind water stains) and outputs itemized repair scopes.

### Stage J — Stage 11 Fix Loop & Iterative Improvements
Through targeted diagnostic engineering:
- **Video Multi-Room Registration**: Improved from 4 / 40 frames on baseline to 31 / 40 registered frames after keyframe filtering, focal estimation, and mapper retries.
- **Impact**: Demonstrated substantial engineering progress on challenging video trajectories.

### Stage K — Product & Inspection Layer
FastAPI backend + Next.js frontend delivers an interactive inspection workspace: live upload, status polling, 2D vector canvas inspection, damage overlays, and instant deliverable exports.

---

## What Works Today

- [x] **Full LiDAR Pipeline**: End-to-end ingestion to deliverable exports.
- [x] **Monocular Video Pipeline**: Keyframe SfM, depth estimation, and polygon construction.
- [x] **Photo Pipeline**: Multi-view feature matching and honest fallback handling.
- [x] **Multi-Room Segmentation & Drift Optimization**: Pose-graph loop closures.
- [x] **Architectural Openings**: Semantic detection + metric jamb measurement.
- [x] **Forensic Damage Engine**: Candidate detection, 3D extent, concealed rules, and repair scope.
- [x] **Calculated Uncertainty Bounds**: 95% intervals on all dimensions.
- [x] **REST API & Next.js UI**: Live capture upload, processing monitor, vector plan canvas.
- [x] **Multi-Format Exports**: JSON, SVG, PDF, and DXF CAD.
- [x] **Deterministic Replay**: Same input yields identical, verifiable outputs.
- [x] **Evaluator Guide**: Responsive UI with one-click copy commands at `/demo`.

---

## What We Proved vs What Remains Unverified

### Proven
- Complete, working end-to-end software pipeline across all stages.
- Fresh uploads process reliably without fixture substitution.
- Same input generates bit-for-bit or numerically identical results across runs.
- Multi-format exports (JSON, SVG, PDF, DXF) generate valid, spec-compliant files.
- Full test suite passes cleanly across backend and frontend.
- Pose-graph optimization measurably reduces trajectory loop closure residuals.

### Not Physically Proven Without Independent Ground Truth
- Absolute physical wall length error (<1.0% gate) — *Requires physical laser disto ground truth*.
- Opening width error (≤2 cm gate) — *Requires physical tape measurements*.
- Ceiling height error (≤1.5 cm gate) — *Requires physical height verification*.
- Physical repeatability — *Requires repeated physical scans of unchanged rooms*.
- Uncertainty calibration — *Requires ground-truth error distribution comparison*.
- Incumbent scanner comparison — *Awaiting parallel commercial scanner captures*.

---

## Project Structure

```
CozmoAIProject/
├── backend/
│   ├── app/
│   │   ├── api/             # FastAPI REST endpoints & job queue
│   │   ├── benchmark/       # Accuracy metrics & gate evaluators
│   │   ├── damage/          # Defect inference & 3D wall projection
│   │   ├── export/          # JSON, SVG, PDF, and DXF exporters
│   │   ├── geometry/        # Polygon extraction, RANSAC, & SLAM
│   │   ├── measurements/    # Wall dimensions, openings, & confidence
│   │   ├── models/          # Domain schemas & data contracts
│   │   └── pipelines/       # LiDAR, Video, and Photo orchestrators
│   └── tests/               # Pytest suite (196 automated tests)
│
├── frontend/
│   ├── src/
│   │   ├── app/             # Next.js App Router pages (/demo, /property, /new)
│   │   ├── components/      # UI, FloorPlan canvas, & Inspector
│   │   ├── domain/          # View models & contract adapters
│   │   ├── geometry/        # SVG projection & label collision
│   │   └── lib/             # API client & export handlers
│   └── tests/               # Frontend test suite (64 unit tests)
│
├── weights/
│   └── yolov8s-worldv2.pt   # Local YOLO-World model checkpoint (25.9 MB)
│
├── scripts/                 # CLI pipelines & benchmark runners
├── docs/                    # Architecture, reports, compliance matrix, & guides
├── benchmark/               # Benchmark suites, manifest, & results
├── outputs/                 # Benchmark summaries & fix-loop evidence
├── sample data/             # Sample LiDAR capture archives
└── data/                    # Development fixtures & dev photo sets
```

---

## Verification & Testing

```bash
# Backend Test Suite (196 Tests)
python3 -m pytest backend/tests

# Dataset Validation & Code Compilation
python3 -m scripts.validate_dataset
python3 -m compileall -q backend scripts

# Model Smoke Test
python3 scripts/smoke_test_damage_model.py

# Frontend Test Suite & Production Build
cd frontend
npm run lint
npm run typecheck
npm test
npm run build
cd ..
```

---

## Core Philosophy

**COZMO is not:**
$$\text{Image} \longrightarrow \text{Black-Box AI} \longrightarrow \text{Guessed Dimensions}$$

**COZMO is:**
$$\text{Sensor Data} \longrightarrow \text{3D Metric Reconstruction} \longrightarrow \text{Rigorous Geometry} \longrightarrow \text{Exact Measurements}$$

*AI is applied exclusively where semantic understanding is needed (identifying doors, windows, and damage), while physical dimensions remain strictly governed by the laws of 3D geometry.*
