# Stage 4 — Metric Measurement Engine & Honest Uncertainty Propagation

## 1. Overview & Architecture

Stage 4 transitions reconstructed geometric models (Stage 2 planar point clouds and Stage 3 2D room polygons) into certified, user-facing metric dimensions: wall lengths, room perimeter, polygon floor area, and clear ceiling height.

Crucially, Stage 4 introduces an **honest uncertainty propagation model** and an **automated measurement validity gate**. Rather than reporting arbitrary or heuristic margins (e.g. $\pm 2\,\text{cm}$), every measurement is derived from physical sensor residuals, intersection conditioning, and deterministic Monte Carlo simulations.

```
Stage 3 room_polygon.json + Stage 2 structure.json
                      ↓
       [backend/app/measurements/validity_gate.py]
            (valid | provisional | invalid)
                      ↓
       [backend/app/measurements/uncertainty.py]
  - Corner positional covariance: σ_C = f(RMSE_A, RMSE_B, θ, extension)
  - Wall edge length intervals:   ΔL = 1.96 * sqrt(σ_Ca² + σ_Cb² + RMSE_w²)
  - Monte Carlo polygon perturb:  N=1000 samples -> Area & Perim distributions
  - Evidence confidence:          Plane conf, residual penalty, inference penalty
                      ↓
       [backend/app/measurements/engine.py]
  - Wall lengths, perimeter, floor area
  - Ceiling height (null if unobserved)
  - Output files: measurements.json, wall_dimensions.json, uncertainty.json,
                  measurement_stats.json, dimensioned_debug.svg
```

---

## 2. Mathematical & Algorithmic Explanations

### 1. How Wall Length is Calculated
Wall lengths are computed directly as the Euclidean distance between consecutive polygon vertices $(x_1, z_1)$ and $(x_2, z_2)$ in the horizontal $XZ$ ground plane:
$$L = \sqrt{(x_2 - x_1)^2 + (z_2 - z_1)^2}$$
- Units are metric meters ($m$).
- Distances are maintained in double-precision floating point internally and never pre-rounded.
- Rounding occurs strictly during JSON serialization (3 decimal places) and visual display (2 decimal places).

### 2. How Perimeter is Calculated
Room perimeter is computed as the exact sum of all validated polygon edges comprising the closed room loop:
$$P = \sum_{i=1}^{N} L_i = \sum_{i=1}^{N} \sqrt{(x_{i+1} - x_i)^2 + (z_{i+1} - z_i)^2}$$
Where vertex $N+1 \equiv 1$ closes the polygon.

### 3. How Polygon Area Works
Floor area is computed from the true closed $XZ$ polygon boundary using the surveyor's formula (Green's theorem via Shapely):
$$A = \frac{1}{2} \left| \sum_{i=1}^{N} (x_i z_{i+1} - x_{i+1} z_i) \right|$$
- Floor area is **never** approximated as bounding-box width $\times$ depth ($W \times D$).
- Units are metric square meters ($m^2$).
- Complex, non-rectangular rooms (L-shapes, alcoves, angled walls) are preserved faithfully.

### 4. How Ceiling Height is Calculated
Ceiling height is determined strictly from Stage 2 structural planes:
1. Both the floor plane and ceiling plane must be explicitly detected (`detected: true`).
2. If both exist, the perpendicular distance between horizontal planes is computed:
   $$H = |\bar{y}_{\text{ceiling}} - \bar{y}_{\text{floor}}|$$
3. If the ceiling plane is unobserved (e.g. insufficient upward LiDAR returns):
   $$\text{ceiling\_height} = \text{null}$$
   $$\text{status} = \text{"not\_observed"}$$
Under no circumstances does the engine hallucinate, guess, or assign nominal default ceiling heights (e.g. $2.4\,\text{m}$).

### 5. Difference Between Confidence and Uncertainty
* **Uncertainty** is a dimensional metric of precision and dispersion expressed in measurement units ($\text{meters}$ or $\text{m}^2$). It specifies the calibrated range $[L_{\text{lower}}, L_{\text{upper}}]$ within which the true physical dimension is expected to lie with $95\%$ probability ($k = 1.96$).
* **Confidence** is a dimensionless score in $[0.0, 1.0]$ representing evidence quality and belief. A high confidence score ($0.90$) indicates dense point support, low sensor noise, and fully observed intersections, whereas low confidence indicates heavy extrapolation or noisy point clouds.

