# Dataset Analysis: Cosmo AI iPhone Scan Benchmark

## 1. Executive Summary
This document provides a comprehensive technical audit of the raw capture data available in `sample data/`.

The dataset consists of **three full LiDAR-equipped handheld iPhone walkthrough captures**, recorded using the open-source **Stray Scanner** format (leveraging Apple ARKit / AVFoundation).

| Scan Archive | Scan ID | Scope | Frames | Video Duration | Depth Frames | Odometry Rows | IMU Rows | Size (Compressed) |
|---|---|---|---|---|---|---|---|---|
| `single_room.zip` | `c00a170fe1` | Single Room | 1,715 | 37.17 s | 1,715 | 1,715 | 3,689 | 84.4 MB |
| `single_scan_floor_only.zip` | `1a8384c3f6` | Multi-Room / Property | 5,251 | 114.78 s | 5,251 | 5,251 | 11,397 | 263.9 MB |
| `single_scan_with_ceiling.zip` | `c7d28f72c6` | Multi-Room / Property | 9,745 | 214.92 s | 9,745 | 9,745 | 21,339 | 484.9 MB |

---

## 2. Assessment of the Three Input Tiers

### Tier 1: PHOTO (Still Photos)
- **Do we have photos?** **NO**. There are no standalone still photo directories (e.g., no folders with 2–8 JPG or HEIC files per room).
- **Count**: 0 dedicated still photos.
- **Resolution**: N/A for raw files.
- **EXIF**: N/A for raw files.
- **Synthesized Alternative for Evaluation**: We can synthesize the Photo Tier by extracting 2–8 keyframes per room from `rgb.mp4` at wide baseline intervals, stripping all depth maps, camera poses, and IMU data to rigorously benchmark the Photo pipeline.

### Tier 2: VIDEO (Walkthrough Video)
- **Do we have videos?** **YES**. Every scan includes a complete walkthrough video in `rgb.mp4`.
- **Codec**: HEVC / H.265 (`hvc1`, Main profile).
- **Resolution**: $1920 \times 1440$ (4:3 aspect ratio).
- **Framerate**:
  - Timebase: $60.0\text{ fps}$.
  - Actual average playback framerate: ~45.3 to 46.1 FPS (VFR capture under mobile thermal throttling).
- **Durations**:
  - `c00a170fe1`: 37.17 s (1,715 frames)
  - `1a8384c3f6`: 114.78 s (5,251 frames)
  - `c7d28f72c6`: 214.92 s (9,745 frames)
- **Audio**: No audio stream.
- **Color Profile**: `bt709`, `yuvj420p` (full PC color range).
- **Handler**: `Core Media Video` (native Apple AVFoundation).

### Tier 3: LIDAR (Depth + Poses + Intrinsics)
- **Do we have depth?** **YES**. Every scan provides synchronized 16-bit depth PNG images.
- **Depth Format**:
  - Format: PNG 16-bit unsigned integer (`uint16`, mode `I;16`).
  - Resolution: $256 \times 192$ (matches ARKit `sceneDepth` buffer).
  - Units: Millimeters ($1\text{ mm} = 0.001\text{ m}$).
  - Range:
    - Min non-zero depth: $0.24\text{ m}$
    - Max depth: $4.48\text{ m}$
- **Confidence Maps**:
  - Format: PNG 8-bit unsigned integer (`uint8`, mode `L`).
  - Resolution: $256 \times 192$.
  - Values: Discrete ARKit confidence levels:
    - `0`: Low confidence
    - `1`: Medium confidence
    - `2`: High confidence
- **Camera Poses**:
  - Provided in `odometry.csv` for every single video/depth frame.
  - Representation: 6-DoF position $(x, y, z)$ in meters, rotation as unit quaternion $(q_x, q_y, q_z, q_w)$.
- **Intrinsics**:
  - `camera_matrix.csv`: Static $3 \times 3$ intrinsic matrix for $1920 \times 1440$ RGB frames ($f_x \approx 1600, f_y \approx 1600, c_x \approx 955, c_y \approx 717$).
  - `odometry.csv`: Per-frame dynamic focal lengths ($f_x, f_y$) and principal points ($c_x, c_y$).
  - For $256 \times 192$ depth maps, intrinsics scale by factor $256 / 1920 = 2/15$ ($f_{x,\text{depth}} \approx 213.3, c_{x,\text{depth}} \approx 127.4$).
- **IMU Data**:
  - Provided in `imu.csv` at ~100 Hz.
  - Acceleration $(a_x, a_y, a_z)$ in units of $g$ ($1\text{ g} = 9.81\text{ m/s}^2$).
  - Angular velocity $(\alpha_x, \alpha_y, \alpha_z)$ in $\text{rad/s}$.
