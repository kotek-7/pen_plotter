import numpy as np

from src.textplot import RenderConfig, render_text


def test_render_text_returns_paper_coordinate_strokes():
    strokes = render_text("ABC", RenderConfig(jitter=0.0, wobble=0.0))

    assert strokes
    points = np.vstack(strokes)
    assert points[:, 0].min() >= 0.0
    assert points[:, 0].max() <= 210.0
    assert points[:, 1].min() >= 0.0
    assert points[:, 1].max() <= 297.0


def test_render_text_is_seeded():
    config = RenderConfig(seed=123, jitter=0.05, wobble=0.02)

    first = render_text("A", config)
    second = render_text("A", config)

    assert len(first) == len(second)
    for a, b in zip(first, second, strict=True):
        np.testing.assert_allclose(a, b)


def test_render_text_wraps_lines():
    config = RenderConfig(font_size=20.0, max_width=25.0, jitter=0.0, wobble=0.0)
    strokes = render_text("AAAA", config)
    ys = np.vstack(strokes)[:, 1]

    assert ys.max() - ys.min() > config.font_size
