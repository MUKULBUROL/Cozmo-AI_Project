"""Stage 7 Video Keyframe Extraction and Visual Quality Filtering.

1. Why this file exists:
   Extracts high-sharpness, non-redundant RGB keyframes from continuous handheld video
   walkthroughs, rejecting motion blur and poor exposure without requiring ARKit odometry.

2. Pipeline stage:
   Stage 7 (Video Tier - Keyframe Selection).

3. Inputs:
   File path to input video (.mp4 or .mov) and output target directory.

4. Outputs:
   Extracted JPEG keyframes and List[VideoKeyframe] structured records with manifest.

5. Coordinate convention:
   2D pixel coordinates (u, v) with top-left origin.

6. Unit convention:
   - Time: Seconds.
   - Sharpness: Laplacian variance (dimensionless).
   - Intensity: Grayscale values in [0, 255].
   - Dimensions: Pixels.

7. Important dependencies:
   cv2, numpy, pathlib, json, backend.app.models.video.VideoKeyframe.

8. Assumptions:
   Video walkthrough has sufficient lighting and non-degenerate camera motion.

9. Main failure modes:
   - Entire video is pitch black or oversaturated -> exposure gate rejects all frames.
   - Severe motion blur throughout -> fallbacks ensure minimum keyframe coverage.

10. What a developer should inspect first when debugging:
    Inspect keyframe JPEG files in output_dir and verify sharpness scores in keyframe_manifest.json.
"""

import json
from pathlib import Path
from typing import List, Tuple, Optional
import cv2
import numpy as np

from backend.app.models.video import VideoKeyframe


def compute_laplacian_sharpness(img: np.ndarray) -> float:
    """Computes edge response variance using discrete Laplacian operator.

    Purpose:
        Quantifies high-frequency image detail to detect motion blur.

    Parameters:
        img: Grayscale (2D) or BGR (3D) uint8 image array.

    Returns:
        float variance of the Laplacian filter response.

    Assumptions:
        Higher values correspond to sharper edges; blurry images exhibit suppressed variance.

    Failure conditions:
        Uniform or empty arrays return 0.0.

    Dependencies:
        cv2.cvtColor, cv2.Laplacian, numpy.var.

    Debugging clues:
        Sharp scenes score > 100.0; motion blurred scenes drop below 30.0.
    """
    if img is None or img.size == 0:
        return 0.0
    if img.ndim == 3:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    else:
        gray = img
    # Full-resolution 4K/2K Laplacians dominate CPU time while adding no useful ranking
    # precision. Preserve aspect ratio and score a bounded thumbnail instead.
    if gray.shape[1] > 640:
        target_height = max(1, int(round(gray.shape[0] * 640 / gray.shape[1])))
        gray = cv2.resize(gray, (640, target_height), interpolation=cv2.INTER_AREA)
    # Compute discrete Laplacian using 64-bit float to prevent overflow
    lap = cv2.Laplacian(gray, cv2.CV_64F)
    return float(np.var(lap))


def evaluate_exposure_quality(
    img: np.ndarray,
    min_mean_intensity: float = 15.0,
    max_mean_intensity: float = 245.0,
) -> Tuple[bool, float]:
    """Evaluates whether frame has usable exposure (neither crushed blacks nor blown highlights).

    Purpose:
        Rejects uninformative under- or over-exposed frames before feature extraction.

    Parameters:
        img: Grayscale or BGR uint8 image array.
        min_mean_intensity: Lower bound for acceptable mean brightness (0-255).
        max_mean_intensity: Upper bound for acceptable mean brightness (0-255).

    Returns:
        Tuple of (is_acceptable: bool, mean_intensity: float).

    Assumptions:
        Useful indoor frames typically have mean brightness between 40 and 200.

    Failure conditions:
        Empty image returns (False, 0.0).

    Dependencies:
        numpy.mean.
    """
    if img is None or img.size == 0:
        return False, 0.0
    if img.ndim == 3:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    else:
        gray = img
    mean_val = float(np.mean(gray))
    is_ok = bool(min_mean_intensity <= mean_val <= max_mean_intensity)
    return is_ok, mean_val


