import os
import time

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtWidgets import QLineEdit  # noqa: E402

from mindas_scene.gui.app import MainWindow, create_app  # noqa: E402
from mindas_scene.project import Project  # noqa: E402


def pump(app, ms=500):
    end = time.perf_counter() + ms / 1000
    while time.perf_counter() < end:
        app.processEvents()


@pytest.fixture(scope="module")
def app():
    return create_app(["test"])


def test_studio_edit_preview_save_reopen(app, tmp_path):
    win = MainWindow()
    win.show()
    pump(app)
    assert win.scene_list.count() == 5 and win.view._pixmap is not None

    win.add_scene("chart")
    assert win.scene_list.count() == 6 and win.current_scene().template == "chart"
    edit = win.scene_scroll.widget().findChild(QLineEdit, "field_heading")
    edit.setText("Quarterly results")
    assert win.current_scene().fields["heading"] == "Quarterly results" and win.dirty

    win.move_scene(-1)
    win.duplicate_scene()
    win.delete_scene()
    win._set_format("portrait")
    win.play()
    pump(app, 700)
    assert win.t > 0.2
    win.stop()

    win.path = tmp_path / "studio.mscene"
    assert win.save() and not win.dirty
    reopened = Project.load(win.path)
    assert reopened.format == "portrait" and len(reopened.scenes) == 6
    assert any(s.fields.get("heading") == "Quarterly results" for s in reopened.scenes)

    win2 = MainWindow(str(win.path))
    pump(app)
    assert win2.scene_list.count() == 6 and not win2.dirty
    win.close()
    win2.close()
