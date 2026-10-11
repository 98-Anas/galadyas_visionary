"""Launch demo for mindas_terminal (45 s, 1080p).

Uses Windows fonts (Cascadia Mono, Segoe UI); change F and the font helpers on other systems.

    uv run python examples/pillow/mindas_terminal_demo.py
"""

import math

from PIL import Image, ImageDraw, ImageFont

from mindas_scene import clamp, fade, mix, ramp, render

W, H, FPS, DUR = 1920, 1080, 30, 45.0
F = r"C:\Windows\Fonts\\"
mono = lambda s: ImageFont.truetype(F + "CascadiaMono.ttf", s)
sans = lambda s: ImageFont.truetype(F + "segoeui.ttf", s)
light = lambda s: ImageFont.truetype(F + "segoeuisl.ttf", s)
M22, M20, M18 = mono(22), mono(20), mono(18)

BG = (9, 11, 16); WIN = (15, 18, 25); BAR = (21, 25, 34); LINE = (36, 42, 56)
FG = (205, 214, 230); DIM = (98, 108, 130); ACC = (122, 162, 247); GRN = (158, 206, 106)
YEL = (224, 175, 104); MAG = (187, 154, 247)


def ctext(d, y, s, font, col):
    w = d.textlength(s, font=font); d.text(((W - w) / 2, y), s, font=font, fill=col)

PROMPT = [("anas@workstation", GRN), (" ~/projects/pipeline", ACC), (" (main)", MAG), (" $ ", FG)]

def prompt(d, x, y, font):
    for s, c in PROMPT:
        d.text((x, y), s, font=font, fill=c); x += d.textlength(s, font=font)
    return x

X0, Y0, X1, Y1 = 150, 90, 1770, 900  # window

