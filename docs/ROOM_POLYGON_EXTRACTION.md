# Stage 3 — 2D Wall Projection, Corner Intersections & Room Polygon Extraction

This document explains how **CosmoAIProject** converts 3D architectural planes extracted in Stage 2 into a clean, closed, two-dimensional room footprint in Stage 3.

---

## 1. Why 3D Wall Planes Become 2D Lines

In Stage 2, architectural walls are represented as 3D planes in 3D Euclidean space:

$$a \cdot x + b \cdot y + c \cdot z + d = 0$$

Because rooms are designed for walking and human habitation, an architectural floor plan is fundamentally a **2D horizontal cross-section**. If all walls are vertical, their thickness and cross-section do not change as you look up and down. By projecting 3D vertical wall planes downward onto the horizontal ground floor, each 3D wall plane collapses neatly into a 2D line.

---

## 2. Why the XZ Plane is Used

In Apple ARKit and the Stray Scanner coordinate conventions verified in Stage 1 and Stage 2:
- The **$Y$-axis points vertically upward** ($\mathbf{g} \approx -1.0 \cdot \hat{\mathbf{y}}$).
- The **$XZ$-plane represents the horizontal ground floor plane**.

Therefore, when projecting a 3D wall $a \cdot x + b \cdot y + c \cdot z + d = 0$ to 2D, we drop the vertical component $y$ (since vertical walls have $b \approx 0$). Normalizing by $\sqrt{a^2 + c^2}$ yields our robust 2D line equation:

$$A \cdot x + B \cdot z + C = 0 \quad \text{where} \quad A^2 + B^2 = 1$$

Here, $(A, B)$ is the horizontal normal vector pointing perpendicular to the wall, and $(-B, A)$ is the tangent vector running along the wall length.

---

## 3. Infinite Line vs. Finite Wall Segment

In mathematics, a line $A x + B z + C = 0$ is infinite in both directions:

```text
<═════════════════════════════ Infinite Line ═════════════════════════════>
                     [--- Observed Wall Segment ---]
```

However, physical buildings have **finite wall segments**. An infinite line extending from a bedroom wall would slice through hallways, neighboring apartments, and outdoors.

Stage 3 computes the **finite extent** $[s_{\min}, s_{\max}]$ of each wall along its tangent vector:
- The 3D inlier points belonging to the wall are projected onto the 2D line tangent.
- Robust 1st and 99th percentiles are taken as the physical start and end points $\mathbf{p}_{\text{start}}$ and $\mathbf{p}_{\text{end}}$.
- The observed length of the wall is $L = s_{\max} - s_{\min}$.

Restricting lines to finite segments prevents intersections from creating fake corners miles away from the scanned room.

---

## 4. How Wall Intersections Create Corners

When two non-parallel walls meet, their 2D lines intersect at a unique point $(x, z)$:

$$\begin{bmatrix} A_1 & B_1 \\ A_2 & B_2 \end{bmatrix} \begin{bmatrix} x \\ z \end{bmatrix} = \begin{bmatrix} -C_1 \\ -C_2 \end{bmatrix}$$

Using Cramer's rule, the intersection point is solved directly:

$$x = \frac{-C_1 B_2 - (-C_2) B_1}{\det}, \quad z = \frac{A_1 (-C_2) - A_2 (-C_1)}{\det}$$

where $\det = A_1 B_2 - A_2 B_1$.

```text
Wall A ───────────────┐
                      │  ← Candidate Corner (X)
                      │
                      │ Wall B
```

---

## 5. Why Mathematical Intersections Can Be False

Not every mathematical line intersection represents a real physical corner:

1. **Near-Parallel Lines:** If two walls are parallel or nearly parallel ($\det \approx 0$), solving for an intersection involves dividing by a near-zero number, generating wild coordinates far outside the scan.
2. **Distant Intersections:** Two real walls from opposite sides of a property might intersect if projected infinitely, even though they never meet physically.
3. **Mid-Wall Crossings:** An interior partition line or hallway wall might mathematically intersect an exterior wall in the middle, rather than meeting at its physical corner.

Stage 3 rejects intersections that:
- Have an angle smaller than $12^\circ$ (nearly parallel).
- Require extending past observed wall extents by more than `max_extension_m` ($0.35\text{ m}$).
- Lie farther than `max_point_to_segment_m` ($0.40\text{ m}$) from the finite segments.

