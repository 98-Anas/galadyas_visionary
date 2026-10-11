"""Compose a video from clips that crossfade into each other."""

from dataclasses import dataclass
from typing import Callable

from .canvas import Canvas
from .motion import ramp

Draw = Callable[[Canvas, float], None]


@dataclass
class Clip:
    """Draws `draw(canvas, local_time)` between `start` and `end`, fading at both edges."""

    start: float
    end: float
    draw: Draw
    fade_in: float = 0.6
    fade_out: float = 0.6
    isolate: bool = True  # draw on a private layer even when fully visible (needed if draw() uses camera or blur)

    def opacity(self, t: float) -> float:
        a = ramp(t, self.start, self.start + self.fade_in) if self.fade_in > 0 else 1.0
        b = 1 - ramp(t, self.end - self.fade_out, self.end) if self.fade_out > 0 else 1.0
        return a * b


class Timeline:
    """A draw function made of clips. Clips that overlap in time crossfade."""

    def __init__(self, *clips: Clip, background: Draw | None = None, foreground: Draw | None = None):
        self.clips = list(clips)
        self.background = background
        self.foreground = foreground

    @property
    def duration(self) -> float:
        return max(c.end for c in self.clips)

    def __call__(self, c: Canvas, t: float) -> None:
        if self.background:
            self.background(c, t)
        for clip in self.clips:
            if clip.start <= t < clip.end:
                opacity = clip.opacity(t)
                if opacity >= 1 and not clip.isolate:
                    clip.draw(c, t - clip.start)
                elif opacity > 0:
                    layer = c.layer()
                    clip.draw(layer, t - clip.start)
                    c.composite(layer, opacity)
        if self.foreground:
            self.foreground(c, t)
