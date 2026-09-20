"""Stage 8 automated test proving photo ingestion ignores colocated sensor and video files.

1. Why this file exists: enforces the critical photo-only isolation rule at the filesystem boundary.
2. Pipeline stage: Stage 8 input isolation.
3. Inputs: temporary still images plus forbidden decoy video/sensor files.
4. Outputs: assertions that only normalized image paths enter the manifest.
5. Coordinate system: image pixels only; no sensor coordinate is loaded.
6. Units: irrelevant to forbidden decoys; fixture images are pixels.
7. Dependencies: Pillow, pytest, and Stage 8 ingestion.
8. Assumptions: the room input scanner only examines direct supported image suffixes.
9. Failure modes: any forbidden path in selected/source records fails the test.
10. First debugging points: inspect ``discover_photo_files`` suffix and traversal rules.
"""

from pathlib import Path

from PIL import Image

from backend.app.pipelines.photo.ingestion import ingest_photo_room


def test_photo_only_isolation_ignores_video_and_sensor_files(tmp_path: Path) -> None:
    """Select only stills when RGB video, odometry, depth, confidence, and LiDAR decoys coexist."""
    room = tmp_path / "room"
    room.mkdir()
    Image.new("RGB", (800, 600), "red").save(room / "a.jpg")
    Image.new("RGB", (800, 600), "blue").save(room / "b.jpg")
    (room / "rgb.mp4").write_bytes(b"forbidden video")
    (room / "odometry.csv").write_text("forbidden pose", encoding="utf-8")
    (room / "lidar.ply").write_text("forbidden cloud", encoding="utf-8")
    (room / "depth").mkdir()
    (room / "depth" / "000.png").write_bytes(b"forbidden depth")
    (room / "confidence").mkdir()
    (room / "confidence" / "000.png").write_bytes(b"forbidden confidence")
    manifest = ingest_photo_room(room, tmp_path / "output", "isolated", "room_01")
    selected = {Path(record.source_path).name for record in manifest.selected_photos}
    assert selected == {"a.jpg", "b.jpg"}
    serialized = (tmp_path / "output" / "photo_manifest.json").read_text(encoding="utf-8")
    for forbidden in ["rgb.mp4", "odometry.csv", "lidar.ply", "depth/000.png", "confidence/000.png"]:
        assert forbidden not in serialized
