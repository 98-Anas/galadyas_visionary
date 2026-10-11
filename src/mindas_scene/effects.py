"""Cinematic effects for a Canvas: gradients, glows, shadows, vignette, camera, blur.

Masks are cached, so effects that repeat every frame cost little after the first.
"""

from functools import lru_cache

from PIL import Image, ImageDraw, ImageFilter, ImageOps

from .canvas import Canvas, paste
from .motion import clamp

_BILINEAR = Image.Resampling.BILINEAR


@lru_cache(maxsize=16)
def _vgradient(size, top, bottom):
    mask = Image.linear_gradient("L").resize(size, _BILINEAR)
    return Image.composite(Image.new("RGBA", size, (*bottom, 255)), Image.new("RGBA", size, (*top, 255)), mask)


def vertical_gradient(c: Canvas, top, bottom) -> None:
    """Fill the canvas with a top-to-bottom gradient."""
    c.img.paste(_vgradient(c.img.size, tuple(top), tuple(bottom)))


@lru_cache(maxsize=32)
def _radial(px: int):
    g = ImageOps.invert(Image.radial_gradient("L"))  # 255 at the center, 0 at the edge
    return g.point(lambda v: int(255 * (v / 255) ** 2.2)).resize((px, px), _BILINEAR)


def glow(c: Canvas, center, radius: float, color, strength: float = 1.0) -> None:
    """A soft circular light, brightest at `center`, gone at `radius`."""
    px = max(2, round(2 * radius * c.scale))
    mask = _radial(px)
    if strength < 1:
        mask = mask.point(lambda v: int(v * strength))
    light = Image.new("RGBA", (px, px), (*color, 0))
    light.putalpha(mask)
    paste(c.img, light, center[0] * c.scale - px / 2, center[1] * c.scale - px / 2)


@lru_cache(maxsize=8)
def _vignette(size, strength):
    g = Image.radial_gradient("L").resize(size, _BILINEAR)  # ellipse fitted to the frame
    alpha = g.point(lambda v: int(255 * strength * clamp((v / 255 - 0.5) / 0.6) ** 1.6))
    im = Image.new("RGBA", size, (0, 0, 0, 0))
    im.putalpha(alpha)
    return im


def vignette(c: Canvas, strength: float = 0.6) -> None:
    """Darken the corners to pull the eye to the center."""
    c.img.alpha_composite(_vignette(c.img.size, round(strength, 3)))


@lru_cache(maxsize=16)
def _scrim(size, color, opacity):
    mask = Image.linear_gradient("L").resize(size, _BILINEAR).point(lambda v: int(v * opacity))
    im = Image.new("RGBA", size, (*color, 0))
    im.putalpha(mask)
    return im


def scrim(c: Canvas, y0: float, y1: float, color=(0, 0, 0), opacity: float = 0.85) -> None:
    """A band that fades from transparent at y0 to `color` at y1; keeps captions legible."""
    size = (c.img.width, max(1, round((y1 - y0) * c.scale)))
    paste(c.img, _scrim(size, tuple(color), round(opacity, 3)), 0, y0 * c.scale)


@lru_cache(maxsize=32)
def _shadow(w, h, radius, blur, opacity, color, scale):
    k = 4  # blur at quarter resolution, then scale up: same look, a fraction of the cost
    pad = blur * 2
    small = Image.new("L", (max(1, round((w + 2 * pad) * scale / k)), max(1, round((h + 2 * pad) * scale / k))), 0)
    f = scale / k
    ImageDraw.Draw(small).rounded_rectangle((pad * f, pad * f, (pad + w) * f, (pad + h) * f), radius * f,
                                            fill=round(255 * opacity))
    small = small.filter(ImageFilter.GaussianBlur(blur * f / 2))
    mask = small.resize((round((w + 2 * pad) * scale), round((h + 2 * pad) * scale)), _BILINEAR)
    im = Image.new("RGBA", mask.size, (*color, 0))
    im.putalpha(mask)
    return im, pad


def shadow(c: Canvas, box, radius: float = 12, blur: float = 40, opacity: float = 0.5,
           offset=(0, 20), color=(0, 0, 0)) -> None:
    """A soft drop shadow for a (rounded) rectangle. Draw it before the shape."""
    x0, y0, x1, y1 = box
    im, pad = _shadow(round(x1 - x0), round(y1 - y0), radius, blur, round(opacity, 3), tuple(color), c.scale)
    paste(c.img, im, (x0 - pad + offset[0]) * c.scale, (y0 - pad + offset[1]) * c.scale)


def gradient_rect(c: Canvas, box, left, right, radius: float = 0) -> None:
    """A rounded rectangle filled with a left-to-right gradient."""
    s = c.scale
    w, h = round((box[2] - box[0]) * s), round((box[3] - box[1]) * s)
    if w < 1 or h < 1:
        return
    g = Image.linear_gradient("L").transpose(Image.Transpose.ROTATE_90)  # 0 at left, 255 at right
    fill = Image.composite(Image.new("RGBA", (w, h), (*right, 255)), Image.new("RGBA", (w, h), (*left, 255)),
                           g.resize((w, h), _BILINEAR))
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, w - 1, h - 1), min(radius * s, h / 2, w / 2), fill=255)
    fill.putalpha(mask)
    paste(c.img, fill, box[0] * s, box[1] * s)


def camera(c: Canvas, zoom: float = 1.0, focus=None) -> None:
    """Zoom the canvas around `focus` (logical px). Moving `focus` pans; areas outside become transparent."""
    fx, fy = focus or (c.w / 2, c.h / 2)
    if zoom == 1 and (fx, fy) == (c.w / 2, c.h / 2):
        return
    s = c.scale
    W, H = c.img.size
    a = 1 / zoom
    data = (a, 0, fx * s - W / 2 * a, 0, a, fy * s - H / 2 * a)
    img = c.img.convert("RGBa").transform((W, H), Image.Transform.AFFINE, data, Image.Resampling.BICUBIC)
    c.set_image(img.convert("RGBA"))


def blur(c: Canvas, radius: float) -> None:
    if radius > 0:
        c.set_image(c.img.filter(ImageFilter.GaussianBlur(radius * c.scale)))
