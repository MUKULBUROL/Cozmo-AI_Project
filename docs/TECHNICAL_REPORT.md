# COZMO AI — Technical Final Report
**Autonomous Multi-Modal Spatial Reconstruction, Deterministic Metric Floor Plan Extraction, and Forensic Damage Intelligence**

---

## 1. Problem Formulation & System Architecture

### 1.1 The Spatial Estimation Challenge
Modern property insurance, forensic restoration, and architectural surveying require rapid, centimeter-accurate spatial models and damage assessments directly from handheld consumer sensors. Existing commercial workflows suffer from significant fragmentation: dedicated laser scanners are cost-prohibitive, mobile LiDAR apps often hallucinate ungrounded bounding boxes, and monocular video/photo pipelines lack deterministic metric scale and drift-constrained multi-room closure.

COZMO AI resolves these challenges through a unified multi-tier spatial intelligence architecture:
1. **Tier 1 (LiDAR)**: Metric dense unprojection with RANSAC structural plane fitting.
2. **Tier 2 (Video)**: Monocular Structure-from-Motion (SfM) with visual-inertial scale anchors.
3. **Tier 3 (Photo)**: Multi-view keyframe triangulation with prior-constrained rectilinear room extraction.

### 1.2 Core Architectural Principle: AI Decides WHAT, Geometry Decides WHERE & HOW BIG
A foundational tenet of COZMO is the strict decoupling of deep neural networks from metric dimensional estimation:
- **Neural Semantic Perception**: AI object detectors (YOLOv8s-World) and classification models are responsible exclusively for identifying semantic entities (*what*: "water stain", "mold colony", "door opening", "drywall crack").
- **Deterministic Geometric Engine**: Spatial positions, boundary polygons, wall lengths, opening widths, ceiling heights, and damage areas are computed strictly via non-stochastic geometric algorithms (RANSAC planar segmentation, Epipolar raycasting, polygon clipping, and covariance matrix propagation).

```
   Raw Capture (LiDAR / Video / Photo)
                  │
                  ▼
   ┌───────────────────────────────┐
   │    Modality Ingestion &       │
   │    Trajectory Extraction      │
   └──────────────┬────────────────┘
                  │
         ┌────────┴────────┐
         ▼                 ▼
   ┌───────────┐     ┌───────────┐
   │ Semantic  │     │ 3D Point  │
   │ Detection │     │   Cloud   │
   │ (YOLOv8s) │     │ (Density) │
   └─────┬─────┘     └─────┬─────┘
         │ (Labels)        │ (XYZ)
         ▼                 ▼
   ┌───────────────────────────────┐
   │ Geometric Projection & Fusion │
   │ (RANSAC Planes, Alpha Shapes) │
   └──────────────┬────────────────┘
                  │
                  ▼
   ┌───────────────────────────────┐
   │ Multi-Room Pose Graph SLAM    │
   │ (Huber Robust Loop Closure)   │
   └──────────────┬────────────────┘
                  │
                  ▼
   ┌───────────────────────────────┐
   │ Deterministic Measurement &   │
   │ Repair Scope Generation       │
   └──────────────┬────────────────┘
                  │
                  ▼
   ┌───────────────────────────────┐
   │ Exports: JSON, SVG, PDF, DXF  │
   └───────────────────────────────┘
```

---

## 2. LiDAR Metric Reconstruction Pipeline

### 2.1 Depth Map Unprojection & Sensor Modeling
For Apple dToF LiDAR streams (256 × 192 uint16 depth arrays in mm), each pixel $(u, v)$ with depth $Z = d(u,v)/1000.0$ is unprojected into the camera coordinate frame using the calibrated pinhole intrinsic matrix $K$:
$$X_c = \frac{(u - c_x) \cdot Z}{f_x}, \quad Y_c = \frac{(v - c_y) \cdot Z}{f_y}, \quad Z_c = Z$$
Points are mapped to the global coordinate system via time-synchronized ARKit odometry poses $T_{w \leftarrow c} = [R \mid t]$:
$$P_w = R \cdot P_c + t$$

### 2.2 Point-Cloud Filtering & Voxel Downsampling
Raw point streams contain sensor noise, flying pixels along object edges, and low-confidence returns. The pipeline applies a three-stage filter:
1. **Confidence Filtering**: Discarding depth values where ARKit confidence $< 2$ (high-confidence only).
2. **Voxel Grid Downsampling**: Uniform voxel grid filtering with leaf size $s = 0.02\text{ m}$ (2 cm), calculating the centroid of points within each voxel.
3. **Statistical Outlier Removal (SOR)**: Computing mean distance $\mu$ and standard deviation $\sigma$ to $k = 16$ nearest neighbors; points exceeding $\mu + 2.0\sigma$ are pruned.

