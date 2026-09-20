# Stage 11 Fix Declaration — Video Multi-Room Registration Recovery

## Failure
`VIDEO_MULTIROOM_SFM_REGISTRATION_FAILURE`

Current Baseline:
- 40 multi-room RGB keyframes extracted from 214.93s video (`c7d28f72c6`)
- Only 4 registered views (KF06, KF07, KF26, KF27)
- Registration ratio: 10.0%
- Reprojection error: 0.732 px
- Largest tracking gap: 106.066s
- Multi-room property status: `NOT_EVALUABLE`
- Drift evaluation status: `NOT_EVALUABLE`

---

## Baseline Evidence
Measured directly from `outputs/fix_loop/stage11_video/before/registration_diagnostics.json` and `database.db`:
1. **Match Graph Disconnection**: Across all 780 candidate pairs in exhaustive matching, only 21 pairs achieved valid two-view epipolar geometry ($\ge 15$ inliers).
2. **Component Fragmentation**: The matching graph fragmented into 24 disconnected components, including 16 completely isolated nodes (KF01, KF03, KF04, KF11, KF13, KF14, KF15, KF20, KF23, KF24, KF28, KF30, KF33, KF34, KF37, KF39).
3. **Sequential Tracking Failure**: 32 of 39 adjacent frame transitions ($i \leftrightarrow i+1$) produced 0 verified geometric inliers. Only 6 transitions had valid inliers (KF06-07: 83, KF08-09: 20, KF17-18: 129, KF26-27: 131, KF31-32: 175, KF35-36: 15).
4. **PyColmap Sub-Model Splitting**: Incremental SfM mapped 3 separate small clusters:
   - Sub-model 0: 4 keyframes (KF06, KF07, KF26, KF27)
   - Sub-model 1: 4 keyframes (KF19, KF20, KF36, KF38)
   - Sub-model 2: 3 keyframes (KF10, KF12, KF29)
   The pipeline discarded sub-models 1 and 2, keeping only the 4 frames in sub-model 0.

---

## Root Cause

### Primary Root Cause
**Rigid, Overlap-Agnostic Windowed Keyframe Sampling**:
The baseline keyframe extractor divided the 9,745-frame (214.93s) video into 40 fixed time-windows of ~243 frames (~5.4s) and selected the single frame with the highest discrete Laplacian score ($\text{argmax}(\text{sharpness})$) independently inside each window. Because candidates were chosen without any inter-frame visual motion delta or overlap constraint, keyframes landed at opposite edges of adjacent windows, resulting in blind temporal gaps between consecutive keyframes of up to 468 frames (10.32s, e.g. KF33 $\rightarrow$ KF34), 433 frames (9.55s, KF36 $\rightarrow$ KF37), 413 frames (9.11s, KF00 $\rightarrow$ KF01), and 381 frames (8.40s, KF07 $\rightarrow$ KF08). In a continuous indoor walkthrough, moving 5 to 10 seconds through doorways, tight turns, or down hallways completely changes the visible field of view, causing adjacent keyframes to have near-zero visual overlap and completely severing the visual odometry chain.

### Secondary Contributing Factors
1. **Incremental Mapper Sub-Model Discarding**: When PyColmap encounters disconnected visual islands, it initializes separate sub-models. The baseline pipeline simply selected `max(num_reg_images)` and discarded all other reconstructed views.
2. **Sensitivity of Feature Matching**: Standard default SIFT feature matching parameters without guided matching or cross-validation tuning left sparse indoor walls with insufficient mutual nearest-neighbor matches.

---

## Proposed Fix
We implement a focused, multi-layer fix adhering strictly to the RGB-only mandate:

1. **Overlap-Aware Continuous Keyframe Selection** (`keyframes.py`):
   - Replace rigid independent window $\text{argmax}(\text{sharpness})$ with overlap-aware sequential selection.
   - Enforce an upper bound on inter-keyframe time/motion spacing ($\le 160$ frames / $\sim 3.5$s) while respecting the 40-keyframe budget.
   - Ensure consecutive candidate frames maintain sufficient visual continuity (motion delta $\ge \text{min\_delta}$ and $\le \text{max\_delta}$) and adequate exposure/sharpness.
2. **Hybrid Local Sequential + Wide-Window + Loop Retrieval Matching** (`sfm.py`):
   - Explicitly match local sequential neighbors ($i \pm 1, i \pm 2, \dots, i \pm 5$) to guarantee dense chain connectivity.
   - Employ visual similarity retrieval (e.g. global descriptor or BoW / feature histogram top-k candidates) to discover loop closures and re-entry bridges across different rooms.
   - Enable guided matching during two-view geometric verification to recover inliers on low-contrast planar walls.
3. **Reconstruction Consolidation / Multi-Component Recovery** (`sfm.py`):
   - In PyColmap incremental mapping, configure robust mapper thresholds (`abs_pose_min_num_inliers=6`, `min_focal_length_ratio=0.1`) to register intermediate frames into the primary model.
4. **Strict RGB-Only Isolation**:
   - Zero access to `depth/`, `confidence/`, `odometry.csv`, `imu.csv`, or ARKit poses.

---

## Quantitative Predictions (Recorded Pre-Implementation)

Before implementing the changes, we state our quantitative predictions:

- **Expected Keyframes Total**: `40`
- **Expected Registered Views**: `24 / 40` (60.0%)
- **Expected Registration Ratio Range**: `50.0% – 70.0%` (at least 20 / 40 registered views)
- **Expected Largest Tracking Gap**: `< 25.0s` (down from 106.066s)
- **Expected Connected Graph Components**: $\le 5$ (down from 24)
- **Expected Consecutive Transition Inliers**: $\ge 25 / 39$ connected (up from 6 / 39)
- **Expected Multi-Room Property Status**: `PROVISIONAL` (qualifying for evaluation with $\ge 20$ registered views and $\ge 30\%$ registration ratio, pending downstream geometry consistency)

*Note: This prediction is committed before modifying algorithm behavior and will not be edited post-fix.*
