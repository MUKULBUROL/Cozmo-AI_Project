"""Semantic opening detector using open-vocabulary zero-shot vision models.

1. Why this file exists:
   Detects architectural openings (doors, open doorways, and windows) in RGB keyframes
   using a locally runnable open-vocabulary detector (YOLO-World), strictly decoupling
   semantic visual recognition ('what is this object?') from metric physical dimensioning.

2. Pipeline stage:
   Stage 5 (Door/Window Detection & Metric Opening Measurement) - Semantic Perception.

3. Inputs:
   RGB keyframe file paths or numpy image arrays.

4. Outputs:
   Candidate opening detections with bounding boxes [x1, y1, x2, y2], confidence scores,
   and semantic classes ('door', 'doorway', 'window').

5. Coordinate/Unit assumptions:
   Pixel coordinates in image space: [x1, y1, x2, y2] where (0, 0) is top-left.
   Scores bounded in [0.0, 1.0].

6. Dependencies:
   pathlib, typing, numpy, ultralytics.

7. Most likely failure/debugging points:
   - High visual false-positive rates on furniture edges, picture frames, and mirrors
     (mitigated downstream by geometric wall plane projection and association).
   - Missing CLIP text encoder if not pre-installed.
   - Low lighting or steep oblique angles causing missed detections (mitigated by lower thresholding).
"""

import os
from pathlib import Path
from typing import List, Dict, Any, Union, Optional, Tuple
import numpy as np


class OpenVocabularyOpeningDetector:
    """Pretrained open-vocabulary detector configured for doors, doorways, and windows."""

    def __init__(
        self,
        model_name: str = "weights/yolov8s-worldv2.pt",
        weights_path: Optional[str] = None,
        device: str = "cpu",
        classes: Optional[List[str]] = None,
    ):
        """Initializes the open-vocabulary YOLO-World model.

        Purpose:
            Loads pretrained weights and compiles the custom zero-shot text vocabulary.

        Parameters:
            model_name: Ultralytics YOLO-World weight filename or path.
            weights_path: Optional explicit path to model weights.
            device: Compute device ('cpu' or 'cuda').
            classes: Custom text vocabulary (defaults to doors, doorways, windows).

        Returns:
            None.

        Assumptions:
            Weights are cached in local directory or downloaded on first run.

        Failure conditions:
            Raises RuntimeError if weight loading or text embedding compilation fails.

        Debugging:
            Check device parameter if CPU vs GPU execution needs to be forced.
        """
        from ultralytics import YOLOWorld

        self.device = device
        self.classes = classes or ["door", "open doorway", "doorway", "window"]
        REPO_ROOT = Path(__file__).resolve().parents[3]
        selected = Path(weights_path or model_name)
        if not selected.is_absolute() or not selected.exists():
            candidates = [
                selected,
                REPO_ROOT / selected,
                REPO_ROOT / "weights" / selected.name,
                Path("weights") / selected.name,
            ]
            for cand in candidates:
                if cand.exists():
                    selected = cand
                    break
        self.model = YOLOWorld(str(selected))
        self.model.set_classes(self.classes)

    def detect(
        self,
        image: Union[str, Path, np.ndarray],
        conf_threshold: float = 0.08,
        iou_threshold: float = 0.45,
        frame_id: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Executes zero-shot detection on an individual RGB frame.

        Purpose:
            Extracts candidate bounding boxes and maps class predictions to canonical labels.

        Parameters:
            image: Filesystem path to JPEG/PNG image or uint8 numpy RGB array.
            conf_threshold: Minimum confidence score to retain candidate.
            iou_threshold: NMS overlap threshold.
            frame_id: Optional video frame sequence index for multi-frame tracking.

        Returns:
            List of candidate detection dictionaries.

        Assumptions:
            Image is in RGB channel order.

        Failure conditions:
            Returns empty list if image file is missing or corrupted.

        Debugging:
            Inspect raw detector scores before filtering to evaluate threshold sensitivity.
        """
        try:
            results = self.model.predict(
                source=image,
                conf=conf_threshold,
                iou=iou_threshold,
                device=self.device,
                verbose=False,
            )
        except Exception as e:
            return []

        candidates: List[Dict[str, Any]] = []
        for r in results:
            boxes = r.boxes
            if boxes is None or len(boxes) == 0:
                continue

            for b in boxes:
                cls_id = int(b.cls[0])
                raw_name = r.names[cls_id].lower()
                conf = float(b.conf[0])
                xyxy = [float(x) for x in b.xyxy[0].tolist()]

                # Standardize semantic class
                if "window" in raw_name:
                    canonical_class = "window"
                elif "doorway" in raw_name or "open door" in raw_name:
                    canonical_class = "doorway"
                else:
                    canonical_class = "door"

                candidates.append({
                    "class": canonical_class,
                    "raw_class": raw_name,
                    "detector_score": round(conf, 3),
                    "bbox": [round(c, 1) for c in xyxy],
                    "status": "candidate",
                    "frame_id": frame_id,
                })

        return candidates


# Canonical export alias
OpeningDetector = OpenVocabularyOpeningDetector

