"""mindas_terminal launch film: 30 s, 1080p, 2x supersampled.

    uv run mindas-scene render examples/mindas_terminal/launch.py -o examples/mindas_terminal/mindas_terminal_launch.mp4
    uv run mindas-scene still examples/mindas_terminal/launch.py 7 13 18 24 30 36 44

Every figure on screen comes from the mindas_terminal README. Uses the fonts
bundled with mindas_scene, so it renders the same on every OS.
"""

import math

from PIL import Image

from mindas_scene import (Canvas, Clip, Font, Timeline, Video, clamp, ease_out_cubic, ease_out_expo, fade, keyframes,
                          linear, mix, ramp, stagger)
from mindas_scene import effects as fx

W, H = 1920, 1080

# palette
BG_TOP, BG_BOT, BG_MID = (13, 15, 25), (5, 6, 10), (9, 11, 17)
WIN, BAR, LINE, KEY = (15, 18, 26), (21, 25, 35), (38, 44, 60), (28, 33, 46)
FG, SOFT, DIM = (220, 226, 240), (152, 162, 186), (98, 108, 132)
ACC, VIO, GRN, YEL, RED = (122, 162, 247), (187, 154, 247), (158, 206, 106), (224, 175, 104), (247, 118, 142)

MONO = ("JetBrainsMono-Regular.ttf",)
LIGHT = ("Inter-Light.ttf",)
SEMI = ("Inter-SemiBold.ttf",)
M22, M20, M18 = Font(MONO, 22), Font(MONO, 20), Font(MONO, 18)


# ---------------------------------------------------------------- shared pieces

def background(c: Canvas, t: float) -> None:
    """Deep gradient with two slow drifting lights, painted at quarter resolution."""
    small = Canvas(W, H, scale=c.scale / 4)
    fx.vertical_gradient(small, BG_TOP, BG_BOT)
    fx.glow(small, (960 + 260 * math.sin(t * 0.11), 360 + 50 * math.cos(t * 0.08)), 900, ACC, 0.17)
    fx.glow(small, (1560 - 160 * math.sin(t * 0.09), 980), 760, VIO, 0.10)
    c.img.paste(small.img.resize(c.img.size, Image.Resampling.BILINEAR))


def finish(c: Canvas, t: float) -> None:
    fx.vignette(c, 0.55)


def words(c, cx, y, text, font, color, t, start, step=0.06, dur=0.8, rise=16, tracking=0):
    """Centered text that arrives word by word, each rising into place."""
    parts = text.split(" ")
    space = c.textlength(" ", font)
    widths = [c.textlength(p, font, tracking) for p in parts]
    x = cx - (sum(widths) + space * (len(parts) - 1)) / 2
    for i, (p, w) in enumerate(zip(parts, widths)):
        a = stagger(t, start, i, step, dur)
        if a > 0:
            c.text((x, y + rise * (1 - a)), p, font, mix(BG_MID, color, a), tracking=tracking)
        x += w + space


def mark(c, cx, cy, size, a):
    """The mindas_terminal glyph: a prompt inside a rounded square."""
    r = size / 2
    lift = 14 * (1 - a)
    c.rect((cx - r, cy - r + lift, cx + r, cy + r + lift), outline=mix(BG_MID, ACC, a), width=2, radius=size * 0.24)
    c.text((cx, cy + lift + 2), "›_", Font(MONO, size * 0.42), mix(BG_MID, ACC, a), anchor="mm")


def keycap(c, x, y, label, a, font=M20):
    w = c.textlength(label, font) + 28
    c.rect((x, y, x + w, y + 40), fill=mix(BG_MID, KEY, a), outline=mix(BG_MID, LINE, a), width=1.5, radius=8)
    c.text((x + w / 2, y + 20), label, font, mix(BG_MID, FG, a), anchor="mm")
    return w


# ---------------------------------------------------------------- 1. opening

