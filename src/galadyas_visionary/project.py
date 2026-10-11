"""Projects: a list of template scenes plus format and theme, stored as .gvis (JSON).

Loading is forgiving: unknown keys are dropped, missing fields get defaults and
out-of-range values are clamped, so a hand-edited or older file still opens.
"""

import json
import math
import os
import uuid
from dataclasses import dataclass, field
from functools import partial
from pathlib import Path

from . import effects as fx
from .canvas import Canvas
from .cosmos import galaxy, starfield
from .render import Video
from .templates import TEMPLATES, Context
from .themes import DEFAULT_THEME, PRESETS, Theme, hex_to_rgb
from .timeline import Clip, Timeline

SCHEMA = 1
EXTENSION = ".gvis"
FORMATS = {"landscape": ("Landscape 16:9", (1920, 1080)),
           "portrait": ("Portrait 9:16", (1080, 1920)),
           "square": ("Square 1:1", (1080, 1080))}
FPS_CHOICES = (24, 25, 30, 60)
BACKDROPS = {"glow": "Soft glow", "stars": "Starfield", "galaxy": "Whirlpool Galaxy"}
MIN_SCENE, MAX_SCENE = 1.5, 120.0


class ProjectError(ValueError):
    """The file is not a project this version can open."""


def _clamp(v, lo, hi, default):
    try:
        v = float(v)
    except (TypeError, ValueError):
        return default
    return default if math.isnan(v) else min(hi, max(lo, v))


@dataclass
class Scene:
    template: str
    fields: dict
    duration: float
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])

    @classmethod
    def new(cls, template_id: str) -> "Scene":
        tpl = TEMPLATES[template_id]
        return cls(template_id, tpl.defaults(), tpl.duration)

    def copy(self) -> "Scene":
        return Scene(self.template, dict(self.fields), self.duration)

    @property
    def summary(self) -> str:
        return TEMPLATES[self.template].summary(self.fields)


@dataclass
class Project:
    name: str = "Untitled"
    format: str = "landscape"
    fps: int = 30
    theme: str = DEFAULT_THEME
    accent: str = ""           # hex override of the theme accent; empty uses the theme's
    transition: float = 0.6
    backdrop: str = "glow"
    audio: str = ""
    scenes: list[Scene] = field(default_factory=list)
    base_dir: Path | None = field(default=None, compare=False)

    # ---------------------------------------------------------------- timing

    @property
    def size(self) -> tuple[int, int]:
        return FORMATS[self.format][1]

    def starts(self) -> list[float]:
        """Start time of each scene; consecutive scenes overlap by the transition."""
        out, t = [], 0.0
        for s in self.scenes:
            out.append(t)
            t += s.duration - self.transition
        return out

    @property
    def duration(self) -> float:
        if not self.scenes:
            return 0.0
        return self.starts()[-1] + self.scenes[-1].duration

    def scene_at(self, t: float) -> int:
        idx = 0
        for i, s in enumerate(self.starts()):
            if t >= s:
                idx = i
        return idx

    def resolved_theme(self) -> Theme:
        return PRESETS[self.theme].with_accent(hex_to_rgb(self.accent))

    # ---------------------------------------------------------------- files

    def to_dict(self) -> dict:
        return {"app": "galadyas_visionary", "schema": SCHEMA, "name": self.name, "format": self.format, "fps": self.fps,
                "theme": self.theme, "accent": self.accent, "transition": self.transition, "backdrop": self.backdrop, "audio": self.audio,
                "scenes": [{"id": s.id, "template": s.template, "duration": s.duration, "fields": s.fields}
                           for s in self.scenes]}

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)

    @classmethod
    def from_dict(cls, data: dict, base_dir: Path | None = None) -> "Project":
        if not isinstance(data, dict) or data.get("app") != "galadyas_visionary":
            raise ProjectError("This file is not a galadyas_visionary project.")
        if int(data.get("schema", 1)) > SCHEMA:
            raise ProjectError("This project was saved by a newer version of galadyas_visionary. Please update.")
        p = cls(base_dir=base_dir)
        p.name = str(data.get("name") or "Untitled")[:120]
        p.format = data.get("format") if data.get("format") in FORMATS else "landscape"
        p.fps = int(data["fps"]) if data.get("fps") in FPS_CHOICES else 30
        p.theme = data.get("theme") if data.get("theme") in PRESETS else DEFAULT_THEME
        p.accent = data.get("accent") if hex_to_rgb(data.get("accent") or "") else ""
        p.transition = _clamp(data.get("transition"), 0.0, 1.5, 0.6)
        p.backdrop = data.get("backdrop") if data.get("backdrop") in BACKDROPS else "glow"
        p.audio = str(data.get("audio") or "")
        for raw in data.get("scenes") or []:
            if not isinstance(raw, dict) or raw.get("template") not in TEMPLATES:
                continue  # skip scenes from templates this version does not know
            tpl = TEMPLATES[raw["template"]]
            given = raw.get("fields") if isinstance(raw.get("fields"), dict) else {}
            values = {f.key: str(given.get(f.key, f.default)) for f in tpl.fields}
            dur = _clamp(raw.get("duration"), MIN_SCENE, MAX_SCENE, tpl.duration)
            p.scenes.append(Scene(tpl.id, values, dur, str(raw.get("id") or uuid.uuid4().hex[:8])))
        return p

    @classmethod
    def load(cls, path) -> "Project":
        path = Path(path)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            raise ProjectError(f"The project file is damaged ({e.msg}, line {e.lineno}).") from None
        return cls.from_dict(data, path.resolve().parent)

    def save(self, path) -> Path:
        """Write atomically: a crash mid-save never leaves a half-written project."""
        path = Path(path)
        if path.suffix != EXTENSION:
            path = path.with_suffix(EXTENSION)
        self._rebase(path.resolve().parent)
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_text(self.to_json(), encoding="utf-8")
        os.replace(tmp, path)
        return path

    def _rebase(self, new_base: Path) -> None:
        """Keep media paths valid when the project moves: relative inside the project folder, else absolute."""
        def fix(value: str) -> str:
            if not value:
                return value
            p = Path(value)
            if not p.is_absolute() and self.base_dir:
                p = self.base_dir / p
            p = p.resolve()
            try:
                rel = os.path.relpath(p, new_base)
            except ValueError:  # another drive on Windows
                return str(p)
            return str(p) if rel.startswith("..") else rel.replace("\\", "/")

        for s in self.scenes:
            for f in TEMPLATES[s.template].fields:
                if f.kind == "image":
                    s.fields[f.key] = fix(s.fields.get(f.key, ""))
        self.audio = fix(self.audio)
        self.base_dir = new_base

    def resolve(self, value: str) -> Path | None:
        """Absolute path for a media field value, or None when it is empty or missing."""
        if not value:
            return None
        p = Path(value)
        if not p.is_absolute() and self.base_dir:
            p = self.base_dir / p
        return p if p.is_file() else None

    def video(self) -> Video:
        return build_video(self.to_json(), str(self.base_dir) if self.base_dir else "")


