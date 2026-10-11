import json
import threading

import imageio_ffmpeg
import pytest
from PIL import Image

from galadyas_visionary import Cancelled
from galadyas_visionary.project import FORMATS, Project, ProjectError, Scene, build_video, sample_project
from galadyas_visionary.templates import TEMPLATES, count_up, rows

HOSTILE = ["", "   ", "x" * 400, "word " * 200, "|||", "\n\n\n", "Ünïcødé — “quotes” ✓", "no | number | here",
           "-5 | -3", "1e9 | 3", "12,500+ | users\n | empty label\nbad line"]


def test_round_trip(tmp_path):
    p = sample_project()
    p.accent = "#ff8800"
    path = p.save(tmp_path / "demo")
    assert path.suffix == ".gvis"
    q = Project.load(path)
    assert q.to_dict() == p.to_dict()


def test_save_is_atomic_and_leaves_no_temp(tmp_path):
    sample_project().save(tmp_path / "a.gvis")
    assert [f.name for f in tmp_path.iterdir()] == ["a.gvis"]


def test_rejects_foreign_damaged_and_newer_files(tmp_path):
    bad = tmp_path / "x.gvis"
    bad.write_text("{not json", encoding="utf-8")
    with pytest.raises(ProjectError, match="damaged"):
        Project.load(bad)
    bad.write_text(json.dumps({"hello": 1}), encoding="utf-8")
    with pytest.raises(ProjectError, match="not a galadyas_visionary"):
        Project.load(bad)
    bad.write_text(json.dumps({"app": "galadyas_visionary", "schema": 99}), encoding="utf-8")
    with pytest.raises(ProjectError, match="newer version"):
        Project.load(bad)


def test_forgiving_load_cleans_bad_values():
    p = Project.from_dict({"app": "galadyas_visionary", "format": "cinema", "fps": 7, "theme": "Nope", "accent": "pink",
                           "transition": "fast", "scenes": [
                               {"template": "title", "duration": 9999, "fields": {"title": 5, "junk": "x"}},
                               {"template": "unknown"}, "garbage", {"template": "end", "duration": float("nan")}]})
    assert (p.format, p.fps, p.theme, p.accent, p.transition) == ("landscape", 30, "Midnight", "", 0.6)
    assert [s.template for s in p.scenes] == ["title", "end"]
    assert p.scenes[0].duration == 120 and p.scenes[0].fields["title"] == "5" and "junk" not in p.scenes[0].fields
    assert p.scenes[1].duration == TEMPLATES["end"].duration


def test_timing_overlaps_by_transition():
    p = Project(transition=0.5, scenes=[Scene.new("title"), Scene.new("end")])
    d0 = p.scenes[0].duration
    assert p.starts() == [0.0, d0 - 0.5]
    assert p.duration == pytest.approx(d0 - 0.5 + p.scenes[1].duration)
    assert p.scene_at(0.1) == 0 and p.scene_at(p.duration - 0.1) == 1


@pytest.mark.parametrize("fmt", list(FORMATS))
@pytest.mark.parametrize("tid", list(TEMPLATES))
def test_every_template_survives_hostile_input_in_every_format(tid, fmt, tmp_path):
    tpl = TEMPLATES[tid]
    for text in HOSTILE:
        fields = {f.key: (str(tmp_path / "missing.png") if f.kind == "image" else text) for f in tpl.fields}
        p = Project(format=fmt, scenes=[Scene(tid, fields, tpl.duration)])
        v = p.video()
        for t in (0.0, 0.7, tpl.duration / 2, tpl.duration - 0.01):
            img = v.preview(t, scale=0.2)
            assert img.size == (round(FORMATS[fmt][1][0] * 0.2), round(FORMATS[fmt][1][1] * 0.2))


@pytest.mark.parametrize("fmt", list(FORMATS))
def test_images_render_in_logo_and_showcase(fmt, tmp_path):
    img = tmp_path / "shot.png"
    Image.new("RGB", (800, 500), (200, 60, 60)).save(img)
    p = Project(format=fmt, scenes=[Scene("showcase", {"heading": "H", "caption": "", "image": str(img)}, 4),
                                    Scene("title", {**TEMPLATES["title"].defaults(), "logo": str(img)}, 4)])
    frame = p.video().preview(3.0, scale=0.25)
    data = frame.tobytes()
    reds = sum(1 for i in range(0, len(data), 3) if data[i] > 150 and data[i + 1] < 100)
    assert reds > 100  # the image is actually on screen


def test_media_paths_follow_the_project(tmp_path):
    media = tmp_path / "assets"
    media.mkdir()
    logo = media / "logo.png"
    Image.new("RGB", (10, 10)).save(logo)
    p = Project(scenes=[Scene("title", {**TEMPLATES["title"].defaults(), "logo": str(logo)}, 4)])
    p.save(tmp_path / "proj.gvis")
    assert p.scenes[0].fields["logo"] == "assets/logo.png"
    q = Project.load(tmp_path / "proj.gvis")
    assert q.resolve(q.scenes[0].fields["logo"]) == logo.resolve()
    other = tmp_path / "elsewhere"
    other.mkdir()
    q.save(other / "copy.gvis")
    moved = Project.load(other / "copy.gvis")
    assert moved.resolve(moved.scenes[0].fields["logo"]) == logo.resolve()


def test_helpers():
    assert count_up("12,500+", 0.5) == "6,250+"
    assert count_up("98.5%", 1) == "98.5%"
    assert count_up("24/7", 1) == "24/7"
    assert count_up("n/a", 0.3) == "n/a"
    assert rows("a | b\n\n c \n", 2) == [["a", "b"], ["c", ""]]


def test_parallel_export_from_project(tmp_path):
    p = Project(fps=24, scenes=[Scene.new("title"), Scene.new("stats")])
    p.scenes[0].duration = p.scenes[1].duration = 1.5
    out = p.video().render(tmp_path / "out.mp4", quality="standard", workers=2)
    frames, _ = imageio_ffmpeg.count_frames_and_secs(str(out))
    assert frames == round(p.duration * 24)
    assert not list(tmp_path.glob(".*partial*"))


def test_cancel_removes_partial_file(tmp_path):
    p = Project(scenes=[Scene.new("title")])
    cancel = threading.Event()
    seen = []

    def progress(done, total):
        seen.append(done)
        if done == 5:
            cancel.set()

    with pytest.raises(Cancelled):
        p.video().render(tmp_path / "x.mp4", quality="draft", workers=1, progress=progress, cancel=cancel)
    assert list(tmp_path.iterdir()) == [] and max(seen) <= 6


def test_build_video_is_rebuildable_from_its_factory():
    v = sample_project().video()
    fn, args = v.factory
    assert fn is build_video and fn(*args).duration == v.duration