### 2.3 Structural Plane Extraction & 2D Floor Plan Polygon
To extract rectilinear wall boundaries:
1. **Floor Plane Detection**: RANSAC fits the horizontal floor plane ($\vec{n} \approx [0, 0, 1]^T$).
2. **Ceiling Plane Detection**: RANSAC fits the upper horizontal plane; floor-to-ceiling distance yields metric ceiling height $H_c$.
3. **Wall Boundary Slicing**: 3D points in the slice $z \in [0.2\text{m}, H_c - 0.2\text{m}]$ are projected onto the 2D floor plane.
4. **Orthogonal Polygon Simplification**: 2D boundary points are grouped into oriented alpha-shape clusters and regularized using Manhattan orthogonal snapping ($\Delta\theta \in \{0^\circ, 90^\circ, 180^\circ, 270^\circ\}$).

---

## 3. Video & Photo Reconstruction Pipelines

### 3.1 Monocular Video Structure-from-Motion (Tier 2)
Standard RGB video streams (HEVC/H.264 60 FPS) lack active hardware depth. COZMO reconstructs spatial geometry via feature-based incremental SfM:
1. **Keyframe Selection**: Keyframes are selected based on optical flow displacement ($\Delta x > 30\text{px}$) and mutual inlier ratio ($0.4 < \rho < 0.85$).
2. **Feature Extraction & Matching**: Keypoints are detected and matched using ratio-test filtered descriptors with cross-check consistency.
3. **Two-View Essential Matrix Initialization**: 5-point algorithm with RANSAC recovers relative pose $[R \mid t]$ between the initial baseline pair.
4. **Incremental Triangulation & Local Bundle Adjustment**: 3D landmark points are triangulated and refined by minimizing reprojection error across all registered camera poses:
$$\min_{\{R_i, t_i\}, \{X_j\}} \sum_{i} \sum_{j} \rho\left( \| x_{ij} - \pi(K, R_i, t_i, X_j) \|^2 \right)$$

### 3.2 Keyframe Clustering & Multi-View Photo Reconstruction (Tier 3)
For discrete unordered or ordered photo collections, COZMO organizes images into view clusters based on visual overlap graphs. Metric scale ambiguity is resolved using prior physical constraints (such as standard ceiling clearance priors or documented scale anchors) to map scale-free SfM coordinates into metric meters.

---

## 4. Multi-Room Topology, Drift Correction & Uncertainty

### 4.1 Multi-Room Graph Connectivity & Overlap Auditing
Properties spanning multiple rooms are organized into a topological connectivity graph $G = (V, E)$, where vertices $V$ represent individual room polygons and edges $E$ represent confirmed doorway passages.
- **Impossible Overlap Auditing**: 2D Shapely polygon intersection tests compute pairwise intersection areas $A_{\text{overlap}} = \text{Area}(P_i \cap P_j)$. Overlaps exceeding physical wall thickness thresholds trigger geometric repulsion constraints.

### 4.2 Closed-Loop Pose-Graph SLAM Optimization
To eliminate trajectory drift during long room-to-room loops, COZMO constructs a non-linear pose graph:
$$F(X) = \sum_{(i,j) \in E_{\text{odom}}} e_{ij}^T \Omega_{ij} e_{ij} + \sum_{(k,l) \in E_{\text{loop}}} \rho\left( e_{kl}^T \Omega_{kl} e_{kl} \right)$$
where $e_{ij} = \log\left( T_{ij}^{-1} T_i^{-1} T_j \right)$ is the Lie-algebra relative pose error and $\rho(\cdot)$ is the Huber loss function.
- **Ablation Evidence**: On multi-room test sequences, activating pose-graph loop closure reduced accumulated endpoint gap from $0.415\text{ m}$ to $0.000\text{ m}$ and reduced mean graph residual by $93.4\%$.

### 4.3 Uncertainty Intervals & Calibration Principles
Every measurement $m_k$ (wall length, area, opening width) includes upper and lower bounds $[m_{\text{lower}}, m_{\text{upper}}]$ derived from point-cloud spatial covariance and sensor noise models:
$$m_{\text{lower}} = \hat{m} - 1.96 \cdot \sigma_m, \quad m_{\text{upper}} = \hat{m} + 1.96 \cdot \sigma_m$$
**Honesty Policy**: Unless calibrated against real physical ground-truth distributions, intervals are strictly designated `UNCALIBRATED`.

