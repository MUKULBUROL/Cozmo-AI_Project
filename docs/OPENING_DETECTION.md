# STAGE 5 — ARCHITECTURAL OPENING DETECTION & METRIC CLEARANCE MEASUREMENT

<!--
1. Why this file exists:
   Comprehensive technical architectural specification and operational guide for Stage 5 opening detection
   and metric width measurement in the CosmoAI pipeline.

2. Pipeline stage:
   Stage 5 (Door/Window Detection & Metric Opening Measurement) - Documentation & Specification.

3. Inputs:
   RGB video, synchronized 6D camera poses, LiDAR depth maps, Stage 2 structural wall planes, Stage 3 room polygon.

4. Outputs:
   Formal explanation of the hybrid semantic-geometric pipeline, multi-frame observation clustering,
   ray-plane unprojection, uncalibrated 95% engineering uncertainty modeling, and corridor doorway refinement.

5. Coordinate/Unit conventions:
   Metric meters (m) in 3D world coordinates (Y vertical upward, XZ horizontal floor plane).
   Pixel coordinates (u, v) in camera frame with principal point (cx, cy).

6. Dependencies:
   backend.app.perception, backend.app.geometry, ultralytics, scipy, numpy.

7. Most likely failure/debugging points:
   - Confusion between 2D pixel bounding box width and physical 3D wall clearance width.
   - Phantom visual detections (e.g. wardrobes, TVs, picture frames) mistakenly assigned to structural walls.
   - Premature claims of metric accuracy before empirical laser/tape calibration.
-->

## 1. Why an AI Model Detects Doors and Windows

Computer vision models (such as YOLO-World or open-vocabulary zero-shot detectors) excel at semantic categorization: identifying whether an image region depicts a door, doorway, or window.
Natural architectural environments feature extensive variations in visual appearance:
- Closed timber or painted doors with surface panels, handles, and moldings.
- Open doorways revealing adjoining corridors or rooms with varying floor levels.
- Glazed exterior windows with mullions, reflections, blinds, and external daylight.

AI visual models answer the qualitative question:
> **"What is this object?"**

Visual models evaluate texture, edges, and context across the RGB keyframe to classify candidate bounding boxes with provisional detector confidence scores.

---

## 2. Why AI Does NOT Measure Width

A fundamental design principle of CosmoAI is that **AI models must never estimate physical metric dimensions directly from 2D pixel crops**.

An image-based neural network outputting `"Door width = 0.91 m"` suffers from fatal physical limitations:
1. **Perspective Distortion**: A 0.80m doorway photographed from 1.0m away appears larger in pixels than a 1.20m doorway photographed from 4.0m away.
2. **Oblique Camera Angles**: Doorways viewed at 45° or 60° incident angles undergo severe non-linear foreshortening.
3. **Focal Length Variations**: Changing camera zoom, lens distortion, or sensor cropping alters pixel dimensions without changing physical reality.
4. **Hallucination Risk**: Deep networks trained on indoor benchmarks learn statistical priors (e.g., standard residential doors are ~0.9m) and output plausible guesses rather than measuring the actual object in front of the camera.

In CosmoAI:
- **AI answers:** *"What is this object?"* (Semantic detection)
- **Geometry answers:** *"Where is it in 3D space, and what is its exact physical clearance width?"* (Metric calculation)

---

## 3. How Segmentation and Boundary Refinement Help

Standard object detection produces axis-aligned 2D bounding boxes $[x_1, y_1, x_2, y_2]$. Bounding boxes contain significant background noise, wall moldings, and perspective slants that overestimate or underestimate the true opening clearance.

