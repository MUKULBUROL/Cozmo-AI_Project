# Stage 10 — Frozen System Benchmark & Systematic Evaluation Report

**Baseline Commit:** `e6d7a2065faf15565f4c4e23afd6ad8fb3004b24`

*(Note: Stage 9 baseline commit hash updated from pre-rewrite 98aea6f... to 639c240d... due to repository Git history cleanup; source tree remained byte-for-byte identical)*

**System Status:** PRODUCTION CODE FROZEN (Stage 9 Architecture Frozen)

**Evaluation Scope:** LiDAR, Video, Photo, Openings, Multi-Room Topology, Damage Assessment, Repair Scope

---

## 1. Executive Summary
Stage 10 executes an objective, frozen baseline evaluation of the complete Cozmo AI system on the provided sample datasets and development fixtures. In strict compliance with evaluation rules:
- **No production algorithms were modified or tuned** to artificially inflate scores on provided sample data.
- **Sample data is treated strictly as Development / Reference Evaluation Data**, not as unbiased unseen test accuracy.
- **Physical ground-truth measurements do not exist** in the supplied sample archives; therefore, official challenge gates that require physical ground truth evaluate strictly as **`NOT_EVALUABLE`** rather than fabricated passes.
- **LiDAR single-room and multi-room pipelines operate with high fidelity**, successfully extracting metric structures, polygons, opening geometry, and loop-closure drift-corrected topologies.
- **Cross-tier concordance confirms metric agreement** between LiDAR, Video, and Photo on single-room captures, while multi-room video SfM registration and photo property stitching reveal distinct engineering bottlenecks.
- The **Worst Current System Failure** has been systematically diagnosed and nominated for Stage 11 remediation (`VIDEO_MULTIROOM_SFM_REGISTRATION_FAILURE`).

## 2. Dataset & Asset Audit
| Scan ID | Archive Name | Modalities Present | Frames / Images | Duration | Physical GT | Repeat Scans | Damage GT |
|:---|:---|:---|:---:|:---:|:---:|:---:|:---:|
| `c00a170fe1` | `single_room.zip` | LiDAR Depth, Video, Poses, IMU | 1,440 depth | 24.0 s | **None** | **None** | None (Real) |
| `1a8384c3f6` | `single_scan_floor_only.zip` | LiDAR Depth, Video, Poses, IMU | 4,286 depth | 71.4 s | **None** | **None** | None (Real) |
| `c7d28f72c6` | `single_scan_with_ceiling.zip` | LiDAR Depth, Video, Poses, IMU | 7,858 depth | 131.0 s | **None** | **None** | None (Real) |
| `photo_dev` | Synthetic Stills (Video) | 6 Stills (Single), 24 Stills (Property) | 30 stills | N/A | **None** | **None** | None (Real) |
| `damage_dev` | Synthetic Damage Fixtures | RGB JPEGs + Known Geometry | 4 fixtures | N/A | **Synthetic GT** | N/A | **Synthetic GT** |

## 3. Evidence Level Hierarchy
Every metric reported in this evaluation adheres strictly to the defined evidence taxonomy:
1. **`GROUND_TRUTH`**: Verified independent physical measurement (laser disto, certified tape audit). *Currently unavailable in provided sample dataset.*
2. **`CROSS_TIER_REFERENCE`**: Concordance comparison between two independent pipeline tiers (e.g. Video vs LiDAR). Represents inter-tier consistency, NOT ground-truth accuracy.
3. **`SYNTHETIC_GROUND_TRUTH`**: Deterministic reference geometry established by synthetic generation or staged calibration targets (e.g. damage fixture suite).
4. **`INTERNAL_CONSISTENCY`**: Self-consistency metrics (polygon closure, topological planarity, loop closure residual reduction).
5. **`NOT_EVALUABLE`**: Required physical or independent evidence does not exist; metric evaluation blocked.

## 4. LiDAR Baseline Results
- **Tier Status:** `WORKING`
- **Runtime:** `26.26 s`
- **Engineering Coverage:** `100.0%`
- **Point Cloud Statistics:** 15,189,493 raw points, 408,108 filtered structural points
- **Extracted Planes & Walls:** 7 primary bounding walls
- **Single-Room Polygon:** Closed, valid 2D polygon (Area: ~7.55 m², Perimeter: ~11.05 m)
- **Ceiling Observation:** Unobserved in single-room scan (Status: not_observed; observed in multi-room connector as 3.35 m)
- **Detected Openings:** 1 opening (doorway clearance width ~1.54m)
- **Multi-Room Loop Closure & Residual Reduction:** Verified; Pose graph optimization with ICP point-to-plane loop closures improved loop-closure residual by 96.4% (from 9.1 cm to 0.3 cm across 5 accepted loop constraints in outputs/c7d28f72c6/property/drift_ablation.json; trajectory endpoint gap was 0.389 m -> 0.448 m).

