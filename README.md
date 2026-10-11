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
from mindas_scene import Clip, Font, Timeline, Video, mix, ramp
from mindas_scene import effects as fx

TITLE = Font(("segoeuil.ttf", "Inter-Light.ttf", "DejaVuSans.ttf"), 96)

def background(c, t):
    fx.vertical_gradient(c, (13, 15, 25), (5, 6, 10))
    fx.glow(c, (960, 420), 800, (122, 162, 247), 0.15)

def title(c, t):
    c.text((960, 480), "hello", TITLE, mix((9, 11, 17), (220, 226, 240), ramp(t, 0.2, 1.2)), anchor="mt")

video = Video(Timeline(Clip(0, 4, title), background=background))
```

```
uv run mindas-scene still scene.py 1.5 3        # PNG previews, seconds
uv run mindas-scene render scene.py --draft     # fast 1x / 15 fps preview
uv run mindas-scene render scene.py             # final: 2x supersampled, all cores
```

## Examples

| Example | Run |
|---|---|
| [mindas_terminal launch film](examples/mindas_terminal/) (45 s, rendered MP4 included) | `uv run mindas-scene render examples/mindas_terminal/launch.py` |
| Title card | `uv run mindas-scene render examples/pillow/title_card.py` |
| Manim hello scene | `uv run manim -pqh examples/manim/hello_scene.py HelloScene` |

## Building blocks

| Module | What it gives you |
|---|---|
| `Canvas`, `Font` | Draw in logical pixels; stored at `scale`x for supersampled edges; font fallbacks across OSes |
| `Timeline`, `Clip` | Scenes with crossfades, plus background and foreground layers |
| `effects` | Gradients, glows, soft shadows, vignette, scrims, gradient bars, camera zoom and pan, blur |
| `motion` | `ramp`, `fade`, `stagger`, `keyframes`, easings (`ease_out_expo`, `ease_out_back`, ...) |
| `Video` | Parallel rendering across cores, draft mode, audio muxing, film grain against banding |

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