def terminal(img, t):
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((X0, Y0, X1, Y1), 14, fill=WIN, outline=LINE, width=2)
    # tab bar
    d.rounded_rectangle((X0, Y0, X1, Y0 + 48), 14, fill=BAR); d.rectangle((X0, Y0 + 30, X1, Y0 + 48), fill=BAR)
    tx = X0 + 22
    for i, name in enumerate(["1  bash", "2  pwsh", "3  ubuntu (wsl)"]):
        w = d.textlength(name, font=M18) + 36
        if i == 0:
            d.rounded_rectangle((tx, Y0 + 8, tx + w, Y0 + 48), 8, fill=WIN)
            d.rectangle((tx, Y0 + 44, tx + w, Y0 + 46), fill=ACC)
        d.text((tx + 18, Y0 + 16), name, font=M18, fill=FG if i == 0 else DIM); tx += w + 6
    d.text((X1 - 190, Y0 + 16), "mindas_terminal", font=M18, fill=DIM)
    # status bar
    sy = Y1 - 44
    d.rectangle((X0 + 2, sy, X1 - 2, Y1 - 14), fill=BAR)
    prefix = 9.2 < t < 9.9 or 14.4 < t < 15.0
    mode, keys = ("PREFIX", "%  split right   \"  split down   t  tasks   g  toolkits   m  manual   :  palette") if prefix else \
                 ("NORMAL", "^B  prefix   ^B %  split   ^B t  tasks   ^B g  toolkits   ^B m  manual   ^Q  quit")
    mc = YEL if prefix else ACC
    mw = d.textlength(mode, font=M18) + 28
    d.rectangle((X0 + 2, sy, X0 + 2 + mw, Y1 - 14), fill=mc)
    d.text((X0 + 16, sy + 5), mode, font=M18, fill=BG)
    d.text((X0 + mw + 22, sy + 5), keys, font=M18, fill=DIM)
    d.rounded_rectangle((X0, Y0, X1, Y1), 14, outline=LINE, width=2)

    top, bot = Y0 + 64, sy - 10
    split = ramp(t, 9.9, 10.5)
    mid = X1 - (X1 - X0) * 0.5 * split
    # left pane: shell
    lx, ly, lh = X0 + 26, top + 6, 34
    x = prompt(d, lx, ly, M22)
    typed = "git status"
    n = int(clamp((t - 3.6) / 0.11, 0, 7))
    if t < 5.3:
        d.text((x, ly), typed[:n], font=M22, fill=FG)
        if n == 7:
            gx = x + d.textlength(typed[:7], font=M22)
            d.text((gx, ly), typed[7:], font=M22, fill=DIM)
            if t > 4.5:
                d.rounded_rectangle((gx - 4, ly + 34, gx + 330, ly + 70), 6, fill=BAR, outline=LINE)
                d.text((gx + 8, ly + 41), "\u2192 accept   from history", font=M18, fill=DIM)
        if int(t * 2) % 2 == 0 or n < 7:
            cx = x + d.textlength(typed[:n], font=M22); d.rectangle((cx, ly + 2, cx + 11, ly + 28), fill=FG)
    else:
        d.text((x, ly), typed, font=M22, fill=FG)
        out = [("On branch main", FG), ("Your branch is up to date with 'origin/main'.", FG), ("", FG),
               ("Changes not staged for commit:", FG), ("        modified:   etl/transform.py", (247, 118, 142)),
               ("        modified:   etl/schema.yaml", (247, 118, 142))]
        shown = int(clamp((t - 5.6) / 0.06, 0, len(out)))
        for i in range(shown):
            d.text((lx, ly + lh * (i + 1)), out[i][0], font=M22, fill=out[i][1])
        if shown == len(out):
            py = ly + lh * (len(out) + 2); px = prompt(d, lx, py, M22)
            if t < 10.5 and int(t * 2) % 2 == 0: d.rectangle((px, py + 2, px + 11, py + 28), fill=FG)
            # mistyped command, fixed with one key
            bad, good = "pyhton run.py", "python run.py"
            k = int(clamp((t - 21.2) / 0.07, 0, len(bad)))
            if t < 23.0:
                d.text((px, py), bad[:k], font=M22, fill=FG)
            else:
                d.text((px, py), bad, font=M22, fill=FG)
                d.text((lx, py + lh), "bash: pyhton: command not found", font=M22, fill=(247, 118, 142))
                hy = py + lh * 2 + 8
                d.rounded_rectangle((lx - 6, hy, lx + 640, hy + 40), 6, fill=BAR, outline=ACC if t < 24.4 else LINE)
                d.text((lx + 8, hy + 8), "did you mean  ", font=M18, fill=DIM)
                d.text((lx + 8 + d.textlength("did you mean  ", font=M18), hy + 8), good, font=M18, fill=GRN)
                d.text((lx + 470, hy + 8), "→ accept", font=M18, fill=DIM)
                if t > 24.4:
                    py2 = hy + 58; px2 = prompt(d, lx, py2, M22)
                    d.text((px2, py2), good, font=M22, fill=FG)
                    if t > 24.8: d.text((lx, py2 + lh), "running …", font=M22, fill=DIM)
    # right pane: task manager
    if split > 0:
        d.rectangle((mid, top - 8, X1 - 3, bot), fill=WIN)
        d.line((mid, top - 8, mid, bot), fill=ACC if t < 14.4 else LINE, width=2)
        a = ramp(t, 10.3, 10.8) if split > 0.99 else 0
        rx = mid + 28
        def T(xy, s, f, c): d.text(xy, s, font=f, fill=mix(WIN, c, a))
        T((rx, top + 6), "Task manager", M22, ACC)
        T((rx + 200, top + 9), "sort: CPU   only this terminal: on", M18, DIM)
        cols = [0, 110, 420, 540, 680]
        for c, h in zip(cols, ["PID", "NAME", "CPU %", "MEM", "GPU %"]):
            T((rx + c, top + 56), h, M18, DIM)
        if a > 0: d.line((rx, top + 86, X1 - 30, top + 86), fill=mix(WIN, LINE, a), width=1)
        rows = [(48213, "python  train.py", 92, "6.1 GB", 87), (48190, "python  etl/run.py", 41, "1.4 GB", 0),
                (47702, "jupyter-lab", 6, "412 MB", 0), (47655, "bash", 1, "9 MB", 0), (47640, "pwsh", 0, "86 MB", 0)]
        for i, (pid, name, cpu, mem, gpu) in enumerate(rows):
            j = 3 * math.sin(t * 3 + i) if cpu > 5 else 0
            yy = top + 100 + i * 40
            if i == 0 and a > 0: d.rectangle((rx - 10, yy - 6, X1 - 24, yy + 30), fill=mix(WIN, (30, 38, 58), a))
            T((rx, yy), str(pid), M20, FG); T((rx + 110, yy), name, M20, FG)
            T((rx + 420, yy), f"{cpu + j:5.1f}", M20, YEL if cpu > 50 else FG)
            T((rx + 540, yy), mem, M20, FG); T((rx + 680, yy), f"{gpu + (j if gpu else 0):5.1f}", M20, GRN if gpu else DIM)
            bw = 120 * (cpu + j) / 100
            if a > 0: d.rectangle((rx + 420, yy + 30, rx + 420 + bw, yy + 32), fill=mix(WIN, ACC, a * 0.6))
        T((rx, top + 330), "s sort   / filter   x terminate   K kill (with confirmation)", M18, DIM)
    # toolkit overlay
    o = fade(t, 15.0, 20.6, 0.35)
    if o > 0:
        ov = Image.new("RGBA", img.size, (0, 0, 0, 0)); od = ImageDraw.Draw(ov)
        od.rectangle((X0, Y0, X1, Y1), fill=(0, 0, 0, int(120 * o)))
        img.paste(Image.alpha_composite(img.convert("RGBA"), ov).convert("RGB"))
        d = ImageDraw.Draw(img)
        bx0, by0, bx1, by1 = 470, 230, 1450, 740
        dy = 14 * (1 - o)
        def C(c): return mix(WIN, c, o)
        d.rounded_rectangle((bx0, by0 + dy, bx1, by1 + dy), 12, fill=BAR, outline=C(ACC), width=2)
        d.text((bx0 + 30, by0 + 24 + dy), "Toolkits", font=M22, fill=C(ACC))
        d.text((bx0 + 160, by0 + 27 + dy), "profile: data-eng    109 commands \u00b7 11 fields \u00b7 offline", font=M18, fill=C(DIM))
        q = "parquet"[:int(clamp((t - 15.6) / 0.1, 0, 7))]
        d.rounded_rectangle((bx0 + 28, by0 + 70 + dy, bx1 - 28, by0 + 116 + dy), 6, fill=WIN, outline=C(LINE))
        d.text((bx0 + 46, by0 + 80 + dy), "\u203a " + q, font=M22, fill=C(FG))
        res = [("Parquet schema", "data engineering", "{file}"), ("CSV to Parquet", "data engineering", "{input} {output}"),
               ("Missing values per column", "data science", "{file}"), ("Run a SQL query on files", "data engineering", "{query}")]
        if len(q) >= 3:
            for i, (nm, field, ph) in enumerate(res):
                yy = by0 + 140 + i * 54 + dy
                sel = i == (1 if t > 18.0 else 0)
                if sel: d.rounded_rectangle((bx0 + 20, yy - 8, bx1 - 20, yy + 38), 6, fill=C((32, 40, 62)))
                d.text((bx0 + 46, yy), nm, font=M22, fill=C(FG if sel else (170, 178, 196)))
                d.text((bx0 + 470, yy + 3), ph, font=M18, fill=C(YEL))
                d.text((bx1 - 46 - d.textlength(field, font=M18), yy + 3), field, font=M18, fill=C(DIM))
        d.line((bx0 + 28, by1 - 66 + dy, bx1 - 28, by1 - 66 + dy), fill=C(LINE))
        d.text((bx0 + 46, by1 - 48 + dy), "enter  insert     placeholders are filled with safe quoting", font=M18, fill=C(DIM))