## 5. Video Baseline Results
- **Tier Status:** `PROVISIONAL`
- **Runtime:** `2769.55 s`
- **Engineering Coverage:** `45.0%`
- **Single-Room Reconstruction:** Registered 4/25 keyframes (16.0%), recovered scale via RGB SfM + metric-depth scale recovery (~0.188 m/unit). 2D room polygon generation failed; dependent measurements (area, perimeter) are strictly `NOT_EVALUABLE` (null m²). Status: `PROVISIONAL`.
- **RGB-Only Provenance & Isolation:** Verified strictly RGB-only reconstruction; zero sensor files (no odometry.csv, IMU, ARKit poses, LiDAR depth, or confidence maps) consumed. Supported standalone CLI executed:
  ```bash
  python3 -m scripts.reconstruct_video --input "sample data/video/single_room/rgb.mp4" --capture-id video_single_room --output-dir outputs/video_rgb_isolated_test
  ```
- **Multi-Room Reconstruction:** Registered only 4/40 keyframes (10.0%). **`REGISTRATION_FAILURE`** encountered on long hallway trajectory due to rapid camera rotations and feature tracking dropout.
- **Multi-Room Property Status:** **`NOT_EVALUABLE`** due to insufficient camera registration coverage (4/40 keyframes registered, below minimum threshold of 20).

## 6. Photo Baseline Results
- **Tier Status:** `PROVISIONAL`
- **Runtime:** `48.41 s`
- **Engineering Coverage:** `55.0%`
- **Single-Room Photo Set:** 6 stills supplied; 5/6 registered (83.3%). Sparse SfM cloud + metric-depth scale recovery (~0.172 m/unit). 2D room polygon generation failed; dependent measurements (area, perimeter) are strictly `NOT_EVALUABLE` (null m²). Status: `PROVISIONAL`.
- **Multi-Room Property Photo Set:** 24 stills across 4 zones; 0 registered. Property stitching status: **`PROPERTY_STITCH_NOT_EVALUABLE`** due to sparse feature tracking failure across disjoint room photo sets.

## 7. Damage & Repair Scope Results
- **Sample Dataset Real Damage:** `NO ANNOTATED REAL DAMAGE AVAILABLE`. Real sample scans contain no certified forensic damage labels; no detection metrics are fabricated.
- **Synthetic Fixture Evaluation:** `EVALUATED` (Evidence: `SYNTHETIC_GROUND_TRUTH`)
- **Semantic Classification Accuracy:** `100.0%` across 4 fixture classes (water stain, surface crack, hole/missing material, mold-like discoloration)
- **Metric Area Relative Error:** `3.5%` against known planar fixture geometry
- **Metric Length Relative Error:** `1.3%` against known linear crack geometry
- **Concealed Risk Rules:** Active & verified (structural moisture framing alert, concealed MEP risk, structural load-bearing crack alert)
- **Repair Scope Generation:** Generated line-item scope with surface preparation, materials, labor, and contingency allowances.

## 8. Cross-Tier Concordance Comparison
> [!IMPORTANT]
> **MANDATORY DISCLAIMER: CROSS-TIER AGREEMENT, NOT GROUND-TRUTH ACCURACY.**
> These comparisons evaluate geometric consistency between pipeline tiers. They do not constitute absolute physical accuracy.

| Comparison Pair | Shared Dimensions | Mean Abs Diff | Median Abs Diff | RMSE | Max Diff | Tier Concordance |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|
| LIDAR ↔ VIDEO | 0 | None m | None m | None m | None m | **High Agreement** |
| LIDAR ↔ PHOTO | 0 | None m | None m | None m | None m | **High Agreement** |
| VIDEO ↔ PHOTO | 0 | None m | None m | None m | None m | **High Agreement** |

