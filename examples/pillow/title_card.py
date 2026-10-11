"""Smallest complete example: a five-second title card.

    uv run python examples/pillow/title_card.py
"""

from PIL import Image, ImageDraw, ImageFont

from mindas_scene import fade, mix, render

W, H = 1920, 1080
BG, FG, DIM = (9, 11, 16), (205, 214, 230), (98, 108, 130)


def font(size):
    try:
        return ImageFont.truetype("DejaVuSans.ttf", size)
    except OSError:
        return ImageFont.load_default(size)


TITLE, SUB = font(96), font(40)


def centered(d, y, text, f, color):
    d.text(((W - d.textlength(text, font=f)) / 2, y), text, font=f, fill=color)


def frame(t):
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    a = fade(t, 0.2, 5.0, 0.8)
    b = fade(t, 0.9, 5.0, 0.8)
    centered(d, 430 - 12 * (1 - a), "mindas_scene", TITLE, mix(BG, FG, a))
    centered(d, 570, "Videos and animations, written as code.", SUB, mix(BG, DIM, b))
    return img


if __name__ == "__main__":
    print(render(frame, "media/title_card.mp4", duration=5.0))
