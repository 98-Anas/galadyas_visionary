"""galadyas_visionary demo film, built from real footage of the studio.

    uv run python tools/capture_studio.py media/footage        # record the app (about 90 s)
    uv run galadyas-visionary render examples/galadyas_visionary/demo.py -o examples/galadyas_visionary/galadyas_visionary_demo.mp4

Every frame inside the window is a grab of the running app; nothing in it is mocked up.
Figures on screen (11 templates, 3 formats, 5 themes) are counted from the code below.
"""

import math
import os
from pathlib import Path

from galadyas_visionary import (Canvas, Clip, Font, PRESETS, TEMPLATES, Timeline, Video, ease_out_cubic, fade,
                                keyframes, mix, ramp, stagger)
from galadyas_visionary import effects as fx
from galadyas_visionary.cosmos import starfield
from galadyas_visionary.project import FORMATS
from galadyas_visionary.templates import reveal

W, H = 1920, 1080
TH = PRESETS["Midnight"]
BG = TH.bg_mid
LIGHT, SEMI, BODY = ("Inter-Light.ttf",), ("Inter-SemiBold.ttf",), ("Inter-Regular.ttf",)
FOOTAGE = Path(os.environ.get("FOOTAGE", Path(__file__).resolve().parents[2] / "media" / "footage"))
FPS_FOOTAGE = 15


def frames(clip: str) -> list[Path]:
    return sorted((FOOTAGE / clip).glob("*.png"))


def background(c: Canvas, t: float) -> None:
    small = Canvas(W, H, scale=c.scale / 4)
    fx.vertical_gradient(small, TH.bg_top, TH.bg_bottom)
    fx.glow(small, (W * (0.5 + 0.12 * math.sin(t * 0.1)), H * 0.32), 900, TH.accent, 0.16)
    fx.glow(small, (W * 0.82, H * 0.92), 760, TH.accent2, 0.09)
    from PIL import Image
    c.img.paste(small.img.resize(c.img.size, Image.Resampling.BILINEAR))
    starfield(c, t, density=0.6, brightness=0.8)


def finish(c: Canvas, t: float) -> None:
    fx.vignette(c, TH.vignette)


def chips(c, y, labels, t, start):
    f = Font(SEMI, 20)
    widths = [c.textlength(s, f, 1) + 44 for s in labels]
    x = W / 2 - (sum(widths) + 14 * (len(labels) - 1)) / 2
    for i, (s, w) in enumerate(zip(labels, widths)):
        k = stagger(t, start, i, 0.12, 0.6)
        if k > 0:
            yy = y + 10 * (1 - k)
            c.rect((x, yy, x + w, yy + 46), fill=mix(BG, TH.surface, k), outline=mix(BG, TH.line, k), width=1.5,
                   radius=23)
            c.text((x + w / 2, yy + 23), s, f, mix(BG, TH.text, k), anchor="mm", tracking=1)
        x += w + 14


# ---------------------------------------------------------------- 1. opening

def opening(c, t):
    reveal(c, W / 2, 360, "galadyas_visionary", Font(LIGHT, 104), TH.text, ramp(t, 0.15, 1.3, lambda v: v))
    reveal(c, W / 2, 510, "Polished videos from templates, made on your own machine.", Font(LIGHT, 36), TH.muted,
           ramp(t, 0.7, 1.8, lambda v: v))
    chips(c, 610, ["Open source", "Under development", "Works offline"], t, 1.4)


# ---------------------------------------------------------------- 2. the studio, real footage

WX0, WY0, WW, WH = 288, 64, 1344, 756   # window box (16:9, like the footage), clear of the captions
SHOTS = [  # clip, caption label, caption, camera keyframes (local t -> zoom, focus x, focus y)
    ("01_play", "THE STUDIO", "Scenes on the left, a live preview in the middle.",
     [(0, (1.0, 960, 442)), (4.6, (1.07, 860, 420))]),
    ("02_edit", "WRITE", "Type, and the preview follows.",
     [(0, (1.04, 1060, 420)), (3.8, (1.08, 1120, 400))]),
    ("03_style", "STYLE", "One project. Every theme and format.",
     [(0, (1.0, 960, 442)), (5.3, (1.03, 900, 442))]),
    ("04_cosmic", "CINEMATIC", "Scenes like the Whirlpool Galaxy, built in.",
     [(0, (1.02, 960, 442)), (2.0, (1.12, 880, 420)), (4.5, (1.14, 880, 420))]),
    ("05_export", "EXPORT", "Export to MP4, on your own machine.",
     [(0, (1.0, 960, 442)), (5.2, (1.08, 960, 430))]),
]


