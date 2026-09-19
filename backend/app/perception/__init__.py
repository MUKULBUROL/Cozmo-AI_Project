"""Perception package for architectural opening detection and metric width measurement.

1. Why this file exists:
   Exposes high-level interfaces for Stage 5 perception: RGB keyframe extraction, open-vocabulary
   semantic detection, depth boundary refinement, visual rendering, and master pipeline orchestration.

2. Pipeline stage:
   Stage 5 (Door/Window Detection & Metric Opening Measurement) - Package Interface.

3. Inputs:
   Various scan artifacts (video, poses, depth maps, structural wall models).

4. Outputs:
   Exported perception modules and functions.

5. Coordinate/Unit conventions:
   Metric meters for 3D world geometry, pixels for 2D images.

6. Dependencies:
   keyframes, detector, segmentation, opening_viz, pipeline.

7. Most likely failure/debugging points:
   - Circular imports between perception and geometry subpackages.
"""

from .keyframes import extract_keyframes
from .detector import OpeningDetector
from .segmentation import refine_opening_boundaries_with_depth
from .opening_viz import save_annotated_frame, render_openings_floorplan_svg
from .pipeline import run_opening_pipeline

__all__ = [
    "extract_keyframes",
    "OpeningDetector",
    "refine_opening_boundaries_with_depth",
    "save_annotated_frame",
    "render_openings_floorplan_svg",
    "run_opening_pipeline",
]
