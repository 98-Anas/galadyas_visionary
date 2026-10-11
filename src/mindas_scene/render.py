"""Turn a draw function into an MP4: supersampling, parallel workers, optional audio."""

import importlib.util
import os
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from functools import lru_cache
from itertools import repeat
from pathlib import Path
from typing import Callable

import imageio_ffmpeg
from PIL import Image, ImageChops

from .canvas import Canvas

Draw = Callable[[Canvas, float], None]
_JOB_MODULE = "_mindas_scene_job"


@lru_cache(maxsize=4)
def _grain(size, sigma):
    noise = Image.effect_noise(size, sigma)
    return Image.merge("RGB", (noise, noise, noise))


class Video:
    """A draw function plus format settings.

    draw(canvas, t) paints one frame at time t (seconds) on a canvas of `size` logical pixels.
    `ssaa` is the supersampling factor; `dither` adds faint grain that hides gradient banding.
    """

    _registry: list["Video"] = []

    def __init__(self, draw: Draw, duration: float | None = None, size=(1920, 1080), fps: int = 30,
                 ssaa: float = 2, background=(0, 0, 0), dither: float = 2.0):
        self.draw = draw
        self.duration = duration if duration is not None else draw.duration
        self.size, self.fps, self.ssaa = tuple(size), fps, ssaa
        self.background, self.dither = background, dither
        # Remember where this video was defined so worker processes can rebuild it.
        self._source = os.path.normcase(os.path.abspath(sys._getframe(1).f_code.co_filename))
        self._index = sum(v._source == self._source for v in Video._registry)
        Video._registry.append(self)

    def frame(self, t: float, ssaa: float | None = None) -> Image.Image:
        c = Canvas(*self.size, scale=self.ssaa if ssaa is None else ssaa, background=self.background)
        self.draw(c, t)
        img = c.to_image(self.size)
        if self.dither:
            img = ImageChops.add(img, _grain(self.size, self.dither), 1.0, -128)
        return img

    def stills(self, times, out_dir="media/stills") -> list[Path]:
        """Save PNGs at the given times; the quickest way to check a moment."""
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        paths = []
        for t in times:
            p = out_dir / f"{Path(self._source).stem}_{t:06.2f}.png"
            self.frame(t).save(p)
            paths.append(p)
        return paths

    def render(self, out, workers: int | None = None, draft: bool = False, audio=None, crf: int = 18) -> Path:
        """Encode to H.264 MP4. Draft mode renders at 1x, 15 fps for fast iteration."""
        out = Path(out)
        out.parent.mkdir(parents=True, exist_ok=True)
        fps = 15 if draft else self.fps
        ssaa = 1 if draft else self.ssaa
        times = [i / fps for i in range(int(round(self.duration * fps)))]
        workers = workers or os.cpu_count() or 1
        proc = subprocess.Popen(_ffmpeg_cmd(out, self.size, fps, crf, audio), stdin=subprocess.PIPE)
        started = time.perf_counter()
        try:
            if workers > 1 and Path(self._source).is_file():
                with ProcessPoolExecutor(workers, initializer=_init_worker,
                                         initargs=(self._source, self._index)) as pool:
                    frames = pool.map(_worker_frame, times, repeat(ssaa), chunksize=4)
                    _write(proc, frames, len(times), started)
            else:
                _write(proc, (self.frame(t, ssaa).tobytes() for t in times), len(times), started)
        finally:
            proc.stdin.close()
            if proc.wait() != 0:
                raise RuntimeError(f"ffmpeg exited with {proc.returncode}")
        return out


def _write(proc, frames, total, started):
    for i, data in enumerate(frames, 1):
        proc.stdin.write(data)
        if i % 30 == 0 or i == total:
            print(f"\r  frame {i}/{total}  {time.perf_counter() - started:5.1f}s", end="", file=sys.stderr, flush=True)
    print(file=sys.stderr)


def _ffmpeg_cmd(out, size, fps, crf, audio):
    cmd = [imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{size[0]}x{size[1]}", "-r", str(fps), "-i", "-"]
    if audio:
        cmd += ["-i", str(audio), "-map", "0:v", "-map", "1:a", "-c:a", "aac", "-b:a", "192k", "-shortest"]
    cmd += ["-c:v", "libx264", "-preset", "slow", "-crf", str(crf), "-pix_fmt", "yuv420p",
            "-movflags", "+faststart", str(out)]
    return cmd


def load(path, index: int = 0) -> Video:
    """Import a scene file and return the `index`-th Video it defines."""
    path = os.path.normcase(os.path.abspath(path))
    Video._registry = []
    spec = importlib.util.spec_from_file_location(_JOB_MODULE, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[_JOB_MODULE] = module
    spec.loader.exec_module(module)
    videos = [v for v in Video._registry if v._source == path]
    if len(videos) <= index:
        raise LookupError(f"{path} defines no Video #{index}")
    return videos[index]


_job: Video | None = None


def _init_worker(source, index):
    global _job
    _job = load(source, index)


def _worker_frame(t, ssaa):
    return _job.frame(t, ssaa).tobytes()