- **Coordinate Systems**:
  - World coordinate system: ARKit convention (Right-handed, $+Y$ points UP along gravity vector, $+X$ and $+Z$ span the horizontal floor plane).
  - Depth coordinate system: Standard optical pinhole ($+Z$ forward into scene, $+X$ right, $+Y$ down).

---

## 3. Metadata Availability Audit

| Metadata Item | Status | Detail / Value in Sample Data |
|---|---|---|
| **Camera Intrinsics** | **AVAILABLE** | Complete $3\times 3$ matrix in `camera_matrix.csv` & per-frame in `odometry.csv` |
| **Focal Length ($f_x, f_y$)** | **AVAILABLE** | $f_x \approx 1599.7\text{ px}, f_y \approx 1599.7\text{ px}$ (for 1920x1440) |
| **Principal Point ($c_x, c_y$)** | **AVAILABLE** | $c_x \approx 955.4\text{ px}, c_y \approx 717.8\text{ px}$ |
| **Distortion Parameters** | **AVAILABLE** | Distortion center logged in `odometry.csv` (empty/near zero for rectified stream) |
| **Camera Poses** | **AVAILABLE** | Complete 6-DoF translation $(x, y, z)$ and quaternion $(q_x, q_y, q_z, q_w)$ per frame |
| **Timestamps** | **AVAILABLE** | Monotonic timestamps in seconds with millisecond precision across all CSVs |
| **IMU (Accel + Gyro)** | **AVAILABLE** | $a_x, a_y, a_z, \alpha_x, \alpha_y, \alpha_z$ logged at ~100 Hz in `imu.csv` |
| **LiDAR Depth** | **AVAILABLE** | 16-bit uint16 depth PNGs ($256 \times 192$) for every frame |
| **LiDAR Confidence** | **AVAILABLE** | 8-bit uint8 confidence PNGs ($256 \times 192$, levels 0, 1, 2) |
| **Device Model** | **UNKNOWN** | Device string is not explicitly serialized in the CSV headers (inferred iPhone 12 Pro–15 Pro from Stray Scanner / ARKit specs) |
| **Image Dimensions** | **AVAILABLE** | Video: $1920 \times 1440$; Depth: $256 \times 192$ |
| **Video FPS** | **AVAILABLE** | $60.0\text{ fps}$ nominal timebase, ~45.5 FPS average effective |
| **Coordinate System** | **AVAILABLE** | ARKit right-handed Y-up (confirmed via IMU gravity alignment) |
| **Units** | **AVAILABLE** | Metric: meters for poses/geometry, millimeters for depth, $g$ for acceleration |

---

## 4. Trajectory and Property Scale Analysis

### Trajectory Bounds (Estimated from Odometry Poses):

1. **`single_room` (`c00a170fe1`)**:
   - $X$ span: $[-2.55, 1.06]\text{ m}$ (range: $3.62\text{ m}$)
   - $Y$ span: $[-0.19, 0.09]\text{ m}$ (range: $0.28\text{ m}$ vertical walking motion)
   - $Z$ span: $[-0.74, 4.04]\text{ m}$ (range: $4.78\text{ m}$)
   - Room footprint: $\approx 3.6\text{ m} \times 4.8\text{ m}$ (~17.3 m²)

2. **`single_scan_floor_only` (`1a8384c3f6`)**:
   - $X$ span: $[-6.08, 2.43]\text{ m}$ (range: $8.51\text{ m}$)
   - $Z$ span: $[-0.13, 8.54]\text{ m}$ (range: $8.67\text{ m}$)
   - Property footprint: $\approx 8.5\text{ m} \times 8.7\text{ m}$ (~73.7 m²)
   - Loop-closure start-to-end distance: $0.172\text{ m}$

3. **`single_scan_with_ceiling` (`c7d28f72c6`)**:
   - $X$ span: $[-2.19, 6.11]\text{ m}$ (range: $8.30\text{ m}$)
   - $Z$ span: $[-0.24, 8.89]\text{ m}$ (range: $9.13\text{ m}$)
   - Property footprint: $\approx 8.3\text{ m} \times 9.1\text{ m}$ (~75.8 m²)
   - Loop-closure start-to-end distance: $0.389\text{ m}$

### Drift Observation:
Notice that in the multi-minute walkthrough `single_scan_with_ceiling`, the trajectory returns to the same origin point with an accumulated drift of **$0.389\text{ m}$ (38.9 cm)**.
This directly validates the challenge requirement:
> *"Drift: must explicitly handle accumulated drift. 'Use poses as-is' fails."*
Without loop closure and pose graph optimization, a 39 cm drift causes walls to fail to align, creating doubled walls and distorted opening dimensions.