def opening(c, t):
    mark(c, 960, 330, 104, ramp(t, 0.2, 1.1, ease_out_cubic))
    a = ramp(t, 0.6, 1.6)
    track = 30 * (1 - ramp(t, 0.6, 2.4, ease_out_expo)) + 1
    c.text((960, 470), "mindas_terminal", Font(LIGHT, 108), mix(BG_MID, FG, a), anchor="mt", tracking=track)
    words(c, 960, 625, "One terminal workspace, wherever you work.", Font(LIGHT, 38), SOFT, t, 1.5)


# ---------------------------------------------------------------- 2. the terminal

T0 = 3.8                              # the terminal choreography below is written from 3.8 s to 27.4 s
START = 2.6                           # where the terminal clip now starts in the 30 s cut
# Time remap (film time -> choreography time): plays each beat faster, idle holds fastest.
REMAP = [(2.6, 3.8), (3.6, 4.8), (6.4, 9.3), (9.8, 14.6), (13.4, 21.0), (17.4, 27.4)]
X0, Y0, X1, Y1 = 150, 92, 1770, 892   # window
PROMPT = [("anas@workstation", GRN), (" ~/projects/pipeline", ACC), (" (main)", VIO), (" $ ", FG)]

# camera: (time, (zoom, focus x, focus y))
HOME = (0.94, 960, 600)  # slightly pulled back and lifted, leaving room for captions
CAM = [(3.8, HOME), (5.0, HOME), (6.0, (1.14, 700, 380)), (8.8, (1.14, 700, 380)), (9.8, HOME),
       (10.9, HOME), (11.8, (1.1, 1260, 470)), (14.2, (1.1, 1260, 470)), (15.1, HOME),
       (20.8, HOME), (21.6, (1.14, 720, 560)), (25.6, (1.14, 720, 560)), (27.0, (0.98, 960, 580))]

CAPTIONS = [(4.9, 9.8, "01", "AUTOCOMPLETE", "Suggestions as you type, drawn from your own history."),
            (10.5, 15.0, "02", "PANES AND TASKS", "Split the view. Watch CPU, memory and GPU beside your work."),
            (15.4, 20.9, "03", "TOOLKITS", "A curated, offline command library for your field."),
            (21.3, 26.6, "04", "SMART HINTS", "Mistyped a command? One key fixes it.")]

KEYS = [(5.6, 6.6, ["→"]), (9.4, 10.3, ["Ctrl", "B", "%"]), (10.6, 11.5, ["Ctrl", "B", "t"]),
        (14.6, 15.5, ["Ctrl", "B", "g"]), (18.3, 19.1, ["↓"]), (23.9, 24.8, ["→"])]


def prompt(c, x, y, f=M22):
    for s, col in PROMPT:
        c.text((x, y), s, f, col)
        x += c.textlength(s, f)
    return x


