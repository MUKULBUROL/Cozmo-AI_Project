# Stage 7: Video Reconstruction Technical Documentation

## Executive Overview
Stage 7 introduces the **Video Input Tier** to the Cozmo AI floorplan reconstruction system. The pipeline processes ordinary handheld smartphone RGB video (`.mp4`, `.mov`) into metric 3D point clouds, structural planes, and quality-gated room or property outputs. It emits an explicit `NOT_EVALUABLE` result instead of claiming a floor plan when visual registration is too sparse.

In accordance with the core architectural principle:
```
LiDAR  ───► Metric 3D Representation ───► Shared Structural Geometry Engine (Stages 2–6)
Video  ───► Metric 3D Representation ───► THE SAME Structural Geometry Engine (Stages 2–6)
```
No second geometry engine is built for video. The video tier terminates by outputting standard `ReconstructionResult` and `video_pointcloud_filtered.ply`, reusing all downstream structural algorithms.

---

## Technical Foundations

### 1. Why Video Reconstruction is Harder than LiDAR
Unlike LiDAR sensors—which emit time-of-flight laser pulses providing direct, unambiguous metric depth for every pixel—RGB video records only 2D pixel intensity $(R, G, B)$.
- **Scale Ambiguity**: Pure visual motion yields projections that are geometrically identical under uniform scaling.
- **Visual Artifacts**: Handheld video suffers from motion blur, rolling shutter distortions, exposure changes, and low-texture surfaces (e.g. blank white walls).
- **Drift**: Visual odometry accumulates trajectory drift over long sequences without periodic loop closures.

### 2. How Keyframes are Selected
Processing every video frame (at 60 fps) through neural networks is computationally infeasible and introduces redundant stationary observations. Keyframes are selected using:
- **Temporal Stride Windowing**: Evaluates windows every 15–30 frames.
- **Laplacian Variance Sharpness**: Computes edge response variance $\sigma_{\text{Lap}}^2$ to filter out motion blur.
- **Inter-Frame Visual Motion Delta**: Computes normalized thumbnail difference to ensure camera translation/parallax before selection.
- **Exposure Quality Gate**: Rejects crushed blacks ($<15$) or blown highlights ($>245$).

### 3. How Camera Poses are Recovered
Visual camera poses ($R, t$) are estimated using **pycolmap (COLMAP C++ backend)**:
1. **Feature Extraction**: Extracts SIFT descriptors from selected keyframes.
2. **Feature Matching**: Uses exhaustive matching for the bounded 20-50 keyframe workload and falls back to sequential matching when the installed pycolmap interface requires it.
3. **Incremental Bundle Adjustment**: Solves camera poses and triangulates 3D tie points while self-calibrating camera intrinsics $(f_x, f_y, c_x, c_y)$.

### 4. Why Visual SfM Has Arbitrary Scale
In monocular epipolar geometry, the essential matrix $E = [t]_\times R$ and the projection equations are invariant to multiplying all camera translations $t$ and 3D point coordinates $X$ by an arbitrary constant $\lambda > 0$. Therefore, SfM coordinates are dimensionless units.

### 5. What Metric Depth Does
We utilize a locally runnable, indoor-specialized pretrained model:
`depth-anything/Depth-Anything-V2-Metric-Indoor-Small-hf` (ViT-S backbone, 24.8M parameters).
Trained on indoor benchmarks (Hypersim), it predicts dense metric depth maps directly in meters ($0.2\text{m} < Z < 8.0\text{m}$).

### 6. How Absolute Metric Scale is Estimated
To bridge arbitrary SfM units and physical meters, we calculate the global scale multiplier $s$:
1. For each 3D tie point $X_{\text{world}}$, project into observing keyframes:
   $$z_{\text{sfm}} = (R^T (X_{\text{world}} - C))_z$$
2. Sample the predicted metric depth $z_{\text{metric}}$ at projected pixel coordinates $(u, v)$.
3. Compute scale ratio $s_i = \frac{z_{\text{metric}}}{z_{\text{sfm}}}$.
4. Robustly estimate global scale using the median ratio with **Median Absolute Deviation (MAD)** outlier rejection:
   $$s = \text{median}(s_{\text{inliers}})$$
   $$\sigma_s = \frac{1.4826 \cdot \text{MAD}}{\sqrt{N_{\text{inliers}}}}$$
5. Scale camera translations $t_{\text{metric}} = s \cdot t_{\text{sfm}}$ and point coordinates $X_{\text{metric}} = s \cdot X_{\text{sfm}}$. Rotations remain invariant.

### 7. How Uncertainty is Computed
Video measurements incorporate expanded uncertainty components:
$$\sigma_{\text{total}} = \sqrt{\sigma_{\text{corner\_a}}^2 + \sigma_{\text{corner\_b}}^2 + \sigma_{\text{wall\_rmse}}^2 + (L \cdot \sigma_{\text{scale\_rel}})^2 + \sigma_{\text{pose}}^2 + \sigma_{\text{depth}}^2}$$
Because neural depth and visual SfM have higher variance than active LiDAR, video confidence intervals are naturally and honestly wider.

