from mindas_scene import Canvas, Clip, Timeline, Video, fade, keyframes, mix, ramp, stagger
from mindas_scene import effects as fx


def test_ramp_bounds():
    assert ramp(0.0, 1.0, 2.0) == 0.0
    assert ramp(3.0, 1.0, 2.0) == 1.0
    assert ramp(1.5, 1.0, 2.0) == 0.5


def test_fade_holds_between_edges():
    assert fade(0.0, 1.0, 5.0) == 0.0
    assert fade(3.0, 1.0, 5.0) == 1.0
    assert fade(5.0, 1.0, 5.0) == 0.0


def test_stagger_orders_items():
    assert stagger(1.0, 1.0, 0, 0.5, 1.0) == 0.0
    assert stagger(2.0, 1.0, 0, 0.5, 1.0) == 1.0
    assert stagger(2.0, 1.0, 1, 0.5, 1.0) < 1.0


def test_keyframes_tuples_and_ends():
    frames = [(0.0, (1.0, 0.0)), (1.0, (2.0, 10.0))]
    assert keyframes(-1, frames) == (1.0, 0.0)
    assert keyframes(0.5, frames) == (1.5, 5.0)
    assert keyframes(9, frames) == (2.0, 10.0)


def test_mix_endpoints():
    assert mix((0, 0, 0), (200, 100, 50), 0.0) == (0, 0, 0)
    assert mix((0, 0, 0), (200, 100, 50), 1.0) == (200, 100, 50)


def test_canvas_scales_device_pixels():
    c = Canvas(100, 50, scale=2)
    assert c.img.size == (200, 100)
    c.rect((0, 0, 10, 10), fill=(255, 0, 0))
    assert c.img.getpixel((19, 19))[:3] == (255, 0, 0)
    assert c.img.getpixel((25, 25))[3] == 0


def test_effects_run_at_any_scale():
    for s in (1, 2):
        c = Canvas(64, 64, scale=s, background=(0, 0, 0))
        fx.vertical_gradient(c, (0, 0, 0), (255, 255, 255))
        fx.glow(c, (32, 32), 20, (255, 0, 0), 0.5)
        fx.shadow(c, (10, 10, 50, 50), blur=8)
        fx.gradient_rect(c, (0, 0, 64, 8), (0, 0, 0), (255, 255, 255), radius=4)
        fx.camera(c, 1.5, (20, 20))
        fx.vignette(c)
        assert c.img.size == (64 * s, 64 * s)


def test_gradient_rect_runs_left_to_right():
    c = Canvas(100, 10, background=(0, 0, 0))
    fx.gradient_rect(c, (0, 0, 100, 10), (0, 0, 0), (255, 255, 255))
    assert c.img.getpixel((5, 5))[0] < c.img.getpixel((95, 5))[0]


def test_timeline_crossfades():
    tl = Timeline(Clip(0, 2, lambda c, t: c.rect((0, 0, 8, 8), fill=(255, 255, 255)), fade_in=1, fade_out=0))
    early, late = Canvas(8, 8, background=(0, 0, 0)), Canvas(8, 8, background=(0, 0, 0))
    tl(early, 0.5)
    tl(late, 1.5)
    assert 0 < early.img.getpixel((4, 4))[0] < late.img.getpixel((4, 4))[0] == 255


def test_render_writes_mp4(tmp_path):
    video = Video(lambda c, t: c.rect((0, 0, 64, 64), fill=(int(255 * t), 0, 0)), duration=1.0,
                  size=(64, 64), fps=10, ssaa=1)
    out = video.render(tmp_path / "x.mp4", workers=1)
    assert out.stat().st_size > 0


def test_tracked_text_shares_one_baseline():
    from mindas_scene import Font
    font = Font(("segoeuil.ttf", "DejaVuSans.ttf"), 40)
    plain, tracked = Canvas(400, 100, background=(0, 0, 0)), Canvas(400, 100, background=(0, 0, 0))
    plain.text((10, 20), "mind_al", font, (255, 255, 255), anchor="lt")
    tracked.text((10, 20), "mind_al", font, (255, 255, 255), anchor="lt", tracking=0.001)
    rows = lambda c: c.img.convert("L").getbbox()
    assert abs(rows(plain)[1] - rows(tracked)[1]) <= 1 and abs(rows(plain)[3] - rows(tracked)[3]) <= 1