def compute_visual_motion_delta(img1: np.ndarray, img2: np.ndarray) -> float:
    """Computes mean absolute difference between two frames to measure visual displacement.

    Purpose:
        Quantifies visual motion to prevent extracting redundant stationary frames.

    Parameters:
        img1: First frame (uint8 array).
        img2: Second frame (uint8 array).

    Returns:
        float mean absolute difference in [0.0, 255.0].

    Assumptions:
        Both images are resized to matching thumbnail dimensions for efficient evaluation.

    Failure conditions:
        Returns 0.0 if either image is None.

    Dependencies:
        cv2.resize, cv2.absdiff, numpy.mean.
    """
    if img1 is None or img2 is None or img1.size == 0 or img2.size == 0:
        return 0.0
    g1 = cv2.cvtColor(img1, cv2.COLOR_BGR2GRAY) if img1.ndim == 3 else img1
    g2 = cv2.cvtColor(img2, cv2.COLOR_BGR2GRAY) if img2.ndim == 3 else img2

    # Resize to standard evaluation resolution
    thumb1 = cv2.resize(g1, (160, 120), interpolation=cv2.INTER_AREA)
    thumb2 = cv2.resize(g2, (160, 120), interpolation=cv2.INTER_AREA)

    diff = cv2.absdiff(thumb1, thumb2)
    return float(np.mean(diff))


