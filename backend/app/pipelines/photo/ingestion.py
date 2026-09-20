"""Stage 8 photo-only input ingestion, EXIF normalization, and quality auditing.

1. Why this file exists:
   Establishes a strict still-image boundary before any expensive geometric reconstruction.
2. Pipeline stage:
   Stage 8, Step 1-5 (photo contract, count validation, EXIF, and quality audit).
3. Inputs:
   A single room directory containing direct-child JPG, JPEG, PNG, or locally decodable HEIC.
4. Outputs:
   Normalized RGB images, ``photo_manifest.json``, and ``photo_contact_sheet.jpg``.
5. Coordinate system:
   Source pixels are transformed by EXIF orientation into top-left-origin processing pixels.
6. Units:
   Dimensions are pixels; luminance is 0-255; sharpness is Laplacian variance.
7. Dependencies:
   Pillow for safe decode/EXIF and OpenCV/NumPy for quality metrics.
8. Assumptions:
   Only direct image children belong to the room; filenames contain no ordering semantics.
9. Failure modes:
   Missing directories, fewer than two decodable images, unsupported HEIC, or corrupt images.
10. First debugging points:
   Inspect ``photo_manifest.json``, rejected reasons, and the contact sheet annotations.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

import cv2
import numpy as np
from PIL import ExifTags, Image, ImageDraw, ImageOps

from backend.app.pipelines.photo.models import (
    PhotoCaptureManifest,
    PhotoQuality,
    PhotoRecord,
)

SUPPORTED_PHOTO_SUFFIXES = {".jpg", ".jpeg", ".png", ".heic", ".heif"}
ORIENTATION_TRANSFORMS = {
    1: "identity",
    2: "mirror_horizontal",
    3: "rotate_180",
    4: "mirror_vertical",
    5: "transpose",
    6: "rotate_90_clockwise",
    7: "transverse",
    8: "rotate_270_clockwise",
}


def discover_photo_files(input_dir: Path) -> List[Path]:
    """Return deterministic direct-child photo paths without traversing sibling sensor data.

    Parameters:
        input_dir: Room folder to inspect; it must exist and be a directory.
    Returns:
        Case-insensitively name-sorted paths with supported still-image suffixes.
    Coordinates/units:
        Not applicable; this function only establishes a filesystem boundary.
    Assumptions:
        Nested folders are not part of a single-room capture.
    Failure/debugging:
        Raises ``FileNotFoundError`` or ``NotADirectoryError``. Check the exact CLI input path.
    """
    input_dir = Path(input_dir)
    if not input_dir.exists():
        raise FileNotFoundError(f"Photo input directory does not exist: {input_dir}")
    if not input_dir.is_dir():
        raise NotADirectoryError(f"Photo input must be a directory: {input_dir}")
    return sorted(
        (
            path
            for path in input_dir.iterdir()
            if path.is_file() and path.suffix.lower() in SUPPORTED_PHOTO_SUFFIXES
        ),
        key=lambda path: (path.name.casefold(), path.name),
    )


def _json_safe_exif(exif: Image.Exif) -> Dict[str, Any]:
    """Convert Pillow EXIF values into a small JSON-safe dictionary for diagnostics.

    Parameters:
        exif: Pillow EXIF mapping from the original encoded image.
    Returns:
        Named scalar/string EXIF values; binary maker notes are intentionally omitted.
    Coordinates/units:
        Focal values retain EXIF millimeters; orientation remains the integer EXIF code.
    Assumptions:
        Metadata is untrusted and may contain malformed vendor values.
    Failure/debugging:
        Individual malformed tags are stringified rather than failing ingestion.
    """
    result: Dict[str, Any] = {}
    for tag_id, value in exif.items():
        name = ExifTags.TAGS.get(tag_id, str(tag_id))
        if isinstance(value, bytes):
            continue
        if isinstance(value, (str, int, float, bool)) or value is None:
            result[name] = value
        else:
            try:
                result[name] = float(value)
            except (TypeError, ValueError, ZeroDivisionError):
                result[name] = str(value)
    return result


def _optional_float(value: Any) -> float | None:
    """Parse one optional positive EXIF rational as float without trusting vendor types.

    Parameters:
        value: EXIF scalar, ratio, tuple, or missing value.
    Returns:
        Positive float or ``None`` when unavailable/invalid.
    Coordinates/units:
        The caller determines units, normally focal length in millimeters.
    Assumptions:
        Zero and negative values are unusable calibration evidence.
    Failure/debugging:
        Conversion errors return ``None``; inspect the raw manifest EXIF value.
    """
    if value is None:
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError, ZeroDivisionError):
        return None
    return parsed if parsed > 0.0 and np.isfinite(parsed) else None


def compute_photo_quality(rgb: np.ndarray, prior_hashes: Iterable[np.ndarray]) -> Tuple[PhotoQuality, np.ndarray]:
    """Measure blur, exposure, resolution cues, and near-duplicate similarity.

    Parameters:
        rgb: EXIF-normalized uint8 RGB image with shape HxWx3.
        prior_hashes: Perceptual 16x16 grayscale signatures from earlier selected images.
    Returns:
        ``(quality, signature)`` where signature can be compared with later views.
    Coordinates/units:
        Image pixels use top-left origin; sharpness is Laplacian variance and similarity is 0-1.
    Assumptions:
        Quality thresholds are diagnostic warnings, not geometric acceptance claims.
    Failure/debugging:
        Raises ``ValueError`` for malformed arrays. Inspect normalized image decode and shape.
    """
    if rgb.ndim != 3 or rgb.shape[2] != 3 or rgb.size == 0:
        raise ValueError(f"Expected non-empty RGB image, got shape {rgb.shape}")
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    sharpness = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    mean_luminance = float(gray.mean())
    dark_fraction = float(np.mean(gray <= 15))
    bright_fraction = float(np.mean(gray >= 245))
    signature = cv2.resize(gray, (16, 16), interpolation=cv2.INTER_AREA).astype(np.float32)
    signature = (signature - signature.mean()) / max(float(signature.std()), 1e-6)
    similarities = [
        float(np.clip((np.mean(signature * previous) + 1.0) / 2.0, 0.0, 1.0))
        for previous in prior_hashes
    ]
    duplicate_similarity = max(similarities, default=0.0)
    warnings: List[str] = []
    if sharpness < 35.0:
        warnings.append("motion_blur_or_soft_focus")
    if mean_luminance < 35.0 or dark_fraction > 0.55:
        warnings.append("severe_darkness")
    if mean_luminance > 225.0 or bright_fraction > 0.55:
        warnings.append("severe_overexposure")
    if duplicate_similarity > 0.985:
        warnings.append("duplicate_viewpoint_likely")
    if min(rgb.shape[:2]) < 720:
        warnings.append("low_resolution")
    return (
        PhotoQuality(
            sharpness=sharpness,
            mean_luminance=mean_luminance,
            dark_fraction=dark_fraction,
            bright_fraction=bright_fraction,
            duplicate_similarity=duplicate_similarity,
            warnings=warnings,
        ),
        signature,
    )


def _write_contact_sheet(records: List[PhotoRecord], output_path: Path) -> None:
    """Write a labeled overview of exactly the stills selected for reconstruction.

    Parameters:
        records: Selected normalized photo records in deterministic order.
        output_path: JPEG destination.
    Returns:
        None; writes one contact sheet.
    Coordinates/units:
        Display-only image pixels; no geometric coordinate is inferred.
    Assumptions:
        Record image paths remain readable after normalization.
    Failure/debugging:
        Pillow I/O errors propagate. Check normalized file paths in the manifest.
    """
    thumb_size = (320, 240)
    label_height = 44
    columns = min(4, len(records))
    rows = (len(records) + columns - 1) // columns
    sheet = Image.new("RGB", (columns * thumb_size[0], rows * (thumb_size[1] + label_height)), "white")
    draw = ImageDraw.Draw(sheet)
    for index, record in enumerate(records):
        with Image.open(record.image_path) as image:
            thumb = ImageOps.contain(image.convert("RGB"), thumb_size)
        x = (index % columns) * thumb_size[0]
        y = (index // columns) * (thumb_size[1] + label_height)
        sheet.paste(thumb, (x + (thumb_size[0] - thumb.width) // 2, y))
        draw.text((x + 6, y + thumb_size[1] + 4), f"{record.photo_id}: {Path(record.source_path).name}", fill="black")
        draw.text((x + 6, y + thumb_size[1] + 20), f"sharp {record.quality.sharpness:.1f}", fill="black")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output_path, format="JPEG", quality=90)


def ingest_photo_room(
    input_dir: Path,
    output_dir: Path,
    capture_id: str,
    room_id: str,
    synthetic_development_set: bool = False,
    max_photos: int = 8,
) -> PhotoCaptureManifest:
    """Normalize, audit, and deterministically select 2-8 stills for one room.

    Parameters:
        input_dir: Directory whose direct children are candidate still images.
        output_dir: Stage 8 room output directory.
        capture_id: Stable capture identifier for manifests and downstream artifacts.
        room_id: Stable room identifier independent of folder ordering.
        synthetic_development_set: Labels video-derived development stills honestly.
        max_photos: Selection cap, constrained to the assessment maximum of eight.
    Returns:
        ``PhotoCaptureManifest`` with selected normalized images and quality evidence.
    Coordinates/units:
        EXIF-transposed image pixels; no pose, depth, or metric coordinate is read.
    Assumptions:
        Filename sorting is deterministic but carries no geometric adjacency meaning.
    Failure/debugging:
        Raises ``ValueError`` when fewer than two images decode. Inspect rejection reasons and
        install a Pillow HEIF plugin if HEIC decoding is required locally.
    """
    if not 2 <= max_photos <= 8:
        raise ValueError(f"max_photos must be within [2, 8], received {max_photos}")
    paths = discover_photo_files(input_dir)
    output_dir = Path(output_dir)
    normalized_dir = output_dir / "normalized"
    normalized_dir.mkdir(parents=True, exist_ok=True)
    selected_paths = paths[:max_photos]
    omitted_paths = [str(path.resolve()) for path in paths[max_photos:]]
    records: List[PhotoRecord] = []
    rejected: List[Dict[str, str]] = []
    signatures: List[np.ndarray] = []

    for path in selected_paths:
        try:
            with Image.open(path) as source:
                original_width, original_height = source.size
                exif = source.getexif()
                exif_data = _json_safe_exif(exif)
                orientation = int(exif.get(274, 1) or 1)
                normalized = ImageOps.exif_transpose(source).convert("RGB")
                rgb = np.asarray(normalized)
            quality, signature = compute_photo_quality(rgb, signatures)
            normalized_path = normalized_dir / f"photo_{len(records):02d}.jpg"
            Image.fromarray(rgb).save(normalized_path, format="JPEG", quality=95)
            focal_mm = _optional_float(exif_data.get("FocalLength"))
            focal_35 = _optional_float(exif_data.get("FocalLengthIn35mmFilm"))
            records.append(
                PhotoRecord(
                    photo_id=len(records),
                    capture_id=capture_id,
                    room_id=room_id,
                    source_path=str(path.resolve()),
                    image_path=str(normalized_path.resolve()),
                    original_width=original_width,
                    original_height=original_height,
                    width=rgb.shape[1],
                    height=rgb.shape[0],
                    orientation=orientation if orientation in ORIENTATION_TRANSFORMS else 1,
                    orientation_transform=ORIENTATION_TRANSFORMS.get(orientation, "identity"),
                    exif=exif_data,
                    timestamp=exif_data.get("DateTimeOriginal") or exif_data.get("DateTime"),
                    camera_make=exif_data.get("Make"),
                    camera_model=exif_data.get("Model"),
                    focal_length_mm=focal_mm,
                    focal_length_35mm=focal_35,
                    intrinsics_source="exif_focal_length" if focal_mm or focal_35 else "sfm_self_calibration",
                    quality=quality,
                )
            )
            signatures.append(signature)
        except Exception as exc:
            rejected.append({"path": str(path.resolve()), "reason": f"{type(exc).__name__}: {exc}"})

    if len(records) < 2:
        raise ValueError(
            f"Photo capture requires at least 2 decodable stills; found {len(records)} in {input_dir}. "
            f"Rejected: {rejected}"
        )
    warnings = sorted({warning for record in records for warning in record.quality.warnings})
    if omitted_paths:
        warnings.append(f"deterministically_selected_first_{max_photos}_of_{len(paths)}_images")
    manifest = PhotoCaptureManifest(
        capture_id=capture_id,
        room_id=room_id,
        input_directory=str(Path(input_dir).resolve()),
        synthetic_development_set=synthetic_development_set,
        discovered_count=len(paths),
        selected_count=len(records),
        selection_policy=f"casefold_filename_order_first_{max_photos}",
        selected_photos=records,
        omitted_paths=omitted_paths,
        rejected_images=rejected,
        warnings=warnings,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    with open(output_dir / "photo_manifest.json", "w", encoding="utf-8") as manifest_file:
        json.dump(manifest.model_dump(), manifest_file, indent=2)
    _write_contact_sheet(records, output_dir / "photo_contact_sheet.jpg")
    return manifest
