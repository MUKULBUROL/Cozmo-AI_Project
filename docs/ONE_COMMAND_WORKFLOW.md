# COZMO AI — One-Command Execution Workflow

This document provides exact, verified one-command execution instructions for every modality tier, automated damage analysis, multi-room property stitching, exports generation, and official benchmark evaluation.

---

## 1. Quick Reference: One Command Per Modality

### LiDAR Reconstruction (Tier 1)
Processes raw iPhone LiDAR sensor archives (depth frames + odometry trajectory + camera intrinsics):
```bash
python3 scripts/reconstruct_lidar.py --scan 1a8384c3f6 --archive "sample data/single_scan_floor_only.zip" --voxel-size 0.02 --min-confidence 2
```
**Outputs**:
- `outputs/1a8384c3f6/baseline_filtered.ply`: Downsampled, outlier-filtered metric 3D point cloud.
- `outputs/1a8384c3f6/trajectory.json`: Metric camera trajectory diagnostics.
- `outputs/1a8384c3f6/reconstruction_stats.json`: Spatial bounding box and point statistics.

---

### Video SfM Reconstruction (Tier 2)
Extracts keyframes, tracks features, initializes two-view epipolar geometry, and performs bundle-adjusted Structure-from-Motion:
```bash
python3 scripts/reconstruct_video.py --archive "sample data/single_room.zip" --scan c00a170fe1 --capture-id video_rec_01 --max-keyframes 30
```
**Outputs**:
- `outputs/video_rec_01/keyframes/`: Selected keyframe still images.
- `outputs/video_rec_01/pointcloud.ply`: Triangulated 3D sparse feature point cloud.
- `outputs/video_rec_01/camera_trajectory.json`: Recovered camera poses and tracking gaps.

---

### Photo Multi-View Reconstruction (Tier 3)
Extracts multi-view keyframe clusters, estimates metric scale priors, and traces rectilinear room boundaries:
```bash
python3 scripts/reconstruct_photos.py --input "data/photo_dev/sample_room" --capture-id photo_rec_01
```
**Outputs**:
- `outputs/photo_rec_01/room_polygon.json`: Scaled 2D room boundary polygon with uncertainty bounds.
- `outputs/photo_rec_01/measurements.json`: Wall length and room area estimates.

---

### Multi-Room Property Reconstruction & Exports
Unified multi-room property pipeline executing room polygon extraction, door matching, pose-graph loop closure, and exports (JSON, SVG, PDF, DXF):
```bash
python3 scripts/reconstruct_property.py --scan c7d28f72c6 --archive "sample data/single_scan_with_ceiling.zip" --headless
```
**Outputs**:
- `outputs/c7d28f72c6/property.json`: Complete property hierarchy and measurement contracts.
- `outputs/c7d28f72c6/floor_plan.svg`: Scalable vector 2D floor plan.
- `outputs/c7d28f72c6/inspection_report.pdf`: Multi-page printable architectural inspection report.
- `outputs/c7d28f72c6/floor_plan.dxf`: Release-12 metric CAD drawing.

---

### Forensic Damage & Automated Scope Analysis
Executes YOLOv8s semantic damage detection, 3D wall projection, concealed cavity rule evaluation, and repair scope itemization:
```bash
python3 scripts/analyze_damage.py --capture-id c00a170fe1
```
**Outputs**:
- `outputs/damage_analysis/damage_detections.json`: Localized defect bounding boxes with classifications.
- `outputs/damage_analysis/repair_scope.json`: Contractor line-item repair costs and labor hours.
- `outputs/damage_analysis/scope_report.md`: Markdown summary of repairs with concealed moisture warnings.

---

### Official Challenge Benchmark Runner
Executes the automated gate evaluator across all modalities against physical ground-truth contracts:
```bash
python3 scripts/run_final_benchmark.py
```
**Outputs**:
- `benchmark/results/metrics.json`: Detailed measurement arrays and statistical residuals.
- `benchmark/results/gate_results.json`: Gate-by-gate pass/fail/evaluable statuses.
- `benchmark/results/summary.csv`: Tabular gate evaluation summary.
- `docs/FINAL_BENCHMARK_REPORT.md`: Comprehensive 16-section benchmark report.

---

## 2. Server-Mode Workflow (FastAPI + Next.js UI)

To launch the full interactive evaluation workspace:

**Terminal 1 (FastAPI Backend)**:
```bash
uvicorn backend.app.api.main:app --host 0.0.0.0 --port 8000 --reload
```

**Terminal 2 (Next.js Frontend)**:
```bash
cd frontend && npm run dev
```

Open browser at `http://localhost:3000`:
1. Navigate to **New Capture**.
2. Select desired tier (**LiDAR**, **Video**, or **Photo**).
3. Upload raw capture archive (e.g. `sample data/single_scan_floor_only.zip`).
4. View real-time processing and inspect reconstructed interactive floor plan, 3D point cloud, measurements, and damage scopes.
5. Click **Export** to download JSON, SVG, PDF, or DXF.
