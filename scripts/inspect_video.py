"""Inspect video stream properties, codec, duration, and keyframe distribution.

Usage:
    python -m scripts.inspect_video
    python -m scripts.inspect_video --archive "sample data/single_scan_with_ceiling.zip" --scan c7d28f72c6
"""

import argparse
import os
import zipfile
import subprocess
import tempfile
import json


def inspect_video(archive_path: str, scan_id: str):
    video_rel_path = f"{scan_id}/rgb.mp4"
    if not os.path.exists(archive_path):
        print(f"Archive not found: {archive_path}")
        return

    with zipfile.ZipFile(archive_path, "r") as zf:
        if video_rel_path not in zf.namelist():
            print(f"Video {video_rel_path} not found in {archive_path}")
            return

        with tempfile.TemporaryDirectory() as tmpdir:
            temp_mp4 = os.path.join(tmpdir, "video.mp4")
            with open(temp_mp4, "wb") as f:
                f.write(zf.read(video_rel_path))

            cmd = [
                "ffprobe", "-v", "error",
                "-show_format", "-show_streams",
                "-print_format", "json",
                temp_mp4
            ]
            res = subprocess.run(cmd, capture_output=True, text=True)
            info = json.loads(res.stdout)
            
            stream = info["streams"][0]
            fmt = info["format"]

            print("=" * 60)
            print(f"VIDEO INSPECTION: {archive_path} -> {scan_id}")
            print("=" * 60)
            print(f"  Container Format:      {fmt.get('format_long_name')}")
            print(f"  Codec:                 {stream.get('codec_long_name')} ({stream.get('codec_name')})")
            print(f"  Profile:               {stream.get('profile')}")
            print(f"  Resolution:            {stream.get('width')} x {stream.get('height')} (Aspect: 4:3)")
            print(f"  Pixel Format:          {stream.get('pix_fmt')}")
            print(f"  Color Space / Range:   {stream.get('color_space')} / {stream.get('color_range')}")
            print(f"  Nominal Timebase:      {stream.get('r_frame_rate')} FPS")
            print(f"  Average Framerate:     {stream.get('avg_frame_rate')}")
            print(f"  Total Duration:        {float(fmt.get('duration', 0)):.2f} seconds")
            print(f"  Total Frames:          {stream.get('nb_frames')}")
            print(f"  File Size:             {int(fmt.get('size', 0)) / (1024*1024):.2f} MB")
            print(f"  Bitrate:               {int(fmt.get('bit_rate', 0)) / 1000:.1f} kbps")
            print(f"  Creation Time:         {fmt.get('tags', {}).get('creation_time', 'N/A')}")
            print(f"  Handler:               {stream.get('tags', {}).get('handler_name', 'N/A')}")
            print("-" * 60)


def main():
    parser = argparse.ArgumentParser(description="Inspect video stream properties")
    parser.add_argument("--archive", default=None, help="Zip archive to inspect")
    parser.add_argument("--scan", default=None, help="Scan ID inside archive")
    args = parser.parse_args()

    if args.archive and args.scan:
        inspect_video(args.archive, args.scan)
    else:
        scans = [
            ("sample data/single_room.zip", "c00a170fe1"),
            ("sample data/single_scan_floor_only.zip", "1a8384c3f6"),
            ("sample data/single_scan_with_ceiling.zip", "c7d28f72c6")
        ]
        for arc, sc in scans:
            inspect_video(arc, sc)


if __name__ == "__main__":
    main()
