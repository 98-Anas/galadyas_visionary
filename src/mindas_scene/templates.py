"""Scene templates: ready-made, animated layouts filled in from a few fields.

Each template draws itself in proportion to the canvas, so one scene works in
16:9, 9:16 and 1:1. Text that is too long shrinks and wraps instead of
overflowing; malformed list lines are skipped instead of failing.
"""

import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from . import effects as fx
from .canvas import Canvas, Font
from .motion import ease_out_cubic, ease_out_expo, keyframes, mix, ramp, stagger
from .themes import BODY, DISPLAY, LABEL, Theme


@dataclass(frozen=True)
class Field:
    key: str
    label: str
    kind: str              # text | multiline | list | image
    default: str = ""
    help: str = ""


@dataclass
class Context:
    theme: Theme
    base_dir: Path | None = None
    duration: float = 5.0

    def resolve(self, path: str) -> Path | None:
        if not path:
            return None
        p = Path(path)
        if not p.is_absolute() and self.base_dir:
            p = self.base_dir / p
        return p if p.is_file() else None


@dataclass(frozen=True)
class Template:
    id: str
    name: str
    description: str
    fields: tuple[Field, ...]
    draw: Callable[[Canvas, float, dict, Context], None]
    duration: float = 5.0
    isolate: bool = False

    def defaults(self) -> dict:
        return {f.key: f.default for f in self.fields}

    def summary(self, values: dict) -> str:
        for f in self.fields:
            if f.kind in ("text", "multiline") and values.get(f.key, "").strip():
                return values[f.key].strip().splitlines()[0][:60]
        return self.name


# ---------------------------------------------------------------- layout helpers

def unit(c: Canvas) -> float:
    return min(c.w, c.h) / 1080


def margin(c: Canvas) -> float:
    return (150 if c.w > c.h * 1.2 else 96) * unit(c)


def fit(c: Canvas, text: str, kind: tuple, size: float, max_w: float, max_lines: int, min_size: float):
    """Largest font (down to min_size) at which `text` wraps into at most `max_lines` lines."""
    while True:
        f = Font(kind, size)
        lines = c.wrap(text, f, max_w) if text.strip() else []
        if len(lines) <= max_lines or size <= min_size:
            return f, lines[:max_lines] if size <= min_size else lines
        size *= 0.92


def lines_in(c, lines, x, y, font, color, t, start, ctx, lh, anchor="m", step=0.08, dur=0.8, rise=None):
    """Lines that rise and fade in one after another. Returns the y below the block."""
    rise = 18 * unit(c) if rise is None else rise
    for i, line in enumerate(lines):
        a = stagger(t, start, i, step, dur)
        if a > 0 and line:
            c.text((x, y + i * lh + rise * (1 - a)), line, font, mix(ctx.theme.bg_mid, color, a),
                   anchor=anchor + "a")
    return y + len(lines) * lh


def eyebrow(c, x, y, text, ctx, a, anchor="l"):
    """A small spaced-out label in the accent color."""
    if text.strip() and a > 0:
        u = unit(c)
        c.text((x, y), text.strip().upper(), Font(LABEL, 22 * u), mix(ctx.theme.bg_mid, ctx.theme.accent, a),
               anchor=anchor + "a", tracking=4 * u)


def rows(text: str, columns: int) -> list[list[str]]:
    """Parse one item per line, columns separated by '|'. Blank lines are ignored."""
    out = []
    for line in text.splitlines():
        if not line.strip():
            continue
        parts = [p.strip() for p in line.split("|")]
        out.append((parts + [""] * columns)[:columns])
    return out


_NUM = re.compile(r"^(?P<pre>[^\d\-]*)(?P<num>-?\d[\d,]*(?:\.\d+)?)(?P<post>.*)$")


def count_up(value: str, k: float) -> str:
    """'12,500+' at k=0.5 -> '6,250+'. Text without a number is returned unchanged."""
    m = _NUM.match(value.strip())
    if not m:
        return value
    raw = m["num"].replace(",", "")
    try:
        n = float(raw)
    except ValueError:
        return value
    decimals = len(raw.split(".")[1]) if "." in raw else 0
    shown = n * k
    body = f"{shown:,.{decimals}f}" if "," in m["num"] else f"{shown:.{decimals}f}"
    return f"{m['pre']}{body}{m['post']}"


