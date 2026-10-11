"""mindas_scene Studio: build a video from templates, preview it live, export to MP4."""

import multiprocessing
import os
import sys
import threading
import time
import traceback
from pathlib import Path

from PySide6.QtCore import QObject, QSettings, QSize, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import (QAction, QColor, QDesktopServices, QFont, QFontDatabase, QImage, QKeySequence, QPainter,
                           QPainterPath, QPixmap, QShortcut)
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QColorDialog, QComboBox, QDialog, QDoubleSpinBox,
                               QFileDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem,
                               QMainWindow, QMenu, QMessageBox, QPlainTextEdit, QProgressBar, QPushButton, QScrollArea,
                               QSizePolicy, QSlider, QSplitter, QTabWidget, QToolButton, QVBoxLayout, QWidget)

from .. import __version__
from ..canvas import BUNDLED_FONTS
from ..project import EXTENSION, FORMATS, FPS_CHOICES, MAX_SCENE, MIN_SCENE, Project, ProjectError, Scene, \
    sample_project
from ..render import Cancelled
from ..templates import TEMPLATES
from ..themes import PRESETS
from . import style

APP = "mindas_scene Studio"
FILTER = f"mindas_scene project (*{EXTENSION})"


# ================================================================ preview rendering

class PreviewRenderer(QObject):
    """Renders preview frames on a background thread. Only the newest request is kept,
    so the UI never queues up stale work while the user types or scrubs."""

    frame_ready = Signal(QImage, float)
    failed = Signal(str)

    def __init__(self):
        super().__init__()
        self._lock = threading.Lock()
        self._wake = threading.Event()
        self._pending = None
        self._key = None
        self._video = None
        self._alive = True
        threading.Thread(target=self._loop, name="preview", daemon=True).start()

    def request(self, project_json: str, base_dir: str, t: float, scale: float):
        with self._lock:
            self._pending = (project_json, base_dir, t, scale)
        self._wake.set()

    def stop(self):
        self._alive = False
        self._wake.set()

    def _loop(self):
        from ..project import build_video
        while self._alive:
            self._wake.wait()
            self._wake.clear()
            with self._lock:
                job, self._pending = self._pending, None
            if not job or not self._alive:
                continue
            project_json, base_dir, t, scale = job
            try:
                if (project_json, base_dir) != self._key:
                    self._video = build_video(project_json, base_dir)
                    self._key = (project_json, base_dir)
                img = self._video.preview(t, scale)
                qimg = QImage(img.tobytes(), img.width, img.height, 3 * img.width, QImage.Format.Format_RGB888).copy()
                self.frame_ready.emit(qimg, t)
            except Exception as e:  # keep the preview alive whatever a template does
                self.failed.emit(f"{type(e).__name__}: {e}")


class PreviewView(QWidget):
    """Shows the current frame, letterboxed, with rounded corners."""

    def __init__(self):
        super().__init__()
        self._pixmap: QPixmap | None = None
        self._aspect = 16 / 9
        self.setMinimumSize(320, 200)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def set_aspect(self, w: int, h: int):
        self._aspect = w / h
        self.update()

    def set_frame(self, img: QImage):
        self._pixmap = QPixmap.fromImage(img)
        self.update()

    def target(self):
        w, h = self.width() - 32, self.height() - 32
        if w / max(h, 1) > self._aspect:
            w = int(h * self._aspect)
        else:
            h = int(w / self._aspect)
        return (self.width() - w) // 2, (self.height() - h) // 2, w, h

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        x, y, w, h = self.target()
        path = QPainterPath()
        path.addRoundedRect(x, y, w, h, 10, 10)
        p.setClipPath(path)
        if self._pixmap:
            p.drawPixmap(x, y, w, h, self._pixmap)
        else:
            p.fillRect(x, y, w, h, QColor(style.PANEL))


# ================================================================ small widgets

