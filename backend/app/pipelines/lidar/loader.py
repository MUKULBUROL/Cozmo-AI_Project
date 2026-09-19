"""Streaming data loader for Stray Scanner / ARKit LiDAR captures."""

import os
import zipfile
import io
import csv
from typing import Generator, Tuple, Dict, Any, Optional
from PIL import Image
import numpy as np

from backend.app.models.capture import CameraIntrinsics, Pose6D


class LiDARScanLoader:
    """Streams synchronized depth frames, confidence maps, poses, and intrinsics."""

    def __init__(self, archive_path: str, scan_id: str):
        self.archive_path = archive_path
        self.scan_id = scan_id

        if not os.path.exists(archive_path):
            raise FileNotFoundError(f"Scan archive not found at: {archive_path}")

        self.zf = zipfile.ZipFile(archive_path, "r")
        self.namelist = set(self.zf.namelist())

        self.camera_matrix = self._load_camera_matrix()
        self.odometry_records = self._load_odometry()

        # Depth scale factor: 1920x1440 RGB -> 256x192 Depth
        self.scale_x = 256.0 / 1920.0
        self.scale_y = 192.0 / 1440.0

    def _load_camera_matrix(self) -> np.ndarray:
        cam_path = f"{self.scan_id}/camera_matrix.csv"
        if cam_path not in self.namelist:
            raise ValueError(f"Missing camera_matrix.csv in {self.scan_id}")

        content = self.zf.read(cam_path).decode("utf-8").strip().splitlines()
        matrix = []
        for line in content:
            parts = [float(p.strip()) for p in line.split(",") if p.strip()]
            if len(parts) == 3:
                matrix.append(parts)

        K = np.array(matrix, dtype=np.float64)
        if K.shape != (3, 3):
            raise ValueError(f"Invalid camera matrix shape: {K.shape}, expected (3, 3)")
        return K

    def _load_odometry(self) -> list[Dict[str, Any]]:
        odom_path = f"{self.scan_id}/odometry.csv"
        if odom_path not in self.namelist:
            raise ValueError(f"Missing odometry.csv in {self.scan_id}")

        content = self.zf.read(odom_path).decode("utf-8").splitlines()
        if not content:
            raise ValueError(f"Empty odometry.csv in {self.scan_id}")

        header = [h.strip() for h in content[0].split(",")]
        records = []
        for line in content[1:]:
            if not line.strip():
                continue
            parts = [p.strip() for p in line.split(",")]
            record = dict(zip(header, parts))
            records.append(record)
        return records

    @property
    def total_frames(self) -> int:
        return len(self.odometry_records)

    def get_scaled_intrinsics(self, frame_record: Optional[Dict[str, Any]] = None) -> CameraIntrinsics:
        """Computes intrinsics scaled to 256x192 depth resolution."""
        if frame_record and frame_record.get("fx"):
            fx_raw = float(frame_record["fx"])
            fy_raw = float(frame_record["fy"])
            cx_raw = float(frame_record["cx"])
            cy_raw = float(frame_record["cy"])
        else:
            fx_raw = self.camera_matrix[0, 0]
            fy_raw = self.camera_matrix[1, 1]
            cx_raw = self.camera_matrix[0, 2]
            cy_raw = self.camera_matrix[1, 2]

        return CameraIntrinsics(
            fx=fx_raw * self.scale_x,
            fy=fy_raw * self.scale_y,
            cx=cx_raw * self.scale_x,
            cy=cy_raw * self.scale_y,
            width=256,
            height=192,
        )

    def stream_frames(
        self, frame_stride: int = 1, max_frames: Optional[int] = None
    ) -> Generator[Tuple[int, float, np.ndarray, np.ndarray, Pose6D, CameraIntrinsics], None, None]:
        """Generator yielding (frame_index, timestamp, depth_mm, confidence, pose, intrinsics).

        depth_mm: uint16 array of shape (192, 256) in millimeters.
        confidence: uint8 array of shape (192, 256) in {0, 1, 2}.
        """
        yielded = 0
        for i in range(0, len(self.odometry_records), frame_stride):
            if max_frames is not None and yielded >= max_frames:
                break

            record = self.odometry_records[i]
            frame_id = record["frame"]
            timestamp = float(record["timestamp"])

            depth_path = f"{self.scan_id}/depth/{frame_id}.png"
            conf_path = f"{self.scan_id}/confidence/{frame_id}.png"

            if depth_path not in self.namelist or conf_path not in self.namelist:
                continue

            # Read depth
            depth_bytes = self.zf.read(depth_path)
            depth_img = Image.open(io.BytesIO(depth_bytes))
            depth_mm = np.array(depth_img, dtype=np.uint16)

            if depth_mm.shape != (192, 256):
                raise ValueError(f"Unexpected depth shape: {depth_mm.shape}, expected (192, 256)")

            # Read confidence
            conf_bytes = self.zf.read(conf_path)
            conf_img = Image.open(io.BytesIO(conf_bytes))
            confidence = np.array(conf_img, dtype=np.uint8)

            intrinsics = self.get_scaled_intrinsics(record)
            pose = Pose6D(
                timestamp=timestamp,
                frame_index=int(frame_id),
                x=float(record["x"]),
                y=float(record["y"]),
                z=float(record["z"]),
                qx=float(record["qx"]),
                qy=float(record["qy"]),
                qz=float(record["qz"]),
                qw=float(record["qw"]),
                intrinsics=intrinsics,
            )

            yield (int(frame_id), timestamp, depth_mm, confidence, pose, intrinsics)
            yielded += 1

    def close(self):
        self.zf.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
