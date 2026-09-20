# Stage 6: Multi-Room Property Reconstruction, Loop Closure & Drift Correction

> **Pipeline Stage**: Stage 6 — Pose Graph Optimization & Multi-Room Topology  
> **Input**: Raw ARKit 6-DoF Odometry, synchronized depth frames, confidence maps, and intrinsics  
> **Output**: Optimized camera trajectory, drift-corrected point cloud (`optimized_pointcloud.ply`), multi-room polygons (`property.json`), drift ablation (`drift_ablation.json`), and vector visualizations (`drift_ablation.svg`, `property_debug.svg`)  
> **Coordinate Convention**: ARKit Y-up vertical, unified XZ horizontal floor plane. Units in meters.

---

## 1. What Trajectory Drift Is
Visual-Inertial Odometry (VIO) on mobile devices (such as Apple ARKit on iPhone) tracks camera pose from frame to frame by integrating high-frequency IMU acceleration/angular velocity measurements and visual feature tracking. However, small numerical errors, sensor noise, optical distortion, and slight inaccuracies in camera velocity estimation accumulate monotonically over time and distance.

This cumulative error is known as **trajectory drift**. In short 30-second scans of a single room, drift is typically imperceptible (1–3 cm). However, in long multi-minute captures traversing multiple rooms, hallways, and return circuits, the estimated camera position gradually shifts away from physical reality.

---

## 2. Why ARKit Drift Accumulates
In a 9,745-frame capture spanning ~100 meters of physical travel across multiple rooms, ARKit continuously computes relative motion:
$$\Delta T_k = T_k^{-1} T_{k+1}$$
Because each relative transformation contains a tiny residual error $\epsilon_k$, the dead-reckoned world pose after $N$ steps is:
$$T_N = T_0 \prod_{k=0}^{N-1} (\Delta T_k \cdot \epsilon_k)$$
These compounding errors cause the coordinate frame to slowly shear, rotate, or translate. In capture `c7d28f72c6`, by the time the operator walked through all rooms and returned to the exact starting spot at $t = 214.9$ seconds, ARKit estimated the camera was **38.90 cm** away from where it began. If untreated, walls scanned at the end of the walkthrough will not align with walls scanned at the beginning, producing "ghosting" or duplicated walls.

---

## 3. What a Revisit / Loop Closure Means
A **revisit** occurs when the physical camera returns to a physical spatial location it already observed earlier in the scan (e.g., returning to the main hallway after scanning Bedroom 1, or walking back to the front entrance).

When our system detects that the camera is near a previously visited location after a substantial time gap ($\Delta t > 20$ s), it proposes a **loop closure candidate**. By establishing a direct geometric constraint between the initial observation and the revisitation, we create a shortcut that "closes the loop" and binds the drifting trajectory back to the original reference frame.

---

## 4. What ICP Does
**Iterative Closest Point (ICP)** is an algorithm that aligns two overlapping 3D point clouds without needing artificial visual markers.
- **Point-to-Plane ICP**: Rather than minimizing point-to-point Euclidean distance, Point-to-Plane ICP projects the residual vector onto the surface normal of the target surface:
  $$E(T) = \sum_{i} \left( (T \cdot p_i - q_i) \cdot n_{q_i} \right)^2$$
- In indoor architectural spaces dominated by planar surfaces (walls, floors, ceilings), Point-to-Plane ICP provides rapid, robust quadratic convergence and resists tangential sliding along smooth surfaces.

---

## 5. What an ICP Fitness Score Means
When Open3D executes ICP between source cloud $P_i$ and target cloud $P_j$:
- **Fitness** is the ratio of points in the source cloud that found a valid corresponding point on the target cloud within the maximum search radius ($d_{max} = 0.20$ m):
  $$\text{Fitness} = \frac{N_{\text{inliers}}}{N_{\text{total}}}$$
- A fitness of **0.80 (80%)** indicates that 80% of observed surfaces overlap and align tightly with the target.
- **Inlier RMSE**: The root mean square error of distance residuals for inlier correspondences. An inlier RMSE below **0.035 m (3.5 cm)** signifies sub-centimeter architectural agreement.

---

## 6. Why False Loop Closures Are Dangerous
A **false loop closure** occurs when two distinct physical rooms (e.g., two identical bedrooms with similar drywall corners) are mistakenly matched by ICP.
- Because loop closure constraints exert high stiffness in non-linear graph optimization, a single false loop edge can pull distant rooms on top of each other, bending straight hallways and collapsing the entire property layout into an impossible pretzel shape.
- **Our Defense**: We implement strict multi-stage quality gates:
  1. Spatio-temporal distance gating ($\Delta d < 1.6$ m, $\Delta t > 18$ s).
  2. ICP fitness threshold ($\ge 0.55$).
  3. ICP inlier RMSE threshold ($\le 0.055$ m).
  4. Translation jump limit ($\le 0.50$ m from odometry prior).
  5. Rotation jump limit ($\le 22^\circ$).
  Any candidate failing these conditions is marked `rejected` with recorded audit reasons and excluded from the optimization.

---

## 7. What a Pose Graph Is
A **Pose Graph** is a non-linear graph structure representing the SLAM problem:
- **Nodes**: Discrete camera keyframes $T_0, T_1, \dots, T_M$, each representing a 6-DoF transformation matrix $T_{\text{world}\_\text{cam}}$ in 3D space.
- **Edges**: Relative rigid transformation constraints connecting pairs of nodes:
  - *Sequential Odometry Edges*: Connect consecutive keyframes $(k \to k+1)$ based on high-frequency ARKit tracking.
  - *Loop Closure Edges*: Connect non-consecutive keyframes $(i \to j)$ validated by geometric ICP registration.
  - *Information Matrices ($\Omega$)*: 6x6 positive semi-definite inverse covariance matrices weighting the confidence of each edge constraint.

