"""Smallest complete example: a five-second title card.

    uv run mindas-scene render examples/pillow/title_card.py
"""

from mindas_scene import Clip, Font, Timeline, Video, ease_out_expo, mix, ramp
from mindas_scene import effects as fx

BG_TOP, BG_BOT, FG, DIM, ACC = (13, 15, 25), (5, 6, 10), (220, 226, 240), (130, 140, 162), (122, 162, 247)
TITLE = Font(("segoeuil.ttf", "Inter-Light.ttf", "DejaVuSans.ttf"), 104)
SUB = Font(("segoeuil.ttf", "Inter-Light.ttf", "DejaVuSans.ttf"), 38)


def background(c, t):
    fx.vertical_gradient(c, BG_TOP, BG_BOT)
    fx.glow(c, (960 + 120 * t, 420), 800, ACC, 0.15)


def title(c, t):
    a = ramp(t, 0.2, 1.2)
    tracking = 28 * (1 - ramp(t, 0.2, 2.0, ease_out_expo)) + 1
    c.text((960, 440), "mindas_scene", TITLE, mix(BG_BOT, FG, a), anchor="mt", tracking=tracking)
    c.text((960, 590 + 12 * (1 - ramp(t, 0.8, 1.8))), "Videos and animations, written as code.", SUB,
           mix(BG_BOT, DIM, ramp(t, 0.8, 1.8)), anchor="mt")


video = Video(Timeline(Clip(0, 5, title, fade_in=0, fade_out=0.8), background=background,
                       foreground=lambda c, t: fx.vignette(c, 0.5)))

if __name__ == "__main__":
    print(video.render("media/title_card.mp4"))
