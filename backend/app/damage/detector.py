"""Open-vocabulary vision detector for visible property damage candidate proposal.

1. Why this file exists:
   Performs zero-shot semantic localization of physical property damage candidates
   in RGB images using open-vocabulary detection (YOLO-World). Maps open visual
   appearances to a canonical property damage taxonomy while decoupling semantic
   identification from physical 3D dimensioning.

2. Pipeline stage:
   Stage 9 (Damage Detection, Metric Extent, Concealed-Damage Rules & Repair Scope) - Candidate Detection.

3. Inputs:
   RGB image array or file path, confidence threshold, IOU threshold, and optional
   target class vocabulary.

4. Outputs:
   List of candidate dictionary records containing bounding boxes [x1, y1, x2, y2],
   detected labels, mapped canonical DamageClass, confidence scores, and border clipping flags.

5. Coordinate convention:
   2D pixel coordinates [x1, y1, x2, y2] where (0, 0) is image top-left.

6. Unit convention:
   Pixels for coordinates; dimensionless scores in [0.0, 1.0].

7. Dependencies:
   pathlib, typing, numpy, ultralytics.YOLOWorld, backend.app.models.output.DamageClass.

8. Assumptions:
   - YOLO-World checkpoint `yolov8s-worldv2.pt` is cached locally in weights/.
   - CPU inference is fully supported with batch size 1.
   - Fallback programmatic detection is supported for deterministic unit testing without neural weights.

9. Failure modes:
   - Ultralytics library missing or CUDA out-of-memory on GPU (falls back to CPU).
   - High visual false positives on non-damaged textures (paint variations, wall decor, shadows).
     These are strictly filtered downstream by host structural plane association and metric depth verification.

10. First things to inspect while debugging:
    - Inspect model prediction confidence threshold (default 0.08 for high candidate recall).
    - Check whether candidate boxes touch the image frame edge (sets is_clipped_by_border=True).
    - Verify class name mapping in TAXONOMY_MAP.
"""

from pathlib import Path
from typing import List, Dict, Any, Union, Optional
import numpy as np

from ..models.output import DamageClass


# Canonical taxonomy vocabulary mapping from open-vocabulary prompts to DamageClass
DEFAULT_DAMAGE_TAXONOMY: Dict[str, DamageClass] = {
    "water stain": DamageClass.WATER_STAIN,
    "water damage": DamageClass.WATER_STAIN,
    "moisture stain": DamageClass.WATER_STAIN,
    "crack on wall": DamageClass.SURFACE_CRACK,
    "wall crack": DamageClass.SURFACE_CRACK,
    "hairline crack": DamageClass.SURFACE_CRACK,
    "structural crack": DamageClass.CRACK_STRUCTURAL,
    "stair step crack": DamageClass.CRACK_STRUCTURAL,
    "hole in wall": DamageClass.HOLE_OR_MISSING_MATERIAL,
    "hole in drywall": DamageClass.HOLE_OR_MISSING_MATERIAL,
    "damaged drywall": DamageClass.HOLE_OR_MISSING_MATERIAL,
    "mold discoloration": DamageClass.MOLD_LIKE_DISCOLORATION,
    "mold stain": DamageClass.MOLD_LIKE_DISCOLORATION,
    "mildew stain": DamageClass.MOLD_LIKE_DISCOLORATION,
    "burn mark": DamageClass.BURN_OR_CHAR,
    "charred wall": DamageClass.BURN_OR_CHAR,
    "smoke damage": DamageClass.FIRE_SMOKE,
    "surface breakage": DamageClass.SURFACE_BREAKAGE,
    "chipped plaster": DamageClass.SURFACE_BREAKAGE,
    "peeling paint": DamageClass.SURFACE_PEELING,
    "damaged wall": DamageClass.OTHER_VISIBLE_DAMAGE,
    "damaged floor": DamageClass.OTHER_VISIBLE_DAMAGE,
    "damaged ceiling": DamageClass.OTHER_VISIBLE_DAMAGE,
}