CAPS = [(3.4, 9.0, "Suggestions as you type, from your own history."),
        (10.3, 14.8, "Tabs, panes, and a task manager with GPU usage, side by side."),
        (15.4, 20.6, "A curated, offline command library for your field."),
        (21.0, 26.4, "Mistyped a command? One key fixes it.")]

KEYS = [(5.0, 5.9, ["\u2192"]), (9.1, 10.0, ["Ctrl", "B", "%"]), (10.2, 11.0, ["Ctrl", "B", "t"]),
        (14.3, 15.2, ["Ctrl", "B", "g"]), (18.2, 19.0, ["\u2193"]), (24.0, 24.9, ["\u2192"])]

def keypills(d, t):
    for s, e, ks in KEYS:
        a = fade(t, s, e, 0.15)
        if a <= 0: continue
        x = X1 - 30
        for k in reversed(ks):
            w = d.textlength(k, font=M20) + 30
            x -= w
            d.rounded_rectangle((x, Y1 - 112, x + w, Y1 - 68), 8, fill=mix(WIN, (40, 48, 68), a), outline=mix(WIN, ACC, a), width=2)
            d.text((x + 15, Y1 - 103), k, font=M20, fill=mix(WIN, FG, a))
            x -= 10

def bar(d, y, label, lo, hi, t0, t, col):
    p = ramp(t, t0, t0 + 1.6)
    X, Wd = 360, 1200
    d.text((X, y), label, font=light(34), fill=FG)
    d.rounded_rectangle((X, y + 60, X + Wd, y + 84), 12, fill=BAR)
    w = Wd * hi / 80000 * p
    if w > 24: d.rounded_rectangle((X, y + 60, X + w, y + 84), 12, fill=col)
    s = f"{int(lo * p):,} \u2013 {int(hi * p):,} lines/s"
    d.text((X + Wd - d.textlength(s, font=mono(30)), y + 6), s, font=mono(30), fill=col)