def window(c, T):
    c.rect((X0, Y0, X1, Y1), fill=WIN, radius=16)
    c.rect((X0, Y0, X1, Y0 + 50), fill=BAR, radius=16)
    c.rect((X0, Y0 + 30, X1, Y0 + 50), fill=BAR)
    tx = X0 + 22
    for i, name in enumerate(["1  bash", "2  pwsh", "3  ubuntu (wsl)"]):
        w = c.textlength(name, M18) + 36
        if i == 0:
            c.rect((tx, Y0 + 9, tx + w, Y0 + 50), fill=WIN, radius=8)
            c.rect((tx + 10, Y0 + 46, tx + w - 10, Y0 + 48), fill=ACC)
        c.text((tx + 18, Y0 + 17), name, M18, FG if i == 0 else DIM)
        tx += w + 6
    c.text((X1 - 24, Y0 + 17), "mindas_terminal", M18, DIM, anchor="ra")

    # status bar: keys for the current mode
    sy = Y1 - 46
    c.rect((X0 + 1, sy, X1 - 1, Y1 - 16), fill=BAR)
    prefix = 9.4 < T < 10.0 or 14.6 < T < 15.2
    mode, keys = (("PREFIX", "%  split right    \"  split down    t  tasks    g  toolkits    m  manual    :  palette")
                  if prefix else
                  ("NORMAL", "^B  prefix    ^B %  split    ^B t  tasks    ^B g  toolkits    ^B m  manual    ^Q  quit"))
    mw = c.textlength(mode, M18) + 28
    c.rect((X0 + 1, sy, X0 + 1 + mw, Y1 - 16), fill=YEL if prefix else ACC)
    c.text((X0 + 15, sy + 15), mode, M18, BG_BOT, anchor="lm")
    c.text((X0 + mw + 22, sy + 15), keys, M18, DIM, anchor="lm")
    c.rect((X0, Y0, X1, Y1), outline=LINE, width=1.5, radius=16)
    c.line((X0 + 16, Y0 + 1, X1 - 16, Y0 + 1), fill=(54, 62, 84), width=1)  # top highlight

    top = Y0 + 66
    split = ramp(T, 10.0, 10.6, ease_out_cubic)
    mid = X1 - (X1 - X0) * 0.5 * split
    shell_pane(c, T, X0 + 26, top + 6)
    if split > 0:
        task_pane(c, T, mid, top, sy - 10, split)
    toolkit_overlay(c, T)


def shell_pane(c, T, lx, ly, lh=34):
    x = prompt(c, lx, ly)
    typed = "git status"
    n = int(clamp((T - 4.9) / 0.1, 0, 7))
    blink = int(T * 2) % 2 == 0
    if T < 5.9:
        c.text((x, ly), typed[:n], M22, FG)
        cx = x + c.textlength(typed[:n], M22)
        if n == 7:
            c.text((cx, ly), typed[7:], M22, DIM)
            if T > 5.2:
                c.rect((cx - 4, ly + 36, cx + 300, ly + 72), fill=BAR, outline=LINE, radius=6)
                c.text((cx + 10, ly + 54), "→ accept   from history", M18, DIM, anchor="lm")
        if blink or n < 7:
            c.rect((cx, ly + 2, cx + 11, ly + 28), fill=FG)
        return
    c.text((x, ly), typed, M22, FG)
    out = [("On branch main", FG), ("Your branch is up to date with 'origin/main'.", FG), ("", FG),
           ("Changes not staged for commit:", FG), ("        modified:   etl/transform.py", RED),
           ("        modified:   etl/schema.yaml", RED)]
    shown = int(clamp((T - 6.1) / 0.05, 0, len(out)))
    for i in range(shown):
        c.text((lx, ly + lh * (i + 1)), out[i][0], M22, out[i][1])
    if shown < len(out):
        return
    py = ly + lh * (len(out) + 2)
    px = prompt(c, lx, py)
    bad, good = "pyhton run.py", "python run.py"
    k = int(clamp((T - 21.8) / 0.08, 0, len(bad)))
    c.text((px, py), bad[:k], M22, FG)
    if T < 23.3:
        if blink or 0 < k < len(bad):
            cx = px + c.textlength(bad[:k], M22)
            c.rect((cx, py + 2, cx + 11, py + 28), fill=FG)
        return
    c.text((lx, py + lh), "bash: pyhton: command not found", M22, RED)
    hy = py + lh * 2 + 10
    on = T < 24.3
    c.rect((lx - 8, hy, lx + 560, hy + 42), fill=BAR, outline=ACC if on else LINE, width=1.5, radius=8)
    c.text((lx + 8, hy + 21), "did you mean", M18, DIM, anchor="lm")
    c.text((lx + 160, hy + 21), good, M18, GRN, anchor="lm")
    c.text((lx + 545, hy + 21), "→ accept", M18, DIM, anchor="rm")
    if not on:
        py2 = hy + 62
        px2 = prompt(c, lx, py2)
        c.text((px2, py2), good, M22, FG)
        if T > 24.7:
            dots = "." * (1 + int(T * 3) % 3)
            c.text((lx, py2 + lh), "running" + dots, M22, DIM)