def extract_video_keyframes(
    video_path: Path,
    output_dir: Path,
    min_frame_stride: int = 5,
    max_frame_stride: int = 30,
    blur_threshold: float = 25.0,
    max_keyframes: int = 60,
    min_motion_delta: float = 3.0,
    rotation_deg: int = 0,
) -> List[VideoKeyframe]:
    """Extracts informative, sharp keyframes from video and saves them to disk.

    Purpose:
        Produces a compact sequence of high-quality keyframes for visual SfM and depth estimation.

    Parameters:
        video_path: Path to video file (.mp4, .mov).
        output_dir: Directory where extracted JPEG frames and manifest will be stored.
        min_frame_stride: Minimum frames between consecutive keyframe selections.
        max_frame_stride: Maximum frames between consecutive keyframe selections.
        blur_threshold: Minimum Laplacian sharpness score.
        max_keyframes: Maximum number of keyframes to extract.
        min_motion_delta: Minimum visual motion difference required relative to previous keyframe.
        rotation_deg: Clockwise display rotation applied to decoded frames before all quality
            measurements and JPEG output. Coordinates and dimensions in returned records refer
            to the normalized display image.

    Returns:
        List of VideoKeyframe records.

    Assumptions:
        Video can be decoded with OpenCV VideoCapture. Selection spacing is increased when the
        requested keyframe cap would otherwise be reached before the end of the capture.

    Failure conditions:
        Raises ValueError if video cannot be opened or rotation is not a multiple of 90 degrees.

    Dependencies:
        cv2.VideoCapture, compute_laplacian_sharpness, evaluate_exposure_quality, compute_visual_motion_delta.

    Debugging clues:
        Check output_dir/keyframe_manifest.json to verify selected frame distribution.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise ValueError(f"Could not open video file: {video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS)
    if fps <= 0:
        fps = 30.0

    frame_count = max(0, int(cap.get(cv2.CAP_PROP_FRAME_COUNT)))
    if max_keyframes <= 0:
        cap.release()
        raise ValueError("max_keyframes must be greater than zero")

    rotation_deg %= 360
    if rotation_deg not in {0, 90, 180, 270}:
        cap.release()
        raise ValueError("rotation_deg must be 0, 90, 180, or 270")

    keyframes: List[VideoKeyframe] = []
    last_keyframe_img: Optional[np.ndarray] = None
    last_selected_frame_idx = -min_frame_stride
    frame_idx = 0
    window_count = min(max_keyframes, frame_count) if frame_count else 0
    current_window = -1
    best_candidate: Optional[Tuple[int, np.ndarray, float, bool]] = None

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        if rotation_deg == 90:
            frame = cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
        elif rotation_deg == 180:
            frame = cv2.rotate(frame, cv2.ROTATE_180)
        elif rotation_deg == 270:
            frame = cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)

        if window_count > 1:
            sharpness = compute_laplacian_sharpness(frame)
            exposure_ok, _ = evaluate_exposure_quality(frame)
            window_index = min(
                window_count - 1,
                int(frame_idx * window_count / max(1, frame_count)),
            )

            if window_index != current_window and best_candidate is not None:
                selected_idx, selected_frame, selected_sharpness, selected_exposure = best_candidate
                keyframe_id = len(keyframes)
                img_path = output_dir / f"frame_{keyframe_id:06d}.jpg"
                cv2.imwrite(str(img_path), selected_frame, [cv2.IMWRITE_JPEG_QUALITY, 95])
                keyframes.append(VideoKeyframe(
                    keyframe_id=keyframe_id,
                    frame_index=selected_idx,
                    timestamp=float(selected_idx / fps),
                    image_path=str(img_path.resolve()),
                    sharpness_score=selected_sharpness,
                    width=int(selected_frame.shape[1]),
                    height=int(selected_frame.shape[0]),
                    selection_reason=(
                        "sharpest_in_window"
                        if selected_exposure and selected_sharpness >= blur_threshold
                        else "forced_window"
                    ),
                ))
                last_keyframe_img = selected_frame
                last_selected_frame_idx = selected_idx
                best_candidate = None

            current_window = window_index
            # Stage 11 continuity & overlap: score candidate by combining edge sharpness,
            # exposure quality, and Gaussian temporal centering within the window to prevent
            # inter-window frame gaps from exploding into multi-second tracking blind spots.
            w_size = max(1.0, float(frame_count) / float(window_count))
            w_center = (float(window_index) + 0.5) * w_size
            sigma = max(5.0, 0.35 * w_size)
            dist_penalty = float(np.exp(-((float(frame_idx) - w_center) ** 2) / (2.0 * sigma * sigma)))

            base_sharpness = sharpness if exposure_ok else sharpness * 0.1
            candidate_score = base_sharpness * (0.3 + 0.7 * dist_penalty)

            previous_score = -1.0
            if best_candidate is not None:
                prev_idx, _, prev_sharp, prev_exp = best_candidate
                prev_base = prev_sharp if prev_exp else prev_sharp * 0.1
                prev_dist_pen = float(np.exp(-((float(prev_idx) - w_center) ** 2) / (2.0 * sigma * sigma)))
                previous_score = prev_base * (0.3 + 0.7 * prev_dist_pen)

            if candidate_score > previous_score and not (
                window_index == 0 and best_candidate is not None
            ):
                best_candidate = (frame_idx, frame.copy(), sharpness, exposure_ok)
        else:
            frames_since_last = frame_idx - last_selected_frame_idx
            if frames_since_last >= min_frame_stride:
                sharpness = compute_laplacian_sharpness(frame)
                exposure_ok, _ = evaluate_exposure_quality(frame)
                motion_ok = (
                    last_keyframe_img is None
                    or compute_visual_motion_delta(last_keyframe_img, frame) >= min_motion_delta
                    or frames_since_last >= max_frame_stride
                )
                if exposure_ok and motion_ok and (
                    sharpness >= blur_threshold or frames_since_last >= max_frame_stride
                ):
                    keyframe_id = len(keyframes)
                    img_path = output_dir / f"frame_{keyframe_id:06d}.jpg"
                    cv2.imwrite(str(img_path), frame, [cv2.IMWRITE_JPEG_QUALITY, 95])
                    keyframes.append(VideoKeyframe(
                        keyframe_id=keyframe_id,
                        frame_index=frame_idx,
                        timestamp=float(frame_idx / fps),
                        image_path=str(img_path.resolve()),
                        sharpness_score=sharpness,
                        width=int(frame.shape[1]),
                        height=int(frame.shape[0]),
                        selection_reason=(
                            "sharpness_stride" if sharpness >= blur_threshold else "forced_stride"
                        ),
                    ))
                    last_keyframe_img = frame
                    last_selected_frame_idx = frame_idx

                    if len(keyframes) >= max_keyframes:
                        break

        frame_idx += 1

    cap.release()

    if best_candidate is not None and len(keyframes) < max_keyframes:
        selected_idx, selected_frame, selected_sharpness, selected_exposure = best_candidate
        keyframe_id = len(keyframes)
        img_path = output_dir / f"frame_{keyframe_id:06d}.jpg"
        cv2.imwrite(str(img_path), selected_frame, [cv2.IMWRITE_JPEG_QUALITY, 95])
        keyframes.append(VideoKeyframe(
            keyframe_id=keyframe_id,
            frame_index=selected_idx,
            timestamp=float(selected_idx / fps),
            image_path=str(img_path.resolve()),
            sharpness_score=selected_sharpness,
            width=int(selected_frame.shape[1]),
            height=int(selected_frame.shape[0]),
            selection_reason=(
                "sharpest_in_window"
                if selected_exposure and selected_sharpness >= blur_threshold
                else "forced_window"
            ),
        ))

    # Write manifest JSON
    manifest_data = {
        "total_keyframes": len(keyframes),
        "keyframes": [kf.model_dump() for kf in keyframes],
    }
    manifest_file = output_dir / "keyframe_manifest.json"
    with open(manifest_file, "w", encoding="utf-8") as f:
        json.dump(manifest_data, f, indent=2)

    return keyframes
