"""A first Manim scene: a title, then a curve drawn under its axes.

    uv sync --extra manim
    uv run manim -pqh examples/manim/hello_scene.py HelloScene
"""

from manim import BLUE_C, DOWN, GREY_B, UP, Axes, Create, FadeIn, FadeOut, Scene, Text, Write, np


class HelloScene(Scene):
    def construct(self):
        title = Text("mindas_scene", weight="LIGHT").scale(1.2)
        sub = Text("animations, written as code", color=GREY_B).scale(0.5).next_to(title, DOWN)
        self.play(Write(title), run_time=1.2)
        self.play(FadeIn(sub, shift=UP * 0.2))
        self.wait(0.6)
        self.play(FadeOut(title), FadeOut(sub))

        axes = Axes(x_range=[0, 2 * np.pi, np.pi / 2], y_range=[-1.5, 1.5, 0.5], x_length=10, y_length=4)
        curve = axes.plot(np.sin, color=BLUE_C)
        label = Text("y = sin x").scale(0.7).next_to(axes, UP)
        self.play(Create(axes), run_time=1.0)
        self.play(Create(curve), Write(label), run_time=2.0)
        self.wait(1.0)
