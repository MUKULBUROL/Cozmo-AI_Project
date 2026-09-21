# COZMO

COZMO reconstructs floor plans and property measurements from:

- LiDAR captures
- handheld video
- room photos

It generates:

- interactive floor plans
- room measurements
- openings
- damage findings
- repair scope
- JSON / SVG / PDF / DXF exports

---

## Quick Start

### 1. Start Backend API
```bash
python3 -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
```
Health Check: `http://localhost:8000/api/health`

### 2. Start Frontend Workspace
```bash
cd frontend
npm run dev
```
Open in browser:
```
http://localhost:3000
```

### 3. Evaluator Workflow
1. Click **New Capture**
2. Choose **LiDAR**, **Video**, or **Photos**
3. Upload the supported capture
4. Wait for processing
5. Review the property plan
6. Export the result

---

## Installation & Setup

```bash
# Clone repository
git clone https://github.com/MUKULBUROL/Cozmo-AI_Project.git
cd Cozmo-AI_Project

# Setup Python environment
python3 -m venv .venv
source .venv/bin/activate
pip install -e .

# Setup Frontend dependencies
cd frontend
npm ci
cd ..
```

---

## Supported Inputs

| Capture Type | Recommended Hardware / Format | Description |
|---|---|---|
| **LiDAR** | iPhone Pro (12 Pro–16 Pro) ZIP archive | Direct metric depth frames with odometry poses |
| **Video** | Handheld 60 FPS MP4 / MOV | Monocular walkthrough with keyframe feature tracking |
| **Photos** | 2–8 overlapping JPG/PNG photos | Multi-view perspective room images |

---

## Deliverable Outputs

| Format | Deliverable | Description |
|---|---|---|
| **JSON** | Property JSON (`.json`) | Machine-readable schema with rooms, walls, openings, damages, and 95% intervals |
| **SVG** | Vector Floor Plan (`.svg`) | Standalone 2D vector architectural drawing with metric coordinates |
| **PDF** | Inspection Report (`.pdf`) | Multi-page report with cover card, dimension schedules, and repair scope |
| **DXF** | CAD Drawing (`.dxf`) | Release-12 layered CAD format (`WALLS`, `OPENINGS`, `DIMENSIONS`, `DAMAGE`) |

---

## CLI Usage (One-Command Workflows)

Run individual reconstruction pipelines from the terminal:

### LiDAR Reconstruction
```bash
python3 scripts/reconstruct_lidar.py --scan 1a8384c3f6 --archive "sample data/single_scan_floor_only.zip" --voxel-size 0.02
```

### Video Reconstruction
```bash
python3 scripts/reconstruct_video.py --archive "sample data/single_room.zip" --scan c00a170fe1 --capture-id video_rec_01 --max-keyframes 30
```

### Photo Reconstruction
```bash
python3 scripts/reconstruct_photos.py --input "data/photo_dev/sample_room" --capture-id photo_rec_01
```

### Multi-Room Property Pipeline & Exports
```bash
python3 scripts/reconstruct_property.py --scan c7d28f72c6 --archive "sample data/single_scan_with_ceiling.zip" --headless
```

### Forensic Damage & Scope Analysis
```bash
python3 scripts/analyze_damage.py --fixture-set "data/damage_dev/SYNTHETIC_DEVELOPMENT_DAMAGE_SET.json"
```

---

## Project Structure

```
CozmoAIProject/
├── README.md
├── pyproject.toml
├── .gitignore
│
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
│   ├── package.json
│   ├── .env.example
│   ├── src/
│   │   ├── app/             # Next.js App Router pages
│   │   ├── components/      # UI, FloorPlan canvas, & Inspector
│   │   ├── domain/          # View models & contract adapters
│   │   ├── geometry/        # SVG projection & label collision
│   │   └── lib/             # API client & export handlers
│   └── tests/               # Frontend Node test suite (59 unit tests)
│
├── scripts/                 # CLI pipelines & benchmark runners
├── docs/                    # Architecture, reports, & specifications
├── benchmark/               # Benchmark suites, manifest, & results
├── outputs/                 # Benchmark summaries & fix-loop evidence
└── data/                    # Development fixtures & ground-truth schemas
```

---

## Benchmark Suite

Run the final benchmark and gate evaluation suite:
```bash
python3 scripts/run_final_benchmark.py
```

Generated benchmark artifacts:
- `benchmark/results/metrics.json`
- `benchmark/results/gate_results.json`
- `benchmark/results/summary.csv`
- `docs/FINAL_BENCHMARK_REPORT.md`

---

## Key Documentation

- [Compliance Matrix](file:///docs/COMPLIANCE_MATRIX.md)
- [Final Benchmark Report](file:///docs/FINAL_BENCHMARK_REPORT.md)
- [Technical Report (6-Page)](file:///docs/TECHNICAL_REPORT.md)
- [Capture Protocol Guide](file:///docs/CAPTURE_PROTOCOL.md)
- [One-Command Workflow](file:///docs/ONE_COMMAND_WORKFLOW.md)
- [Stage 11 Fix Loop Bundle](file:///docs/FIX_LOOP_BUNDLE.md)
- [Final Repository Audit](file:///docs/FINAL_REPOSITORY_AUDIT.md)

---

## Known Limitations & Absolute Honesty Statement

1. **Independent Physical Ground Truth**: Certified laser disto / steel tape measurements were not bundled in the initial raw sample scans. All dependent physical accuracy gates are strictly marked `NOT_EVALUABLE` / `PENDING_GT`.
2. **Incumbent Scanner Benchmarking**: Awaiting parallel iPhone scans from commercial applications; evaluation structure is configured under `benchmark/incumbent/`.
3. **Monocular Video Scale**: Unscaled SfM point clouds require external metric scale anchors (IMU or known object reference) for absolute metric scaling.