### 6. Where Uncertainty Comes From
Uncertainty is derived from physical and geometric contributors:
1. **Wall plane fitting RMSE ($\sigma_{\text{plane}}$)**: Scatter of LiDAR points relative to the fitted 3D plane.
2. **Corner intersection geometry ($\sigma_{\text{geom}}$)**: Lateral wall errors propagated through the intersection:
   $$\sigma_{\text{geom}} = \sqrt{\frac{\sigma_A^2 + \sigma_B^2}{\sin^2(\theta)}}$$
   Where $\theta$ is the angle between wall normals.
3. **Inference extrapolation penalty ($\sigma_{\text{inf}}$)**: Linear penalty proportional to gap distance ($0.50 \times \text{extension\_m}$).
4. **Discretization noise floor ($\sigma_{\text{voxel}}$)**: Baseline LiDAR voxel resolution ($0.01\,\text{m}$).

Combined wall length uncertainty:
$$\sigma_L = \sqrt{\sigma_{C_{\text{start}}}^2 + \sigma_{C_{\text{end}}}^2 + \sigma_{\text{wall\_plane}}^2}$$
Margin of error ($95\%$ coverage):
$$\Delta L = 1.96 \cdot \sigma_L$$

Floor area and perimeter uncertainty intervals are computed via **deterministic Monte Carlo simulation** ($N = 1000$ samples, fixed seed $= 42$), perturbing vertex coordinates by their 2D positional covariance ellipses.

### 7. Why Inferred Corners Reduce Trust
When corners are occluded or unobserved in LiDAR scans, Stage 3 geometrically extends adjacent wall segments to find their intersection. While mathematically valid, extrapolation introduces:
- Drift over unobserved spatial regions.
- Inability to verify the presence of small jogs, pillars, or recesses.
- Increased positional standard deviation $\sigma_C$.
Consequently, inferred corners widen the $95\%$ uncertainty interval and incur a $15\%$ confidence penalty per extrapolated endpoint.

### 8. Why Doorway / T-Junction Ambiguity Matters
In real captures (such as scan `c00a170fe1`), an open doorway into an adjoining corridor creates:
- Perpendicular corridor walls terminating at the doorway.
- Short connecting edges (e.g. the $0.251\,\text{m}$ segment along `wall_02` between `corner_06` and `corner_05`).
- Collinear vertices where multiple corners share a single physical wall plane.
Because these represent room transitions rather than sealed single-room boundaries, the measurement validity gate classifies the scan as **`PROVISIONAL`** (`corridor_doorway_t_junction_detected`), alerting downstream consumers that doorway transitions are present.

### 9. Why Ground Truth is Still Needed
No physical tape-measure or terrestrial LiDAR (Faro/Leica) ground truth currently exists for the sample dataset. Therefore:
- The system never claims "accurate to 1 cm", "99% accurate", or "exact dimensions".
- All dimensions are defined as **engineering estimates derived from mobile reconstruction**.
- External calibration against laser benchmarks is mandatory before certifying dimensions for legal, construction, or insurance dispute settlements.

### 10. Current Limitations
1. **Single-Room Scope**: Stage 4 operates on single closed loops. Multi-room topology and shared wall thickness are deferred to subsequent stages.
2. **Unobserved Ceilings**: Consumer iPhone scans pointing predominantly downward or horizontally fail to register ceiling returns, resulting in null ceiling height.
3. **Planar Wall Assumption**: Curved or non-planar walls are segmented into multiple planar approximations.

---

## 3. Output Deliverables Specification

Stage 4 exports 5 standardized artifacts into `outputs/<scan_id>/measurements/`:

| File | Purpose |
| :--- | :--- |
| `measurements.json` | Master deliverable conforming to the Challenge Output Contract (`Measurement[float]`, `status`, `walls`, `floor_area`, `perimeter`, `ceiling_height`). |
| `wall_dimensions.json` | Wall-by-wall breakdown with coordinate endpoints, intervals, confidence, and error components. |
| `uncertainty.json` | Comprehensive error propagation log and Monte Carlo area/perimeter distributions. |
| `measurement_stats.json` | High-level summary metrics and gate reasons for CI/CD and CLI consumption. |
| `dimensioned_debug.svg` | High-contrast dark-mode CAD diagnostic visualization with dimension leaders, corner markers, and status HUD. |
