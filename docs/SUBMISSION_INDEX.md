# COZMO AI — Challenge Submission Index

This index provides evaluators with a concise roadmap of the COZMO AI repository, documentation, verification tools, and benchmark evidence.

---

## 1. Core Documentation Map

| Document | File Path | Focus |
|---|---|---|
| **Overview & Quickstart** | [README.md](file:///home/devcontainers/Projects/Active/CosmoAIProject/README.md) | Setup, architecture summary, and evaluator entrypoints |
| **Evaluator Demonstration** | [docs/EVALUATOR_DEMONSTRATION.md](file:///home/devcontainers/Projects/Active/CosmoAIProject/docs/EVALUATOR_DEMONSTRATION.md) | Step-by-step CLI and web app demonstration walkthrough |
| **Compliance Matrix** | [docs/COMPLIANCE_MATRIX.md](file:///home/devcontainers/Projects/Active/CosmoAIProject/docs/COMPLIANCE_MATRIX.md) | Evaluation against all challenge gates (Implemented vs. Benchmark Proven) |
| **Capture Protocol & Devices** | [docs/CAPTURE_PROTOCOL.md](file:///home/devcontainers/Projects/Active/CosmoAIProject/docs/CAPTURE_PROTOCOL.md) | Field capture guidelines, motion speed, and device matrix |
| **One-Command Workflow** | [docs/ONE_COMMAND_WORKFLOW.md](file:///home/devcontainers/Projects/Active/CosmoAIProject/docs/ONE_COMMAND_WORKFLOW.md) | CLI commands for LiDAR, Video, Photo, and Multi-Room pipelines |
| **Benchmark Report** | [docs/FINAL_BENCHMARK_REPORT.md](file:///home/devcontainers/Projects/Active/CosmoAIProject/docs/FINAL_BENCHMARK_REPORT.md) | Comprehensive metric verification and gate evidence |
| **Fix Loop Bundle** | [docs/FIX_LOOP_BUNDLE.md](file:///home/devcontainers/Projects/Active/CosmoAIProject/docs/FIX_LOOP_BUNDLE.md) | Stage 11 video multi-room loop closure fix evidence (before/after) |
| **Technical Report** | [docs/TECHNICAL_REPORT.md](file:///home/devcontainers/Projects/Active/CosmoAIProject/docs/TECHNICAL_REPORT.md) | Architecture, error budget, device matrix, and design principles (≤6 pages) |
| **Evidence Audit** | [docs/FINAL_EVIDENCE_AUDIT.md](file:///home/devcontainers/Projects/Active/CosmoAIProject/docs/FINAL_EVIDENCE_AUDIT.md) | Pre-submission audit of benchmark claims vs. available ground truth |
| **Reproducibility Report** | [docs/FINAL_SAMPLE_REPRODUCIBILITY.md](file:///home/devcontainers/Projects/Active/CosmoAIProject/docs/FINAL_SAMPLE_REPRODUCIBILITY.md) | Deterministic end-to-end sample data reproduction audit |

---

## 2. Interactive Evaluator Web Guide

When running the frontend (`cd frontend && npm run dev`), open:
- **Interactive Evaluator Guide**: `http://localhost:3000/demo` (or `http://localhost:3000/evaluator-guide`)
- **Workspace Web App**: `http://localhost:3000`
- **Backend API Docs**: `http://localhost:8000/docs`

---

## 3. Data & Artifact Locations

- **Assessor Sample Archives**: `sample data/` (`single_room.zip`, `single_scan_floor_only.zip`, `single_scan_with_ceiling.zip`)
- **Development Photo Sets**: `data/photo_dev/single_room/`, `data/photo_dev/property_photo_dev/`
- **Development Damage Sets**: `data/damage_dev/SYNTHETIC_DEVELOPMENT_DAMAGE_SET.json`
- **Benchmark Evidence**: `outputs/benchmarks/stage10_baseline/`, `outputs/fix_loop/stage11_video/`
- **Runtime Reconstruction Outputs**: `outputs/<capture_id>/`

---

## 4. Key Verification Commands

```bash
# 1. LiDAR Reconstruction
python3 scripts/reconstruct_lidar.py --scan 1a8384c3f6 --archive "sample data/single_scan_floor_only.zip" --voxel-size 0.02

# 2. Multi-Room Property Reconstruction with Loop Closure
python3 scripts/reconstruct_property.py --scan c7d28f72c6 --archive "sample data/single_scan_with_ceiling.zip" --headless

# 3. Video Monocular Reconstruction
python3 scripts/reconstruct_video.py --archive "sample data/single_room.zip" --scan c00a170fe1 --capture-id video_rec_01 --max-keyframes 30

# 4. Photo Multi-View Reconstruction
python3 scripts/reconstruct_photos.py --input "data/photo_dev/single_room" --capture-id photo_rec_01

# 5. Forensic Damage & Scope Analysis
python3 scripts/analyze_damage.py --capture-id c00a170fe1

# 6. Sample Data Reproducibility Verification
python3 -m scripts.run_final_same_input_reproducibility

# 7. Complete Test Suites
python3 -m pytest backend/tests
cd frontend && npm test && npm run build
```
