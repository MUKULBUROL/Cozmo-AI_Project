# Stage 9: Visual Property Damage Perception, Metric Extent, Concealed-Damage Rules & Repair Scope

## 1. Executive Summary & Overview
Stage 9 implements visual property damage perception, metric damage extent computation, host structural surface association, multi-view candidate deduplication, deterministic concealed-damage risk flagging, and evidence-linked repair scope generation across **LiDAR**, **Video**, and **Photo** capture modalities.

The fundamental architectural principle of the Cozmo AI Project governs this stage:
> **AI says WHAT something is.**  
> **GEOMETRY says WHERE it is and HOW LARGE it is.**

The perception system uses an open-vocabulary vision model to classify visual appearances. Bounding boxes are never used as measurements, and physical dimensions are never hallucinated. Instead, pixel-level binary masks are back-projected through Stage 1–8 calibrated camera poses onto verified Stage 2 structural planes (walls, floors, ceilings) to calculate metric surface areas ($m^2$) or linear crack lengths ($m$) with honest confidence intervals.

---

## 2. Visible vs. Concealed Damage: The Safety Boundary
Building envelopes and finishes enclose internal cavities (framing studs, plumbing lines, electrical wiring, fiberglass insulation). Ordinary optical sensors (RGB cameras and LiDAR) **cannot penetrate opaque solid surfaces**.

* **Visible Damage**: Direct, verifiable surface optical phenomena (stains, surface cracks, material breaches, charred surfaces) observable in RGB pixels.
* **Concealed Damage**: Secondary or hidden defects behind the finish (hidden mold in cavities, rotted framing, soaked insulation, active hidden pipe leaks).

### Mandatory Contract Rule
The system **NEVER** diagnoses unseen internal facts (e.g., it never claims "hidden mold exists behind the wall"). Instead, it triggers deterministic, auditable **`ConcealedDamageFlag`** alerts where:
- `is_risk_flag_only = true`
- `requires_inspection = true`
- An actionable forensic inspection protocol is emitted (e.g., non-invasive moisture meter survey, cavity boroscope inspection, structural engineering evaluation).

---

## 3. Configurable Property Damage Taxonomy
The semantic taxonomy maps open-vocabulary visual prompts to standardized canonical categories (`DamageClass`):

| Canonical Class (`DamageClass`) | Description | Measurement Type |
| :--- | :--- | :--- |
| `water_stain` | Discoloration ring, moisture saturation pattern | Surface Area ($m^2$) |
| `surface_crack` | Hairline or cosmetic fracture on plaster/drywall | Linear Length ($m$) |
| `crack_structural` | Diagonal shear, stair-step, or load-bearing fissure | Linear Length ($m$) |
| `hole_or_missing_material` | Drywall puncture, impact breach, missing finish | Surface Area ($m^2$) |
| `mold_like_discoloration` | Dark, patchy discoloration (honest semantic label) | Surface Area ($m^2$) |
| `burn_or_char` | Scorched, charred, or smoke-deposited surface | Surface Area ($m^2$) |
| `surface_breakage` | Chipped plaster, spalled concrete, broken baseboard | Surface Area ($m^2$) |
| `other_visible_damage` | General unclassified surface degradation | Surface Area ($m^2$) |

---

## 4. Perception Model & Zero-Shot Detection
* **Model**: YOLO-World (`ultralytics.YOLOWorld`).
* **Checkpoint**: `yolov8s-worldv2.pt` (25.9 MB).
* **Execution**: Local CPU inference (AMD Ryzen 5 5500U, ~0.25 s per frame after initial CLIP text compilation).
* **Licensing**: AGPL-3.0 / open-source.
* **Role**: Candidate generation only. Returns candidate bounding boxes $[x_1, y_1, x_2, y_2]$, class confidence scores, and border clipping flags.

---

