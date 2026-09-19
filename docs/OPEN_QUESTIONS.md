# Open Questions & Unknowns (Stage 0)

This document tracks all critical ambiguities, missing parameters, and unknowns that cannot be determined directly from the sample dataset. These items must be resolved with challenge organizers or handled with principled fallback designs.

---

## 1. Sensor Modalities & Photo Tier Sourcing
1. **Photo Tier Input Format**:
   - In this sample archive, no standalone still photos were provided.
   - *Question*: Will the official test benchmark provide a folder of discrete `.jpg`/`.heic` images per room with EXIF focal length metadata, or are we expected to extract keyframes from walkthrough video as our standard photo tier input?
2. **Absolute Scale in the Photo Tier**:
   - Monocular still photos have an inherent scale ambiguity ($s \in \mathbb{R}^+$).
   - *Question*: Will the photo captures include any physical scale reference (e.g. known marker, standard door height prior, or EXIF sensor width + distance)?
   - *Fallback Design*: We will utilize architectural dimensional priors (standard US/EU interior door heights: $2.032\text{ m} \pm 0.05\text{ m}$ / ceiling height distributions) to resolve scale, and widen the measurement confidence interval accordingly (e.g., $\pm 8\%$).
3. **Capture Markers & Calibration Aids**:
   - *Question*: Does the walk-in test permit any non-invasive calibration aids (e.g. ArUco markers or AprilTags on door frames), or must the system be 100% markerless?
   - *Assumption*: We assume purely markerless capture.

---

## 2. Walkthrough Video & Pose Availability
1. **Video Tier Tracking Data**:
   - In the sample data, `rgb.mp4` comes alongside `odometry.csv` (ARKit VIO poses).
   - *Question*: In the official VIDEO tier test on non-Pro iPhones (e.g. base iPhone 15 without LiDAR), will ARKit VIO poses (`odometry.csv`) still be provided, or will only raw `.mp4` video be supplied?
   - *Architecture Decision*: We must build the Video Tier pipeline to support **both**:
     - Fast path: Video + ARKit VIO odometry.
     - Autonomous path: Raw video $\rightarrow$ Visual Odometry / Monocular Depth (Depth Anything v3 / COLMAP / DROID-SLAM).

---

## 3. Damage Taxonomy & Concealed Damage Rules
1. **Damage Classification Taxonomy**:
   - The challenge requires: "Per-surface damage regions, Damage class, Metric damage extent, Concealed-damage flags, Rule that triggered each concealed-damage flag, Scope line items keyed to surfaces."
   - *Question*: What is the authoritative list of damage classes? (e.g. IICRC S500 water damage categories, ASTM drywall cracks, or insurance Xactimate scope codes?)
   - *Working Schema*: We established baseline classes: `water_stain`, `crack_structural`, `crack_cosmetic`, `mold`, `impact`, `fire_smoke`, `corrosion`, `surface_peeling`.
2. **Concealed Damage Trigger Rules**:
   - *Question*: What domain rules govern concealed damage flags?
   - *Examples*:
     - *Rule CD-01 (Baseboard Water)*: Water staining within $10\text{ cm}$ of floor triggers concealed moisture inspection flag for insulation/framing.
     - *Rule CD-02 (Ceiling Deflection)*: Ceiling sag $> 2\text{ cm}$ over $2\text{ m}$ triggers joist/truss inspection flag.
     - *Rule CD-03 (Crack Continuity)*: Cracks propagating continuously across two perpendicular walls trigger structural settlement flag.

---

## 4. Final Evaluation & Output Schema
1. **Output Coordinate Alignment**:
   - *Question*: Should the whole-property floor plan be rotated to align principal walls with orthogonal axes ($X$ and $Y$), or maintain the ARKit world frame?
   - *Architecture Decision*: We will compute Manhattan frame alignment (aligning dominant wall normal with $+X$) for clean 2D architectural exports while preserving the global 3D transform.
2. **Opening Width Gate ($\le 2\text{ cm}$ on $\ge 85\%$ of openings)**:
   - *Question*: Is opening width evaluated from rough stud opening or finished casing jamb-to-jamb?
   - *Assumption*: Evaluated from visible inner jamb width (the visual opening detected by segmentation and depth discontinuity).
3. **Repeatability Tolerance Verification**:
   - *Question*: How will the challenge evaluator align two independent captures to evaluate the $1\text{ cm}$ or $0.5\%$ agreement? (e.g. Iterative Closest Point on wall line segments or bounding boxes?)
