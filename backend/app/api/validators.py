"""Tier-specific input file validation for capture uploads.

Purpose:
    Validates uploaded files against the expected format for each sensor
    tier before dispatching to reconstruction pipelines.  Prevents invalid
    or unsupported files from entering the processing queue.

Stage:
    Frontend Stage 3 — Live FastAPI Integration.

Inputs:
    Uploaded filename, file bytes or path, and target CaptureTier.

Outputs:
    ValidationResult indicating acceptance or rejection with reason.

Dependencies:
    zipfile (stdlib), pathlib.

Assumptions:
    - LiDAR captures are zip archives containing ``<scan_id>/odometry.csv``.
    - Video captures are ``.mp4`` / ``.mov`` files, or zip archives
      containing ``*/rgb.mp4``.
    - Photo captures are zip archives containing JPEG/PNG image files.
    - Maximum upload size is 2 GB (configurable).

Units / Coordinates:
    N/A.

Failure Modes:
    - Corrupt zip files raise zipfile.BadZipFile (caught and reported).
    - Files exceeding size limit are rejected before full read.

First Debugging Points:
    Check the returned ``ValidationResult.reason`` string for details.
"""

import zipfile
from io import BytesIO
from pathlib import Path
from typing import NamedTuple, Optional

from backend.app.models.capture import CaptureTier


class ValidationResult(NamedTuple):
    """Outcome of an input file validation check.

    Attributes:
        valid: True if the file is acceptable for the given tier.
        reason: Human-readable explanation (populated on rejection).
        detected_scan_id: For LiDAR zips, the detected scan ID inside.
    """
    valid: bool
    reason: str
    detected_scan_id: Optional[str] = None


# Maximum upload size: 2 GB
MAX_UPLOAD_BYTES = 2 * 1024 * 1024 * 1024

# Accepted image extensions for photo tier
PHOTO_EXTENSIONS = {".jpg", ".jpeg", ".png"}

# Accepted video extensions
VIDEO_EXTENSIONS = {".mp4", ".mov"}


def validate_upload(
    filename: str,
    file_data: bytes,
    tier: CaptureTier,
) -> ValidationResult:
    """Validate an uploaded file for the specified reconstruction tier.

    Purpose:
        Entry point for all upload validation.  Dispatches to
        tier-specific validators after common checks.

    Parameters:
        filename: Original upload filename.
        file_data: Raw file bytes.
        tier: Target sensor tier.

    Returns:
        ValidationResult with acceptance/rejection and reason.

    Assumptions:
        file_data contains the complete file content.

    Failure Conditions:
        Returns invalid result for unsupported formats, corrupt
        archives, or files exceeding size limits.

    Debugging Clues:
        Check reason field for specific rejection cause.
    """
    if not filename or not filename.strip():
        return ValidationResult(False, "No filename provided.")

    if len(file_data) == 0:
        return ValidationResult(False, "Uploaded file is empty.")

    if len(file_data) > MAX_UPLOAD_BYTES:
        size_mb = len(file_data) / (1024 * 1024)
        return ValidationResult(
            False,
            f"File size ({size_mb:.0f} MB) exceeds maximum allowed "
            f"({MAX_UPLOAD_BYTES / (1024 * 1024):.0f} MB).",
        )

    if tier == CaptureTier.LIDAR:
        return _validate_lidar(filename, file_data)
    elif tier == CaptureTier.VIDEO:
        return _validate_video(filename, file_data)
    elif tier == CaptureTier.PHOTO:
        return _validate_photo(filename, file_data)
    else:
        return ValidationResult(False, f"Unknown tier: {tier}")


def _validate_lidar(filename: str, file_data: bytes) -> ValidationResult:
    """Validate a LiDAR tier upload.

    Purpose:
        LiDAR captures must be zip archives containing a subdirectory
        with an ``odometry.csv`` file (as expected by LiDARScanLoader).

    Parameters:
        filename: Original filename.
        file_data: Raw zip bytes.

    Returns:
        ValidationResult.  ``detected_scan_id`` is set on success.

    Failure Conditions:
        Not a zip, no odometry.csv found inside.
    """
    ext = Path(filename).suffix.lower()
    if ext != ".zip":
        return ValidationResult(
            False,
            f"LiDAR tier requires a .zip archive, got '{ext}'.",
        )

    try:
        with zipfile.ZipFile(BytesIO(file_data), "r") as zf:
            names = zf.namelist()
            # Look for <scan_id>/odometry.csv pattern
            for name in names:
                parts = Path(name).parts
                if len(parts) >= 2 and parts[-1] == "odometry.csv":
                    scan_id = parts[-2]
                    return ValidationResult(
                        True,
                        f"Valid LiDAR archive with scan '{scan_id}'.",
                        detected_scan_id=scan_id,
                    )

            return ValidationResult(
                False,
                "Zip archive does not contain a <scan_id>/odometry.csv "
                "file.  LiDAR captures require an ARKit trajectory archive.",
            )
    except zipfile.BadZipFile:
        return ValidationResult(False, "File is not a valid zip archive.")


def _validate_video(filename: str, file_data: bytes) -> ValidationResult:
    """Validate a Video tier upload.

    Purpose:
        Video tier accepts direct .mp4/.mov files or zip archives
        containing ``*/rgb.mp4`` (the format used by existing backend
        test data).

    Parameters:
        filename: Original filename.
        file_data: Raw file bytes.

    Returns:
        ValidationResult.

    Failure Conditions:
        Unsupported extension; zip without rgb.mp4.
    """
    ext = Path(filename).suffix.lower()

    if ext in VIDEO_EXTENSIONS:
        return ValidationResult(True, f"Valid video file ({ext}).")

    if ext == ".zip":
        try:
            with zipfile.ZipFile(BytesIO(file_data), "r") as zf:
                names = zf.namelist()
                for name in names:
                    if name.endswith("rgb.mp4") or name.endswith(".mp4"):
                        return ValidationResult(
                            True,
                            f"Valid video archive containing '{name}'.",
                        )
                return ValidationResult(
                    False,
                    "Zip archive does not contain an .mp4 video file.",
                )
        except zipfile.BadZipFile:
            return ValidationResult(False, "File is not a valid zip archive.")

    return ValidationResult(
        False,
        f"Video tier requires .mp4, .mov, or .zip containing video.  "
        f"Got '{ext}'.",
    )


def _validate_photo(filename: str, file_data: bytes) -> ValidationResult:
    """Validate a Photo tier upload.

    Purpose:
        Photo tier accepts zip archives containing JPEG or PNG image
        files.  The pipeline expects a directory of images.

    Parameters:
        filename: Original filename.
        file_data: Raw file bytes.

    Returns:
        ValidationResult.

    Failure Conditions:
        Not a zip; zip contains no image files.
    """
    ext = Path(filename).suffix.lower()

    if ext != ".zip":
        return ValidationResult(
            False,
            f"Photo tier requires a .zip archive of images, got '{ext}'.",
        )

    try:
        with zipfile.ZipFile(BytesIO(file_data), "r") as zf:
            names = zf.namelist()
            image_count = sum(
                1 for n in names
                if Path(n).suffix.lower() in PHOTO_EXTENSIONS
                and not n.startswith("__MACOSX")
            )
            if image_count == 0:
                return ValidationResult(
                    False,
                    "Zip archive contains no JPEG or PNG image files.",
                )
            return ValidationResult(
                True,
                f"Valid photo archive with {image_count} image(s).",
            )
    except zipfile.BadZipFile:
        return ValidationResult(False, "File is not a valid zip archive.")
