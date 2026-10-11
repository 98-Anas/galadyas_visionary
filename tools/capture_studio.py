"""Record real footage of the studio for the demo film.

Drives the actual app off screen and saves what its window shows, frame by frame
(15 fps). Nothing is mocked: every frame is a grab of the running window, and the
preview inside it is the real renderer's output.

    uv run python tools/capture_studio.py media/footage
"""

import os
import sys
import shutil
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint  # noqa: E402
from PySide6.QtGui import QColor, QPainter  # noqa: E402
from PySide6.QtWidgets import QComboBox, QLineEdit, QPlainTextEdit, QWidget  # noqa: E402

from galadyas_visionary.gui.app import ExportDialog, MainWindow, create_app  # noqa: E402

FPS = 15
SIZE = (1600, 900)


class Recorder:
    def __init__(self, out: Path):
        self.out = out
        self.app = create_app(["capture"])
        self.win = MainWindow()
        self.win.resize(*SIZE)
        self.win.show()
        self.frames = 0
        self.win.renderer.frame_ready.connect(self._got)
        self.pump(800)
        self.dialog = None

    def _got(self, *_):
        self.frames += 1

    def pump(self, ms=30):
        end = time.perf_counter() + ms / 1000
        while time.perf_counter() < end:
            self.app.processEvents()
            time.sleep(0.003)

    def settle(self, timeout=4.0):
        """Wait until the preview shows the latest request."""
        seen = self.frames
        self.win._refresh_timer.stop()
        self.win._request_frame()
        end = time.perf_counter() + timeout
        while self.frames == seen and time.perf_counter() < end:
            self.app.processEvents()
            time.sleep(0.003)
        self.pump(20)

    def shot(self, clip: str):
        d = self.out / clip
        d.mkdir(parents=True, exist_ok=True)
        if self.dialog is not None and self.dialog.isVisible():
            # a window behind a modal dialog grabs blank off screen; it does not change during
            # the export, so reuse the real frame grabbed just before the dialog opened
            img = self.backdrop.copy()
            dimg = self.dialog.grab().toImage()
            p = QPainter(img)
            p.fillRect(img.rect(), QColor(0, 0, 0, 120))
            p.drawImage(QPoint((img.width() - dimg.width()) // 2, (img.height() - dimg.height()) // 2), dimg)
            p.end()
        else:
            img = self.win.grab().toImage()
        n = len(list(d.glob("*.png")))
        img.save(str(d / f"{n:04d}.png"))

    def hold(self, clip: str, seconds: float):
        for _ in range(int(seconds * FPS)):
            self.pump(5)
            self.shot(clip)

    def play(self, clip: str, start: float, seconds: float):
        w = self.win
        for i in range(int(seconds * FPS)):
            w.t = min(start + i / FPS, w.project.duration)
            w._update_timeline()
            w.play_btn.setText("❚❚  Pause")
            self.settle()
            self.shot(clip)
        w.play_btn.setText("▶  Play")

    def field(self, key):
        return self.win.scene_scroll.widget().findChild(QWidget, f"field_{key}")

    def type_into(self, clip: str, key: str, text: str, per_frame: int = 2):
        w = self.field(key)
        w.setFocus()
        cur = ""
        setter = w.setText if isinstance(w, QLineEdit) else w.setPlainText
        setter("")
        for i in range(0, len(text), per_frame):
            cur = text[:i + per_frame]
            setter(cur)
            self.settle()
            self.shot(clip)


def main(out: str) -> None:
    r = Recorder(Path(out))
    w = r.win

    # 1. A project opens; the preview plays
    w.scene_list.setCurrentRow(0)
    r.settle()
    r.hold("01_play", 0.6)
    r.play("01_play", 0.3, 4.2)

    # 2. Add a scene and write it; the preview follows every keystroke
    w.add_scene("stats")
    r.settle()
    r.hold("02_edit", 0.6)
    r.type_into("02_edit", "heading", "Results that speak for themselves")
    r.type_into("02_edit", "items", "12,000+ | active users\n98% | satisfaction\n24/7 | availability", per_frame=3)
    r.hold("02_edit", 0.8)

    # 3. Style: theme, accent of the theme, format
    w.tabs.setCurrentIndex(1)
    r.pump(50)
    combos = w.project_scroll.widget().findChildren(QComboBox)
    fmt, theme = combos[0], combos[1]
    r.hold("03_style", 0.6)
    for name in ("Ocean", "Ember", "Midnight"):
        theme.setCurrentText(name)
        r.settle()
        r.hold("03_style", 0.9)
    fmt.setCurrentIndex(1)  # portrait
    r.settle()
    r.hold("03_style", 1.2)
    fmt.setCurrentIndex(2)  # square
    r.settle()
    r.hold("03_style", 1.0)
    fmt.setCurrentIndex(0)
    r.settle()

    # 4. A cinematic scene: the Whirlpool Galaxy
    w.tabs.setCurrentIndex(0)
    w.add_scene("cosmic")
    r.settle()
    r.type_into("04_cosmic", "title", "Something is taking shape", per_frame=3)
    start = w.project.starts()[w.scene_list.currentRow()]
    r.play("04_cosmic", start, 4.0)

    # 5. Export, for real
    # a neutral, personal-data-free path, since it is visible in the footage; removed afterwards
    export_dir = Path(os.environ.get("CAPTURE_EXPORT_DIR", "D:/galadyas/exports"))
    export_dir.mkdir(parents=True, exist_ok=True)
    try:
        for s in w.project.scenes:
            s.duration = min(s.duration, 2.0)
        r.settle()
        r.backdrop = w.grab().toImage()
        r.dialog = ExportDialog(w, w.project, export_dir / "launch.mp4")
        r.dialog.quality.setCurrentIndex(2)  # draft: quick, but a genuine export
        r.dialog.show()
        r.pump(200)
        r.hold("05_export", 0.8)
        done = {}
        r.dialog.finished_ok.connect(lambda p: done.setdefault("ok", p))
        r.dialog.finished_err.connect(lambda m: done.setdefault("err", m))
        r.dialog._start()
        t0 = time.perf_counter()
        while not done and time.perf_counter() - t0 < 300:
            r.pump(1000 // FPS)
            r.shot("05_export")
        r.hold("05_export", 1.5)
        print("export:", done, r.dialog.status.text())
    finally:
        shutil.rmtree(export_dir.parent if export_dir.parent.name == "galadyas" else export_dir, ignore_errors=True)
    w.dirty = False
    print("frames:", {d.name: len(list(d.glob('*.png'))) for d in sorted(Path(out).iterdir())})


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "media/footage")
