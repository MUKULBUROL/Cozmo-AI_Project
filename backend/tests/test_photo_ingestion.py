"""Stage 8 deterministic tests for photo ingestion and EXIF normalization.

1. Why this file exists: prevents regressions in the strict 2-8 still-image input contract.
2. Pipeline stage: Stage 8 ingestion and quality audit.
3. Inputs: temporary synthetic JPEG/PNG fixtures only.
4. Outputs: assertions over manifests, normalized images, and contact sheets.
5. Coordinate system: top-left-origin image pixels after EXIF orientation.
6. Units: pixels and 0-255 image values.
7. Dependencies: pytest, Pillow, NumPy, and the photo ingestion module.
8. Assumptions: tests avoid pycolmap and neural inference.
9. Failure modes: fixture decode or metadata preservation failures surface as assertions.
10. First debugging points: inspect the temporary manifest and normalized image dimensions.
"""

from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from backend.app.pipelines.photo.ingestion import ingest_photo_room


def _write_image(path: Path, value: int, size: tuple[int, int] = (800, 600), orientation: int | None = None) -> None:
    """Write one textured fixture image with optional EXIF orientation.

    ``size`` is width/height in pixels and ``value`` controls the deterministic pattern. The
    function returns nothing, assumes a writable parent, and failures indicate fixture I/O rather
    than pipeline behavior; inspect the pytest temporary directory first.
    """
    yy, xx = np.mgrid[0:size[1], 0:size[0]]
    rgb = np.stack(((xx + value) % 255, (yy + value) % 255, (xx + yy + value) % 255), axis=-1).astype(np.uint8)
    image = Image.fromarray(rgb, "RGB")
    exif = Image.Exif()
    if orientation is not None:
        exif[274] = orientation
    image.save(path, exif=exif)


def test_two_image_minimum_validation(tmp_path: Path) -> None:
    """Reject one view and accept exactly two independent stills without reading siblings."""
    input_dir = tmp_path / "room"
    input_dir.mkdir()
    _write_image(input_dir / "one.jpg", 10)
    with pytest.raises(ValueError, match="at least 2"):
        ingest_photo_room(input_dir, tmp_path / "failed", "capture", "room_01")
    _write_image(input_dir / "two.jpg", 20)
    manifest = ingest_photo_room(input_dir, tmp_path / "accepted", "capture", "room_01")
    assert manifest.selected_count == 2


def test_more_than_eight_uses_deterministic_selection(tmp_path: Path) -> None:
    """Select the same first eight casefold-sorted names and record every omitted path."""
    input_dir = tmp_path / "room"
    input_dir.mkdir()
    for index in range(10):
        _write_image(input_dir / f"image_{index:02d}.jpg", index * 7)
    manifest = ingest_photo_room(input_dir, tmp_path / "output", "capture", "room_01")
    assert manifest.selected_count == 8
    assert [Path(record.source_path).name for record in manifest.selected_photos] == [f"image_{i:02d}.jpg" for i in range(8)]
    assert [Path(path).name for path in manifest.omitted_paths] == ["image_08.jpg", "image_09.jpg"]


def test_exif_orientation_is_normalized(tmp_path: Path) -> None:
    """Rotate EXIF orientation 6 into processing pixels while preserving original dimensions."""
    input_dir = tmp_path / "room"
    input_dir.mkdir()
    _write_image(input_dir / "rotated.jpg", 30, size=(800, 600), orientation=6)
    _write_image(input_dir / "plain.jpg", 40)
    manifest = ingest_photo_room(input_dir, tmp_path / "output", "capture", "room_01")
    record = next(item for item in manifest.selected_photos if Path(item.source_path).name == "rotated.jpg")
    assert (record.original_width, record.original_height) == (800, 600)
    assert (record.width, record.height) == (600, 800)
    assert record.orientation_transform == "rotate_90_clockwise"


def test_missing_exif_uses_sfm_calibration(tmp_path: Path) -> None:
    """Keep EXIF-free PNG inputs valid and explicitly defer intrinsics to SfM."""
    input_dir = tmp_path / "room"
    input_dir.mkdir()
    _write_image(input_dir / "a.png", 50)
    _write_image(input_dir / "b.png", 70)
    manifest = ingest_photo_room(input_dir, tmp_path / "output", "capture", "room_01")
    assert all(record.orientation == 1 for record in manifest.selected_photos)
    assert all(record.intrinsics_source == "sfm_self_calibration" for record in manifest.selected_photos)
    assert (tmp_path / "output" / "photo_contact_sheet.jpg").exists()
