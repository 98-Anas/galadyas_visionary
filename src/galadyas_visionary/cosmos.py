"""Space visuals: a procedural Whirlpool Galaxy (M51) and a starfield.

The galaxy is a fixed, seeded particle model: two broad logarithmic spiral arms
of young blue stars studded with pink star-forming knots, dark dust lanes on the
inner edge of each arm, a warm old-star bulge, a diffuse disk and halo, and the
companion galaxy NGC 5195 at the tip of one arm. Each frame rotates it (inner
regions a little faster), tilts it, splats the stars into a float light buffer,
adds blurred copies for nebulosity and tone-maps by luminance so colors stay
natural. All numpy: a 1080p frame costs well under a second, previews far less.
"""

import math
from functools import lru_cache

import numpy as np
from PIL import Image, ImageDraw

from .canvas import Canvas, paste


# ---------------------------------------------------------------- numeric helpers

def _box(a: np.ndarray, r: int, axis: int) -> np.ndarray:
    a = np.moveaxis(a, axis, -1)
    n = a.shape[-1]
    p = np.concatenate([np.repeat(a[..., :1], r + 1, -1), a, np.repeat(a[..., -1:], r, -1)], -1)
    c = np.cumsum(p, axis=-1, dtype=np.float32)
    out = (c[..., 2 * r + 1:] - c[..., :n]) * (1.0 / (2 * r + 1))
    return np.moveaxis(out, -1, axis)


def gaussian(a: np.ndarray, sigma: float) -> np.ndarray:
    """Gaussian blur over the last two axes (three box passes per axis)."""
    if sigma < 0.5:
        return a
    r = max(1, int(round((math.sqrt(4 * sigma * sigma + 1) - 1) / 2)))
    for axis in (-1, -2):
        for _ in range(3):
            a = _box(a, r, axis)
    return a


def _splat(buf: np.ndarray, xs, ys, weights) -> None:
    h, w = buf.shape[1:]
    xi, yi = xs.astype(np.int64), ys.astype(np.int64)
    ok = (xi >= 0) & (xi < w) & (yi >= 0) & (yi < h)
    idx = yi[ok] * w + xi[ok]
    for ch in range(3):
        buf[ch] += np.bincount(idx, weights=weights[ok, ch], minlength=w * h).reshape(h, w)


def _resize(arr: np.ndarray, size: int) -> np.ndarray:
    return np.stack([np.asarray(Image.fromarray(ch).resize((size, size), Image.Resampling.BICUBIC)) for ch in arr])


def _to_rgba(light: np.ndarray) -> Image.Image:
    """Float RGB light (3, h, w) -> RGBA whose alpha is the brightest channel (good over dark backgrounds)."""
    rgb = np.clip(light * 255, 0, 255).astype(np.uint8)
    alpha = rgb.max(axis=0)
    return Image.fromarray(np.dstack([rgb[0], rgb[1], rgb[2], alpha]), "RGBa").convert("RGBA")


# ---------------------------------------------------------------- the galaxy model

PITCH = math.tan(math.radians(16))
R0 = 0.10


def _arm_theta(r, arm):
    return np.log(r / R0) / PITCH + arm * np.pi


