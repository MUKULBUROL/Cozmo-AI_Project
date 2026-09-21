# COZMO AI — Spatial Capture Protocol & Best Practices

This guide provides precise, evaluator-friendly instructions for capturing architectural spaces across all three supported modalities (**LiDAR**, **Video**, and **Photo**) to maximize reconstruction accuracy, point-cloud density, and measurement precision.

---

## 1. Modality-by-Modality Capture Guidelines

### Tier 1: LiDAR (iOS LiDAR Sensor Archives)

**Target Device**: iPhone 12 Pro or newer, iPad Pro 2020 or newer equipped with dToF LiDAR.

#### Required Archive Structure
The capture package must be uploaded as a `.zip` archive containing:
```
capture_archive.zip/
  ├── depth/                  # 16-bit uint16 PNG depth frames (values in millimeters)
  │   ├── frame_00000.png
  │   └── ...
  ├── confidence/             # 8-bit uint8 PNG confidence maps (0=low, 1=medium, 2=high)
  │   ├── frame_00000.png
  │   └── ...
  ├── odometry.csv            # ARKit camera trajectory poses (timestamp, tx, ty, tz, qx, qy, qz, qw)
  ├── camera_matrix.csv       # 3x3 intrinsic matrix (fx, fy, cx, cy)
  └── imu.csv                 # Accelerometer and gyroscope telemetry (optional but recommended)
```

#### Sensor Resolution & Units
- **Depth Resolution**: 256 × 192 (or 192 × 144) uint16 array in millimeters.
- **Odometry Reference Frame**: Right-handed metric coordinate frame (+X Right, +Y Up, -Z Forward).

#### Operator Movement Protocol
1. **Perimeter Traversal**: Walk smoothly along the interior perimeter of the room at 0.5 m/s.
2. **Smooth Pitching**: Tilt the device slowly between 15° downwards (floor-wall boundary) and 15° upwards (wall-ceiling boundary).
3. **Loop Closure**: Return to within 0.5m of the starting physical location to provide closing trajectory constraints for the pose-graph optimizer.
4. **Avoid Sudden Jerks**: Avoid rapid panning (> 45 deg/s) to prevent ARKit visual-inertial tracking loss.

---

### Tier 2: Video (Monocular Video Streams)

**Target Device**: Standard smartphone or handheld camera (iOS / Android / Action Camera).

#### Supported Formats & Codecs
- **Container**: `.mp4`, `.mov`
- **Codec**: HEVC (H.265) or AVC (H.264)
- **Framerate**: 30 FPS or 60 FPS (60 FPS strongly recommended for reduced motion blur)
- **Resolution**: 1080p (1920 × 1080) or 1440p (1920 × 1440) or 4K (3840 × 2160)

#### Camera Movement & Sweeping Guidance
1. **Steady Walking**: Hold the camera firmly at chest height (~1.3m to 1.5m above finished floor level).
2. **Continuous Overlap**: Move around the room in a continuous circular loop, maintaining visible overlap with previously recorded features.
3. **Slow Turns**: In corners, pivot on the spot slowly (minimum 3 seconds per 90° corner sweep).
4. **Motion Blur Mitigation**: Ensure sufficient indoor illumination (open blinds or turn on ambient ceiling lights) to allow shutter speeds >= 1/120s.

#### Keyframe Density
- The system automatically extracts keyframes based on optical flow and visual disparity (target: 30 to 60 keyframes per standard room).

---

### Tier 3: Photo (Multi-View Keyframe Clusters)

**Target Device**: Any digital camera or smartphone.

#### Supported Formats & Count
- **Formats**: `.jpg`, `.jpeg`, `.png` packed inside a single `.zip` archive.
- **Recommended Count**: 20 to 50 photos for a single room; 60 to 120 photos for multi-room properties.

#### Overlap & Parallax Guidance
1. **High Visual Overlap**: Ensure **60% to 80% overlap** between successive photographs.
2. **Translate, Don't Just Rotate**: Always take 1–2 steps between camera shots to produce baseline parallax. Pure rotational panoramas from a single tripod position fail Epipolar triangulation.
3. **Corners & Openings**: Capture corners from at least 3 distinct vantage points. Capture door and window frames with both the frame and adjacent wall visible.
4. **Lighting & Exposure**: Maintain fixed exposure and white balance if camera controls permit. Avoid harsh backlit windows where possible.

---

## 2. Multi-Room Traversal Protocol

When scanning multi-room properties:
1. **Connector Strategy**: Always scan the connecting hallway or threshold while traversing between Room A and Room B. Do not pause or cut recording during door transitions.
2. **Door Openings**: Leave all interior passage doors fully open before commencing the capture session.
3. **Return Loop**: Walk from Room A → Hallway → Room B → Room C → Hallway → Room A to allow multi-room loop closure and global drift minimization.

---

## 3. Damage Capture Best Practices

For insurance or forensic defect documentation:
1. **Context Shot**: Capture an establishing wide shot showing the damage relative to adjacent walls/corners.
2. **Perpendicular Close-Up**: Capture a direct, perpendicular shot (0.5m to 1.0m distance) of the defect (crack, stain, mold patch, hole).
3. **Lighting**: Ensure direct illumination without deep cast shadows over the damaged surface.

---

## 4. Summary Quick-Reference Card

| Parameter | LiDAR Tier | Video Tier | Photo Tier |
|---|---|---|---|
| **Input Format** | `.zip` (depth+poses+intrinsics) | `.mp4`, `.mov` | `.zip` (JPEG/PNG sequence) |
| **Typical File Size** | 50 MB – 250 MB | 30 MB – 150 MB | 20 MB – 80 MB |
| **Recommended Capture Duration** | 45s – 90s per room | 30s – 60s per room | 2 – 4 minutes |
| **Metric Scale Anchor** | Hardware dToF Depth | Visual-Inertial / Priors | Reference Priors / Scale Bar |
| **Typical Point Density** | High (~100k - 500k pts) | Moderate (~10k - 50k pts) | Moderate (~5k - 30k pts) |
| **Expected Processing Time** | ~1.2s | ~2.4s | ~1.8s |