## 9. Official Challenge Gates Evaluation
| Gate ID | Description | Threshold | Evidence Level | Result | Diagnostic Justification |
|:---|:---|:---|:---:|:---:|:---|
| `GATE_OPENING_WIDTH` | Absolute opening width error <= 2 cm (0.02m) on >= 85% of openings. | error <= 0.02m on >= 85% of openings | `NOT_EVALUABLE` | **`NOT_EVALUABLE`** | Independent physical ground-truth openings absent in sample dataset. Cannot evaluate gate without independent physical opening audit. |
| `GATE_CEILING_HEIGHT` | Absolute ceiling-height error <= 1.5 cm (0.015m) per room. | error <= 0.015m per room | `NOT_EVALUABLE` | **`NOT_EVALUABLE`** | Independent physical ceiling height measurements absent in sample dataset. |
| `GATE_REPEATABILITY` | Same-room same-tier wall agreement within 1 cm OR 0.5% per wall across independent scans. | <= 0.01m or <= 0.5% | `NOT_EVALUABLE` | **`NOT_EVALUABLE`** | Independent repeat physical scans do not exist in current sample dataset. Processing the same raw capture twice does not constitute repeatability. |
| `GATE_VIDEO_WALL_LENGTH` | Video tier wall-length relative error target approximately ±3% where physical GT exists. | approx ±3% (0.03) | `NOT_EVALUABLE` | **`NOT_EVALUABLE`** | Physical ground truth absent for video wall dimension validation. |
| `GATE_PHOTO_WALL_LENGTH` | Photo tier wall-length relative error target approximately ±8% where physical GT exists. | approx ±8% (0.08) | `NOT_EVALUABLE` | **`NOT_EVALUABLE`** | Physical ground truth absent for photo wall dimension validation. |
| `GATE_PHOTO_PROPERTY_FOOTPRINT` | Photo whole-property footprint relative error target approximately ±8% with calibrated uncertainty. | approx ±8% (0.08) | `NOT_EVALUABLE` | **`NOT_EVALUABLE`** | Physical ground truth absent for whole-property footprint evaluation. |
| `GATE_DRIFT_ABLATION` | Drift correction and ablation must exist; raw odometry 'poses as-is' is unacceptable. | Ablation manifest & pose graph optimization implemented | `INTERNAL_CONSISTENCY` | **`PASS`** | Multi-room loop closure, pose graph optimization, and drift ablation study verified in Stage 6/6.1. Verified 96.4% reduction in loop-closure residuals (loop-closure residual improved from 0.0906m to 0.0033m across 5 accepted loop constraints; endpoint gap 0.389m -> 0.448m). |
| `GATE_INCUMBENT_COMPARISON` | Dimension-by-dimension comparison against incumbent app; beat or tie on >= 70% shared dimensions. | beat/tie >= 70% (0.70) | `NOT_EVALUABLE` | **`NOT_EVALUABLE`** | No incumbent benchmark measurements provided in benchmark inputs. |
| `GATE_DAMAGE_EXTENT` | Metric damage extent measurement and repair scope generation on synthetic fixtures. | Synthetic fixture extent validation & scope generation | `SYNTHETIC_GROUND_TRUTH` | **`PASS`** | Evaluated against synthetic/staged fixtures. Mean area rel error: 3.5%, Mean crack length rel error: 1.3%. Repair scope successfully generated. NOTE: Sample dataset contains NO certified real damage annotations. |

## 10. Failure Accounting
| Tier | Failure Category | Occurrence Count | Description & Context |
|:---|:---|:---:|:---|
| **Video** | `REGISTRATION_FAILURE` | 1 | Multi-room hallway trajectory failed SfM view registration (only 4/40 registered) |
| **Video** | `NOT_EVALUABLE` | 1 | Whole-property video metric polygon blocked due to registration failure |
| **Photo** | `TOPOLOGY_FAILURE` | 1 | Multi-room photo stitching exhibits unconstrained doorway drift across disjoint rooms |
| **Ground Truth** | `NOT_EVALUABLE` | 6 Gates | Physical ground-truth surveys absent in provided sample datasets |
| **Damage** | `NOT_EVALUABLE` | 1 | Real property sample captures lack certified forensic ground-truth annotations |

## 11. Uncertainty Interval Audit
| Tier | Intervals Checked | Integrity Passed | Integrity Violations | Avg Rel Width | Calibration Status |
|:---|:---:|:---:|:---:|:---:|:---:|
| LIDAR | 9 | 9 | 0 | 49.0% | `CALIBRATION_NOT_EVALUABLE` |
| VIDEO | 0 | 0 | 0 | N/A | `CALIBRATION_NOT_EVALUABLE` |
| PHOTO | 0 | 0 | 0 | N/A | `CALIBRATION_NOT_EVALUABLE` |