@lru_cache(maxsize=1)
def _model(seed: int = 51):
    rng = np.random.default_rng(seed)
    parts_r, parts_t, parts_c = [], [], []

    def add(r, t, c):
        parts_r.append(r)
        parts_t.append(t)
        parts_c.append(c.astype(np.float32))

    # broad arms of young stars
    n = 90000
    r = R0 + (1.02 - R0) * rng.power(1.15, n)
    arm = rng.integers(0, 2, n)
    t = _arm_theta(r, arm) + rng.normal(0, 0.16 + 0.10 * r, n)
    r = r * (1 + rng.normal(0, 0.045, n))
    add(r, t, np.array([0.66, 0.78, 1.0]) * rng.exponential(0.42, (n, 1)))

    # star-forming knots along the arms: clumps of blue and pink
    k = 260
    kr = R0 * 2 + (0.98 - R0 * 2) * rng.random(k)
    kt = _arm_theta(kr, rng.integers(0, 2, k)) + rng.normal(0, 0.08, k)
    per = 40
    cr = np.repeat(kr, per) * (1 + rng.normal(0, 0.012, k * per))
    ct = np.repeat(kt, per) + rng.normal(0, 0.03, k * per) / np.repeat(kr, per) * 0.4
    pink = np.repeat(rng.random(k) < 0.45, per)
    col = np.where(pink[:, None], [1.0, 0.36, 0.62], [0.58, 0.74, 1.0]) * rng.exponential(0.8, (k * per, 1))
    add(cr, ct, col)

    # diffuse disk, inter-arm light and the warm bulge
    n = 60000
    add(np.clip(rng.exponential(0.30, n), 0, 1.3), rng.uniform(0, 2 * np.pi, n),
        np.array([0.92, 0.86, 0.80]) * rng.exponential(0.2, (n, 1)))
    n = 26000
    add(np.abs(rng.normal(0, 0.07, n)), rng.uniform(0, 2 * np.pi, n),
        np.array([1.0, 0.84, 0.64]) * rng.exponential(0.42, (n, 1)))

    # dust lanes on the inner (trailing) edge of each arm
    n = 30000
    dr = R0 * 1.5 + (0.9 - R0 * 1.5) * rng.random(n)
    dt = _arm_theta(dr, rng.integers(0, 2, n)) - 0.26 + rng.normal(0, 0.06, n)

    # NGC 5195, the companion, just beyond the tip of arm 0
    tip = float(_arm_theta(np.array([1.08]), 0)[0]) + 0.15
    pc = (1.12 * math.cos(tip), 1.12 * math.sin(tip))
    n = 9000
    comp = rng.normal(0, 1, (n, 2)) * np.array([0.042, 0.036]) * np.sqrt(rng.exponential(1, (n, 1))) + pc
    ccol = np.array([1.0, 0.84, 0.64]) * rng.exponential(0.28, (n, 1))
    return (np.concatenate(parts_r).astype(np.float32), np.concatenate(parts_t).astype(np.float32),
            np.concatenate(parts_c), dr.astype(np.float32), dt.astype(np.float32),
            comp.astype(np.float32), ccol.astype(np.float32), pc)