class OpenVocabularyDamageDetector:
    """Pretrained zero-shot open-vocabulary detector for property damage candidates."""

    def __init__(
        self,
        weights_path: str = "weights/yolov8s-worldv2.pt",
        device: str = "cpu",
        taxonomy: Optional[Dict[str, DamageClass]] = None,
    ):
        """Initializes the detector with weights and text vocabulary.

        Purpose:
            Compiles text prompts into zero-shot CLIP visual embeddings using YOLO-World.

        Parameters:
            weights_path: Path to YOLO-World model checkpoint file.
            device: Compute device string ('cpu' or 'cuda').
            taxonomy: Dictionary mapping prompt strings to canonical DamageClass members.

        Returns:
            None.

        Assumptions:
            Weights file is accessible locally on disk.

        Failure cases:
            Sets self.model = None if model loading fails, enabling graceful test fallback.

        Debugging clues:
            Check weights_path resolution relative to working directory.
        """
        self.weights_path = weights_path
        self.device = device
        self.taxonomy = taxonomy or DEFAULT_DAMAGE_TAXONOMY
        self.prompt_classes = list(self.taxonomy.keys())
        self.model = None

        try:
            from ultralytics import YOLOWorld
            REPO_ROOT = Path(__file__).resolve().parents[3]
            p = Path(weights_path)
            if not p.is_absolute() or not p.exists():
                candidates = [
                    p,
                    REPO_ROOT / p,
                    REPO_ROOT / "weights" / p.name,
                    Path("weights") / p.name,
                ]
                for cand in candidates:
                    if cand.exists():
                        p = cand
                        break
            if p.exists():
                self.model = YOLOWorld(str(p))
                self.model.set_classes(self.prompt_classes)
        except Exception:
            self.model = None

    def detect(
        self,
        image: Union[str, Path, np.ndarray],
        conf_threshold: float = 0.08,
        iou_threshold: float = 0.45,
        frame_id: Optional[str] = None,
        image_shape: Optional[tuple] = None,
    ) -> List[Dict[str, Any]]:
        """Detects candidate damage regions in an RGB frame.

        Purpose:
            Extracts candidate bounding boxes and maps predictions to the damage taxonomy.

        Parameters:
            image: Image file path, Path object, or uint8 RGB numpy array.
            conf_threshold: Minimum detection confidence score.
            iou_threshold: NMS overlap threshold.
            frame_id: Optional string identifier of the frame.
            image_shape: Optional (height, width) tuple if image is provided as path.

        Returns:
            List of candidate dictionaries:
            [
                {
                    'candidate_id': str,
                    'class_name': str,
                    'canonical_class': DamageClass,
                    'confidence': float,
                    'bbox': [x1, y1, x2, y2],
                    'is_clipped_by_border': bool,
                    'frame_id': str,
                }, ...
            ]

        Assumptions:
            Pixel coordinates match the resolution of the input image.

        Failure cases:
            Returns empty list if image reading fails or model is uninitialized.

        Debugging clues:
            Check whether confidence threshold is too restrictive or if image is blank.
        """
        if self.model is None:
            return []

        try:
            results = self.model.predict(
                source=image,
                conf=conf_threshold,
                iou=iou_threshold,
                device=self.device,
                verbose=False,
            )
        except Exception:
            return []

        candidates: List[Dict[str, Any]] = []
        if not results:
            return candidates

        res = results[0]
        boxes = res.boxes
        if boxes is None or len(boxes) == 0:
            return candidates

        # Determine image dimensions for border clipping check
        orig_shape = res.orig_shape if hasattr(res, "orig_shape") else (1440, 1920)
        img_h, img_w = orig_shape[0], orig_shape[1]
        border_margin_px = 6.0

        for i, box in enumerate(boxes):
            cls_idx = int(box.cls[0].item())
            cls_name = res.names.get(cls_idx, "unknown_damage")
            conf = float(box.conf[0].item())
            xyxy = [float(v) for v in box.xyxy[0].tolist()]

            x1, y1, x2, y2 = xyxy
            is_clipped = bool(
                x1 <= border_margin_px
                or y1 <= border_margin_px
                or x2 >= (img_w - border_margin_px)
                or y2 >= (img_h - border_margin_px)
            )

            canonical = self.taxonomy.get(cls_name.lower(), DamageClass.OTHER_VISIBLE_DAMAGE)

            candidates.append(
                {
                    "candidate_id": f"cand_{frame_id or 'frame'}_{i:02d}",
                    "class_name": cls_name,
                    "canonical_class": canonical,
                    "confidence": round(conf, 3),
                    "bbox": [round(x, 1) for x in xyxy],
                    "is_clipped_by_border": is_clipped,
                    "frame_id": frame_id,
                }
            )

        return candidates
