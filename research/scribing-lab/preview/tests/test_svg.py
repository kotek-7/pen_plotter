from __future__ import annotations

from scribing_preview.svg import PreviewConfig, trajectory_to_svg


def _point(x: float, y: float, pen_state: int) -> dict[str, float | int]:
    return {"x": x, "y": y, "t": 0, "pen_state": pen_state, "pressure": 0.9 if pen_state else 0.0}


def test_trajectory_to_svg_renders_pen_down_runs_as_paths() -> None:
    trajectory = [
        _point(0.0, 297.0, 0),
        _point(10.0, 280.0, 1),
        _point(20.0, 280.0, 1),
        _point(20.0, 280.0, 0),
        _point(30.0, 270.0, 1),
        _point(40.0, 260.0, 1),
    ]

    svg = trajectory_to_svg(trajectory)

    assert svg.startswith("<svg")
    # Two pen-down strokes are rendered as solid paths.
    assert sum(1 for line in svg.splitlines() if 'stroke="#1f2937"' in line) == 2


def test_trajectory_to_svg_flips_y_axis_only_at_draw_time() -> None:
    config = PreviewConfig(paper_height=297.0, scale=1.0)
    trajectory = [_point(0.0, 297.0, 1), _point(0.0, 0.0, 1)]

    svg = trajectory_to_svg(trajectory, config)

    # y=297 (paper top) maps to svg y=0; y=0 (paper bottom) maps to svg y=297.
    assert "M 0.00 0.00" in svg
    assert "L 0.00 297.00" in svg


def test_trajectory_to_svg_can_hide_travel() -> None:
    trajectory = [_point(0.0, 0.0, 0), _point(50.0, 50.0, 0)]

    with_travel = trajectory_to_svg(trajectory, PreviewConfig(show_travel=True))
    without_travel = trajectory_to_svg(trajectory, PreviewConfig(show_travel=False))

    assert "stroke-dasharray" in with_travel
    assert "stroke-dasharray" not in without_travel