## 5. Pixel Mask Segmentation
Bounding boxes enclose substantial undamaged wall finish. To calculate exact physical extent, candidate regions undergo boundary refinement via [`DamageMaskSegmenter`](file:///home/devcontainers/Projects/Active/CosmoAIProject/backend/app/damage/segmenter.py):
1. **Contrast & Edge Separation**: Measures luminance and color deviation from undamaged wall border pixels.
2. **Morphological Filtering**: Closes thin gaps, suppresses isolated noise, and selects the primary connected component.
3. **Depth Step Integration**: When aligned depth is present, detects geometric depth discontinuities (e.g. wall breaches and holes).
4. **Boundary Extraction**: Computes outer polygon contour coordinates in pixel space.

---

## 6. 2D → 3D Projection Math
Common projection math is shared across all capture tiers:
1. For sampled mask pixels $(u, v)$, optical rays in the camera coordinate frame are computed:
   $$\mathbf{r}_{cam} = \left[ \frac{u - c_x}{f_x}, \frac{v - c_y}{f_y}, 1.0 \right]^T, \quad \mathbf{r}_{cam} \leftarrow \frac{\mathbf{r}_{cam}}{\|\mathbf{r}_{cam}\|}$$
2. The ray is transformed into metric world coordinates using the camera's 6D rotation matrix $R$:
   $$\mathbf{r}_{world} = R \cdot \mathbf{r}_{cam}$$
3. For each candidate structural plane $\Pi_i: a x + b y + c z + d = 0$, the analytical intersection distance $t$ is solved:
   $$t = -\frac{\mathbf{n} \cdot \mathbf{C}_{cam} + d}{\mathbf{n} \cdot \mathbf{r}_{world}}$$
4. Hits with $t > 0.1\text{ m}$ and $t \le 8.0\text{ m}$ are evaluated.

---

## 7. Structural Host-Surface Association
* The system evaluates ray intersections against all Stage 2 structural planes.
* The structural plane receiving the highest valid geometric support (minimum 50% consensus) is assigned as `host_surface_id`.
* The damage region is classified as `wall`, `floor`, or `ceiling`.
* An orthonormal 2D coordinate frame $(\mathbf{u}_{local}, \mathbf{v}_{local})$ is constructed on the host plane:
  - For vertical walls: $\mathbf{v}_{local} = (0, 1, 0)$ (vertical elevation) and $\mathbf{u}_{local} = \mathbf{v}_{local} \times \mathbf{n}$.
  - For horizontal floors/ceilings: $\mathbf{v}_{local} = (0, 0, 1)$ and $\mathbf{u}_{local} = (1, 0, 0)$.

---

## 8. Metric Extent & Uncertainty Estimation
Points on the host plane are projected into local coordinates $(u_{local}, v_{local})$:
* **Area-Type Damage**: Planar convex hull / alpha shape integration yields true surface area in $m^2$.
* **Linear-Type Damage**: Principal component curve analysis along the dominant crack direction yields linear length in meters ($m$).
* **Uncertainty Propagation**:
  $$\text{Uncertainty Fraction} = \text{clip}\left(0.08 + 0.15 \left(\frac{1}{\cos\theta} - 1\right) + 0.35 \cdot \mathbf{1}_{\text{clipped}} + 5.0 \cdot \text{RMSE}_{\text{plane}}, \, 0.08, \, 0.85\right)$$
* **Gating**:
  - Oblique angle $> 75^\circ$ $\to$ `status = NOT_EVALUABLE`.
  - Border clipping $> 20\%$ $\to$ `status = PROVISIONAL`.
  - Missing metric geometry $\to$ `status = NOT_EVALUABLE`.

---

## 9. Multi-View Observation Fusion
When the same damage appears across multiple keyframes or angles:
1. Observations sharing the same `host_surface_id` and having 3D centroid distance $\le 0.35\text{ m}$ are clustered.
2. Multi-view fusion computes:
   - Fused 3D centroid (confidence-weighted mean).
   - Fused metric extent ($m^2$ or $m$).
   - Measurement spread ($\pm \sigma$ standard deviation across observations).
   - `supporting_images` list.
   - `best_image_id` (selected by minimum viewing angle and maximum focus sharpness).

---

## 10. Concealed-Damage Deterministic Rule Engine
Forensic building rules in [`backend/app/damage/rules.py`](file:///home/devcontainers/Projects/Active/CosmoAIProject/backend/app/damage/rules.py) execute deterministically:
1. `RULE_WATER_STAIN_WALL_CAVITY`: Water stain on wall $\to$ Flag possible concealed moisture in cavity; recommend pin/pinless moisture meter probing.
2. `RULE_WATER_STAIN_CEILING_PLENUM`: Water stain on ceiling $\to$ Flag possible overhead roof/plumbing leak; recommend plenum/attic access.
3. `RULE_MOLD_DISCOLORATION_SAMPLING`: Mold-like discoloration $\to$ Flag suspected microbial colony; recommend certified hygienist air/tape sampling.
4. `RULE_CRACK_STRUCTURAL_SHEAR`: Structural crack $> 0.25\text{ m}$ on wall $\to$ Flag lateral shear / foundation settlement risk; recommend structural engineer review.
5. `RULE_BURN_CHAR_FRAMING`: Burn/char on wall/ceiling $\to$ Flag structural stud section loss and hidden wiring risk; recommend cavity exposure and electrical continuity testing.

---

## 11. Repair Scope Generation
Remediation line items in [`backend/app/damage/scope.py`](file:///home/devcontainers/Projects/Active/CosmoAIProject/backend/app/damage/scope.py) derive directly from physical evidence:
* **Quantities**: Derived strictly from measured geometry ($m^2$ for area, linear $m$ for crack).
* **Unmeasurable Safety**: When damage extent is `NOT_EVALUABLE`, quantity is set to `None` with `inspection_required = true`.
* **Traceability**: Every line item includes `basis: <damage_id>` and confidence.
* **Remediation Phasing**:
  1. Diagnostic pre-inspection (e.g. moisture survey).
  2. Containment setup (negative air barrier for mold/char).
  3. Demolition / removal of affected finish (exact measured extent).
  4. Restoration and finish coating to match existing (exact measured extent).

---

## 12. Cross-Tier Capabilities & Limitations
| Modality | Geometry Quality | Extent Status | Limitations |
| :--- | :--- | :--- | :--- |
| **LiDAR** | Calibrated metric depth + ARKit 6D poses | `ACCEPTED` / `PROVISIONAL` | Highest geometric fidelity; depth valid up to 5 m. |
| **Video** | Provisional depth + SfM camera poses | `PROVISIONAL` / `NOT_EVALUABLE` | Unscaled video trajectory yields provisional/unscaled extents. |
| **Photo** | Provisional depth + sparse SfM poses | `PROVISIONAL` / `NOT_EVALUABLE` | Stills yield valid semantics; metric extents require scale anchors. |

---

## 13. Development Dataset & Ground Truth Status
* **Raw Dataset Audit**: Sample LiDAR scans (`c00a170fe1`, `c7d28f72c6`) contain undamaged rooms.
* **Development Fixtures**: Transparently labeled synthetic test cases in `data/damage_dev/` with known metric dimensions ($1.20\text{ m}^2$ stain, $1.50\text{ m}$ crack, $0.35\text{ m}^2$ hole, $0.60\text{ m}^2$ mold).
* **Benchmark Accuracy**: **NOT VERIFIED** until physical staged-damage ground truth is captured in Stage 10.

---

## 14. CLI Commands & Execution

### Analyze Damage on a Capture
```bash
python3 -m scripts.analyze_damage --capture-id c00a170fe1 --tier lidar
```

### View Formatted Damage Report
```bash
python3 -m scripts.view_damage --capture-id c00a170fe1 --headless
```

### Model Smoke Test
```bash
python3 -m scripts.smoke_test_damage_model
```

### Run Stage 9 Tests
```bash
python3 -m pytest backend/tests/test_damage_*.py backend/tests/test_concealed_rules.py backend/tests/test_scope_generation.py -v
```