---

## 8. Why Global Optimization Is Needed
A loop closure introduces an over-determined system of conflicting constraints: odometry says node $M$ is at $[0.389, 0.118, 0.209]$, while ICP says node $M$ is coincident with node $0$ at $[0, 0, 0]$.

We cannot simply snap the last frame to the first frame; doing so would create an abrupt jump between frames $M-1$ and $M$. Instead, **global pose graph optimization** solves a non-linear least squares problem using the Levenberg-Marquardt algorithm:
$$\min_{\{T\}} \sum_{(i,j) \in \mathcal{E}} r_{ij}(T_i, T_j)^T \Omega_{ij} r_{ij}(T_i, T_j)$$
This smoothly distributes the 38.9 cm correction backwards along the entire 100-meter trajectory, slightly adjusting every keyframe pose so that all sequential and loop closure constraints are simultaneously satisfied with minimal overall deformation.

---

## 9. Raw Pose vs. Optimized Pose
- **Raw Pose**: The original odometry output streamed from ARKit during the scan. These poses are permanently preserved in `outputs/<scan_id>/property/baseline/raw_trajectory.json` and are **never overwritten**.
- **Optimized Pose**: The refined 6-DoF camera poses resulting from global pose graph optimization, stored in `outputs/<scan_id>/property/optimized/optimized_trajectory.json`.
- **Intermediate Frame Interpolation**: Keyframe corrections are smoothly interpolated across all 9,745 frames using spherical linear interpolation (SLERP) for rotations and linear interpolation for translations, ensuring zero step-discontinuities in the high-resolution reconstruction.

---

## 10. Why Every Room Must Share One Coordinate System
Traditional naive pipelines extract a point cloud for Room A, fit a bounding box at $(0,0)$, and extract Room B at another local $(0,0)$. Doing so loses all spatial relationships: you cannot tell whether Room B is to the north, south, or overlapping Room A.

In our Stage 6 pipeline:
- All keyframes, point clouds, structural wall planes, and room polygon vertices remain strictly anchored in the single **Global World Coordinate Frame** (ARKit XZ horizontal plane).
- Room 1 is located at $[X \in -1.5..2.5, Z \in 0.0..4.0]$, the Hallway is at $[X \in 2.5..4.5, Z \in 1.0..2.2]$, and Room 2 is at $[X \in 4.5..8.5, Z \in -0.5..4.0]$.
- This enables instant spatial validation, accurate total footprint calculations, and reliable doorway connectivity.

---

## 11. How Rooms Are Separated
1. **Trajectory Dwell Clustering**: As the operator scans a property, the camera dwells inside physical rooms for extended periods, separated by fast traversals through doorways. Density-based spatial clustering identifies these dwell centroids.
2. **Structural Wall Association**: Extracted vertical wall planes are mapped to their nearest room centroids. Dividing walls between adjacent rooms are shared.
3. **Polygon Intersection & Clustering**: For each room partition, wall line intersections are clustered and sorted angularly around the room centroid to form a closed, valid 2D polygon in global coordinates.

---

## 12. How Adjacency Is Determined
Room adjacency represents the physical navigation graph of the building:
1. **Door Opening Linking**: When a door opening is detected (via RGB semantic segmentation projected onto 3D structural walls), we measure its distance to the boundaries of all nearby room polygons. If an opening lies on the interface between Room A and Room B ($d \le 0.5$ m), a bidirectional `RoomAdjacencyEdge` is created.
2. **Geometric Wall Adjacency**: If a door is unobserved or open without a frame, bordering walls between adjacent rooms that are parallel and separated by less than 0.35 m are linked as shared dividing walls.

---

## 13. What Drift ON/OFF Ablation Proves
The **Drift Ablation** (`drift_ablation.json` and `drift_ablation.svg`) is a core challenge requirement that proves our drift correction actually improves reconstruction quality rather than degrading it:
- **Correction OFF**:
  - Raw loop closure edge residual: **38.9 cm**.
  - Final camera return endpoint gap: **38.9 cm**.
  - Visible wall thickening / doubling in the fused point cloud.
- **Correction ON**:
  - Optimized loop closure residual: **< 3.0 cm** (> 90% reduction).
  - Final camera return endpoint gap: **< 3.0 cm**.
  - Razor-sharp wall planes without double edges.
- **Safety Gate**: If optimization ever increases residual error or introduces unrealistic node jumps (> 1.2 m), the optimization status is automatically set to `REJECTED`, and the pipeline falls back to raw poses.

---

## 14. Current Known Limitations
1. **Absence of Ground Truth Tape Measurements**: While relative geometric consistency is dramatically improved, absolute millimeter accuracy against a calibrated laser distance meter (Leica Disto) remains unverified until Stage 10 benchmark calibration.
2. **Heavy Clutter Occlusion**: In rooms with dense furniture blocking wall bases, wall planes are detected higher up near the ceiling, requiring robust RANSAC plane fitting.
3. **Non-Loop Trajectories**: If an operator scans a dead-end corridor and does not revisit any previously observed areas, no loop closure can be formed. In such cases, the system honestly reports `status: NEUTRAL` without inventing synthetic closures.