CosmoAI uses depth-guided boundary refinement:
1. **Depth Step Discontinuity Analysis**: For open doorways, camera rays passing through the opening travel deeper into the adjoining room or hallway. By analyzing horizontal depth profiles across the candidate region, the system detects sharp step discontinuities ($\Delta z \ge 0.15\text{ m}$) marking the exact inner physical jamb surfaces.
2. **Vertical Gradient Alignment**: For closed doors or flush windows, vertical intensity gradients and boundary columns isolate the left and right structural frames ($u_{\text{left}}, u_{\text{right}}$).
3. **Threshold and Sill Estimation**: Header and sill pixels are refined along the vertical midline to establish vertical aperture extents.

---

## 4. How Pixels Become 3D World Geometry

To transition from 2D pixel space to 3D metric space without heuristics, CosmoAI reuses Stage 1 camera geometry and perspective ray unprojection.

Given:
- Refined pixel coordinates $(u, v)$
- Pinhole camera intrinsics $(f_x, f_y, c_x, c_y)$
- 6D camera pose in world coordinates: optical center $\mathbf{C} = [x_c, y_c, z_c]^T$ and orientation quaternion $\mathbf{q} = [q_x, q_y, q_z, q_w]$

1. **Normalized Camera Ray**:
   $$\mathbf{r}_{\text{cam}} = \frac{1}{\|\mathbf{r}\|} \begin{bmatrix} \frac{u - c_x}{f_x} \\ \frac{v - c_y}{f_y} \\ 1 \end{bmatrix}$$
2. **World-Space Ray Direction**:
   $$\mathbf{r}_{\text{world}} = \mathbf{R}(\mathbf{q}) \cdot \mathbf{r}_{\text{cam}}$$
3. **Analytical Plane Intersection**:
   Given a Stage 2 structural wall plane equation $\mathbf{n} \cdot \mathbf{p} + d = 0$ with unit normal $\mathbf{n} = [a, b, c]^T$:
   $$t_{\text{hit}} = -\frac{\mathbf{n} \cdot \mathbf{C} + d}{\mathbf{n} \cdot \mathbf{r}_{\text{world}}}$$
   $$\mathbf{P}_{\text{world}} = \mathbf{C} + t_{\text{hit}} \cdot \mathbf{r}_{\text{world}}$$

This guarantees that the resulting 3D jamb points $\mathbf{P}_{\text{left}}$ and $\mathbf{P}_{\text{right}}$ lie mathematically on the host structural wall plane.

---

## 5. How an Opening Is Attached to a Wall Plane

Not every visual detection belongs to a structural wall. Interior spaces contain wardrobes, freestanding bookshelves, mirrors, and televisions that visually mimic doors and windows.

CosmoAI performs strict structural wall association:
1. **Ray Intersection Validation**: Rays must project forward ($t_{\text{hit}} > 0$) onto the candidate plane without near-parallel grazing angles ($|\mathbf{n} \cdot \mathbf{r}| \ge 0.10$).
2. **Finite Segment Extents**: The 3D centroid of the opening $(x, z)$ must lie within the finite span of the Stage 2/3 wall segment (maximum proximity tolerance $\le 0.45\text{ m}$).
3. **Physical Clearance Filter**: Projected width must fall within plausible architectural limits ($0.45\text{ m} \le W \le 2.60\text{ m}$).
4. **Scoring & Attribution**: Candidates are tested against all Stage 2 walls. The wall minimizing projection residual while maximizing spatial overlap receives the opening attribution.

Detections failing structural association are recorded in `opening_observations.json` with explicit rejection reasons (e.g. `no_supporting_structural_wall_within_tolerance`) and excluded from physical floor plans.

---

## 6. How Opening Width Is Calculated

Once the left jamb point $\mathbf{P}_1 = (x_1, y_1, z_1)$ and right jamb point $\mathbf{P}_2 = (x_2, y_2, z_2)$ are projected onto the host structural wall plane:

The metric clearance width is computed strictly in 3D Euclidean world coordinates:
$$W = \sqrt{(x_2 - x_1)^2 + (z_2 - z_1)^2}$$

Because both endpoints are constrained to the structural wall plane:
- $W$ measures true horizontal physical clearance.
- It is invariant to camera distance and tilt.
- It avoids bounding box heuristic scaling.