def number(value: str) -> float | None:
    m = _NUM.match(value.strip())
    try:
        return float(m["num"].replace(",", "")) if m else None
    except ValueError:
        return None


def placeholder(c, box, text, ctx):
    th = ctx.theme
    c.rect(box, fill=th.surface, outline=th.line, width=1.5, radius=18 * unit(c))
    c.text(((box[0] + box[2]) / 2, (box[1] + box[3]) / 2), text, Font(BODY, 26 * unit(c)), th.muted, anchor="mm")


# ---------------------------------------------------------------- templates

def draw_title(c, t, f, ctx):
    th, u, m = ctx.theme, unit(c), margin(c)
    max_w = c.w - 2 * m
    logo = ctx.resolve(f["logo"])
    tf, tlines = fit(c, f["title"], DISPLAY, 116 * u, max_w, 2, 56 * u)
    sf, slines = fit(c, f["subtitle"], DISPLAY, 40 * u, max_w * 0.85, 3, 26 * u)
    tlh, slh = tf.size * 1.15, sf.size * 1.4
    h = (150 * u if logo else 0) + (60 * u if f["eyebrow"].strip() else 0) + len(tlines) * tlh \
        + (40 * u + len(slines) * slh if slines else 0)
    y = (c.h - h) / 2
    cx = c.w / 2
    if logo:
        a = ramp(t, 0.1, 0.9, ease_out_cubic)
        layer = c.layer()
        layer.image(logo, (cx - 55 * u, y + 14 * u * (1 - a), cx + 55 * u, y + 110 * u + 14 * u * (1 - a)))
        c.composite(layer, a)
        y += 150 * u
    if f["eyebrow"].strip():
        eyebrow(c, cx, y, f["eyebrow"], ctx, ramp(t, 0.3, 1.0), anchor="m")
        y += 60 * u
    a = ramp(t, 0.4, 1.4)
    for i, line in enumerate(tlines):
        track = (26 * (1 - ramp(t, 0.4, 2.2, ease_out_expo)) + 0.5) * u if len(tlines) == 1 else 0
        c.text((cx, y + i * tlh), line, tf, mix(th.bg_mid, th.text, a), anchor="ma", tracking=track)
    y += len(tlines) * tlh + 40 * u
    lines_in(c, slines, cx, y, sf, th.muted, t, 1.2, ctx, slh)


def draw_statement(c, t, f, ctx):
    th, u, m = ctx.theme, unit(c), margin(c)
    max_w = min(c.w - 2 * m, 1500 * u)
    qf, qlines = fit(c, f["text"], DISPLAY, 72 * u, max_w, 5, 36 * u)
    lh = qf.size * 1.3
    h = 50 * u + len(qlines) * lh + (70 * u if f["attribution"].strip() else 0)
    y = (c.h - h) / 2
    x = (c.w - max_w) / 2
    a = ramp(t, 0.1, 0.8, ease_out_cubic)
    c.rect((x, y, x + 64 * u * a, y + 4 * u), fill=th.accent)
    y = lines_in(c, qlines, x, y + 50 * u, qf, th.text, t, 0.3, ctx, lh, anchor="l", step=0.12)
    if f["attribution"].strip():
        c.text((x, y + 36 * u), f["attribution"].strip(), Font(BODY, 28 * u),
               mix(th.bg_mid, th.muted, ramp(t, 0.9 + 0.12 * len(qlines), 1.6 + 0.12 * len(qlines))))


