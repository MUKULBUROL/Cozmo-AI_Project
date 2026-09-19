# Floorplan AI (Cosmo AI Project)

> Autonomous computer vision pipeline converting consumer iPhone captures into dimensioned, stitched architectural floor plans with honest measurement confidence.

## Core Philosophy
1. **AI/ML identifies and segments things** (walls, openings, structural features, surface damage).
2. **Geometry calculates where they are and how large they are** (metric coordinates, RANSAC plane fitting, ray unprojection, loop-closure pose graphs).
3. **Honest Measurement Confidence**: Every reported dimension includes an empirical uncertainty interval $[L, U]$ and calibrated confidence level based on sensor physics and reprojection residual.

---

## Input Tiers

| Tier | Source Modality | Target Accuracy Gates |
|---|---|---|
| **PHOTO** | 2–8 ordinary still photos per room | Wall lengths within $\pm 8\%$ |
| **VIDEO** | Handheld walkthrough video (`.mp4`) | Wall lengths within $\pm 3\%$ |
| **LIDAR** | Raw depth + camera poses + intrinsics | Openings $\le 2\text{ cm}$ on $\ge 85\%$, ceiling $\le 1.5\text{ cm}$ |

---

## Dataset Validation

Run the dataset validation command to verify all local capture archives:

```bash
python -m scripts.validate_dataset
```

Inspect video properties and keyframes:
```bash
python -m scripts.inspect_video
python -m scripts.inspect_images --num-frames 6
```

Inspect 3D point cloud generation:
```bash
python -m scripts.inspect_pointcloud --frames 10
```

---

## Repository Structure

```
.
├── backend/
│   ├── app/
│   │   ├── api/             # FastAPI service endpoints
│   │   ├── models/          # Pydantic v2 schemas & Output Contract
│   │   ├── pipelines/       # Tier-specific reconstruction pipelines
│   │   │   ├── photo/       # COLMAP / Sparse SfM
│   │   │   ├── video/       # Visual Odometry / Monocular Depth
│   │   │   └── lidar/       # ARKit LiDAR unprojection & PGO
│   │   ├── perception/      # Segmentation (YOLO, SAM 2)
│   │   ├── geometry/        # RANSAC plane fitting & 2D polygon extraction
│   │   ├── calibration/     # Error models & scale calibration
│   │   ├── stitching/       # Multi-room registration & topological graph
│   │   ├── damage/          # Metric surface damage extent & rule engine
│   │   ├── evaluation/      # Benchmark verification against gates
│   │   └── export/          # JSON, SVG vector, and DXF generators
│   └── tests/               # Unit and integration tests
├── configs/                 # Dataset & pipeline configuration
├── data/                    # Processed models & cached outputs
├── docs/                    # Technical architecture & dataset reports
│   ├── ARCHITECTURE.md
│   ├── DATASET_ANALYSIS.md
│   ├── GROUND_TRUTH.md
│   └── OPEN_QUESTIONS.md
├── outputs/                 # Exported contact sheets, PLYs, floor plans
├── sample data/             # Raw iPhone scan archives (read-only)
├── scripts/                 # Inspection & validation CLI tools
├── pyproject.toml           # Project dependencies & tool configurations
└── README.md
```

---

## Output Contract

The final system produces:
1. `output.json`: Standardized challenge schema with per-room dimensions, walls, openings, ceiling height, damage extents, concealed-damage flags, and confidence intervals.
2. `floorplan.svg`: Clean architectural vector drawing with standard line weights, door swings, and area annotations.
3. `floorplan.dxf`: CAD layer format for architectural integration.