class ColorButton(QPushButton):
    changed = Signal(str)

    def __init__(self, value: str = "", placeholder: str = "Theme default"):
        super().__init__()
        self._placeholder = placeholder
        self.set_value(value)
        self.clicked.connect(self._pick)

    def set_value(self, value: str):
        self._value = value
        self.setText(value or self._placeholder)
        swatch = value or style.BORDER
        self.setStyleSheet(f"QPushButton {{ border-left: 14px solid {swatch}; text-align: left; padding-left: 10px; }}")

    def _pick(self):
        c = QColorDialog.getColor(QColor(self._value or style.ACCENT), self, "Accent color")
        if c.isValid():
            self.set_value(c.name())
            self.changed.emit(c.name())


class FilePicker(QWidget):
    changed = Signal(str)

    def __init__(self, value: str, caption: str, filter_: str, base_dir_fn):
        super().__init__()
        self._caption, self._filter, self._base_dir_fn = caption, filter_, base_dir_fn
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.edit = QLineEdit(value)
        self.edit.setPlaceholderText("None")
        self.edit.setReadOnly(True)
        browse = QPushButton("Choose…")
        clear = QToolButton()
        clear.setText("✕")
        clear.setObjectName("flat")
        clear.setToolTip("Remove")
        lay.addWidget(self.edit, 1)
        lay.addWidget(browse)
        lay.addWidget(clear)
        browse.clicked.connect(self._browse)
        clear.clicked.connect(lambda: self._set(""))

    def _browse(self):
        start = str(self._base_dir_fn() or Path.home())
        path, _ = QFileDialog.getOpenFileName(self, self._caption, start, self._filter)
        if path:
            self._set(path)

    def _set(self, value: str):
        self.edit.setText(value)
        self.changed.emit(value)


def section(text: str) -> QLabel:
    lab = QLabel(text.upper())
    lab.setObjectName("section")
    return lab


def hint(text: str) -> QLabel:
    lab = QLabel(text)
    lab.setObjectName("hint")
    lab.setWordWrap(True)
    return lab


# ================================================================ export