### 8. How the Metric Point Cloud is Created
Metric depth maps are unprojected into 3D camera space:
$$X_{\text{cam}} = \frac{(u - c_x) Z}{f_x}, \quad Y_{\text{cam}} = \frac{(v - c_y) Z}{f_y}, \quad Z_{\text{cam}} = Z$$
Points are transformed into world space via scaled poses $X_{\text{world}} = R_{\text{wc}} X_{\text{cam}} + C_{\text{wc}}$, concatenated across viewpoints, voxel downsampled (0.03m), cleaned via statistical outlier removal, and endowed with estimated surface normals.

### 9. Which Existing Pipeline Stages are Reused
- **Stage 2**: Structural plane extraction (`extract_structure`) finds floor, ceiling, and wall planes via RANSAC.
- **Stage 3**: Room polygon extraction (`run_stage3_pipeline`) projects 2D wall lines, detects corners, and extracts closed room polygons.
- **Stage 4**: Measurement engine (`compute_room_measurements`) produces room area, perimeter, and wall dimensions with uncertainty.
- **Stage 5**: The existing opening pipeline is LiDAR-oriented and is not invoked by Stage 7. Video opening dimensions remain unsupported rather than being inferred from sensor-only inputs.
- **Stage 6**: Multi-room region segmentation, adjacency, and non-overlapping topology validation reuse the existing geometry primitives only after the RGB trajectory passes registration and temporal-coverage gates.

### 10. Why Cross-Tier Comparison is NOT Ground Truth
Comparing video-derived measurements against LiDAR-derived measurements is labeled:
**CROSS-TIER AGREEMENT, NOT GROUND-TRUTH ACCURACY**.
LiDAR scans themselves possess measurement uncertainty and potential drift; agreement demonstrates cross-sensor pipeline consistency, not absolute truth. Absolute accuracy requires calibrated physical tape or laser ground truth.

### 11. Known Limitations
- Extreme featureless white walls with no visual texture may cause sparse tie point dropouts.
- Fast, sudden camera pans causing severe motion blur may drop registered keyframe percentage.
- Highly reflective surfaces (mirrors, glass) require quality masking.
- A valid polygon from one registered SfM component does not establish full-property coverage.
- COLMAP bundle adjustment does not expose an independent correction-off trajectory. Therefore Stage 7 writes drift as `NOT_EVALUABLE` unless a validated RGB loop pair exists; start-to-end displacement alone is never labeled drift.
- Video-derived door and window measurements are not yet produced by the shared Stage 5 implementation.

### 12. CLI Run Commands

#### Single-Room Video Reconstruction
```bash
python3 -m scripts.reconstruct_video \
    --archive "sample data/single_room.zip" \
    --scan c00a170fe1 \
    --capture-id video_single_room
```

#### Multi-Room Whole Property Reconstruction
```bash
python3 -m scripts.reconstruct_video \
    --archive "sample data/single_scan_with_ceiling.zip" \
    --scan c7d28f72c6 \
    --capture-id video_multi_room \
    --multiroom
```

#### Headless Diagnostic Inspection & Cross-Tier Comparison
```bash
python3 -m scripts.view_video_reconstruction \
    --capture-id video_single_room \
    --lidar-scan c00a170fe1 \
    --headless
```

## Executed Validation Results

These results describe the checked-in implementation on the available captures; they are not accuracy claims.

### Standalone RGB Isolation

The pipeline completed from a standalone MP4 in a directory containing no `odometry.csv`, sensor `depth/`, `confidence/`, or LiDAR point cloud. The run registered 4 of 25 keyframes, recovered a provisional metric reconstruction, and completed Stages 2-4. This is execution evidence for input isolation, not proof of geometric accuracy.

### Single-Room Archive

The required `c00a170fe1/rgb.mp4` run registered 4 of 25 keyframes (16%), reconstructed 24 sparse points, and achieved 0.4246 px mean and 0.4073 px median reprojection error. Stage 3 rejected the room polygon with `no_valid_closed_simple_cycle_found`; no polygon was fabricated. Any LiDAR comparison is labeled **CROSS-TIER AGREEMENT, NOT GROUND-TRUTH ACCURACY**.

### Multi-Room Archive

The required `c7d28f72c6/rgb.mp4` run used 40 keyframes from a 214.93-second video and completed in 289.2 seconds internally (299.25 seconds wall clock, 1,367,280 KiB peak RSS). It produced 1,224,248 raw RGB-derived points, 32,790 filtered points, and seven structural wall candidates. Metric scale was 0.2342 m per SfM unit with 0.607% relative uncertainty.

Only 4 of 40 keyframes registered (10%), with 60 sparse points and a 106.066-second gap between registered trajectory islands. The 1.68 m2 closed polygon belongs to a partial SfM component and is not presented as a whole-property result. `property/property.json` and `property/drift_ablation.json` therefore report `NOT_EVALUABLE`, zero claimed rooms, no applied drift correction, and the exact quality-gate reasons.
