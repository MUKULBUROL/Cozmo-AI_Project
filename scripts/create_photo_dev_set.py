"""Create explicitly synthetic Stage 8 still-photo development sets before reconstruction.

1. Why this file exists:
   The supplied dataset has RGB video but no genuine assessment-style independent photo folders.
2. Pipeline stage:
   Development-data preparation before Stage 8; it is never imported by photo reconstruction.
3. Inputs:
   One capture ZIP and scan ID whose only extracted member is ``<scan>/rgb.mp4``.
4. Outputs:
   Six JPEGs per requested room folder and ``SYNTHETIC_DEVELOPMENT_PHOTO_SET.json``.
5. Coordinate system:
   Frames retain decoded top-left-origin RGB/BGR pixel orientation; no poses are exported.
6. Units:
   Frame locations are dimensionless fractions of video duration; image dimensions are pixels.
7. Dependencies:
   Python ZIP/tempfile libraries and OpenCV video decoding.
8. Assumptions:
   Time windows are development sampling regions, not verified semantic room annotations.
9. Failure modes:
   Missing archive/member, undecodable video, invalid fractions, or frame seek/read failure.
10. First debugging points:
   Inspect the generated manifest, source member, frame indices, and JPEG contact visually.
"""

import argparse
import json
import tempfile
import zipfile
from pathlib import Path
from typing import Dict, List

import cv2


PROPERTY_WINDOWS: Dict[str, tuple[float, float]] = {
    "room_01": (0.08, 0.12),
    "connector_01": (0.30, 0.34),
    "room_02": (0.50, 0.54),
    "room_03": (0.74, 0.78),
}


def extract_window_stills(video_path: Path, output_dir: Path, start_fraction: float, end_fraction: float, count: int = 6) -> List[Dict[str, float | int | str]]:
    """Extract evenly spaced independent JPEG files from one development video window.

    Parameters:
        video_path/output_dir: Decodable source and image-only destination.
        start_fraction/end_fraction: Inclusive positions in [0,1] across frame count.
        count: Number of stills, constrained to the assessment range 2-8.
    Returns:
        JSON-safe frame index/timestamp/path records.
    Coordinates/units:
        Fractions are dimensionless; timestamps are seconds and image coordinates are pixels.
    Assumptions:
        Window spacing provides more viewpoint diversity than adjacent frame extraction.
    Failure/debugging:
        Raises ``ValueError`` for bad ranges/decode and ``RuntimeError`` for failed seeks. Inspect
        OpenCV codec support and source archive integrity.
    """
    if not 2 <= count <= 8 or not 0.0 <= start_fraction < end_fraction <= 1.0:
        raise ValueError("Still count must be 2-8 and fractions must satisfy 0 <= start < end <= 1")
    capture = cv2.VideoCapture(str(video_path))
    frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = float(capture.get(cv2.CAP_PROP_FPS))
    if not capture.isOpened() or frame_count < 2 or fps <= 0:
        capture.release()
        raise ValueError(f"Unable to decode development video: {video_path}")
    output_dir.mkdir(parents=True, exist_ok=True)
    indices = [round((start_fraction + (end_fraction - start_fraction) * index / (count - 1)) * (frame_count - 1)) for index in range(count)]
    records = []
    for photo_id, frame_index in enumerate(indices):
        capture.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
        ok, frame = capture.read()
        if not ok or frame is None:
            capture.release()
            raise RuntimeError(f"Failed to decode frame {frame_index} from {video_path}")
        destination = output_dir / f"image_{photo_id + 1:02d}.jpg"
        if not cv2.imwrite(str(destination), frame, [cv2.IMWRITE_JPEG_QUALITY, 95]):
            capture.release()
            raise RuntimeError(f"Failed to write development still: {destination}")
        records.append({"photo_id": photo_id, "source_frame_index": frame_index, "source_timestamp_seconds": frame_index / fps, "image_path": str(destination)})
    capture.release()
    return records


def create_development_set(archive: Path, scan_id: str, output_dir: Path, property_mode: bool) -> Dict[str, object]:
    """Extract only RGB video temporarily and create a labeled single/property photo set.

    Parameters:
        archive/scan_id: Source ZIP and capture root.
        output_dir: Generated image-only destination.
        property_mode: Creates four child folders when true, otherwise one six-image room folder.
    Returns:
        Manifest identifying synthetic provenance and selected source frames.
    Coordinates/units:
        No sensor coordinate, camera pose, or depth is copied; timestamps are provenance only.
    Assumptions:
        Property windows are approximate development regions and require visual review.
    Failure/debugging:
        Missing ``rgb.mp4`` raises ``FileNotFoundError``. Inspect ZIP member names and scan ID.
    """
    member = f"{scan_id}/rgb.mp4"
    with tempfile.TemporaryDirectory() as temporary:
        video_path = Path(temporary) / "rgb.mp4"
        with zipfile.ZipFile(archive, "r") as source_zip:
            if member not in source_zip.namelist():
                raise FileNotFoundError(f"Archive does not contain {member}")
            with source_zip.open(member) as source, open(video_path, "wb") as target:
                target.write(source.read())
        sets: Dict[str, object] = {}
        # Six views need overlap as well as baseline; a short local window proved materially more
        # reliable than uniform whole-video spacing on the development capture.
        windows = PROPERTY_WINDOWS if property_mode else {"single_room": (0.35, 0.50)}
        for room_id, (start, end) in windows.items():
            sets[room_id] = extract_window_stills(video_path, output_dir / room_id if property_mode else output_dir, start, end)
    manifest: Dict[str, object] = {
        "label": "SYNTHETIC DEVELOPMENT PHOTO SET",
        "not_real_assessment_photo_capture": True,
        "source_archive": str(archive),
        "source_scan_id": scan_id,
        "photo_reconstruction_input": str(output_dir),
        "contains_sensor_data": False,
        "sets": sets,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "SYNTHETIC_DEVELOPMENT_PHOTO_SET.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def main() -> None:
    """Parse development extraction arguments and print the synthetic-set manifest.

    The command reads one ZIP member and writes only independent JPEGs/JSON. It returns no value;
    errors identify the archive, member, frame, or destination to inspect first.
    """
    parser = argparse.ArgumentParser(description="Create synthetic Stage 8 development stills")
    parser.add_argument("--archive", required=True)
    parser.add_argument("--scan", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--property", action="store_true", dest="property_mode")
    args = parser.parse_args()
    result = create_development_set(Path(args.archive), args.scan, Path(args.output), args.property_mode)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