class ExportDialog(QDialog):
    progressed = Signal(int, int)
    finished_ok = Signal(str)
    finished_err = Signal(str)

    QUALITIES = [("High: 2× supersampled, smoothest edges", "high"),
                 ("Standard: faster, very good", "standard"),
                 ("Draft: quick check, 15 fps", "draft")]

    def __init__(self, parent, project: Project, default_path: Path):
        super().__init__(parent)
        self.setWindowTitle("Export video")
        self.setMinimumWidth(560)
        self.project = project
        self._cancel = threading.Event()
        self._started = 0.0
        self._running = False

        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 24, 24, 20)
        lay.setSpacing(14)
        title = QLabel("Export video")
        title.setObjectName("heading")
        w, h = project.size
        lay.addWidget(title)
        lay.addWidget(hint(f"{FORMATS[project.format][0]} · {w}×{h} · {project.fps} fps · "
                           f"{project.duration:.1f} s · MP4 (H.264)"))

        form = QFormLayout()
        form.setSpacing(10)
        row = QHBoxLayout()
        self.path = QLineEdit(str(default_path))
        browse = QPushButton("Choose…")
        browse.clicked.connect(self._browse)
        row.addWidget(self.path, 1)
        row.addWidget(browse)
        form.addRow("Save to", row)
        self.quality = QComboBox()
        for label, key in self.QUALITIES:
            self.quality.addItem(label, key)
        form.addRow("Quality", self.quality)
        lay.addLayout(form)

        self.bar = QProgressBar()
        self.bar.setTextVisible(False)
        self.bar.setRange(0, 1)
        self.bar.setValue(0)
        self.status = hint("")
        lay.addWidget(self.bar)
        lay.addWidget(self.status)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        self.open_btn = QPushButton("Show in folder")
        self.open_btn.hide()
        self.open_btn.clicked.connect(self._show)
        self.close_btn = QPushButton("Close")
        self.close_btn.clicked.connect(self._close_or_cancel)
        self.go = QPushButton("Export")
        self.go.setObjectName("primary")
        self.go.clicked.connect(self._start)
        buttons.addWidget(self.open_btn)
        buttons.addWidget(self.close_btn)
        buttons.addWidget(self.go)
        lay.addLayout(buttons)

        self.progressed.connect(self._on_progress)
        self.finished_ok.connect(self._on_done)
        self.finished_err.connect(self._on_error)

    def _browse(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save video", self.path.text(), "MP4 video (*.mp4)")
        if path:
            self.path.setText(path if path.lower().endswith(".mp4") else path + ".mp4")

    def _start(self):
        out = Path(self.path.text().strip())
        if out.suffix.lower() != ".mp4":
            out = out.with_suffix(".mp4")
            self.path.setText(str(out))
        if not out.parent.exists():
            QMessageBox.warning(self, "Export", f"The folder does not exist:\n{out.parent}")
            return
        if out.exists() and QMessageBox.question(self, "Export", f"{out.name} exists. Replace it?") \
                != QMessageBox.StandardButton.Yes:
            return
        self._cancel.clear()
        self._running = True
        self._started = time.perf_counter()
        self.go.setEnabled(False)
        self.open_btn.hide()
        self.close_btn.setText("Cancel")
        self.quality.setEnabled(False)
        self.path.setEnabled(False)
        self.status.setText("Starting…")
        quality = self.quality.currentData()
        video = self.project.video()
        audio = self.project.resolve(self.project.audio)

        def work():
            try:
                video.render(out, quality=quality, audio=audio, progress=self.progressed.emit, cancel=self._cancel)
                self.finished_ok.emit(str(out))
            except Cancelled:
                self.finished_err.emit("")
            except Exception as e:
                self.finished_err.emit(f"{type(e).__name__}: {e}")

        threading.Thread(target=work, name="export", daemon=True).start()

    def _on_progress(self, done, total):
        self.bar.setRange(0, total)
        self.bar.setValue(done)
        elapsed = time.perf_counter() - self._started
        left = elapsed / done * (total - done) if done else 0
        self.status.setText(f"Frame {done} of {total} · about {int(left) + 1} s left")

    def _finish(self):
        self._running = False
        self.go.setEnabled(True)
        self.quality.setEnabled(True)
        self.path.setEnabled(True)
        self.close_btn.setText("Close")

    def _on_done(self, path):
        self._finish()
        self.status.setText(f"Done in {time.perf_counter() - self._started:.0f} s · {Path(path).name}")
        self.open_btn.show()

    def _on_error(self, message):
        self._finish()
        self.bar.setValue(0)
        if message:
            self.status.setText("Export failed.")
            QMessageBox.critical(self, "Export failed", message)
        else:
            self.status.setText("Export cancelled.")

    def _show(self):
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(self.path.text()).parent)))

    def _close_or_cancel(self):
        if self._running:
            self._cancel.set()
            self.status.setText("Cancelling…")
        else:
            self.accept()

    def reject(self):
        if self._running:
            self._cancel.set()
            return
        super().reject()


# ================================================================ main window

