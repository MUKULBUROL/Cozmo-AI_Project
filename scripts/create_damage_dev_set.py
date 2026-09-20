"""Development damage dataset generator and Stage 10 staged capture specification.

1. Why this file exists:
   Generates transparently labeled synthetic development damage fixtures with known
   metric ground-truth extents (m2, linear m) and prepares standardized capture instructions
   for physical staged damage benchmark collection in Stage 10, complying with Steps 22 & 23.

2. Pipeline stage:
   Stage 9 (Damage Detection, Metric Extent, Concealed-Damage Rules & Repair Scope) - Dev Dataset.

3. Inputs:
   Target directory path (defaults to data/damage_dev).

4. Outputs:
   - data/damage_dev/SYNTHETIC_DEVELOPMENT_DAMAGE_SET.json
   - data/damage_dev/STAGED_CAPTURE_INSTRUCTIONS.md
   - Sample synthetic/staged RGB images with known metric defects.

5. Coordinate convention:
   2D pixel coordinates and metric meter ground truth dimensions.

6. Unit convention:
   Areas in square meters (m2); lengths in linear meters (m).

7. Dependencies:
   os, json, pathlib, numpy, cv2, PIL.

8. Assumptions:
   - The sample dataset (c00a170fe1) contains clean, undamaged walls.
   - Synthetic fixtures validate software execution paths without falsely claiming real-world accuracy.

9. Failure modes:
   - File permission errors when creating data/damage_dev.

10. First things to inspect while debugging:
    - Inspect SYNTHETIC_DEVELOPMENT_DAMAGE_SET.json metadata.
"""

import os
import json
from pathlib import Path
import numpy as np
import cv2
from PIL import Image


def create_damage_dev_dataset(output_dir: str = "data/damage_dev"):
    """Generates synthetic development damage images and benchmark specifications."""
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    metadata = {
        "dataset_name": "Synthetic & Staged Property Damage Development Set",
        "stage": "Stage 9 Development & Verification",
        "is_synthetic": True,
        "disclaimer": "Generated exclusively for software-path tests and geometric extent validation. Does not represent real property forensic accuracy.",
        "ground_truth_damages": [
            {
                "id": "dev_water_stain_01",
                "filename": "water_stain_wall.jpg",
                "class": "water_stain",
                "target_surface": "wall",
                "true_area_m2": 1.20,
                "notes": "Large brown moisture perimeter on interior drywall",
            },
            {
                "id": "dev_crack_01",
                "filename": "crack_wall.jpg",
                "class": "surface_crack",
                "target_surface": "wall",
                "true_length_m": 1.50,
                "notes": "Diagonal settling fissure on plaster substrate",
            },
            {
                "id": "dev_hole_01",
                "filename": "hole_wall.jpg",
                "class": "hole_or_missing_material",
                "target_surface": "wall",
                "true_area_m2": 0.35,
                "notes": "Punctured drywall opening with visible stud backing",
            },
            {
                "id": "dev_mold_01",
                "filename": "mold_ceiling.jpg",
                "class": "mold_like_discoloration",
                "target_surface": "ceiling",
                "true_area_m2": 0.60,
                "notes": "Patchy dark discoloration colony on ceiling finish",
            },
        ],
    }

    meta_file = out_path / "SYNTHETIC_DEVELOPMENT_DAMAGE_SET.json"
    with open(meta_file, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    # 1. Generate water_stain_wall.jpg
    img_stain = np.full((1440, 1920, 3), 225, dtype=np.uint8)
    cv2.ellipse(img_stain, (960, 720), (320, 220), 15, 0, 360, (135, 110, 80), -1)
    cv2.ellipse(img_stain, (960, 720), (300, 205), 15, 0, 360, (175, 145, 110), -1)
    # Add texture noise
    noise = np.random.randint(-10, 10, (1440, 1920, 3), dtype=np.int16)
    img_stain = np.clip(img_stain.astype(np.int16) + noise, 0, 255).astype(np.uint8)
    Image.fromarray(img_stain).save(str(out_path / "water_stain_wall.jpg"), quality=90)

    # 2. Generate crack_wall.jpg
    img_crack = np.full((1440, 1920, 3), 230, dtype=np.uint8)
    pts = np.array([[400, 300], [650, 520], [900, 700], [1200, 950], [1500, 1150]], np.int32)
    cv2.polylines(img_crack, [pts], False, (40, 40, 40), 5)
    cv2.polylines(img_crack, [pts], False, (70, 70, 70), 2)
    Image.fromarray(img_crack).save(str(out_path / "crack_wall.jpg"), quality=90)

    # 3. Generate hole_wall.jpg
    img_hole = np.full((1440, 1920, 3), 220, dtype=np.uint8)
    cv2.rectangle(img_hole, (750, 550), (1170, 890), (30, 25, 20), -1)
    cv2.rectangle(img_hole, (770, 570), (1150, 870), (50, 45, 40), -1)
    Image.fromarray(img_hole).save(str(out_path / "hole_wall.jpg"), quality=90)

    # 4. Generate mold_ceiling.jpg
    img_mold = np.full((1440, 1920, 3), 235, dtype=np.uint8)
    for _ in range(80):
        cx = np.random.randint(700, 1220)
        cy = np.random.randint(500, 940)
        rad = np.random.randint(15, 65)
        color = (np.random.randint(30, 55), np.random.randint(45, 70), np.random.randint(30, 50))
        cv2.circle(img_mold, (cx, cy), rad, color, -1)
    Image.fromarray(img_mold).save(str(out_path / "mold_ceiling.jpg"), quality=90)

    # 5. Write STAGED_CAPTURE_INSTRUCTIONS.md
    instructions = """# Stage 10 Benchmark: Staged Property Damage Capture Protocol

## Purpose
Establishes a standardized, reproducible field protocol for capturing authentic ground-truth
property damage across LiDAR, Video, and Photo modalities within a controlled interior environment.

## Protocol Requirements
1. **Target Space**:
   - One enclosed, furnished room (minimum 3.0 m × 4.0 m).
   - Clear architectural walls with defined structural planes.

2. **Staged Damage Classes**:
   - **Defect A (Area Type)**: Simulated water stain or surface spall ($1.0\\text{ m}^2$ to $1.5\\text{ m}^2$).
   - **Defect B (Linear Type)**: Measured hairline / structural crack ($1.0\\text{ m}$ to $2.0\\text{ m}$).

3. **Ground-Truth Benchmark Measurement**:
   - Measure physical bounding polygon using calibrated laser distance meter (accuracy $\\pm 1.5\\text{ mm}$).
   - Measure linear crack chord length using steel engineering tape.
   - Record true coordinates in `data/ground_truth/damage_ground_truth.json`.

4. **Multi-Tier Synchronized Capture**:
   - **LiDAR**: Continuous ARKit sweep capturing synchronized RGB + 256x192 depth + 6D poses.
   - **Video**: 4K/60fps continuous walking trajectory with 80% keyframe overlap.
   - **Photo**: Minimum 8 high-resolution stills from multiple viewing angles ($< 45^\\circ$ incidence).

5. **Lighting Standards**:
   - Uniform diffuse interior illumination (300–500 lux).
   - Avoid direct specular glares or deep flash cast shadows.
"""
    with open(out_path / "STAGED_CAPTURE_INSTRUCTIONS.md", "w", encoding="utf-8") as f:
        f.write(instructions)

    print(f"Created development damage dataset in {out_path}")


if __name__ == "__main__":
    create_damage_dev_dataset()