def task_pane(c, T, mid, top, bot, split):
    c.rect((mid, top - 8, X1 - 2, bot), fill=WIN)
    c.line((mid, top - 8, mid, bot), fill=ACC if T < 14.6 else LINE, width=1.5)
    if split < 1:
        return
    a = ramp(T, 10.7, 11.3)
    col = lambda k: mix(WIN, k, a)
    rx = mid + 28
    c.text((rx, top + 6), "Task manager", M22, col(ACC))
    c.text((rx + 200, top + 9), "sort: CPU   only this terminal: on", M18, col(DIM))
    cols = [0, 110, 420, 540, 680]
    for x, h in zip(cols, ["PID", "NAME", "CPU %", "MEM", "GPU %"]):
        c.text((rx + x, top + 56), h, M18, col(DIM))
    c.line((rx, top + 86, X1 - 30, top + 86), fill=col(LINE))
    rows = [(48213, "python  train.py", 92, "6.1 GB", 87), (48190, "python  etl/run.py", 41, "1.4 GB", 0),
            (47702, "jupyter-lab", 6, "412 MB", 0), (47655, "bash", 1, "9 MB", 0), (47640, "pwsh", 0, "86 MB", 0)]
    for i, (pid, name, cpu, mem, gpu) in enumerate(rows):
        j = 3 * math.sin(T * 2.6 + i * 1.7) if cpu > 5 else 0
        r = stagger(T, 10.9, i, 0.07, 0.5)
        yy = top + 100 + i * 42 + 8 * (1 - r)
        rc = lambda k: mix(WIN, k, a * r)
        if i == 0:
            c.rect((rx - 12, yy - 7, X1 - 22, yy + 33), fill=rc((30, 38, 60)), radius=6)
        c.text((rx, yy), str(pid), M20, rc(FG))
        c.text((rx + 110, yy), name, M20, rc(FG))
        c.text((rx + 420, yy), f"{cpu + j:5.1f}", M20, rc(YEL if cpu > 50 else FG))
        c.text((rx + 540, yy), mem, M20, rc(FG))
        c.text((rx + 680, yy), f"{gpu + (j if gpu else 0):5.1f}", M20, rc(GRN if gpu else DIM))
        if cpu:
            c.rect((rx + 420, yy + 30, rx + 420 + 110 * (cpu + j) / 100, yy + 32), fill=rc((70, 96, 160)))
    c.text((rx, top + 340), "s sort   / filter   x terminate   K kill (with confirmation)", M18, col(DIM))


def toolkit_overlay(c, T):
    o = fade(T, 15.2, 21.0, 0.4)
    if o <= 0:
        return
    dim = c.layer()
    dim.rect((X0, Y0, X1, Y1), fill=(4, 5, 8), radius=16)
    c.composite(dim, 0.55 * o)
    box = c.layer()
    dy = 18 * (1 - ease_out_cubic(o))
    bx0, by0, bx1, by1 = 470, 228 + dy, 1450, 738 + dy
    fx.shadow(box, (bx0, by0, bx1, by1), radius=14, blur=40, opacity=0.6, offset=(0, 18))
    box.rect((bx0, by0, bx1, by1), fill=BAR, outline=(70, 96, 160), width=1.5, radius=14)
    box.text((bx0 + 30, by0 + 26), "Toolkits", M22, ACC)
    box.text((bx0 + 160, by0 + 29), "profile: data-eng    109 commands · 11 fields · offline", M18, DIM)
    q = "parquet"[:int(clamp((T - 15.8) / 0.1, 0, 7))]
    box.rect((bx0 + 28, by0 + 72, bx1 - 28, by0 + 118), fill=WIN, outline=LINE, radius=8)
    box.text((bx0 + 46, by0 + 95), "› " + q, M22, FG, anchor="lm")
    results = [("Parquet schema", "{file}", "data engineering"), ("CSV to Parquet", "{input} {output}", "data engineering"),
               ("Missing values per column", "{file}", "data science"), ("Run a SQL query on files", "{query}", "data engineering")]
    if len(q) >= 3:
        sel = 1 if T > 18.6 else 0
        for i, (name, ph, field) in enumerate(results):
            r = stagger(T, 16.1, i, 0.06, 0.4)
            yy = by0 + 142 + i * 54 + 6 * (1 - r)
            if i == sel:
                box.rect((bx0 + 20, yy - 9, bx1 - 20, yy + 37), fill=mix(BAR, (34, 44, 70), r), radius=8)
            box.text((bx0 + 46, yy), name, M22, mix(BAR, FG if i == sel else SOFT, r))
            box.text((bx0 + 470, yy + 3), ph, M18, mix(BAR, YEL, r))
            box.text((bx1 - 46, yy + 3), field, M18, mix(BAR, DIM, r), anchor="ra")
    box.line((bx0 + 28, by1 - 66, bx1 - 28, by1 - 66), fill=LINE)
    box.text((bx0 + 46, by1 - 36), "enter  insert      placeholders are filled with safe quoting", M18, DIM, anchor="lm")
    c.composite(box, o)


