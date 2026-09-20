# COZMO AI — Spatial Intelligence & Architectural Reconstruction Platform

> Autonomous computer vision and spatial intelligence platform converting consumer iPhone captures (LiDAR, Video, Photo) into centimeter-accurate 2D/3D floor plans, forensic defect annotations, automated contractor repair scopes, and CAD/BIM exports with honest measurement uncertainty.

---

## 1. What COZMO Does

- **Multi-Tier Reconstruction**: Ingests raw iPhone LiDAR sensor archives (dToF depth + ARKit poses), monocular 60 FPS video walkthroughs, or multi-view photo sets.
- **Deterministic Metric Geometry**: Extracts 2D boundary polygons, wall lengths, opening spans (doors/windows), and ceiling heights with sub-centimeter mathematical determinism.
- **Forensic Damage Intelligence**: Detects surface defects (water damage, mold, drywall cracks, impact holes) via YOLOv8s and projects them to 3D wall coordinates to generate automated insurance/restoration repair scopes.
- **Multi-Room Stitching & Drift SLAM**: Optimizes multi-room topological layouts using closed-loop pose-graph SLAM with Huber robust loss.
- **Multi-Format Architectural Exports**: Produces schema-compliant JSON, scalable interactive SVG, publication-ready multi-page PDF inspection reports, and Release-12 DXF CAD drawings.
- **Absolute Honesty & Benchmark Integrity**: Missing physical ground truth strictly yields `PENDING_GT` / `NOT_EVALUABLE`. Zero synthetic hallucinations or fake passes.

---

## 2. System Requirements

- **Operating System**: Linux (Ubuntu 22.04+ recommended) or Windows 11 with WSL2.
- **Python**: Python 3.10, 3.11, or 3.12.
- **Node.js**: Node.js 18+ or 20+ (LTS recommended) and npm.
- **C++ Build Tools**: CMake, C++ compiler, and COLMAP (optional for video SfM).

---

## 3. Installation & Setup

```bash
# 1. Clone repository
git clone https://github.com/MUKULBUROL/Cozmo-AI_Project.git
cd Cozmo-AI_Project

# 2. Install Python dependencies
pip install -r requirements.txt
# or: pip install fastapi uvicorn reportlab shapely open3d pytest

# 3. Install Frontend dependencies
cd frontend
npm install
cd ..
```

---

## 4. Starting the Application

### Backend API (FastAPI)
```bash
uvicorn backend.app.api.main:app --host 0.0.0.0 --port 8000 --reload
```
API Health Check: `http://localhost:8000/api/health`

### Frontend Workspace (Next.js)
```bash
cd frontend
npm run dev
```
Interactive Workspace: `http://localhost:3000`

---

## 5. Evaluator Interactive Flow

1. Open `http://localhost:3000` in your web browser.
2. Click **New Capture** in the header.
3. Select the capture tier (**LiDAR**, **Video**, or **Photo**).
4. Upload a sample capture package (e.g., `sample data/single_scan_floor_only.zip`).
5. Observe live processing steps and transition to the result workspace (`/property/{id}`).
6. Interact with the 2D SVG floor plan (zoom, pan, select walls and damage markers).
7. Review dimensions, uncertainty intervals, opening schedules, and repair line items in the **Inspector Panel**.
8. Open the **Export** menu in the header and download:
   - **JSON**: Property schema hierarchy
   - **SVG**: Vector architectural floor plan
   - **PDF**: Multi-page inspection & repair report
   - **DXF**: Layered CAD vector drawing

---

## 6. CLI Tier Commands (One-Command-Per-Capture)

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

## 7. Official Benchmark Suite

Run the complete final validation and gate assessment suite:
```bash
python3 scripts/run_final_benchmark.py
```

Benchmark artifacts generated in:
- `benchmark/results/metrics.json`
- `benchmark/results/gate_results.json`
- `benchmark/results/summary.csv`
- `docs/FINAL_BENCHMARK_REPORT.md`

---

## 8. Export Formats Overview

| Format | Content & Specifications | Primary Use Case |
|---|---|---|
| **JSON** | Full property schema: rooms, walls, openings, damages, line items | Machine-readable API integrations & downstream BIM databases |
| **SVG** | Vector 2D floor plan with metric coordinates, dimensions, swings | Web viewers, interactive plan embedding, print prep |
| **PDF** | Formatted inspection report with cover card, tables, damage logs, disclaimers | Client/contractor deliverable, insurance adjuster review |
| **DXF** | Release-12 layered CAD format (`WALLS`, `OPENINGS`, `DIMENSIONS`, `DAMAGE`) | AutoCAD, Revit, SketchUp drafting and remodeling |

---

## 9. Key Architectural Documentation

- [Compliance Matrix](file:///docs/COMPLIANCE_MATRIX.md)
- [Final Benchmark Report](file:///docs/FINAL_BENCHMARK_REPORT.md)
- [Technical Report (6-Page)](file:///docs/TECHNICAL_REPORT.md)
- [Capture Protocol Guide](file:///docs/CAPTURE_PROTOCOL.md)
- [One-Command Workflow](file:///docs/ONE_COMMAND_WORKFLOW.md)
- [Stage 11 Fix Loop Bundle](file:///docs/FIX_LOOP_BUNDLE.md)

---

## 10. Known Limitations & Absolute Honesty Statement

1. **Independent Physical Ground Truth**: Certified laser disto / steel tape measurements were not bundled in the initial raw sample scans. All dependent physical accuracy gates are marked `NOT_EVALUABLE` / `PENDING_GT`.
2. **Incumbent Scanner Benchmarking**: Awaiting parallel iPhone scans from commercial applications; structure prepared under `benchmark/incumbent/`.
3. **Monocular Video Scale**: Unscaled SfM point clouds require external metric scale anchors (IMU or known object reference) for absolute metric scaling.