---

## 7. How Multiple Frames Are Fused

A single video walkthrough observes an opening across dozens of frames from varying angles and distances. Emitting multiple independent openings would corrupt the floor plan.

CosmoAI executes multi-frame observation fusion:
1. **Spatial Clustering**: Observations are grouped by `(wall_id, semantic_family)`. Candidates whose 3D centroids lie within $0.55\text{ m}$ along the same wall plane merge into a unified observation cluster.
2. **Outlier Filtering & Fused Width**: The representative width $W_{\text{fused}}$ is computed using the median of supporting frame estimates to eliminate transient occlusion artifacts:
   $$W_{\text{fused}} = \text{median}(\{W_1, W_2, \dots, W_N\})$$
3. **Jamb Coordinate Consolidation**: Left and right 3D jamb endpoints are computed by averaging supporting inlier projections.
4. **Frame Disagreement Tracking**: Frame-to-frame standard deviation $s = \sqrt{\frac{1}{N-1}\sum (W_i - \bar{W})^2}$ is tracked to quantify measurement repeatability.

---

## 8. What Counts as a False Positive

Under strict benchmark challenge rules, inventing a fake opening is penalized equally to missing a real opening.

A candidate is classified as a false positive and rejected if:
1. **No Supporting Wall**: The visual candidate projects into empty space or far from any Stage 2 structural wall.
2. **Implausible Dimensions**: Projected clearance width is $<0.45\text{ m}$ (too narrow for a doorway or window) or $>2.60\text{ m}$ (furniture spans).
3. **Lack of Frame Persistence**: Single-frame provisional detections with detector score $<0.40$ are quarantined into `uncertain_openings`.
4. **Free-standing Furniture**: Wardrobes, cabinets, and decorative screens located in the room interior whose depth steps do not align with verified wall planes.

---

## 9. Why Detection and Measurement Are Separate Challenge Gates

Evaluation of structural openings requires two distinct evaluation gates:

| Gate | Task | Metric | Failure Mode |
|---|---|---|---|
| **Gate 1: Detection** | Semantic presence & wall association | Precision & Recall ($\ge 85\%$) | Missing a real door, hallucinating a mirror/wardrobe |
| **Gate 2: Measurement** | Physical clearance width | Absolute Error $\le 2\text{ cm}$ | Detecting the door correctly but reporting $0.82\text{ m}$ instead of $0.90\text{ m}$ |

A measurement engine cannot succeed if the perception front-end attaches the opening to the wrong wall or measures furniture. Conversely, perfect semantic detection is useless if pixel projection yields 10 cm errors.

---

## 10. Why Ground Truth Is Required Before Claiming $\le 2\text{ cm}$ Accuracy

Physical measurement accuracy cannot be claimed or certified through synthetic benchmarks or self-referential metrics alone.

Until calibrated laser-distance-meter or physical steel-tape measurements are recorded on benchmark spaces:
1. **Uncalibrated Status**: All Stage 5 outputs must report `"calibrated": false` and `"calibration_status": "awaiting_ground_truth_benchmark"`.
2. **Honest Engineering Intervals**: Uncertainty intervals $[W_{\text{lower}}, W_{\text{upper}}]$ represent 95% engineering propagation:
   $$u_c = \sqrt{\frac{s^2}{N} + \sigma_{\text{depth}}^2 + \sigma_{\text{wall}}^2 + \sigma_{\text{jamb}}^2}$$
   $$\Delta_{95\%} = 1.96 \cdot u_c$$
3. **Benchmark Record Readiness**: Every opening JSON record maintains pre-formatted null ground-truth fields:
   ```json
   "ground_truth": {
     "width_m": null,
     "detected": null,
     "absolute_error_m": null,
     "pass_2cm_benchmark": null
   }
   ```
This architecture ensures immediate plug-and-play evaluation as soon as physical ground truth data is supplied.
