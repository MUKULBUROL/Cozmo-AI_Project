# Architecture Document: Floorplan AI

## 1. Problem Statement
The objective is to convert consumer iPhone captures into dimensioned, stitched 2D/3D floor plans with honest measurement confidence intervals across three input tiers (Photo, Video, LiDAR).
The core governing principle is:
> **AI/ML identifies and segments objects; Geometry calculates where they are and how large they are.**
> Under no circumstances do LLMs hallucinate dimensions from raw images.

---

## 2. Input Tiers
| Tier | Device Class | Inputs Available | Primary Challenge | Output Tolerance Target |
|---|---|---|---|---|
| **PHOTO** | iPhone 15+ (Non-Pro/Pro) | 2–8 still photos per room; no depth; no poses | Sparse multi-view geometry, uncalibrated scale | Wall lengths within $\pm 8\%$ |
| **VIDEO** | iPhone 15+ (Non-Pro/Pro) | Handheld walkthrough video (`.mp4`) | Monocular depth, visual drift, frame selection | Wall lengths within $\pm 3\%$ |
| **LIDAR** | Pro-class iPhone | 16-bit depth maps, 6-DoF odometry, camera intrinsics, IMU | Sensor noise, accumulated drift on large loops | $\le 2\text{ cm}$ opening error on $\ge 85\%$ |

---

## 3. Sample Data Findings
Inspection of `sample data/` revealed three Stray Scanner captures:
- `single_room.zip` (`c00a170fe1`): 1,715 frames, $3.6\text{ m} \times 4.8\text{ m}$ single room.
- `single_scan_floor_only.zip` (`1a8384c3f6`): 5,251 frames, $8.5\text{ m} \times 8.7\text{ m}$ multi-room walkthrough.
- `single_scan_with_ceiling.zip` (`c7d28f72c6`): 9,745 frames, $8.3\text{ m} \times 9.1\text{ m}$ multi-room full vertical sweep.
- **Key Finding**: Raw depth is 16-bit uint16 PNG ($256 \times 192$, millimeters). Video is 1920x1440 HEVC. Poses are in ARKit world space ($+Y$ up). The ceiling scan has an accumulated loop-closure drift of $38.9\text{ cm}$. Standalone photos and ground truth annotations are absent.

---

## 4. Proposed Architecture

```
                      +-------------------+
                      |   INPUT CAPTURE   |
                      +---------+---------+
                                |
          +---------------------+---------------------+
          |                     |                     |
     [PHOTO TIER]          [VIDEO TIER]          [LIDAR TIER]
   Sparse keyframes       Walkthrough MP4       Depth + Odometry
          |                     |                     |
    COLMAP / SfM         DROID-SLAM / DA3      Unproject Depth
    Feature match       Monocular depth + VIO   Confidence filter
          |                     |                     |
          +---------------------+---------------------+
                                |
                                v
                   +-------------------------+
                   |  COMMON 3D MODEL        |
                   |  - Dense/Sparse Cloud   |
                   |  - Camera Trajectory    |
                   |  - Pose Graph / Loop Cl |
                   +------------+------------+
                                |
             +------------------+------------------+
             |                                     |
             v                                     v
   +-------------------+                 +-------------------+
   | GEOMETRY ENGINE   |                 | AI PERCEPTION     |
   | - Gravity Align   |                 | - YOLO / Grounding|
   | - Manhattan Frame |                 | - SAM 2 Segments  |
   | - RANSAC Planes   |                 | - Damage Detector |
   | - Wall Projection |                 | - Opening Bounds  |
   +---------+---------+                 +---------+---------+
             |                                     |
             +------------------+------------------+
                                |
                                v
                   +-------------------------+
                   | METRIC RECONSTRUCTION   |
                   | - Wall intersections    |
                   | - Opening jamb-to-jamb  |
                   | - Clear ceiling height  |
                   | - Honest Error Bounds   |
                   +------------+------------+
                                |
                                v
                   +-------------------------+
                   | 2D ROOM FLOOR PLANS     |
                   | & MULTI-ROOM STITCHING  |
                   +------------+------------+
                                |
             +------------------+------------------+
             |                                     |
             v                                     v
   +-------------------+                 +-------------------+
   | JSON OUTPUT       |                 | RENDERED EXPORTS  |
   | Challenge Schema  |                 | - SVG Vector Plan |
   | Calibrated Conf.  |                 | - DXF CAD / PDF   |
   +-------------------+                 +-------------------+
```

---

## 5. Common Intermediate Representation
All three tiers converge into a unified representation (`ReconstructionResult` in `backend/app/models/reconstruction.py`):
1. **Metric Point Cloud**: Coordinate system aligned with gravity ($+Y$ up, $X$-$Z$ horizontal ground plane).
2. **Camera Trajectory**: Timestamps, 6-DoF poses, and uncertainty covariance.
3. **Bounding Extents & Density Metrics**.

From this intermediate representation, the downstream Geometry and Perception engines operate identically regardless of whether the original source was Photo, Video, or LiDAR.

---

## 6. Reconstruction Strategy by Tier
- **LiDAR Tier**:
  - Unproject 16-bit depth PNGs using scaled camera intrinsics ($256 \times 192$).
  - Mask out low confidence ($conf < 2$) and distant points ($Z > 3.5\text{ m}$).
  - Transform to world coordinates using odometry poses.
  - Voxel downsample (e.g. $2\text{ cm}$ voxel grid) for efficient downstream plane extraction.