def frame(t):
    img = Image.new("RGB", (W, H), BG); d = ImageDraw.Draw(img)
    # opening
    a = fade(t, 0.0, 3.4, 0.7)
    if a > 0:
        ctext(d, 430 - 10 * (1 - a), "mindas_terminal", sans(96), mix(BG, FG, a))
        ctext(d, 570, "One terminal workspace, wherever you work.", light(40), mix(BG, DIM, a))
    # terminal
    ta = fade(t, 3.0, 27.0, 0.6)
    if ta > 0:
        layer = Image.new("RGB", (W, H), BG); terminal(layer, t)
        ld = ImageDraw.Draw(layer)
        keypills(ld, t)
        for s, e, txt in CAPS:
            c = fade(t, s, e, 0.4)
            if c > 0: ctext(ld, 950, txt, light(36), mix(BG, FG, c))
        img = Image.blend(img, layer, ta) if ta < 1 else layer
        d = ImageDraw.Draw(img)
    # throughput
    b = fade(t, 27.2, 33.0, 0.5)
    if b > 0:
        layer = Image.new("RGB", (W, H), BG); ld = ImageDraw.Draw(layer)
        ctext(ld, 190, "Fast where it counts.", sans(64), FG)
        ctext(ld, 290, "100,000 lines streamed through bash", light(34), DIM)
        bar(ld, 430, "Linux", 56000, 80000, 27.8, t, GRN)
        bar(ld, 600, "Windows (ConPTY)", 10000, 15500, 28.1, t, ACC)
        ctext(ld, 820, "Figures from the project's own benchmark. Results vary by machine.", light(26), DIM)
        img = Image.blend(img, layer, b); d = ImageDraw.Draw(img)
    # one prefix key
    k = fade(t, 33.2, 37.8, 0.5)
    if k > 0:
        layer = Image.new("RGB", (W, H), BG); ld = ImageDraw.Draw(layer)
        ctext(ld, 180, "Everything is one prefix away.", sans(60), FG)
        ctext(ld, 275, "Ctrl+B, then a single key. Keys for the current mode are always on screen.", light(32), DIM)
        items = [("%", "split pane"), ("t", "task manager"), ("g", "toolkits"),
                 ("[", "copy and search"), (":", "command palette"), ("m", "offline manual")]
        for i, (key, lab) in enumerate(items):
            c = ramp(t, 33.6 + i * 0.18, 34.0 + i * 0.18)
            cx = 330 + (i % 3) * 440; cy = 430 + (i // 3) * 190
            ld.rounded_rectangle((cx, cy, cx + 380, cy + 140), 14, fill=mix(BG, BAR, c), outline=mix(BG, LINE, c), width=2)
            ld.text((cx + 30, cy + 28), "Ctrl+B  " + key, font=mono(32), fill=mix(BG, ACC, c))
            ld.text((cx + 30, cy + 82), lab, font=light(30), fill=mix(BG, FG, c))
        img = Image.blend(img, layer, k); d = ImageDraw.Draw(img)
    # principles
    for i, s in enumerate(["No telemetry.", "No network connections.", "Windows and Linux. The same on both."]):
        c = fade(t, 38.0 + i * 0.6, 41.4, 0.5)
        if c > 0: ctext(d, 400 + i * 90, s, light(52), mix(BG, FG if i < 2 else ACC, c))
    # end card
    e = ramp(t, 41.6, 42.3) * (1 - ramp(t, DUR - 0.5, DUR))
    if e > 0:
        ctext(d, 420, "mindas_terminal", sans(92), mix(BG, FG, e))
        ctext(d, 560, "Open source  \u00b7  Pre-release  \u00b7  Feedback welcome", light(36), mix(BG, DIM, e))
    return img

if __name__ == "__main__":
    print(render(frame, "media/mindas_terminal_demo.mp4", duration=DUR, size=(W, H), fps=FPS))
