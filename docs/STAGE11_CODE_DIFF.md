# Stage 11 — Focused Code Diff Report

## 1. Overview of Changes

This document explains what changed, why each change was made, which root cause hypothesis it resolves, and what remained untouched during Stage 11.

---

## 2. Modified Components

### Component A: Temporal Keyframe Regularization
- **File**: [`backend/app/pipelines/video/keyframes.py`](file:///home/devcontainers/Projects/Active/CosmoAIProject/backend/app/pipelines/video/keyframes.py)
- **Function**: `extract_optimal_keyframes`
- **What Changed**:
  Added Gaussian temporal window weighting:
  $$\text{score}(f) = \text{sharpness}(f) \cdot \exp\left(-\frac{1}{2}\left(\frac{f - \mu_w}{\sigma_w}\right)^2\right)$$
  where $\mu_w$ is the center frame of the window and $\sigma_w = 0.35 \cdot \text{window\_size}$. Frame 0 is explicitly retained as the initial anchor frame.
- **Why It Changed**:
  Prevented neighboring windows from choosing frames at opposing boundaries (e.g., start of window $k$ and end of window $k+1$), which created blind temporal gaps of up to 10.32 seconds (468 frames).
- **Root Cause Addressed**:
  Root Cause A (Keyframes too far apart during rapid motion/panning) and Root Cause I (Keyframe sampling ignoring temporal continuity).

---

### Component B: Architectural SIFT Feature Extraction & Guided Matching
- **File**: [`backend/app/pipelines/video/sfm.py`](file:///home/devcontainers/Projects/Active/CosmoAIProject/backend/app/pipelines/video/sfm.py)
- **Function**: `run_visual_sfm`
- **What Changed**:
  - `feat_opts.sift.max_num_features = 8192` (increased from 4096).
  - `feat_opts.sift.peak_threshold = 0.002` (lowered from 0.004).
  - `match_opts.guided_matching = True` (enabled epipolar-guided correspondence search).
  - `match_opts.sift.max_ratio = 0.85`.
  - `v_opts.min_num_inliers = 10` (calibrated from 15).
  - `v_opts.ransac.min_inlier_ratio = 0.12`.
  - `v_opts.min_E_F_inlier_ratio = 0.80`.
- **Why It Changed**:
  Indoor residential video contains expansive textureless planar surfaces (white drywall, ceilings, polished floors). Standard SIFT parameters produced $< 15$ verified inliers on hallway transitions, causing COLMAP to reject valid match edges. Guided matching leverages preliminary epipolar geometry to find additional support correspondences.
- **Root Cause Addressed**:
  Root Cause D (Low feature count in textureless corridors) and Root Cause E (Excessively strict verification rejecting valid sequential links).

---

### Component C: Incremental Mapper Robustness
- **File**: [`backend/app/pipelines/video/sfm.py`](file:///home/devcontainers/Projects/Active/CosmoAIProject/backend/app/pipelines/video/sfm.py)
- **Function**: `run_visual_sfm`
- **What Changed**:
  - `inc_opts.mapper.init_min_num_inliers = 15`.
  - `inc_opts.mapper.init_min_tri_angle = 1.5`.
  - `inc_opts.mapper.init_max_reg_trials = 5`.
  - `inc_opts.mapper.max_reg_trials = 5`.
  - `inc_opts.mapper.abs_pose_min_num_inliers = 8`.
  - `inc_opts.mapper.abs_pose_min_inlier_ratio = 0.12`.
  - `inc_opts.mapper.ba_local_min_tri_angle = 1.2`.
  - `inc_opts.mapper.filter_min_tri_angle = 0.5`.
  - `inc_opts.mapper.abs_pose_refine_focal_length = False`.
- **Why It Changed**:
  Prevented camera poses from flying out to degenerate coordinates while allowing bridge keyframes with 8–15 correspondences to successfully register into the unified model. Disabling focal length refinement during registration stabilized the self-calibration for monocular video.
- **Root Cause Addressed**:
  Root Cause F (Fragile SfM initialization and bridge frame rejection) and Root Cause H (Fragmented match graph components).

---

### Component D: Depth Unprojection Boundary Clamping
- **File**: [`backend/app/pipelines/video/fusion.py`](file:///home/devcontainers/Projects/Active/CosmoAIProject/backend/app/pipelines/video/fusion.py)
- **Functions**: `unproject_metric_depth_map`, `fuse_video_metric_pointcloud`
- **What Changed**:
  Added `max_depth_m: float = 8.0` parameter and filter condition `(sub_depth <= max_depth_m)`.
- **Why It Changed**:
  Monocular metric depth estimators can predict arbitrarily large values (> 50m) through open doorways, windows, or dark corners. Unprojecting these values generated far-field outliers that exceeded realistic indoor building scale bounds.
- **Root Cause Addressed**:
  Downstream structural validation failures caused by unbounded monocular depth unprojection.

---

### Component E: Pipeline Diagnostics Integration & Fault Tolerance
- **File**: [`backend/app/pipelines/video/pipeline.py`](file:///home/devcontainers/Projects/Active/CosmoAIProject/backend/app/pipelines/video/pipeline.py)
- **Functions**: `run_video_pipeline`
- **What Changed**:
  - Automated export of `registration_diagnostics.json` and `registration_timeline.svg` directly from the pipeline run.
  - Wrapped downstream Stage 2–4 geometry execution in structured exception handling, recording `geometry_limitation` cleanly rather than terminating the pipeline.
- **Why It Changed**:
  Ensures every video reconstruction automatically generates traceable diagnostics for debugging and prevents downstream property errors from masking SfM successes.
- **Root Cause Addressed**:
  Observability and graceful degradation.

---

## 3. New Modules

### Diagnostics Engine
- **File**: [`backend/app/pipelines/video/registration_diagnostics.py`](file:///home/devcontainers/Projects/Active/CosmoAIProject/backend/app/pipelines/video/registration_diagnostics.py)
- **Functions**:
  - `compute_registration_diagnostics`: extracts per-keyframe metrics, blur scores, candidate/verified match counts, inlier ratios, and graph components.
  - `generate_registration_timeline_svg`: generates vector graphic timeline visualizing registered clusters vs tracking gaps.
  - `generate_match_failure_montage`: stitches paired visual comparisons of transition failures.

---

## 4. What Did NOT Change

1. **LiDAR Pipeline**: Zero lines touched in `backend/app/pipelines/lidar/`.
2. **Photo Pipeline**: Zero lines touched in `backend/app/pipelines/photo/`.
3. **Sensor Tier Isolation**: Video tier does not import, load, or query `odometry.csv`, `imu.csv`, `depth/`, `confidence/`, or ARKit poses.
4. **Structural Extraction Core**: Zero modifications to core plane fitting or wall extraction logic in `backend/app/geometry/`.
5. **No Sample ID Hardcoding**: Zero constants or conditions referencing scan `c7d28f72c6`. All algorithmic updates generalize to arbitrary RGB video captures.
