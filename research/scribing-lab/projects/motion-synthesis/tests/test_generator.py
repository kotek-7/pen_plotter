from motion_synthesis import MotionConfig, SkeletonStroke, synthesize_motion


def test_synthesize_motion_is_seeded() -> None:
    strokes = [SkeletonStroke(points=((0.0, 0.0), (10.0, 0.0)), terminal="tome")]

    first = synthesize_motion(strokes, seed=1)
    second = synthesize_motion(strokes, seed=1)

    assert first == second


def test_synthesize_motion_generates_non_uniform_timing() -> None:
    strokes = [
        SkeletonStroke(
            points=((0.0, 0.0), (20.0, 0.0)),
            terminal="none",
        )
    ]

    trajectory = synthesize_motion(
        strokes,
        seed=1,
        config=MotionConfig(timing_jitter_cv=0.0, tremor_mm=0.0, samples_per_segment=8),
    )
    draw_points = [point for point in trajectory if point.pen_state == 1]
    intervals = [
        curr.t - prev.t for prev, curr in zip(draw_points, draw_points[1:], strict=False)
    ]

    assert len(set(intervals)) > 1


def test_synthesize_motion_applies_terminal_pressure() -> None:
    harai = synthesize_motion(
        [SkeletonStroke(points=((0.0, 0.0), (10.0, 0.0)), terminal="harai")],
        seed=1,
        config=MotionConfig(tremor_mm=0.0),
    )
    tome = synthesize_motion(
        [SkeletonStroke(points=((0.0, 0.0), (10.0, 0.0)), terminal="tome")],
        seed=1,
        config=MotionConfig(tremor_mm=0.0),
    )

    harai_down = [point.pressure for point in harai if point.pen_state == 1]
    tome_down = [point.pressure for point in tome if point.pen_state == 1]
    assert harai_down[-1] < harai_down[1]
    assert tome_down[-1] > tome_down[1]