---

## 6. How Small Gaps Are Handled (Corner Inference)

Real-world LiDAR scans rarely capture the microscopic seam of an interior corner because of furniture, shadows, baseboards, or blind spots.

```text
Wall A ───────────────             (missing observation gap: 0.08m)
                                   
                                   │
                                   │ Wall B
                                   │
```

If the gap is small (extension $\le 0.35\text{ m}$), Stage 3 safely extends the wall lines along their known trajectories until they meet.

Crucially, **Stage 3 records every inferred extension** with `inferred = true` and records the exact metric distance extended for each wall:

```json
{
  "id": "corner_04",
  "inferred": true,
  "extension_wall_a_m": 0.08,
  "extension_wall_b_m": 0.04
}
```

This prevents the algorithm from secretly fabricating missing data.

---

## 7. What a Connectivity Graph Is

Instead of naively sorting corners by polar angle from a center point (which fails on L-shaped, U-shaped, or irregular rooms), Stage 3 builds a **topological connectivity graph**:

- **Nodes:** Physical corners ($C_1, C_2, C_3, C_4$).
- **Edges:** Wall segments connecting consecutive corners ($W_1, W_2, W_3, W_4$).

```text
C1 ════════════ W1 ════════════ C2
 ║                              ║
W4                              W2
 ║                              ║
C4 ════════════ W3 ════════════ C3
```

By searching for simple cycles in this graph, Stage 3 guarantees that every edge of the room polygon corresponds to an actual observed architectural wall.

---

## 8. How the Polygon Is Ordered

To draw a floor plan and compute area, the polygon vertices must be ordered in a continuous perimeter sequence:

$$[(x_1, z_1), (x_2, z_2), (x_3, z_3), \dots, (x_1, z_1)]$$

The graph traversal visits corners sequentially along connected wall edges. The first vertex is repeated at the end to ensure the loop is explicitly closed.

---

## 9. How Invalid and Self-Crossing Polygons Are Detected

Stage 3 uses Shapely 2.0 and explicit geometric audits to ensure physical realism:

1. **Closure (`is_closed`):** Checks that $\|\mathbf{p}_{\text{first}} - \mathbf{p}_{\text{last}}\| < 10^{-4}\text{ m}$.
2. **Simplicity (`is_simple`):** Checks that boundary edges do not cross one another (preventing "figure-8" or bowtie polygons).
3. **Spike & Splay Checks:** Detects zero-length edges ($< 0.001\text{ m}$) or acute pinch points.
4. **Area Range:** Verifies that floor area is reasonable ($1.0\text{ m}^2 \le \text{Area} \le 500.0\text{ m}^2$).

If any check fails, the pipeline sets `valid = false` and outputs detailed diagnostics without hallucinating a shape.

---

## 10. Why False Stage 2 Walls Destroy the Floor Plan

If a bed, wardrobe, or table is misclassified by RANSAC as an architectural wall, it creates false 2D lines slicing through the middle of the room.

If fed directly into corner detection:
- It creates 4 to 8 bogus candidate corners.
- It splits the true room in half, cutting calculated square footage by 50% or more.
- It introduces spurious interior cycles.

Stage 3 prevents this through a mandatory **Wall Quality Gate** (`backend/app/geometry/wall_quality.py`). Planes with excessive fitting RMSE ($> 0.15\text{ m}$), low confidence ($< 0.40$), or insufficient vertical height ($< 1.0\text{ m}$) — such as the known **Wall 09 clutter** ($RMSE = 1.945\text{ m}, \text{conf} = 0.274$) — are strictly rejected before 2D projection begins.

---

## 11. Current Limitations (Honest Assessment)

1. **Multi-Room Environments:** In scans where an open door allows the scanner to see hallway walls (e.g. `c00a170fe1`), multiple connected topological cycles can form. Future stages will use doorway detection to cleanly separate room cycles from adjoining corridor networks.
2. **Curved Walls:** The current pipeline assumes piecewise planar walls. Curved walls will be approximated as multi-segment polylines.
3. **Occluded Corners:** Corner gaps $> 0.35\text{ m}$ are intentionally rejected to maintain high metric fidelity.