def caption(c, T):
    for s, e, num, label, text in CAPTIONS:
        a = fade(T, s, e, 0.45)
        if a <= 0:
            continue
        c.text((X0, 930), num, Font(SEMI, 17), mix(BG_MID, ACC, a), tracking=2)
        c.rect((X0 + 36, 939, X0 + 36 + 28 * a, 940.5), fill=mix(BG_MID, ACC, a))
        c.text((X0 + 76, 930), label, Font(SEMI, 17), mix(BG_MID, SOFT, a), tracking=3)
        k = ramp(T, s, s + 0.6, ease_out_cubic) * (1 - ramp(T, e - 0.45, e))
        c.text((X0, 966 + 10 * (1 - k)), text, Font(LIGHT, 36), mix(BG_MID, FG, k))


def keypills(c, T):
    for s, e, ks in KEYS:
        a = fade(T, s, e, 0.15)
        if a <= 0:
            continue
        x = X1
        for k in reversed(ks):
            x -= c.textlength(k, M20) + 28
        for k in ks:
            x += keycap(c, x, 960, k, a) + 8


def terminal(c, u):
    T = keyframes(u + START, REMAP, easing=linear)
    zoom, fxx, fyy = keyframes(T, CAM)
    rise = 46 * (1 - ramp(T, T0, T0 + 1.4, ease_out_cubic))
    win = c.layer()
    fx.shadow(win, (X0, Y0, X1, Y1), radius=16, blur=60, opacity=0.7, offset=(0, 30))
    window(win, T)
    fx.camera(win, zoom, (fxx, fyy - rise / zoom))
    c.composite(win)
    band = clamp((zoom - 0.95) / 0.15)  # only needed while the camera pushes in
    if band > 0:
        fx.scrim(c, 760, 900, BG_BOT, 0.96 * band)
        dark = c.layer()
        dark.rect((0, 900, W, H), fill=BG_BOT)
        c.composite(dark, 0.96 * band)
    caption(c, T)
    keypills(c, T)


# ---------------------------------------------------------------- 3. speed

def speed(c, t):
    words(c, 960, 190, "Fast where it counts.", Font(LIGHT, 66), FG, t, 0.2)
    words(c, 960, 292, "100,000 lines streamed through bash", Font(LIGHT, 32), SOFT, t, 0.6, step=0.04)
    for i, (label, lo, hi, col, dark) in enumerate([("Linux", 56000, 80000, GRN, (52, 84, 46)),
                                                    ("Windows (ConPTY)", 10000, 15500, ACC, (40, 58, 110))]):
        y = 430 + i * 170
        a = ramp(t, 0.8 + i * 0.25, 1.4 + i * 0.25)
        p = ramp(t, 1.1 + i * 0.25, 2.9 + i * 0.25, ease_out_expo)
        c.text((360, y), label, Font(LIGHT, 34), mix(BG_MID, FG, a))
        c.text((1560, y + 4), f"{int(lo * p):,} – {int(hi * p):,} lines/s", Font(MONO, 30),
               mix(BG_MID, col, a), anchor="ra")
        c.rect((360, y + 62, 1560, y + 82), fill=mix(BG_MID, (22, 26, 38), a), radius=10)
        if p > 0.02:
            fx.gradient_rect(c, (360, y + 62, 360 + 1200 * hi / 80000 * p, y + 82), dark, col, radius=10)
    words(c, 960, 820, "Figures from the project's own benchmark. Results vary by machine.",
          Font(LIGHT, 25), DIM, t, 1.6, step=0.02)


