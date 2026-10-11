# mindas_scene

Videos and animations, written as code.

mindas_scene is a self-learning project about building motion graphics with code: product demos, title cards, explainers and math animations. It has two tracks:

- **Pillow + ffmpeg:** a small engine where every frame is a pure function of time. You draw a frame with Pillow, and the engine encodes the frames into an H.264 MP4. You get full control over every pixel and need no external renderer.
- **Manim:** scenes built with [Manim Community](https://www.manim.community/) for diagrams, equations and mathematical motion.

> **Status:** pre-release. The API will change until the first stable version. Feedback is welcome.

## Install

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/). ffmpeg is bundled through `imageio-ffmpeg`.

```
git clone https://github.com/98-Anas/mindas_scene && cd mindas_scene
uv sync                    # Pillow track
uv sync --extra manim      # add Manim (see the Manim install guide for system packages)
```

## Quick start

```python
from PIL import Image, ImageDraw
from mindas_scene import fade, mix, render

BG, FG = (9, 11, 16), (205, 214, 230)

def frame(t):
    img = Image.new("RGB", (1920, 1080), BG)
    a = fade(t, 0.2, 4.0)              # fade in, hold, fade out
    ImageDraw.Draw(img).text((860, 520), "hello", fill=mix(BG, FG, a))
    return img

render(frame, "media/hello.mp4", duration=4.0)
```

## Examples

| Example | Track | Run |
|---|---|---|
| Title card | Pillow | `uv run python examples/pillow/title_card.py` |
| mindas_terminal launch demo (45 s) | Pillow | `uv run python examples/pillow/mindas_terminal_demo.py` |
| Hello scene | Manim | `uv run manim -pqh examples/manim/hello_scene.py HelloScene` |

Output goes to `media/`, which git ignores.

## The model

A video is a function `frame(t) -> Image`. Helpers in `mindas_scene.motion` turn time into values:

| Helper | Returns |
|---|---|
| `ramp(t, a, b)` | 0 before `a`, 1 after `b`, eased in between |
| `fade(t, a, b, d)` | fade in at `a`, hold, fade out by `b` |
| `mix(c1, c2, k)` | blend two RGB colors |
| `ease(x)` | smoothstep easing |

Because frames depend only on `t`, you can preview any moment instantly with `stills(frame, "media/preview", [3.0, 12.5])` without rendering the whole video.

## Roadmap

- Scene composition: sequence and crossfade between scenes
- Audio tracks and narration timing
- Text layout helpers and theme tokens
- Vertical (9:16) and square (1:1) presets for social formats
- More Manim scenes: algorithms, data structures, linear algebra

## Development

```
uv sync
uv run pytest
```

## License

Apache-2.0
