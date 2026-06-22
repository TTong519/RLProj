#!/usr/bin/env python3
"""ffmpeg-based fallback to produce demo GIFs when imageio is not installed.

Usage:
  python demos/capture_demo_gif_ffmpeg.py --task suturing --output docs/demos/suturing.gif

This script is intentionally simple: it points ffmpeg at an existing simulation
frame source. In production, prefer `demos/capture_demo_gif.py` which renders frames
from the simulator directly via imageio.
"""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Capture demo GIF via ffmpeg fallback")
    parser.add_argument("--source", required=True, type=Path, help="Source image/video")
    parser.add_argument("--output", required=True, type=Path, help="Output GIF path")
    parser.add_argument("--duration", type=int, default=30, help="GIF duration in seconds")
    parser.add_argument("--fps", type=int, default=10)
    parser.add_argument("--width", type=int, default=320)
    args = parser.parse_args()

    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        print("ffmpeg not found in PATH", file=sys.stderr)
        raise SystemExit(1)

    cmd = [
        ffmpeg, "-y", "-loop", "1", "-i", str(args.source),
        "-vf", f"fps={args.fps},scale={args.width}:-1",
        "-t", str(args.duration),
        str(args.output),
    ]
    subprocess.run(cmd, check=True)
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