# ---------------------------------------------------------------- 4. one prefix

def prefix(c, t):
    words(c, 960, 170, "Everything is one prefix away.", Font(LIGHT, 62), FG, t, 0.2)
    words(c, 960, 272, "Ctrl+B, then a single key. The keys for each mode stay on screen.",
          Font(LIGHT, 30), SOFT, t, 0.5, step=0.03)
    items = [("%", "split pane"), ("t", "task manager"), ("g", "toolkits"),
             ("[", "copy and search"), (":", "command palette"), ("m", "offline manual")]
    for i, (key, label) in enumerate(items):
        a = stagger(t, 0.9, i, 0.1, 0.7)
        if a <= 0:
            continue
        x, y = 330 + (i % 3) * 440, 410 + (i // 3) * 200 + 24 * (1 - a)
        card = c.layer()
        fx.shadow(card, (x, y, x + 380, y + 150), radius=16, blur=30, opacity=0.55, offset=(0, 16))
        card.rect((x, y, x + 380, y + 150), fill=BAR, outline=LINE, width=1.5, radius=16)
        kx = x + 30
        kx += keycap(card, kx, y + 30, "Ctrl", 1) + 8
        kx += keycap(card, kx, y + 30, "B", 1) + 18
        keycap(card, kx, y + 30, key, 1)
        card.text((x + 30, y + 92), label, Font(LIGHT, 30), FG)
        c.composite(card, a)


# ---------------------------------------------------------------- 5. principles, 6. end

def ending(c, t):
    mark(c, 960, 330, 96, ramp(t, 0.1, 0.9, ease_out_cubic))
    a = ramp(t, 0.3, 1.2)
    track = 18 * (1 - ramp(t, 0.3, 1.9, ease_out_expo)) + 1
    c.text((960, 440), "mindas_terminal", Font(LIGHT, 96), mix(BG_MID, FG, a), anchor="mt", tracking=track)
    words(c, 960, 580, "No telemetry.  No network connections.  The same on Windows and Linux.", Font(LIGHT, 32),
          SOFT, t, 0.9, step=0.05)
    k = ramp(t, 1.8, 2.5, ease_out_cubic)
    label = "Open source  ·  Pre-release  ·  Feedback welcome"
    lf = Font(SEMI, 22)
    w = c.textlength(label, lf, 1.5) + 64
    y = 668 + 10 * (1 - k)
    c.rect((960 - w / 2, y, 960 + w / 2, y + 56), outline=mix(BG_MID, ACC, k), width=1.5, radius=28)
    c.text((960, y + 28), label, lf, mix(BG_MID, FG, k), anchor="mm", tracking=1.5)


timeline = Timeline(
    Clip(0.0, 3.0, lambda c, t: opening(c, t * 1.3), fade_in=0, fade_out=0.6),
    Clip(START, 17.6, terminal, fade_in=0.5, fade_out=0.7),
    Clip(17.4, 21.8, speed),
    Clip(21.6, 25.6, prefix),
    Clip(25.4, 30.0, ending, fade_out=0.9),
    background=background,
    foreground=finish,
)

video = Video(timeline, size=(W, H), fps=30, ssaa=2)

if __name__ == "__main__":
    print(video.render("examples/mindas_terminal/mindas_terminal_launch.mp4"))