class MainWindow(QMainWindow):
    def __init__(self, path: str | None = None):
        super().__init__()
        self.settings = QSettings("mindas", "mindas_scene")
        self.project = sample_project()
        self.path: Path | None = None
        self.dirty = False
        self.t = 0.0
        self.playing = False
        self._play_origin = (0.0, 0.0)
        self._building_form = False

        self.renderer = PreviewRenderer()
        self.renderer.frame_ready.connect(self._on_frame)
        self.renderer.failed.connect(lambda msg: self.statusBar().showMessage(f"Preview problem: {msg}", 8000))

        self._refresh_timer = QTimer(self, singleShot=True, interval=40, timeout=self._request_frame)
        self._play_timer = QTimer(self, interval=16, timeout=self._tick)

        self._build_ui()
        self._build_actions()
        self.resize(QSize(1440, 860))
        if path:
            self.open_path(Path(path))
        else:
            self._load_project(self.project, None)

    # ---------------------------------------------------------------- layout

    def _build_ui(self):
        root = QSplitter()
        root.setHandleWidth(10)
        root.setContentsMargins(10, 0, 10, 10)

        # scenes
        left = QWidget(objectName="panel")
        ll = QVBoxLayout(left)
        ll.setContentsMargins(12, 14, 12, 12)
        head = QHBoxLayout()
        title = QLabel("Scenes", objectName="heading")
        self.add_btn = QToolButton(text="+  Add")
        self.add_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        menu = QMenu(self)
        for tpl in TEMPLATES.values():
            act = menu.addAction(tpl.name)
            act.setToolTip(tpl.description)
            act.triggered.connect(lambda _=False, tid=tpl.id: self.add_scene(tid))
        menu.setToolTipsVisible(True)
        self.add_btn.setMenu(menu)
        head.addWidget(title)
        head.addStretch(1)
        head.addWidget(self.add_btn)
        ll.addLayout(head)
        self.scene_list = QListWidget()
        self.scene_list.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.scene_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scene_list.setTextElideMode(Qt.TextElideMode.ElideRight)
        self.scene_list.currentRowChanged.connect(self._on_select)
        self.scene_list.model().rowsMoved.connect(self._on_reorder)
        ll.addWidget(self.scene_list, 1)
        row = QHBoxLayout()
        for text, tip, fn in [("↑", "Move up", lambda: self.move_scene(-1)), ("↓", "Move down", lambda: self.move_scene(1)),
                              ("Duplicate", "Duplicate scene", self.duplicate_scene), ("Delete", "Delete scene",
                                                                                       self.delete_scene)]:
            b = QToolButton(text=text, toolTip=tip, objectName="flat")
            b.clicked.connect(fn)
            row.addWidget(b)
        row.addStretch(1)
        ll.addLayout(row)
        left.setMinimumWidth(240)

        # preview
        center = QWidget(objectName="panel")
        cl = QVBoxLayout(center)
        cl.setContentsMargins(8, 8, 8, 12)
        self.view = PreviewView()
        cl.addWidget(self.view, 1)
        transport = QHBoxLayout()
        transport.setContentsMargins(12, 0, 12, 0)
        self.play_btn = QPushButton("▶  Play")
        self.play_btn.setFixedWidth(96)
        self.play_btn.clicked.connect(self.toggle_play)
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.valueChanged.connect(self._on_scrub)
        self.time_label = QLabel("0:00.0 / 0:00.0", objectName="muted")
        self.time_label.setMinimumWidth(130)
        self.time_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        transport.addWidget(self.play_btn)
        transport.addWidget(self.slider, 1)
        transport.addWidget(self.time_label)
        cl.addLayout(transport)

        # inspector
        right = QWidget(objectName="panel")
        rl = QVBoxLayout(right)
        rl.setContentsMargins(6, 6, 6, 6)
        self.tabs = QTabWidget()
        self.scene_scroll = QScrollArea(widgetResizable=True)
        self.project_scroll = QScrollArea(widgetResizable=True)
        self.tabs.addTab(self.scene_scroll, "Scene")
        self.tabs.addTab(self.project_scroll, "Project")
        rl.addWidget(self.tabs)
        right.setMinimumWidth(340)

        root.addWidget(left)
        root.addWidget(center)
        root.addWidget(right)
        root.setStretchFactor(1, 1)
        root.setSizes([270, 820, 370])
        self.setCentralWidget(root)
        self.statusBar().showMessage("Ready")

    def _build_actions(self):
        tb = self.addToolBar("Main")
        tb.setMovable(False)
        brand = QLabel("  mindas_scene  ", objectName="heading")
        tb.addWidget(brand)

        def act(text, shortcut, fn, tip=""):
            a = QAction(text, self)
            if shortcut:
                a.setShortcut(shortcut)
            a.setToolTip(f"{tip or text} ({QKeySequence(shortcut).toString()})" if shortcut else tip or text)
            a.triggered.connect(fn)
            tb.addAction(a)
            return a

        act("New", QKeySequence.StandardKey.New, self.new_project)
        act("Open", QKeySequence.StandardKey.Open, self.open_dialog)
        act("Save", QKeySequence.StandardKey.Save, self.save)
        act("Save as", QKeySequence.StandardKey.SaveAs, self.save_as)
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        tb.addWidget(spacer)
        export = QPushButton("Export video", objectName="primary")
        export.setToolTip("Export to MP4 (Ctrl+E)")
        export.clicked.connect(self.export)
        tb.addWidget(export)
        QShortcut(QKeySequence("Ctrl+E"), self, self.export)
        QShortcut(QKeySequence("Space"), self, self._space)
        QShortcut(QKeySequence("Home"), self, lambda: self.seek(0))
        QShortcut(QKeySequence("End"), self, lambda: self.seek(self.project.duration))

    # ---------------------------------------------------------------- project state

    def _load_project(self, project: Project, path: Path | None):
        self.stop()
        self.project, self.path = project, path
        self.view.set_aspect(*project.size)
        self._refresh_list(0 if project.scenes else -1)
        self._build_project_form()
        self.dirty = False
        self._update_title()
        self._update_timeline()
        self.seek(min(2.0, project.duration))

    def _changed(self, rebuild_list=False, keep_time=True):
        self.dirty = True
        self._update_title()
        if rebuild_list:
            self._refresh_list(self.scene_list.currentRow())
        else:
            self._refresh_labels()
        self._update_timeline()
        if not keep_time:
            self.seek(self.t)
        self._refresh_timer.start()

    def _update_title(self):
        name = self.path.name if self.path else self.project.name
        self.setWindowTitle(f"{'• ' if self.dirty else ''}{name} — {APP}")

    def _update_timeline(self):
        self.slider.blockSignals(True)
        self.slider.setRange(0, int(self.project.duration * 1000))
        self.slider.setValue(int(self.t * 1000))
        self.slider.blockSignals(False)
        self._update_time_label()

    def _update_time_label(self):
        fmt = lambda s: f"{int(s // 60)}:{s % 60:04.1f}"
        self.time_label.setText(f"{fmt(self.t)} / {fmt(self.project.duration)}")

    # ---------------------------------------------------------------- scene list

    def _scene_text(self, i, s: Scene):
        summary = s.summary if len(s.summary) <= 26 else s.summary[:25].rstrip() + "…"
        return f"{i + 1:>2}   {TEMPLATES[s.template].name}   ·   {s.duration:g} s\n      {summary}"

    def _refresh_list(self, select: int):
        self.scene_list.blockSignals(True)
        self.scene_list.clear()
        for i, s in enumerate(self.project.scenes):
            item = QListWidgetItem(self._scene_text(i, s))
            item.setData(Qt.ItemDataRole.UserRole, s.id)
            self.scene_list.addItem(item)
        self.scene_list.blockSignals(False)
        if self.project.scenes:
            self.scene_list.setCurrentRow(max(0, min(select, len(self.project.scenes) - 1)))
        self._build_scene_form()

    def _refresh_labels(self):
        for i, s in enumerate(self.project.scenes):
            item = self.scene_list.item(i)
            if item:
                item.setText(self._scene_text(i, s))

    def current_scene(self) -> Scene | None:
        i = self.scene_list.currentRow()
        return self.project.scenes[i] if 0 <= i < len(self.project.scenes) else None

    def _on_select(self, row):
        self._build_scene_form()
        if 0 <= row < len(self.project.scenes):
            s = self.project.scenes[row]
            self.stop()
            self.seek(self.project.starts()[row] + min(2.5, s.duration * 0.6))

    def _on_reorder(self, *_):
        order = [self.scene_list.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.scene_list.count())]
        by_id = {s.id: s for s in self.project.scenes}
        self.project.scenes = [by_id[i] for i in order if i in by_id]
        QTimer.singleShot(0, lambda: self._changed(rebuild_list=True))

    def add_scene(self, template_id):
        i = self.scene_list.currentRow() + 1 if self.project.scenes else 0
        self.project.scenes.insert(i, Scene.new(template_id))
        self._changed(rebuild_list=False)
        self._refresh_list(i)
        self._on_select(i)

    def duplicate_scene(self):
        s = self.current_scene()
        if s:
            i = self.scene_list.currentRow() + 1
            self.project.scenes.insert(i, s.copy())
            self._changed()
            self._refresh_list(i)

    def delete_scene(self):
        s = self.current_scene()
        if not s:
            return
        i = self.scene_list.currentRow()
        del self.project.scenes[i]
        self._changed()
        self._refresh_list(i)

    def move_scene(self, delta):
        i = self.scene_list.currentRow()
        j = i + delta
        if 0 <= i < len(self.project.scenes) and 0 <= j < len(self.project.scenes):
            sc = self.project.scenes
            sc[i], sc[j] = sc[j], sc[i]
            self._changed()
            self._refresh_list(j)

    # ---------------------------------------------------------------- forms

    def _form_page(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(14, 14, 14, 14)
        lay.setSpacing(8)
        return page, lay

    def _build_scene_form(self):
        page, lay = self._form_page()
        s = self.current_scene()
        if not s:
            lay.addWidget(hint("No scene selected. Use + Add to start."))
            lay.addStretch(1)
            self.scene_scroll.setWidget(page)
            return
        tpl = TEMPLATES[s.template]
        lay.addWidget(QLabel(tpl.name, objectName="heading"))
        lay.addWidget(hint(tpl.description))
        lay.addSpacing(8)

        lay.addWidget(section("Duration"))
        dur = QDoubleSpinBox(minimum=MIN_SCENE, maximum=MAX_SCENE, singleStep=0.5, decimals=1, suffix=" s")
        dur.setValue(s.duration)
        dur.valueChanged.connect(lambda v: self._set_duration(s, v))
        lay.addWidget(dur)

        for f in tpl.fields:
            lay.addSpacing(6)
            lay.addWidget(section(f.label))
            value = s.fields.get(f.key, "")
            if f.kind == "text":
                w = QLineEdit(value)
                w.textChanged.connect(lambda v, k=f.key: self._set_field(s, k, v))
            elif f.kind in ("multiline", "list"):
                w = QPlainTextEdit(value)
                w.setFixedHeight(96 if f.kind == "multiline" else 132)
                w.textChanged.connect(lambda k=f.key, w=w: self._set_field(s, k, w.toPlainText()))
            else:  # image
                w = FilePicker(value, f"Choose {f.label.lower()}", "Images (*.png *.jpg *.jpeg *.webp *.bmp)",
                               lambda: self.project.base_dir)
                w.changed.connect(lambda v, k=f.key: self._set_field(s, k, v))
            w.setObjectName(f"field_{f.key}")
            w.setAccessibleName(f.label)
            lay.addWidget(w)
            if f.help:
                lay.addWidget(hint(f.help))
        lay.addStretch(1)
        self.scene_scroll.setWidget(page)

    def _build_project_form(self):
        p = self.project
        page, lay = self._form_page()
        lay.addWidget(QLabel("Project", objectName="heading"))
        lay.addWidget(hint("Settings that apply to the whole video."))
        lay.addSpacing(8)

        def add(label, widget):
            lay.addSpacing(6)
            lay.addWidget(section(label))
            lay.addWidget(widget)

        name = QLineEdit(p.name)
        name.textChanged.connect(lambda v: self._set_project("name", v, refresh=False))
        add("Name", name)

        fmt = QComboBox()
        for key, (label, size) in FORMATS.items():
            fmt.addItem(f"{label}   {size[0]}×{size[1]}", key)
        fmt.setCurrentIndex(list(FORMATS).index(p.format))
        fmt.currentIndexChanged.connect(lambda _: self._set_format(fmt.currentData()))
        add("Format", fmt)

        theme = QComboBox()
        theme.addItems(list(PRESETS))
        theme.setCurrentText(p.theme)
        theme.currentTextChanged.connect(lambda v: self._set_project("theme", v))
        add("Theme", theme)

        accent_row = QWidget()
        al = QHBoxLayout(accent_row)
        al.setContentsMargins(0, 0, 0, 0)
        accent = ColorButton(p.accent)
        reset = QToolButton(text="Reset", objectName="flat")
        accent.changed.connect(lambda v: self._set_project("accent", v))
        reset.clicked.connect(lambda: (accent.set_value(""), self._set_project("accent", "")))
        al.addWidget(accent, 1)
        al.addWidget(reset)
        add("Accent color", accent_row)

        fps = QComboBox()
        for v in FPS_CHOICES:
            fps.addItem(f"{v} fps", v)
        fps.setCurrentIndex(FPS_CHOICES.index(p.fps))
        fps.currentIndexChanged.connect(lambda _: self._set_project("fps", fps.currentData()))
        add("Frame rate", fps)

        trans = QDoubleSpinBox(minimum=0.0, maximum=1.5, singleStep=0.1, decimals=1, suffix=" s")
        trans.setValue(p.transition)
        trans.valueChanged.connect(lambda v: self._set_project("transition", v))
        add("Crossfade between scenes", trans)

        audio = FilePicker(p.audio, "Choose music or narration", "Audio (*.mp3 *.wav *.m4a *.aac *.ogg *.flac)",
                           lambda: self.project.base_dir)
        audio.changed.connect(lambda v: self._set_project("audio", v, refresh=False))
        add("Soundtrack", audio)
        lay.addWidget(hint("Optional. The video keeps its own length; longer audio is trimmed."))
        lay.addStretch(1)
        lay.addWidget(hint(f"mindas_scene {__version__}"))
        self.project_scroll.setWidget(page)

    def _set_field(self, scene, key, value):
        scene.fields[key] = value
        self._changed()

    def _set_duration(self, scene, value):
        scene.duration = value
        self._changed()

    def _set_project(self, key, value, refresh=True):
        setattr(self.project, key, value)
        self._changed() if refresh else (setattr(self, "dirty", True), self._update_title())

    def _set_format(self, key):
        self.project.format = key
        self.view.set_aspect(*self.project.size)
        self._changed()

    # ---------------------------------------------------------------- playback

    def _preview_scale(self):
        _, _, w, h = self.view.target()
        pw, ph = self.project.size
        return max(0.2, min(1.0, w * self.devicePixelRatioF() / pw))

    def _request_frame(self):
        if not self.project.scenes:
            self.view.set_frame(QImage())
            return
        self.renderer.request(self.project.to_json(), str(self.project.base_dir or ""), self.t, self._preview_scale())

    def _on_frame(self, img, _t):
        self.view.set_frame(img)

    def seek(self, t):
        self.t = max(0.0, min(t, self.project.duration))
        self._update_timeline()
        self._refresh_timer.start()

    def _on_scrub(self, value):
        if self.playing:
            self._play_origin = (value / 1000, time.perf_counter())
        self.t = value / 1000
        self._update_time_label()
        self._request_frame()

    def toggle_play(self):
        self.stop() if self.playing else self.play()

    def play(self):
        if not self.project.scenes:
            return
        if self.t >= self.project.duration - 0.05:
            self.t = 0.0
        self.playing = True
        self._play_origin = (self.t, time.perf_counter())
        self.play_btn.setText("❚❚  Pause")
        self._play_timer.start()

    def stop(self):
        self.playing = False
        self._play_timer.stop()
        self.play_btn.setText("▶  Play")

    def _tick(self):
        t0, wall = self._play_origin
        t = t0 + time.perf_counter() - wall
        if t >= self.project.duration:
            t = self.project.duration
            self.stop()
        self.t = t
        self._update_timeline()
        self._request_frame()

    def _space(self):
        if isinstance(QApplication.focusWidget(), (QLineEdit, QPlainTextEdit)):
            return
        self.toggle_play()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._refresh_timer.start()

    # ---------------------------------------------------------------- files

    def _confirm_discard(self) -> bool:
        if not self.dirty:
            return True
        r = QMessageBox.question(self, APP, "Save changes to this project?",
                                 QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard
                                 | QMessageBox.StandardButton.Cancel)
        if r == QMessageBox.StandardButton.Save:
            return self.save()
        return r == QMessageBox.StandardButton.Discard

    def new_project(self):
        if self._confirm_discard():
            self._load_project(sample_project(), None)

    def open_dialog(self):
        if not self._confirm_discard():
            return
        start = self.settings.value("last_dir", str(Path.home()))
        path, _ = QFileDialog.getOpenFileName(self, "Open project", start, FILTER)
        if path:
            self.open_path(Path(path))

    def open_path(self, path: Path):
        try:
            project = Project.load(path)
        except (OSError, ProjectError) as e:
            QMessageBox.critical(self, "Could not open project", str(e))
            return
        self.settings.setValue("last_dir", str(path.parent))
        self._load_project(project, path)
        self.statusBar().showMessage(f"Opened {path.name}", 4000)

    def save(self) -> bool:
        if not self.path:
            return self.save_as()
        try:
            self.path = self.project.save(self.path)
        except OSError as e:
            QMessageBox.critical(self, "Could not save", str(e))
            return False
        self.dirty = False
        self._update_title()
        self._build_scene_form()
        self._build_project_form()
        self.statusBar().showMessage(f"Saved {self.path.name}", 4000)
        return True

    def save_as(self) -> bool:
        start = str(Path(self.settings.value("last_dir", str(Path.home()))) / f"{self.project.name}{EXTENSION}")
        path, _ = QFileDialog.getSaveFileName(self, "Save project", start, FILTER)
        if not path:
            return False
        self.path = Path(path)
        self.settings.setValue("last_dir", str(self.path.parent))
        return self.save()

    def export(self):
        if not self.project.scenes:
            QMessageBox.information(self, "Export", "Add at least one scene first.")
            return
        self.stop()
        folder = self.path.parent if self.path else Path(self.settings.value("last_dir", str(Path.home())))
        ExportDialog(self, self.project, folder / f"{self.project.name or 'video'}.mp4").exec()

    def closeEvent(self, e):
        if self._confirm_discard():
            self.renderer.stop()
            e.accept()
        else:
            e.ignore()


# ================================================================ entry point

def _install_excepthook(app):
    def hook(kind, value, tb):
        traceback.print_exception(kind, value, tb)
        QMessageBox.critical(None, APP, f"Something went wrong:\n{kind.__name__}: {value}")
    sys.excepthook = hook


def create_app(argv=None) -> QApplication:
    app = QApplication.instance() or QApplication(argv or sys.argv)
    app.setApplicationName(APP)
    for f in BUNDLED_FONTS.glob("*.ttf"):
        QFontDatabase.addApplicationFont(str(f))
    app.setFont(QFont("Inter", 10))
    app.setStyleSheet(style.QSS)
    return app


def main(argv=None) -> int:
    multiprocessing.freeze_support()
    argv = sys.argv if argv is None else argv
    app = create_app(argv)
    _install_excepthook(app)
    path = next((a for a in argv[1:] if a.endswith(EXTENSION)), None)
    win = MainWindow(path)
    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
