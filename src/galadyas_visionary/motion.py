"""Timing, easing and color helpers. Every function is pure: pass a time, get a value."""

from typing import Callable, Sequence

Easing = Callable[[float], float]


def clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def lerp(a: float, b: float, k: float) -> float:
    return a + (b - a) * k


# Easings map 0..1 to 0..1.

def linear(x: float) -> float:
    return clamp(x)


def ease(x: float) -> float:
    """Smoothstep: soft start, soft stop."""
    x = clamp(x)
    return x * x * (3 - 2 * x)


def ease_out_cubic(x: float) -> float:
    return 1 - (1 - clamp(x)) ** 3


def ease_in_out_cubic(x: float) -> float:
    x = clamp(x)
    return 4 * x ** 3 if x < 0.5 else 1 - (-2 * x + 2) ** 3 / 2


def ease_out_expo(x: float) -> float:
    x = clamp(x)
    return 1.0 if x >= 1 else 1 - 2 ** (-10 * x)


def ease_out_back(x: float, overshoot: float = 1.4) -> float:
    x = clamp(x) - 1
    return 1 + (overshoot + 1) * x ** 3 + overshoot * x ** 2


# Time to progress.

def ramp(t: float, start: float, end: float, easing: Easing = ease) -> float:
    """0 before `start`, 1 after `end`, eased in between."""
    return easing((t - start) / (end - start))


def fade(t: float, start: float, end: float, duration: float = 0.5, easing: Easing = ease) -> float:
    """Fade in at `start`, hold, fade out by `end`."""
    return ramp(t, start, start + duration, easing) * (1 - ramp(t, end - duration, end, easing))


def stagger(t: float, start: float, index: int, step: float, duration: float, easing: Easing = ease_out_cubic) -> float:
    """Progress of item `index` in a group that starts one after another."""
    s = start + index * step
    return ramp(t, s, s + duration, easing)


def keyframes(t: float, frames: Sequence[tuple[float, float | tuple]], easing: Easing = ease_in_out_cubic):
    """Interpolate between (time, value) pairs. Values may be numbers or tuples of numbers."""
    if t <= frames[0][0]:
        return frames[0][1]
    for (t0, v0), (t1, v1) in zip(frames, frames[1:]):
        if t < t1:
            k = easing((t - t0) / (t1 - t0)) if t1 > t0 else 1.0
            if isinstance(v0, tuple):
                return tuple(lerp(a, b, k) for a, b in zip(v0, v1))
            return lerp(v0, v1, k)
    return frames[-1][1]


def mix(a: tuple, b: tuple, k: float) -> tuple:
    """Blend two RGB colors; k=0 gives a, k=1 gives b."""
    return tuple(int(a[i] + (b[i] - a[i]) * k) for i in range(3))