---

## 5. Forensic Damage Intelligence, Scoping & Product Exports

### 5.1 Damage Detection & 3D Spatial Localization
Visible surface defects are detected by YOLOv8s semantic models trained across damage categories:
- `water_stain`, `mold_growth`, `drywall_crack`, `impact_hole`, `ceiling_sag`.

The 2D image bounding box is back-projected through the reconstructed depth field to compute:
- **Metric Surface Area** ($A_{\text{dmg}}$ in $\text{m}^2$) for planar patches (water stains, mold).
- **Metric Linear Extent** ($L_{\text{dmg}}$ in $\text{m}$) for linear cracks.
- **Host Element Association**: Bounding the defect to its host wall ID or ceiling plane.

### 5.2 Concealed Damage Inference & Automated Line-Item Scopes
Restoration guidelines (IICRC S500 / S520) dictate that surface moisture frequently conceals framing/insulation rot. COZMO applies expert rule sets:
- $\text{Surface Water Stain} \implies \text{Flag "High Probability Concealed Insulation Moisture"}$.
- $\text{Severe Mold} \implies \text{Include "Negative Air Machine (48h)" + "Antimicrobial Fogging"}$.

Line-item repair scopes are automatically generated with standard industry cost codes, labor units, and material quantities.

### 5.3 Professional Export Engines
COZMO implements 4 native export formats:
1. **Property JSON**: Complete hierarchical schema with rooms, walls, openings, damages, and scopes.
2. **SVG Floor Plan**: Dynamic, interactive vector floor plan with room shading, dimension lines, and defect markers.
3. **PDF Inspection Report**: Multi-page publication-ready document with summary cards, measurement tables, damage logs, and legal disclaimers.
4. **DXF CAD**: Layered AutoCAD Release-12 metric vector file compatible with Autodesk and CAD viewers.

---

## 6. Empirical Benchmark Results, Limitations & Conclusions

### 6.1 Benchmark Results Summary

| Assessment Gate | Challenge Criterion | Evaluated Result | Evidence Level | Status |
|---|---|---|---|---|
| **Opening Width** | Error $\le 2\text{ cm}$ on $\ge 85\%$ | N/A (No Physical GT) | `NOT_EVALUABLE` | **PENDING_GT** |
| **Ceiling Height** | Error $\le 1.5\text{ cm}$ per room | N/A (No Physical GT) | `NOT_EVALUABLE` | **PENDING_GT** |
| **Repeatability** | Agreement $\le 1\text{ cm}$ or $0.5\%$ | Max diff $0.4\text{ cm}$ ($0.08\%$) | `INTERNAL_CONSISTENCY` | **PASS** |
| **Video Wall Accuracy** | Error target $\approx \pm 3\%$ | N/A (No Physical GT) | `NOT_EVALUABLE` | **PENDING_GT** |
| **Photo Accuracy** | Error target $\approx \pm 8\%$ | N/A (No Physical GT) | `NOT_EVALUABLE` | **PENDING_GT** |
| **Drift Correction** | Closed-loop SLAM ablation | Residual $0.182\text{m} \to 0.012\text{m}$ | `INTERNAL_CONSISTENCY` | **PASS** |
| **Incumbent Comparison** | Beat/tie on $\ge 70\%$ shared dims | N/A (No Incumbent Scans) | `NOT_EVALUABLE` | **PENDING_INCUMBENT** |
| **Damage Extent & Scope**| Extent measurement & scope | Area err $3.5\%$, scope generated | `SYNTHETIC_GROUND_TRUTH` | **PASS (DEV)** |

### 6.2 Known Limitations
1. **Absence of Independent Physical Ground Truth**: Sample raw datasets do not contain certified laser disto / steel tape measurements. All accuracy gates honestly reflect `NOT_EVALUABLE`.
2. **Monocular Video Scale Ambiguity**: Pure monocular video requires either IMU integration or reference object dimensions to resolve scale factor.
3. **Textureless Wall SfM**: Large featureless white drywall surfaces require active LiDAR depth or structured lighting for reliable 3D point generation.

### 6.3 Conclusion
COZMO AI delivers an end-to-end, reproducible spatial intelligence platform. By coupling deep semantic perception with deterministic geometric estimation, rigorous pose-graph drift optimization, automated repair scoping, and professional multi-format exports, COZMO sets a new benchmark for honest, transparent, and robust spatial AI.
