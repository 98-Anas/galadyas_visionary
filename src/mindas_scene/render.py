"""Turn a draw function into an MP4: supersampling, parallel workers, progress, cancel, optional audio."""

import importlib.util
import os
import subprocess
import sys
import threading
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
Progress = Callable[[int, int], None]
_JOB_MODULE = "_mindas_scene_job"

# name: (supersampling, fps or None for the video's own)
QUALITY = {"draft": (1, 15), "standard": (1, None), "high": (2, None)}


class Cancelled(Exception):
    """Raised by Video.render when its cancel event is set; the partial file is removed."""


@lru_cache(maxsize=4)
def _grain(size, sigma):
    noise = Image.effect_noise(size, sigma)
    return Image.merge("RGB", (noise, noise, noise))


class Video:
    """A draw function plus format settings.

    draw(canvas, t) paints one frame at time t (seconds) on a canvas of `size` logical pixels.
    `ssaa` is the supersampling factor; `dither` adds faint grain that hides gradient banding.
    `factory` is an importable (function, args) that rebuilds this video in worker processes;
    without it, workers re-import the file that created the video.
    """

    _registry: list["Video"] = []

    def __init__(self, draw: Draw, duration: float | None = None, size=(1920, 1080), fps: int = 30,
                 ssaa: float = 2, background=(0, 0, 0), dither: float = 2.0, factory: tuple | None = None):
        self.draw = draw
        self.duration = duration if duration is not None else draw.duration
        self.size, self.fps, self.ssaa = tuple(size), fps, ssaa
        self.background, self.dither, self.factory = background, dither, factory
        self._source = os.path.normcase(os.path.abspath(sys._getframe(1).f_code.co_filename))
        self._index = sum(v._source == self._source for v in Video._registry)
        Video._registry.append(self)

    @property
    def frame_count(self) -> int:
        return int(round(self.duration * self.fps))

    def frame(self, t: float, ssaa: float | None = None) -> Image.Image:
        """The finished frame at time t, at the video's size."""
        c = Canvas(*self.size, scale=self.ssaa if ssaa is None else ssaa, background=self.background)
        self.draw(c, t)
        img = c.to_image(self.size)
        if self.dither:
            img = ImageChops.add(img, _grain(self.size, self.dither), 1.0, -128)
        return img

    def preview(self, t: float, scale: float = 0.5) -> Image.Image:
        """A fast, reduced-size frame for interactive preview (no supersampling, no grain)."""
        c = Canvas(*self.size, scale=scale, background=self.background)
        self.draw(c, min(max(t, 0.0), max(0.0, self.duration - 1e-3)))
        return c.img.convert("RGB")

    def stills(self, times, out_dir="media/stills", stem: str | None = None) -> list[Path]:
        """Save PNGs at the given times; the quickest way to check a moment."""
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        stem = stem or Path(self._source).stem
        paths = []
        for t in times:
            p = out_dir / f"{stem}_{t:06.2f}.png"
            self.frame(t).save(p)
            paths.append(p)
        return paths

    def render(self, out, workers: int | None = None, quality: str = "high", draft: bool = False, audio=None,
               crf: int = 18, progress: Progress | None = None, cancel: threading.Event | None = None) -> Path:
        """Encode to H.264 MP4.

        quality: "draft" (1x, 15 fps), "standard" (1x) or "high" (2x supersampled).
        progress(done, total) is called as frames are written; setting `cancel` stops the
        render, removes the partial file and raises Cancelled.
        """
        if draft:
            quality = "draft"
        ssaa, fps = QUALITY[quality]
        ssaa = min(ssaa, self.ssaa) if quality == "high" else ssaa
        fps = fps or self.fps
        out = Path(out)
        out.parent.mkdir(parents=True, exist_ok=True)
        tmp = out.with_name(f".{out.stem}.partial{out.suffix}")
        times = [i / fps for i in range(int(round(self.duration * fps)))]
        workers = max(1, workers or os.cpu_count() or 1)
        report = progress or _print_progress(time.perf_counter())

        proc = subprocess.Popen(_ffmpeg_cmd(tmp, self.size, fps, crf, audio), stdin=subprocess.PIPE,
                                stderr=subprocess.PIPE)
        ok = False
        try:
            frames = self._frames(times, ssaa, workers)
            try:
                for i, data in enumerate(frames, 1):
                    if cancel is not None and cancel.is_set():
                        raise Cancelled()
                    proc.stdin.write(data)
                    report(i, len(times))
            finally:
                close = getattr(frames, "close", None)
                if close:
                    close()
            proc.stdin.close()
            if proc.wait() != 0:
                raise RuntimeError(f"ffmpeg failed: {proc.stderr.read().decode(errors='replace').strip()}")
            os.replace(tmp, out)
            ok = True
        except BrokenPipeError:
            proc.wait()
            raise RuntimeError(f"ffmpeg failed: {proc.stderr.read().decode(errors='replace').strip()}") from None
        finally:
            if not ok:
                if proc.poll() is None:
                    proc.kill()
                    proc.wait()
                tmp.unlink(missing_ok=True)
            if proc.stderr:
                proc.stderr.close()
        return out

    def _frames(self, times, ssaa, workers):
        """Yield encoded frames in order, from a process pool when that is possible."""
        spec = self._rebuild_spec()
        if workers > 1 and len(times) > 8 and spec:
            pool = ProcessPoolExecutor(min(workers, len(times)), initializer=_init_worker, initargs=(spec,))
            try:
                yield from pool.map(_worker_frame, times, repeat(ssaa), chunksize=4)
            finally:
                pool.shutdown(wait=True, cancel_futures=True)
        else:
            for t in times:
                yield self.frame(t, ssaa).tobytes()

    def _rebuild_spec(self):
        if self.factory:
            return ("factory", *self.factory)
        if Path(self._source).is_file():
            return ("file", self._source, self._index)
        return None


def _print_progress(started):
    def report(i, total):
        if i % 30 == 0 or i == total:
            print(f"\r  frame {i}/{total}  {time.perf_counter() - started:5.1f}s", end="", file=sys.stderr, flush=True)
            if i == total:
                print(file=sys.stderr)
    return report


def _ffmpeg_cmd(out, size, fps, crf, audio):
    cmd = [imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{size[0]}x{size[1]}", "-r", str(fps), "-i", "-"]
    if audio:
        cmd += ["-i", str(audio), "-map", "0:v", "-map", "1:a", "-c:a", "aac", "-b:a", "192k", "-shortest"]
    cmd += ["-c:v", "libx264", "-preset", "medium", "-crf", str(crf), "-pix_fmt", "yuv420p",
            "-movflags", "+faststart", str(out)]
    return cmd


def load(path, index: int = 0) -> Video:
    """Import a scene file (.py) and return the `index`-th Video it defines."""
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


def _init_worker(spec):
    global _job
    if spec[0] == "factory":
        _, fn, args = spec
        _job = fn(*args)
    else:
        _, source, index = spec
        _job = load(source, index)


def _worker_frame(t, ssaa):
    return _job.frame(t, ssaa).tobytes()