def shot(index):
    clip, label, text, cam = SHOTS[index]
    files = frames(clip)

    def draw(c, t):
        if not files:
            c.text((W / 2, H / 2), f"Run tools/capture_studio.py first ({clip} missing)", Font(BODY, 28), TH.muted,
                   anchor="mm")
            return
        frame = files[min(int(t * FPS_FOOTAGE), len(files) - 1)]
        win = c.layer()
        fx.shadow(win, (WX0, WY0, WX0 + WW, WY0 + WH), radius=14, blur=60, opacity=0.65, offset=(0, 28))
        win.image(frame, (WX0, WY0, WX0 + WW, WY0 + WH), radius=14)
        win.rect((WX0, WY0, WX0 + WW, WY0 + WH), outline=TH.line, width=1.5, radius=14)
        zoom, fx_, fy_ = keyframes(t, cam)
        fx.camera(win, zoom, (fx_, fy_))
        c.composite(win)
        fx.scrim(c, 880, 1080, TH.bg_bottom, 0.9 * ramp(zoom, 1.0, 1.06))
        a = fade(t, 0.3, len(files) / FPS_FOOTAGE, 0.4)
        c.text((WX0, 962), f"{index + 1:02d}", Font(SEMI, 17), mix(BG, TH.accent, a), tracking=2)
        c.rect((WX0 + 36, 971, WX0 + 36 + 28 * a, 972.5), fill=mix(BG, TH.accent, a))
        c.text((WX0 + 76, 962), label, Font(SEMI, 17), mix(BG, TH.muted, a), tracking=3)
        reveal(c, WX0, 994, text, Font(LIGHT, 36), TH.text, ramp(t, 0.35, 1.2, lambda v: v) * a, anchor="l")

    return draw, max(len(files), 1) / FPS_FOOTAGE


# ---------------------------------------------------------------- 3. what you get, 4. end

def summary(c, t):
    reveal(c, W / 2, 200, "Everything you need to tell the story", Font(LIGHT, 60), TH.text,
           ramp(t, 0.1, 1.1, lambda v: v))
    cards = [(str(len(TEMPLATES)), "scene templates"), (str(len(FORMATS)), "formats: 16:9, 9:16, 1:1"),
             (str(len(PRESETS)), "themes, plus your accent"), ("0", "accounts or uploads")]
    for i, (big, small) in enumerate(cards):
        k = stagger(t, 0.6, i, 0.12, 0.8)
        if k <= 0:
            continue
        x, y = (W - (4 * 360 + 3 * 30)) / 2 + i * 390, 420 + 24 * (1 - k)
        card = c.layer()
        fx.shadow(card, (x, y, x + 360, y + 240), radius=18, blur=30, opacity=0.5, offset=(0, 16))
        card.rect((x, y, x + 360, y + 240), fill=TH.surface, outline=TH.line, width=1.5, radius=18)
        card.text((x + 34, y + 36), big, Font(LIGHT, 92), TH.text)
        card.rect((x + 36, y + 150, x + 76, y + 153), fill=TH.accent)
        card.text((x + 34, y + 172), small, Font(BODY, 24), TH.muted)
        c.composite(card, k)


def ending(c, t):
    reveal(c, W / 2, 410, "galadyas_visionary", Font(LIGHT, 96), TH.text, ramp(t, 0.1, 1.2, lambda v: v))
    chips(c, 560, ["Open source", "Under development", "Feedback welcome"], t, 0.9)


def build():
    clips = [Clip(0.0, 3.6, opening, fade_in=0, fade_out=0.6, isolate=False, zoom_out=0.985)]
    t = 3.1
    for i in range(len(SHOTS)):
        draw, dur = shot(i)
        clips.append(Clip(t, t + dur, draw, fade_in=0.5, fade_out=0.5, zoom_in=1.02))
        t += dur - 0.5
    clips.append(Clip(t, t + 4.2, summary, fade_in=0.6, fade_out=0.6, zoom_in=1.03, isolate=False))
    t += 4.2 - 0.6
    clips.append(Clip(t, t + 3.6, ending, fade_in=0.6, fade_out=0.9, zoom_in=1.03, isolate=False))
    return Timeline(*clips, background=background, foreground=finish)


video = Video(build(), size=(W, H), fps=30, ssaa=2)

if __name__ == "__main__":
    print(video.render("examples/galadyas_visionary/galadyas_visionary_demo.mp4"))
