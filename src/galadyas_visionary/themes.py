"""Visual themes. A theme is a small set of colors; fonts are bundled and shared by all themes."""

from dataclasses import dataclass, replace

from .canvas import Font

Color = tuple[int, int, int]

DISPLAY = ("Inter-Light.ttf",)
BODY = ("Inter-Regular.ttf",)
LABEL = ("Inter-SemiBold.ttf",)
MONO = ("JetBrainsMono-Regular.ttf",)


@dataclass(frozen=True)
class Theme:
    name: str
    bg_top: Color
    bg_bottom: Color
    surface: Color    # cards, panels
    line: Color       # borders, tracks
    text: Color
    muted: Color
    accent: Color
    accent2: Color
    glow: float       # strength of the background lights
    vignette: float

    @property
    def bg_mid(self) -> Color:
        return tuple((a + b) // 2 for a, b in zip(self.bg_top, self.bg_bottom))

    @property
    def dark(self) -> bool:
        return sum(self.bg_mid) < 384

    def with_accent(self, accent: Color | None) -> "Theme":
        return replace(self, accent=accent) if accent else self


PRESETS: dict[str, Theme] = {t.name: t for t in [
    Theme("Midnight", (13, 15, 25), (5, 6, 10), (21, 25, 35), (38, 44, 60), (222, 228, 242), (148, 158, 182),
          (122, 162, 247), (187, 154, 247), 0.17, 0.55),
    Theme("Graphite", (24, 24, 27), (10, 10, 12), (32, 32, 36), (52, 52, 58), (236, 236, 240), (160, 160, 170),
          (230, 230, 235), (140, 140, 150), 0.08, 0.5),
    Theme("Ocean", (8, 24, 36), (3, 10, 18), (14, 34, 48), (30, 58, 76), (220, 236, 244), (136, 166, 182),
          (64, 196, 212), (90, 140, 240), 0.18, 0.5),
    Theme("Ember", (26, 14, 12), (10, 6, 6), (38, 22, 20), (66, 40, 34), (244, 232, 226), (184, 156, 146),
          (242, 140, 82), (226, 86, 96), 0.16, 0.5),
    Theme("Daylight", (250, 250, 252), (236, 239, 245), (255, 255, 255), (220, 224, 234), (22, 26, 38),
          (98, 106, 124), (52, 98, 230), (130, 90, 230), 0.10, 0.12),
]}

DEFAULT_THEME = "Midnight"


def font(kind: tuple, size: float) -> Font:
    return Font(kind, size)


def hex_to_rgb(value: str | None) -> Color | None:
    if not value:
        return None
    v = value.strip().lstrip("#")
    if len(v) == 3:
        v = "".join(ch * 2 for ch in v)
    if len(v) != 6:
        return None
    try:
        return tuple(int(v[i:i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        return None


def rgb_to_hex(c: Color) -> str:
    return "#{:02x}{:02x}{:02x}".format(*c)