def draw_bullets(c, t, f, ctx):
    th, u, m = ctx.theme, unit(c), margin(c)
    items = [r[0] for r in rows(f["items"], 1)][:7]
    max_w = c.w - 2 * m
    hf, hlines = fit(c, f["heading"], DISPLAY, 68 * u, max_w, 2, 40 * u)
    body = Font(DISPLAY, (40 if c.w >= c.h else 36) * u)
    wrapped = [c.wrap(it, body, max_w - 60 * u)[:3] for it in items]
    gap = 34 * u
    lh = body.size * 1.35
    h = (50 * u if f["eyebrow"].strip() else 0) + len(hlines) * hf.size * 1.2 + 60 * u \
        + sum(len(w) * lh + gap for w in wrapped)
    y = max(m * 0.6, (c.h - h) / 2)
    if f["eyebrow"].strip():
        eyebrow(c, m, y, f["eyebrow"], ctx, ramp(t, 0.1, 0.7))
        y += 50 * u
    y = lines_in(c, hlines, m, y, hf, th.text, t, 0.2, ctx, hf.size * 1.2, anchor="l") + 60 * u
    for i, lines in enumerate(wrapped):
        a = stagger(t, 0.8, i, 0.22, 0.7)
        if a > 0:
            r = 7 * u
            cy = y + body.size * 0.62
            c.ellipse((m + 6 * u - r, cy - r, m + 6 * u + r, cy + r), fill=mix(th.bg_mid, th.accent, a))
            for j, line in enumerate(lines):
                c.text((m + 50 * u + 20 * u * (1 - a), y + j * lh), line, body, mix(th.bg_mid, th.text, a))
        y += len(lines) * lh + gap


def _grid_cols(c, n):
    if c.h > c.w * 1.2:
        return 1
    if c.w > c.h * 1.2:
        return min(3, n) if n != 4 else 2
    return min(2, n)