def build_video(project_json: str, base_dir: str = "") -> Video:
    """Build the Video for a project. Importable and picklable, so render workers can call it."""
    p = Project.from_dict(json.loads(project_json), Path(base_dir) if base_dir else None)
    theme = p.resolved_theme()
    clips = []
    n = len(p.scenes)
    for i, (scene, start) in enumerate(zip(p.scenes, p.starts())):
        tpl = TEMPLATES[scene.template]
        ctx = Context(theme, p.base_dir, scene.duration)
        clips.append(Clip(start, start + scene.duration, partial(_draw_scene, tpl.draw, scene.fields, ctx),
                          fade_in=p.transition if i else 0.0,
                          fade_out=p.transition if i < n - 1 else 0.8,
                          isolate=tpl.isolate))
    timeline = Timeline(*clips, background=partial(_background, theme, p.backdrop), foreground=partial(_finish, theme))
    return Video(timeline, duration=max(p.duration, 0.5), size=p.size, fps=p.fps, ssaa=2,
                 background=theme.bg_bottom, dither=2.0 if theme.dark else 1.0,
                 factory=(build_video, (project_json, base_dir)))


def _draw_scene(draw, fields, ctx, c: Canvas, t: float) -> None:
    draw(c, t, fields, ctx)


def _background(theme: Theme, backdrop: str, c: Canvas, t: float) -> None:
    """Theme gradient and two slow lights (painted at quarter resolution), plus stars or the galaxy."""
    from PIL import Image
    small = Canvas(c.w, c.h, scale=c.scale / 4)
    fx.vertical_gradient(small, theme.bg_top, theme.bg_bottom)
    r = max(c.w, c.h)
    fx.glow(small, (c.w * (0.5 + 0.13 * math.sin(t * 0.11)), c.h * (0.33 + 0.04 * math.cos(t * 0.08))),
            r * 0.47, theme.accent, theme.glow)
    fx.glow(small, (c.w * (0.8 - 0.08 * math.sin(t * 0.09)), c.h * 0.9), r * 0.4, theme.accent2, theme.glow * 0.6)
    c.img.paste(small.img.resize(c.img.size, Image.Resampling.BILINEAR))
    if backdrop in ("stars", "galaxy") and theme.dark:
        starfield(c, t)
    if backdrop == "galaxy":
        wide = c.w > c.h * 1.2
        galaxy(c, t, (c.w * (0.76 if wide else 0.5), c.h * (0.45 if wide else 0.30)), min(c.w, c.h) * 0.36,
               brightness=0.45 if theme.dark else 0.25)


def _finish(theme: Theme, c: Canvas, t: float) -> None:
    fx.vignette(c, theme.vignette)


def sample_project() -> Project:
    """The starter project shown on first launch."""
    p = Project(name="My product")
    for tid in ("title", "bullets", "features", "stats", "end"):
        p.scenes.append(Scene.new(tid))
    return p
