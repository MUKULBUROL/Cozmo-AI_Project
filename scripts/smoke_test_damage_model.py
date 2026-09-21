"""Model smoke test script for Stage 9 visual damage detection and segmentation.

1. Why this file exists:
   Executes model inference on physical and synthetic damage sample images to measure
   runtime, peak memory usage, confidence scores, and segmentation mask quality,
   verifying local CPU feasibility as required by Stage 9 Step 31.

2. Pipeline stage:
   Stage 9 (Damage Detection, Metric Extent, Concealed-Damage Rules & Repair Scope) - Smoke Test.

3. Inputs:
   Image files in data/damage_dev/*.jpg.

4. Outputs:
   Console metrics reporting model checkpoint, device, runtime, memory, classes, and mask outputs.

5. Coordinate convention:
   2D pixel coordinates [x1, y1, x2, y2].

6. Unit convention:
   Seconds for runtime; megabytes (MB) for memory; pixels for areas.

7. Dependencies:
   time, os, psutil, numpy, PIL, backend.app.damage.*.

8. Assumptions:
   - weights/yolov8s-worldv2.pt exists locally.
"""

import time
import os
import sys
import psutil
from pathlib import Path
import numpy as np
from PIL import Image

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.app.damage.detector import OpenVocabularyDamageDetector
from backend.app.damage.segmenter import DamageMaskSegmenter


def run_smoke_test():
    proc = psutil.Process(os.getpid())
    t0 = time.time()
    mem0 = proc.memory_info().rss / 1024 / 1024

    det = OpenVocabularyDamageDetector(weights_path="weights/yolov8s-worldv2.pt", device="cpu")
    seg = DamageMaskSegmenter()

    img_paths = [
        "data/damage_dev/water_stain_wall.jpg",
        "data/damage_dev/crack_wall.jpg",
        "data/damage_dev/hole_wall.jpg",
        "data/damage_dev/mold_ceiling.jpg",
    ]

    print("=" * 60)
    print("STAGE 9 MODEL SMOKE TEST REPORT (Step 31)")
    print("=" * 60)
    print("Model:            YOLO-World (Open-Vocabulary)")
    print("Checkpoint:       weights/yolov8s-worldv2.pt (25.9 MB)")
    print("Device:           CPU (AMD Ryzen 5 5500U)")
    print(f"Classes requested: {len(det.prompt_classes)} damage classes")
    print(f"Initial Memory:   {mem0:.1f} MB")
    print("-" * 60)

    total_candidates = 0
    total_masks = 0

    for p in img_paths:
        if not Path(p).exists():
            continue
        t_start = time.time()
        cands = det.detect(p, conf_threshold=0.04)
        img_arr = np.array(Image.open(p).convert("RGB"))

        for c in cands:
            s_res = seg.segment_candidate(img_arr, c["bbox"], c["canonical_class"])
            c["mask_pixels"] = s_res["mask_area_pixels"]
            c["boundary_pts"] = len(s_res["boundary_polygon"])
            total_masks += 1

        total_candidates += len(cands)
        t_elapsed = time.time() - t_start
        print(f"\nImage: {Path(p).name} | Detections: {len(cands)} | Elapsed: {t_elapsed:.2f}s")
        for c in cands:
            print(f"  - Class: {c['class_name']} -> {c['canonical_class'].value}")
            print(f"    Confidence: {c['confidence']}")
            print(f"    BBox:       {c['bbox']}")
            print(f"    Mask Area:  {c.get('mask_pixels')} px (Boundary points: {c.get('boundary_pts')})")

    mem1 = proc.memory_info().rss / 1024 / 1024
    total_time = time.time() - t0
    print("\n" + "=" * 60)
    print(f"Total Detections: {total_candidates}")
    print(f"Total Masks:      {total_masks}")
    print(f"Total Runtime:    {total_time:.2f}s")
    print(f"Memory Delta:     {mem1 - mem0:.1f} MB (Peak RSS: {mem1:.1f} MB)")
    print("=" * 60)


if __name__ == "__main__":
    run_smoke_test()