def galaxy(c: Canvas, t: float, center, radius: float, brightness: float = 1.0, tilt: float = 0.40,
           angle: float = 0.6, spin: float = 0.045, exposure: float = 1.0) -> None:
    """Draw the Whirlpool Galaxy centered at `center` (logical px); `radius` is the reach of the arms."""
    if brightness <= 0 or radius <= 0:
        return
    r, th, col, dr, dt, comp, ccol, pc = _model()
    s = c.scale
    R = radius * s
    size = int(R * 3.0)
    if size < 16:
        return
    half = size / 2
    cos_t, ca, sa = math.cos(tilt), math.cos(angle), math.sin(angle)

    def place(x, y):
        y = y * cos_t
        return (x * ca - y * sa) * R + half, (x * sa + y * ca) * R + half

    def turn(rr, tt):
        return tt + spin * t * (0.78 + 0.22 / (rr + 0.25))   # inner regions turn a little faster

    # sharp starlight
    stars = np.zeros((3, size, size), np.float32)
    a = turn(r, th)
    x, y = place(r * np.cos(a), r * np.sin(a))
    density = (R / 800) ** 2   # stars per pixel fall as 1/R^2, so weight rises with R^2: same look at any size
    _splat(stars, x, y, col * density)
    whole = spin * t * 0.78
    cw, sw = math.cos(whole), math.sin(whole)
    kx, ky = place(comp[:, 0] * cw - comp[:, 1] * sw, comp[:, 0] * sw + comp[:, 1] * cw)
    _splat(stars, kx, ky, ccol * density)

    # nebulosity at low resolution
    k = max(1, math.ceil(size / 300))
    m = size // k
    small = stars[:, :m * k, :m * k].reshape(3, m, k, m, k).sum(axis=(2, 4))
    dust = np.zeros((3, m, m), np.float32)
    da = turn(dr, dt)
    dx, dy = place(dr * np.cos(da), dr * np.sin(da))
    _splat(dust, dx / k, dy / k, np.ones((len(dr), 3), np.float32))
    dust = gaussian(dust, m / 220)
    dust = dust / (dust.max() or 1)
    yy, xx = np.mgrid[0:m, 0:m].astype(np.float32)
    d2 = ((xx - half / k) ** 2 + (yy - half / k) ** 2) / (R / k) ** 2
    px, py = place(pc[0] * cw - pc[1] * sw, pc[0] * sw + pc[1] * cw)
    e2 = ((xx - px / k) ** 2 + (yy - py / k) ** 2) / (R / k) ** 2
    warm = np.array([1.0, 0.80, 0.58], np.float32)[:, None, None]
    core = (np.exp(-d2 / 0.0025) * 1.1 + np.exp(-d2 / 0.03) * 0.45 + np.exp(-d2 / 0.35) * 0.06
            + np.exp(-e2 / 0.003) * 0.45 + np.exp(-e2 / 0.02) * 0.06)
    unit = 1.0 / (k * k)
    glow = (gaussian(small, m / 300) * 0.9 + gaussian(small, m / 110) * 0.8 + gaussian(small, m / 35) * 0.5) * unit
    glow = glow * (1 - 0.75 * dust) + core[None] * warm
    light = stars * 0.35 + _resize(glow, size)

    # luminance tone map keeps hues natural instead of clipping channels separately
    lum = 0.3 * light[0] + 0.55 * light[1] + 0.15 * light[2]
    mapped = 1 - np.exp(-exposure * brightness * 1.6 * lum)
    light = light * (mapped / np.maximum(lum, 1e-6))[None]
    paste(c.img, _to_rgba(light), center[0] * s - half, center[1] * s - half)


# ---------------------------------------------------------------- starfield

@lru_cache(maxsize=1)
def _stars(seed: int = 7, n: int = 1200):
    rng = np.random.default_rng(seed)
    pos = rng.random((n, 2))
    mag = np.clip(rng.exponential(0.32, n), 0, 1)
    warm = rng.random(n) < 0.25
    phase = rng.uniform(0, 2 * np.pi, n)
    depth = rng.uniform(0.3, 1.0, n)
    return pos, mag, warm, phase, depth


def starfield(c: Canvas, t: float, density: float = 1.0, drift=(5.0, -1.5), brightness: float = 1.0) -> None:
    """Fine, slowly drifting stars with a gentle twinkle, drawn as small sprites."""
    pos, mag, warm, phase, depth = _stars()
    n = int(len(pos) * min(1.0, density))
    s = c.scale
    layer = Image.new("RGBA", c.img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    x = (pos[:n, 0] * c.w + drift[0] * t * depth[:n]) % c.w * s
    y = (pos[:n, 1] * c.h + drift[1] * t * depth[:n]) % c.h * s
    level = np.clip(mag[:n] * (0.7 + 0.3 * np.sin(phase[:n] + t * (1.2 + 2 * depth[:n]))) * brightness, 0, 1)
    for i in np.nonzero(level > 0.03 / min(1.0, s))[0]:
        v = int((60 + 195 * level[i]) * min(1.0, s) ** 0.7)
        color = (255, 226, 196, v) if warm[i] else (214, 226, 255, v)
        rad = (0.45 + 1.1 * level[i] ** 2) * s
        d.ellipse((x[i] - rad, y[i] - rad, x[i] + rad, y[i] + rad), fill=color)
    c.img.alpha_composite(layer)
