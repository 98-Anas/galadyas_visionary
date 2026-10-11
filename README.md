# mindas_scene

Polished product, marketing and report videos, made from templates. Offline, on your own machine.

mindas_scene is a desktop studio for startups, companies and individuals who need to introduce a project, launch a product or present results, without a motion designer and without uploading anything anywhere. Pick scenes, type your words, choose a theme, export an MP4.

> **Status:** release candidate for 1.0. The first public release will be the stable 1.0.

## What you get

- **A focused studio.** Scenes on the left, live preview in the middle, settings on the right. Play, scrub, reorder, export.
- **Templates that look designed.** Title, statement, key points, feature grid, key numbers, bar chart, product showcase and end card, each with considered motion and typography.
- **Every format.** 16:9, 9:16 and 1:1 from the same project. Layouts adapt; long text shrinks and wraps instead of overflowing.
- **Themes.** Midnight, Graphite, Ocean, Ember and Daylight, plus your own accent color.
- **Fast.** Live preview renders in about 10 ms per frame; export uses every CPU core. High quality is 2× supersampled.
- **Consistent everywhere.** Inter and JetBrains Mono are bundled, so a project renders the same on Windows, macOS and Linux.
- **Private.** No account, no telemetry, no network access.
- **For developers too.** The same engine is a Python API for fully custom films.

## Install

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/). ffmpeg is bundled.

```
git clone https://github.com/98-Anas/mindas_scene && cd mindas_scene
uv sync
uv run mindas-scene studio
```

## Using the studio

1. **+ Add** scenes from the templates; drag to reorder.
2. Fill in the fields on the **Scene** tab. Lists take one item per line; pairs use `|`, for example `98% | satisfaction`.
3. Set format, theme, accent, frame rate, crossfade and an optional soundtrack on the **Project** tab.
4. **Export video**: High (2× supersampled), Standard (faster) or Draft (quick check). Exports can be cancelled at any time.

Projects are saved as `.mscene` files (readable JSON). Images and audio inside the project folder are stored with relative paths, so a project folder can be moved or shared as a whole.

| Shortcut | Action |
|---|---|
| Space | Play / pause |
| Home / End | Jump to start / end |
| Ctrl+S, Ctrl+Shift+S | Save, save as |
| Ctrl+O, Ctrl+N | Open, new |
| Ctrl+E | Export |

## Command line

```
uv run mindas-scene render project.mscene -o video.mp4 -q high   # or standard, draft
uv run mindas-scene still project.mscene 2.5 10                 # PNG frames at given seconds
```

## Examples

| Example | Made with | Files |
|---|---|---|
| mindas series teaser (22 s) | Studio templates | [project](examples/mindas_series/mindas_series.mscene), [video](examples/mindas_series/mindas_series_teaser.mp4) |
| mindas_terminal launch film (30 s) | Python API | [script](examples/mindas_terminal/launch.py), [video](examples/mindas_terminal/mindas_terminal_launch.mp4) |
| Title card | Python API | [script](examples/pillow/title_card.py) |
| Hello scene | Manim (optional extra) | [script](examples/manim/hello_scene.py) |

## Python API

For films the templates do not cover, draw frames directly. A video is a function of time:

```python
from mindas_scene import Clip, Font, Timeline, Video, mix, ramp
from mindas_scene import effects as fx

TITLE = Font("Inter-Light.ttf", 96)

def background(c, t):
    fx.vertical_gradient(c, (13, 15, 25), (5, 6, 10))
    fx.glow(c, (960, 420), 800, (122, 162, 247), 0.15)

def title(c, t):
    c.text((960, 480), "hello", TITLE, mix((9, 11, 17), (220, 226, 240), ramp(t, 0.2, 1.2)), anchor="mt")

video = Video(Timeline(Clip(0, 4, title), background=background))
```

```
uv run mindas-scene render scene.py --draft
```

| Module | What it gives you |
|---|---|
| `Canvas`, `Font` | Draw in logical pixels, stored at `scale`× for supersampling; text wrapping, images, font fallbacks |
| `Timeline`, `Clip` | Scenes with crossfades, plus background and foreground layers |
| `effects` | Gradients, glows, soft shadows, vignette, scrims, gradient bars, camera zoom and pan, blur |
| `motion` | `ramp`, `fade`, `stagger`, `keyframes` and easing curves |
| `Video` | Parallel rendering, quality presets, progress and cancel, audio muxing, grain against banding |
| `Project`, `TEMPLATES`, `PRESETS` | The studio's project model, templates and themes, usable from code |

## Development

```
uv sync
uv run pytest
```

The tests cover the engine, project files (including damaged, foreign and newer files), every template in every format with hostile input, media paths, parallel export, cancellation and a scripted run of the studio.

## License

Apache-2.0. Bundled fonts: Inter and JetBrains Mono, both under the SIL Open Font License (see `src/mindas_scene/fonts`).
