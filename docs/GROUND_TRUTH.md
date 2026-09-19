# Ground Truth Audit & Benchmark Strategy

## 1. Ground Truth Inventory in Sample Data

A rigorous recursive inspection was performed across all directories and archives in `sample data/`.

| Ground Truth Category | Present in Dataset? | Details / Status |
|---|---|---|
| **Wall measurements** | **NO** | No tape measurements, laser distance logs, or CAD dimensions provided. |
| **Room dimensions** | **NO** | No room bounding boxes or bounding lengths provided. |
| **Opening measurements** | **NO** | No door/window widths or height annotations provided. |
| **Ceiling height** | **NO** | No ground truth clear ceiling heights provided. |
| **Floor area** | **NO** | No official square footage / square meter values provided. |
| **Room adjacency** | **NO** | No topological adjacency graph provided. |
| **Floor-plan drawings** | **NO** | No 2D architectural drawings, SVGs, or PDF blueprints. |
| **Point clouds** | **NO** | No precomputed ground truth dense LiDAR scans (e.g. Faro / Leica). |
| **Meshes** | **NO** | No ground truth OBJ, PLY, or USDZ meshes provided. |
| **Damage annotations** | **NO** | No defect bounding boxes or damage segmentation masks. |
| **Damage masks** | **NO** | No pixel-wise or surface-wise damage region masks. |
| **Damage classes** | **NO** | No class label schedule provided in raw files. |
| **Confidence/uncertainty labels** | **NO** | No ground truth measurement uncertainty targets. |

---

## 2. Implication for Development and Evaluation

Because the provided sample dataset contains **zero manual ground truth annotations**, we must establish a rigorous validation protocol:

### 1. Pseudo-Ground-Truth Generation (High-Confidence LiDAR Baseline)
- The raw LiDAR depth data (`c7d28f72c6` with ceiling, and `c00a170fe1` single room) has high confidence (`level 2`) points with millimetric accuracy.
- We can construct a **High-Precision Reference Model** by:
  1. Applying pose graph optimization with loop closure on `odometry.csv` to remove the 38.9 cm drift.
  2. Filtering for high-confidence LiDAR depth points ($conf = 2$, range $< 3.5\text{ m}$).
  3. Fitting planar surfaces via RANSAC with strict inlier thresholds ($< 1\text{ cm}$).
  4. Intersecting planes to extract reference wall lengths, opening widths, and ceiling heights.
- This reference model will serve as our internal benchmark target for evaluating the PHOTO and VIDEO pipelines.

### 2. Repeatability Self-Verification (The 1 cm / 0.5% Gate)
The challenge explicitly demands:
> *"Repeatability: two captures of the same room at the same tier must agree within 1 cm OR 0.5% per wall."*

In our dataset, we have **two full captures of the same property**:
1. `single_scan_floor_only` (`1a8384c3f6`)
2. `single_scan_with_ceiling` (`c7d28f72c6`)

We will use these two independent walkthroughs as our primary **Repeatability Benchmark**:
- Run the reconstruction pipeline independently on both scans.
- Align the resulting floor plans using rigid Procrustes / ICP.
- Verify that corresponding wall lengths agree within $\le 1\text{ cm}$ or $\le 0.5\%$.

### 3. Preparation for Official Evaluation Dataset
When the evaluators test our system during the walk-in test on unseen spaces, our pipeline will emit the strict Output Contract schema defined in `backend/app/models/output.py`, with honest confidence intervals on every measurement.
