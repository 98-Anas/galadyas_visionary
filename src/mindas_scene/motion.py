"""Timing and color helpers. Every function is pure: pass a time, get a value."""


def clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def ease(x: float) -> float:
    """Smoothstep: soft start, soft stop."""
    x = clamp(x)
    return x * x * (3 - 2 * x)


def ramp(t: float, start: float, end: float) -> float:
    """0 before `start`, 1 after `end`, eased in between."""
    return ease((t - start) / (end - start))


def fade(t: float, start: float, end: float, duration: float = 0.5) -> float:
    """Fade in at `start`, hold, fade out by `end`."""
    return ramp(t, start, start + duration) * (1 - ramp(t, end - duration, end))


def mix(a: tuple, b: tuple, k: float) -> tuple:
    """Blend two RGB colors; k=0 gives a, k=1 gives b."""
    return tuple(int(a[i] + (b[i] - a[i]) * k) for i in range(3))
