"""A resolution-independent drawing surface.

You draw in logical pixels (for example 1920x1080). The canvas stores pixels at
`scale` times that size, so a 2x canvas gives supersampled, smooth edges once
the frame is downscaled.
"""

import os
import sys
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def _font_dirs() -> list[Path]:
    if sys.platform == "win32":
        dirs = [Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts",
                Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "Windows" / "Fonts"]
    elif sys.platform == "darwin":
        dirs = [Path("/System/Library/Fonts"), Path("/Library/Fonts"), Path.home() / "Library" / "Fonts"]
    else:
        dirs = [Path("/usr/share/fonts"), Path("/usr/local/share/fonts"),
                Path.home() / ".local" / "share" / "fonts", Path.home() / ".fonts"]
    return [d for d in dirs if d.is_dir()]


@lru_cache(maxsize=None)
def find_font(*names: str) -> str | None:
    """Return the first font file found among `names` (file names or paths)."""
    for name in names:
        if Path(name).is_file():
            return str(name)
        for d in _font_dirs():
            if (d / name).is_file():
                return str(d / name)
            for hit in d.rglob(name):
                return str(hit)
    return None


@lru_cache(maxsize=256)
def _load(path: str | None, px: int):
    return ImageFont.truetype(path, px) if path else ImageFont.load_default(px)


class Font:
    """A font at a logical size, with fallbacks: Font(("Inter-Light.ttf", "DejaVuSans.ttf"), 40)."""

    def __init__(self, names: str | tuple[str, ...], size: float):
        self.names = (names,) if isinstance(names, str) else tuple(names)
        self.size = size

    @property
    def path(self) -> str | None:
        return find_font(*self.names)

    def at(self, scale: float):
        return _load(self.path, max(1, round(self.size * scale)))


def _rgba(color):
    if color is None:
        return None
    return tuple(color) if len(color) == 4 else (*color, 255)


def paste(base: Image.Image, im: Image.Image, x: float, y: float) -> None:
    """Alpha-composite `im` onto `base` at device pixel (x, y), clipping at the edges."""
    x, y = round(x), round(y)
    sx, sy = max(0, -x), max(0, -y)
    x, y = max(0, x), max(0, y)
    w = min(im.width - sx, base.width - x)
    h = min(im.height - sy, base.height - y)
    if w > 0 and h > 0:
        base.alpha_composite(im, dest=(x, y), source=(sx, sy, sx + w, sy + h))


class Canvas:
    def __init__(self, width: int, height: int, scale: float = 1.0, background=None):
        self.w, self.h, self.scale = width, height, scale
        size = (max(1, round(width * scale)), max(1, round(height * scale)))
        self.img = Image.new("RGBA", size, _rgba(background) or (0, 0, 0, 0))
        self.draw = ImageDraw.Draw(self.img)

    def set_image(self, img: Image.Image) -> None:
        self.img = img
        self.draw = ImageDraw.Draw(img)

    def _s(self, *values):
        return [v * self.scale for v in values]

    # layers

    def layer(self) -> "Canvas":
        """A transparent canvas of the same size, to draw a group and composite it later."""
        return Canvas(self.w, self.h, self.scale)

    def composite(self, other: "Canvas | Image.Image", opacity: float = 1.0, at=(0, 0)) -> None:
        if opacity <= 0:
            return
        src = other.img if isinstance(other, Canvas) else other
        if opacity < 1:
            src = src.copy()
            src.putalpha(src.getchannel("A").point(lambda v: int(v * opacity)))
        paste(self.img, src, at[0] * self.scale, at[1] * self.scale)

    # shapes

    def rect(self, box, fill=None, outline=None, width: float = 1, radius: float = 0) -> None:
        b = self._s(*box)
        if b[2] <= b[0] or b[3] <= b[1]:
            return
        lw = max(1, round(width * self.scale)) if outline else 0
        r = min(radius * self.scale, (b[2] - b[0]) / 2, (b[3] - b[1]) / 2)
        self.draw.rounded_rectangle(b, r, fill=_rgba(fill), outline=_rgba(outline), width=lw)

    def ellipse(self, box, fill=None, outline=None, width: float = 1) -> None:
        self.draw.ellipse(self._s(*box), fill=_rgba(fill), outline=_rgba(outline),
                          width=max(1, round(width * self.scale)))

    def line(self, points, fill, width: float = 1) -> None:
        self.draw.line(self._s(*points), fill=_rgba(fill), width=max(1, round(width * self.scale)))

    # text

    def textlength(self, text: str, font: Font, tracking: float = 0) -> float:
        return font.at(self.scale).getlength(text) / self.scale + tracking * max(0, len(text) - 1)

    def text(self, xy, text: str, font: Font, fill, anchor: str = "la", tracking: float = 0) -> None:
        """Draw text. `anchor` follows Pillow (e.g. "mt" = middle-top). `tracking` adds letter spacing."""
        f = font.at(self.scale)
        x, y = self._s(*xy)
        if not tracking:
            self.draw.text((x, y), text, font=f, fill=_rgba(fill), anchor=anchor)
            return
        tr = tracking * self.scale
        widths = [f.getlength(ch) for ch in text]
        total = sum(widths) + tr * max(0, len(text) - 1)
        x -= {"m": total / 2, "r": total}.get(anchor[0], 0)
        # Resolve the vertical anchor against the whole string, then set every glyph on one baseline;
        # anchoring each glyph separately would align them by their own tops.
        baseline = y + f.getbbox(text, anchor="l" + anchor[1])[1] - f.getbbox(text, anchor="ls")[1]
        for ch, w in zip(text, widths):
            self.draw.text((x, baseline), ch, font=f, fill=_rgba(fill), anchor="ls")
            x += w + tr

    def to_image(self, size=None) -> Image.Image:
        img = self.img.convert("RGB")
        if size and img.size != tuple(size):
            img = img.resize(size, Image.Resampling.LANCZOS)
        return img