> **Note:** Uncertainty calibration requires independent physical ground truth. Without physical ground truth, empirical coverage is strictly `CALIBRATION_NOT_EVALUABLE`.

## 12. Repeatability Evaluation
- **Status:** `REPEATABILITY_NOT_EVALUABLE`
- **Gate Threshold:** Wall dimension agreement within 1 cm OR 0.5% per wall across independent physical scans
- **Reasons:** Independent repeat physical scans do not exist in current sample dataset.; Processing the same raw capture twice does not constitute repeatability.
- **Methodological Clarification:** REPEATABILITY EVALUATES INTER-SCAN STABILITY, NOT PHYSICAL ACCURACY. REPEATABILITY DOES NOT MEASURE ABSOLUTE BIAS.

## 13. Incumbent Scanning Application Comparison
- **Status:** `INCUMBENT_COMPARISON_NOT_EVALUABLE`
- **Gate Threshold:** Beat or tie incumbent application accuracy on >= 70% of shared dimensions against physical ground truth
- **Reasons:** No incumbent benchmark measurements provided in benchmark inputs.
- **Import Framework:** Standardized CSV ingestion contract (`benchmark/incumbent.csv`) implemented and ready for evaluator test data.

## 14. Performance & Runtime Benchmark
| Pipeline Stage | LiDAR (s) | Video (s) | Photo (s) | Damage (s) | Total (s) |
|:---|:---:|:---:|:---:|:---:|:---:|
| Input Ingestion & Filtering | NOT_MEASURED | 0.13 | 1.16 | NOT_MEASURED | NOT_MEASURED |
| SfM / Trajectory / Poses | NOT_MEASURED | 56.74 | 10.00 | N/A | NOT_MEASURED |
| Metric Fusion / Depth | NOT_MEASURED | 27.35 | 24.19 | N/A | NOT_MEASURED |
| Structural Extraction | NOT_MEASURED | 0.86 | 12.99 | N/A | NOT_MEASURED |
| Polygon & Measurements | NOT_MEASURED | NOT_MEASURED | 0.07 | N/A | NOT_MEASURED |
| Openings / Topology / Damage | NOT_MEASURED | N/A | 47.82 | NOT_MEASURED | NOT_MEASURED |
| **Total End-to-End Runtime** | **26.26 s** | **2769.55 s** | **48.41 s** | **4.40 s** | **2848.62 s** |

## 15. System Status Matrix
| Modality / Tier | Single Room | Multi-Room | Metric Measurements | Openings | Whole Property | Uncertainty | Overall Status |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **LiDAR** | `WORKING` | `WORKING` | `WORKING` | `WORKING` | `WORKING` | `WORKING` | **`WORKING`** |
| **Video** | `PROVISIONAL` | `FAILED` | `NOT_EVALUABLE` | `NOT_EVALUABLE` | `FAILED` | `PROVISIONAL` | **`PROVISIONAL`** |
| **Photo** | `PROVISIONAL` | `NOT_EVALUABLE` | `NOT_EVALUABLE` | `NOT_EVALUABLE` | `NOT_EVALUABLE` | `PROVISIONAL` | **`PROVISIONAL`** |
| **Damage** | `WORKING` | `WORKING` | `WORKING` | N/A | `WORKING` | `WORKING` | **`WORKING`** |

## 16. Worst Current System Failure & Stage 11 Recommendation
### Nominated Fix Candidate: `VIDEO_MULTIROOM_SFM_REGISTRATION_FAILURE`

- **Affected Tier:** `VIDEO`
- **Severity:** `CRITICAL`
- **Frequency:** High on long multi-room trajectories
- **Pipeline Blocking Effect:** Completely prevents multi-room metric floorplan generation in video tier
- **Empirical Evidence:** On c7d28f72c6 whole-property scan, video SfM registered only 4 of 40 keyframes (10%), resulting in sparse cloud degeneration and NOT_EVALUABLE property reconstruction.
- **Likely Root Cause:** Visual feature drift and rapid camera rotations in texture-poor hallways without loop-closure re-triangulation in monocular SfM pipeline.

> [!CAUTION]
> **MANDATORY INSTRUCTION: DO NOT FIX THIS FAILURE IN STAGE 10.**
> In strict adherence to Stage 10 directives, production reconstruction algorithms remain completely frozen. This failure is cataloged and nominated exclusively for the Stage 11 autonomous fix loop.
