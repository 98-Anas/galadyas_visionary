from PIL import Image

from mindas_scene import fade, mix, ramp, render


def test_ramp_bounds():
    assert ramp(0.0, 1.0, 2.0) == 0.0
    assert ramp(3.0, 1.0, 2.0) == 1.0
    assert ramp(1.5, 1.0, 2.0) == 0.5


def test_fade_holds_between_edges():
    assert fade(0.0, 1.0, 5.0) == 0.0
    assert fade(3.0, 1.0, 5.0) == 1.0
    assert fade(5.0, 1.0, 5.0) == 0.0


def test_mix_endpoints():
    assert mix((0, 0, 0), (200, 100, 50), 0.0) == (0, 0, 0)
    assert mix((0, 0, 0), (200, 100, 50), 1.0) == (200, 100, 50)


def test_render_writes_mp4(tmp_path):
    out = render(lambda t: Image.new("RGB", (64, 64), (int(255 * t), 0, 0)), tmp_path / "x.mp4",
                 duration=1.0, size=(64, 64), fps=10)
    assert out.stat().st_size > 0