def draw_features(c, t, f, ctx):
    th, u, m = ctx.theme, unit(c), margin(c)
    items = [r for r in rows(f["items"], 2) if r[0]][:6]
    max_w = c.w - 2 * m
    hf, hlines = fit(c, f["heading"], DISPLAY, 64 * u, max_w, 2, 40 * u)
    sf, slines = fit(c, f["subheading"], DISPLAY, 30 * u, max_w, 2, 22 * u)
    cx = c.w / 2
    cols = _grid_cols(c, max(1, len(items)))
    nrows = math.ceil(len(items) / cols) if items else 0
    gap = 36 * u
    cw = (max_w - gap * (cols - 1)) / cols
    head_h = len(hlines) * hf.size * 1.2 + 16 * u + len(slines) * sf.size * 1.35 + 56 * u
    ch = min(260 * u, (c.h - 1.6 * m - head_h - gap * max(0, nrows - 1)) / max(1, nrows))
    y = max(m * 0.8, (c.h - head_h - nrows * ch - gap * max(0, nrows - 1)) / 2)
    y = lines_in(c, hlines, cx, y, hf, th.text, t, 0.1, ctx, hf.size * 1.2)
    y = lines_in(c, slines, cx, y + 16 * u, sf, th.muted, t, 0.4, ctx, sf.size * 1.35, step=0.05) + 56 * u
    if not items:
        return
    title_f, desc_f = Font(LABEL, 34 * u), Font(BODY, 27 * u)
    for i, (title, desc) in enumerate(items):
        a = stagger(t, 0.7, i, 0.1, 0.7)
        if a <= 0:
            continue
        in_row = min(cols, len(items) - (i // cols) * cols)  # center a short last row
        x0 = m + (max_w - in_row * cw - (in_row - 1) * gap) / 2 + (i % cols) * (cw + gap)
        y0 = y + (i // cols) * (ch + gap) + 26 * u * (1 - a)
        card = c.layer()
        fx.shadow(card, (x0, y0, x0 + cw, y0 + ch), radius=18 * u, blur=30 * u, opacity=0.35 if th.dark else 0.12,
                  offset=(0, 14 * u))
        card.rect((x0, y0, x0 + cw, y0 + ch), fill=th.surface, outline=th.line, width=1.5, radius=18 * u)
        pad = 32 * u
        card.text((x0 + pad, y0 + pad), f"{i + 1:02d}", Font(LABEL, 20 * u), th.accent, tracking=2 * u)
        card.text((x0 + pad, y0 + pad + 40 * u), title, title_f, th.text)
        top_desc = 100 * u
        dl = desc_f.size * 1.45
        room = max(1, int((ch - pad * 2 - top_desc) // dl) + 1)
        for j, line in enumerate(card.wrap(desc, desc_f, cw - 2 * pad)[:room]):
            card.text((x0 + pad, y0 + pad + top_desc + j * dl), line, desc_f, th.muted)
        c.composite(card, a)


def draw_stats(c, t, f, ctx):
    th, u, m = ctx.theme, unit(c), margin(c)
    items = [r for r in rows(f["items"], 2) if r[0]][:6]
    max_w = c.w - 2 * m
    hf, hlines = fit(c, f["heading"], DISPLAY, 64 * u, max_w, 2, 40 * u)
    cx = c.w / 2
    portrait = c.h > c.w * 1.2
    cols = 1 if portrait else min(len(items), 3 if c.w > c.h * 1.2 else 2) or 1
    nrows = math.ceil(len(items) / cols) if items else 0
    tile_h = 230 * u
    block = len(hlines) * hf.size * 1.2 + 90 * u + nrows * tile_h
    y = max(m * 0.7, (c.h - block) / 2)
    y = lines_in(c, hlines, cx, y, hf, th.text, t, 0.1, ctx, hf.size * 1.2) + 90 * u
    cw = max_w / cols
    vf_size = (110 if cols <= 2 else 96) * u
    for i, (value, label) in enumerate(items):
        a = stagger(t, 0.5, i, 0.15, 0.7)
        if a <= 0:
            continue
        k = ramp(t, 0.6 + i * 0.15, 2.4 + i * 0.15, ease_out_expo)
        in_row = min(cols, len(items) - (i // cols) * cols)  # center a short last row
        tx = m + (max_w - in_row * cw) / 2 + (i % cols) * cw + cw / 2
        ty = y + (i // cols) * tile_h + 16 * u * (1 - a)
        vf, _ = fit(c, value, DISPLAY, vf_size, cw - 40 * u, 1, 40 * u)
        c.text((tx, ty), count_up(value, k), vf, mix(th.bg_mid, th.text, a), anchor="ma")
        c.rect((tx - 28 * u * a, ty + vf.size * 1.32, tx + 28 * u * a, ty + vf.size * 1.32 + 3 * u), fill=th.accent)
        lf, llines = fit(c, label, BODY, 28 * u, cw - 40 * u, 2, 20 * u)
        for j, line in enumerate(llines):
            c.text((tx, ty + vf.size * 1.32 + 28 * u + j * lf.size * 1.3), line, lf, mix(th.bg_mid, th.muted, a),
                   anchor="ma")


def draw_chart(c, t, f, ctx):
    th, u, m = ctx.theme, unit(c), margin(c)
    data = [(label, value, number(value)) for label, value in rows(f["items"], 2) if label]
    data = [d for d in data if d[2] is not None and d[2] >= 0][:8]
    max_w = c.w - 2 * m
    hf, hlines = fit(c, f["heading"], DISPLAY, 64 * u, max_w, 2, 40 * u)
    sf, slines = fit(c, f["subheading"], DISPLAY, 30 * u, max_w, 2, 22 * u)
    cx = c.w / 2
    row_h = min(150 * u, (c.h * 0.5) / max(1, len(data)))
    block = len(hlines) * hf.size * 1.2 + len(slines) * sf.size * 1.35 + 80 * u + len(data) * row_h + 90 * u
    y = max(m * 0.7, (c.h - block) / 2)
    y = lines_in(c, hlines, cx, y, hf, th.text, t, 0.1, ctx, hf.size * 1.2)
    y = lines_in(c, slines, cx, y + 12 * u, sf, th.muted, t, 0.4, ctx, sf.size * 1.35, step=0.04) + 80 * u
    top = max((d[2] for d in data), default=0) or 1
    unit_text = f["unit"].strip()
    lf = Font(BODY, min(32 * u, row_h * 0.3))
    for i, (label, value, n) in enumerate(data):
        a = ramp(t, 0.6 + i * 0.15, 1.2 + i * 0.15)
        p = ramp(t, 0.8 + i * 0.15, 2.6 + i * 0.15, ease_out_expo)
        ry = y + i * row_h
        bar_h = max(8 * u, row_h * 0.14)
        c.text((m, ry), label, lf, mix(th.bg_mid, th.text, a))
        shown = count_up(value, p) + (f" {unit_text}" if unit_text else "")
        c.text((m + max_w, ry), shown, Font(LABEL, lf.size), mix(th.bg_mid, th.accent, a), anchor="ra")
        by = ry + lf.size * 1.5
        c.rect((m, by, m + max_w, by + bar_h), fill=mix(th.bg_mid, th.line, a), radius=bar_h / 2)
        w = max_w * (n / top) * p
        if w > bar_h:
            fx.gradient_rect(c, (m, by, m + w, by + bar_h), mix(th.bg_mid, th.accent2, 0.7), th.accent,
                             radius=bar_h / 2)
    if f["footnote"].strip():
        c.text((cx, y + len(data) * row_h + 40 * u), f["footnote"].strip(), Font(BODY, 22 * u),
               mix(th.bg_mid, th.muted, ramp(t, 1.4, 2.2)), anchor="ma")


def draw_showcase(c, t, f, ctx):
    th, u, m = ctx.theme, unit(c), margin(c)
    max_w = c.w - 2 * m
    hf, hlines = fit(c, f["heading"], DISPLAY, 60 * u, max_w, 2, 36 * u)
    sf, slines = fit(c, f["caption"], DISPLAY, 30 * u, max_w, 2, 22 * u)
    cx = c.w / 2
    y = lines_in(c, hlines, cx, m * 0.7, hf, th.text, t, 0.1, ctx, hf.size * 1.2)
    y = lines_in(c, slines, cx, y + 12 * u, sf, th.muted, t, 0.35, ctx, sf.size * 1.35, step=0.04) + 56 * u
    box = (m, y, c.w - m, c.h - m * 0.7)
    a = ramp(t, 0.5, 1.3, ease_out_cubic)
    layer = c.layer()
    img = ctx.resolve(f["image"])
    lift = 30 * u * (1 - a)
    shifted = (box[0], box[1] + lift, box[2], box[3] + lift)
    if img:
        drawn = layer.image(img, shifted, radius=16 * u)
        if drawn:
            under = c.layer()
            fx.shadow(under, drawn, radius=16 * u, blur=50 * u, opacity=0.5 if th.dark else 0.18, offset=(0, 24 * u))
            under.composite(layer)
            layer = under
            zoom = keyframes(t, [(0.5, 1.0), (ctx.duration, 1.04)], easing=lambda x: x)
            fx.camera(layer, zoom, ((drawn[0] + drawn[2]) / 2, (drawn[1] + drawn[3]) / 2))
    else:
        placeholder(layer, shifted, "Add an image or screenshot", ctx)
    c.composite(layer, a)


def draw_end(c, t, f, ctx):
    th, u, m = ctx.theme, unit(c), margin(c)
    max_w = c.w - 2 * m
    logo = ctx.resolve(f["logo"])
    tf, tlines = fit(c, f["title"], DISPLAY, 100 * u, max_w, 2, 48 * u)
    gf, glines = fit(c, f["tagline"], DISPLAY, 36 * u, max_w, 2, 24 * u)
    cta = f["call_to_action"].strip()
    h = (150 * u if logo else 0) + len(tlines) * tf.size * 1.15 + 36 * u + len(glines) * gf.size * 1.4 \
        + (100 * u if cta else 0)
    y = (c.h - h) / 2
    cx = c.w / 2
    if logo:
        a = ramp(t, 0.1, 0.9, ease_out_cubic)
        layer = c.layer()
        layer.image(logo, (cx - 55 * u, y + 14 * u * (1 - a), cx + 55 * u, y + 110 * u + 14 * u * (1 - a)))
        c.composite(layer, a)
        y += 150 * u
    a = ramp(t, 0.3, 1.2)
    for i, line in enumerate(tlines):
        track = (18 * (1 - ramp(t, 0.3, 2.0, ease_out_expo)) + 0.5) * u if len(tlines) == 1 else 0
        c.text((cx, y + i * tf.size * 1.15), line, tf, mix(th.bg_mid, th.text, a), anchor="ma", tracking=track)
    y += len(tlines) * tf.size * 1.15 + 36 * u
    y = lines_in(c, glines, cx, y, gf, th.muted, t, 0.9, ctx, gf.size * 1.4)
    if cta:
        a = ramp(t, 1.4, 2.1, ease_out_cubic)
        cf = Font(LABEL, 26 * u)
        w = c.textlength(cta, cf) + 64 * u
        by = y + 44 * u + 10 * u * (1 - a)
        c.rect((cx - w / 2, by, cx + w / 2, by + 62 * u), outline=mix(th.bg_mid, th.accent, a), width=1.5,
               radius=31 * u)
        c.text((cx, by + 31 * u), cta, cf, mix(th.bg_mid, th.text, a), anchor="mm")


LIST_HELP = "One item per line."
PAIR_HELP = "One item per line: {} | {}"

TEMPLATES: dict[str, Template] = {tpl.id: tpl for tpl in [
    Template("title", "Title", "Opening title with optional logo and subtitle.", (
        Field("logo", "Logo", "image"),
        Field("eyebrow", "Label", "text", "Introducing"),
        Field("title", "Title", "text", "Your product"),
        Field("subtitle", "Subtitle", "multiline", "One sentence that says why it matters."),
    ), draw_title, 5.0),
    Template("statement", "Statement", "A single message or quote, set large.", (
        Field("text", "Statement", "multiline", "Great products deserve a clear story."),
        Field("attribution", "Attribution", "text", ""),
    ), draw_statement, 5.0),
    Template("bullets", "Key points", "A heading with points that appear one by one.", (
        Field("eyebrow", "Label", "text", "Why it matters"),
        Field("heading", "Heading", "text", "Built for the way you work"),
        Field("items", "Points", "list", "Fast to start\nSimple to use\nReady to share", LIST_HELP),
    ), draw_bullets, 6.0),
    Template("features", "Feature grid", "Up to six cards with a title and description.", (
        Field("heading", "Heading", "text", "Everything in one place"),
        Field("subheading", "Subheading", "text", "The essentials, designed to work together."),
        Field("items", "Features", "list",
              "Fast | Results in seconds, not hours.\nSimple | Clear choices and sensible defaults.\n"
              "Reliable | Tested on every release.", PAIR_HELP.format("Title", "Description")),
    ), draw_features, 6.0),
    Template("stats", "Key numbers", "Large figures that count up, with labels.", (
        Field("heading", "Heading", "text", "Results that speak for themselves"),
        Field("items", "Numbers", "list", "12,000+ | active users\n98% | satisfaction\n24/7 | availability",
              PAIR_HELP.format("Value", "Label")),
    ), draw_stats, 5.5),
    Template("chart", "Bar chart", "Compare values with animated bars; good for reports.", (
        Field("heading", "Heading", "text", "Growth by quarter"),
        Field("subheading", "Subheading", "text", "Revenue, in thousands"),
        Field("items", "Bars", "list", "Q1 | 120\nQ2 | 180\nQ3 | 260\nQ4 | 340", PAIR_HELP.format("Label", "Value")),
        Field("unit", "Unit", "text", ""),
        Field("footnote", "Footnote", "text", ""),
    ), draw_chart, 6.0),
    Template("showcase", "Showcase", "A screenshot or product image with a slow camera push.", (
        Field("heading", "Heading", "text", "See it in action"),
        Field("caption", "Caption", "text", ""),
        Field("image", "Image", "image"),
    ), draw_showcase, 6.0, isolate=True),
    Template("end", "End card", "Closing title, tagline and call to action.", (
        Field("logo", "Logo", "image"),
        Field("title", "Title", "text", "Your product"),
        Field("tagline", "Tagline", "text", "Available now."),
        Field("call_to_action", "Call to action", "text", "Learn more"),
    ), draw_end, 4.5),
]}