- **Video Tier**:
  - Sample keyframes based on optical flow displacement and rotation angles.
  - Apply visual odometry / tracking (or ARKit odometry when available).
  - Apply dense monocular depth (Depth Anything v3) with metric scale alignment to camera trajectory.
- **Photo Tier**:
  - Sparse feature extraction and matching (SIFT / LightGlue).
  - Structure from Motion (SfM / COLMAP) for camera pose estimation and sparse point cloud.
  - Scale recovery via architectural dimensional priors (standard door opening heights: $2.032\text{ m}$).

---

## 7. Geometry Strategy
1. **Gravity Normalization**: Use IMU gravity vector to ensure horizontal floor plane normal is exactly $[0, 1, 0]^T$.
2. **Manhattan Frame Estimation**: Estimate dominant orthogonal wall directions using a 2D orientation histogram.
3. **RANSAC Plane Fitting**:
   - Fit horizontal planes for floor and ceiling ($Y_{\text{floor}}, Y_{\text{ceiling}}$).
   - Fit vertical planes for walls ($n_y \approx 0$).
4. **Boundary Extrusion & Intersection**:
   - Project 3D points onto the horizontal 2D plane.
   - Intersect adjacent non-parallel wall planes to form 2D corners.
   - Form enclosed polygon per room with verified winding order.

---

## 8. Calibration & Uncertainty Strategy
Every measurement $m$ is reported as:
$$\text{Measurement} = \left(\text{value}, \text{unit}, \text{lower\_bound}, \text{upper\_bound}, \text{confidence}, \text{method}\right)$$
- **LiDAR Tier**: Uncertainty derived from depth sensor noise model ($\sigma_{\text{depth}} \approx 1.5\text{ mm} + 0.002 \cdot Z^2$) propagated into plane fitting residuals.
- **Video Tier**: Uncertainty combines tracking covariance and depth scale regression residual ($\pm 3\%$).
- **Photo Tier**: Uncertainty incorporates SfM reprojection error and scale prior variance ($\pm 8\%$).

---

## 9. Drift Strategy
- **The Problem**: Over a 3.5-minute walkthrough, odometry accumulated $38.9\text{ cm}$ drift. Using raw poses causes wall doubling and distorted room shapes.
- **Mitigation Pipeline**:
  1. **Keyframe Extraction**: Select keyframes every $0.5\text{ m}$ translation or $20^\circ$ rotation.
  2. **Loop Closure Detection**: Perform global image retrieval (NetVLAD / DBoW / BoW) to identify revisited locations when camera returns within $1.5\text{ m}$ of a previous trajectory point.
  3. **Scan Matching**: ICP / point-to-plane registration between keyframe point clouds.
  4. **Pose Graph Optimization (PGO)**: Optimize 6-DoF trajectory using g2o / SciPy least-squares with loop closure constraints, distributing drift evenly along the loop.

---

## 10. Damage Strategy
1. **Perception**:
   - Segment surface anomalies using fine-tuned YOLOv8 / SAM 2 on high-resolution RGB frames.
   - Classify into damage classes (`water_stain`, `crack_structural`, `mold`, etc.).
2. **Metric Projection**:
   - Back-project damage mask onto the 3D wall or ceiling plane.
   - Compute true physical area in $\text{m}^2$.
3. **Concealed Damage Rule Engine**:
   - Rule CD-01: Water damage within $15\text{ cm}$ of floor line $\rightarrow$ Flag: "Potential subfloor / sill plate moisture intrusion".
   - Rule CD-02: Transverse ceiling crack $> 1.5\text{ m}$ length $\rightarrow$ Flag: "Structural joist deflection inspection required".

---

## 11. Output Contract
The system exports:
1. `output.json`: Schema matching `PropertyPlanOutput` in `backend/app/models/output.py`.
2. `floorplan.svg`: Clean, dimensioned vector drawing with standard architectural line weights, door swing arcs, and room labels.
3. `floorplan.dxf`: CAD-compatible layer export.

---

## 12. Evaluation Strategy & Benchmark Gates
- **Opening Widths Gate**: $\le 2\text{ cm}$ error on $\ge 85\%$ of openings.
- **Ceiling Height Gate**: $\le 1.5\text{ cm}$ per room error.
- **Repeatability Gate**: Compare reconstructed models of `single_scan_floor_only` vs `single_scan_with_ceiling`. Corresponding walls must agree within $1\text{ cm}$ or $0.5\%$.
- **Adjacency & Non-Overlap**: Topological graph validation checking that room polygons have no self-intersections and zero overlapping floor area.

---

## 13. Known Risks & Mitigation
| Risk | Consequence | Mitigation |
|---|---|---|
| **Low-texture white walls** | SfM / Monocular depth failure | Use structural edge features and floor/ceiling plane constraints |
| **Mirror / Glass reflections** | False depth readings | Filter depth points with inconsistent multi-view reprojection |
| **Rapid camera motion / Blur** | Tracking loss | Fallback to IMU pre-integration and keyframe skipping |
| **Scale drift on long video** | Progressive room distortion | Scale-consistent pose graph optimization with loop closure |
