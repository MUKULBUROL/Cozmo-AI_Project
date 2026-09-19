"""Extract representative RGB frames from a capture and generate a contact sheet.

Usage:
    python -m scripts.inspect_images --archive "sample data/single_room.zip" --scan c00a170fe1 --num-frames 6
"""

import argparse
import os
import zipfile
import subprocess
import tempfile
from PIL import Image, ImageDraw, ImageFont


def extract_frames_from_zip(archive_path: str, scan_id: str, num_frames: int = 6, output_path: str = "outputs/contact_sheet.png"):
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    video_rel_path = f"{scan_id}/rgb.mp4"

    with zipfile.ZipFile(archive_path, "r") as zf:
        if video_rel_path not in zf.namelist():
            raise FileNotFoundError(f"Video {video_rel_path} not found in {archive_path}")
        
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_mp4 = os.path.join(tmpdir, "video.mp4")
            with open(temp_mp4, "wb") as f:
                f.write(zf.read(video_rel_path))

            # Probe duration and frame count
            probe_cmd = [
                "ffprobe", "-v", "error", "-select_streams", "v:0",
                "-show_entries", "stream=duration,nb_frames",
                "-of", "default=noprint_wrappers=1:nokey=1", temp_mp4
            ]
            res = subprocess.run(probe_cmd, capture_output=True, text=True)
            lines = res.stdout.strip().splitlines()
            duration = float(lines[0]) if lines and lines[0] else 30.0

            # Extract evenly spaced frames
            timestamps = [duration * (i + 0.5) / num_frames for i in range(num_frames)]
            frame_images = []

            for i, ts in enumerate(timestamps):
                out_img = os.path.join(tmpdir, f"frame_{i}.jpg")
                cmd = [
                    "ffmpeg", "-y", "-ss", f"{ts:.2f}",
                    "-i", temp_mp4, "-frames:v", "1",
                    "-q:v", "2", out_img
                ]
                subprocess.run(cmd, capture_output=True)
                if os.path.exists(out_img):
                    img = Image.open(out_img).resize((480, 360))
                    draw = ImageDraw.Draw(img)
                    draw.text((10, 10), f"Scan: {scan_id} | t={ts:.1f}s", fill=(255, 255, 0))
                    frame_images.append(img)

            if not frame_images:
                print("Failed to extract frames.")
                return

            # Arrange in 2 rows x 3 cols grid
            cols = 3
            rows = (len(frame_images) + cols - 1) // cols
            w, h = frame_images[0].size
            sheet = Image.new("RGB", (cols * w, rows * h), color=(30, 30, 30))

            for idx, img in enumerate(frame_images):
                r = idx // cols
                c = idx % cols
                sheet.paste(img, (c * w, r * h))

            sheet.save(output_path)
            print(f"Contact sheet successfully created with {len(frame_images)} frames at: {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Generate contact sheet from capture video")
    parser.add_argument("--archive", default="sample data/single_room.zip", help="Path to zip archive")
    parser.add_argument("--scan", default="c00a170fe1", help="Scan ID inside archive")
    parser.add_argument("--num-frames", type=int, default=6, help="Number of frames to sample")
    parser.add_argument("--output", default="outputs/contact_sheet.png", help="Output contact sheet path")
    args = parser.parse_args()

    extract_frames_from_zip(args.archive, args.scan, args.num_frames, args.output)


if __name__ == "__main__":
    main()
