"""Render a frame function to MP4 by piping raw frames into ffmpeg."""

import subprocess
from pathlib import Path
from typing import Callable

import imageio_ffmpeg
from PIL import Image

FrameFn = Callable[[float], Image.Image]


def render(frame: FrameFn, out: str | Path, duration: float, size=(1920, 1080), fps: int = 30, crf: int = 18) -> Path:
    """Call `frame(t)` for every frame and encode an H.264 MP4 at `out`."""
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    w, h = size
    cmd = [
        imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w}x{h}", "-r", str(fps), "-i", "-",
        "-c:v", "libx264", "-preset", "slow", "-crf", str(crf),
        "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(out),
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    try:
        for i in range(int(duration * fps)):
            img = frame(i / fps)
            if img.size != size or img.mode != "RGB":
                raise ValueError(f"frame {i}: expected RGB {size}, got {img.mode} {img.size}")
            proc.stdin.write(img.tobytes())
    finally:
        proc.stdin.close()
        if proc.wait() != 0:
            raise RuntimeError(f"ffmpeg exited with {proc.returncode}")
    return out


def stills(frame: FrameFn, out_dir: str | Path, times: list[float]) -> list[Path]:
    """Save PNG previews at the given times; faster than rendering the whole video."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for t in times:
        p = out_dir / f"frame_{t:06.2f}.png"
        frame(t).save(p)
        paths.append(p)
    return paths
