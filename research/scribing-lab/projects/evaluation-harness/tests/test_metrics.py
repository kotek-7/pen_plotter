from evaluation_harness.metrics import compute_trajectory_metrics


def test_compute_trajectory_metrics_for_empty_input() -> None:
    metrics = compute_trajectory_metrics([])

    assert metrics["status"] == "empty"
    assert metrics["point_count"] == 0
    assert metrics["stroke_count"] == 0


def test_compute_trajectory_metrics_counts_strokes_and_distances() -> None:
    points = [
        {"x": 0.0, "y": 0.0, "t": 0, "pen_state": 0},
        {"x": 3.0, "y": 4.0, "t": 100, "pen_state": 1},
        {"x": 6.0, "y": 8.0, "t": 200, "pen_state": 1},
        {"x": 7.0, "y": 8.0, "t": 300, "pen_state": 0},
        {"x": 8.0, "y": 8.0, "t": 400, "pen_state": 1},
    ]

    metrics = compute_trajectory_metrics(points)

    assert metrics["status"] == "ok"
    assert metrics["point_count"] == 5
    assert metrics["stroke_count"] == 2
    assert metrics["draw_distance_mm"] == 11.0
    assert metrics["penup_distance_mm"] == 1.0
    assert metrics["mean_draw_speed_mm_s"] == 50.0
    assert metrics["max_draw_speed_mm_s"] == 50.0
    assert metrics["draw_speed_cv"] == 0.0


def test_compute_trajectory_metrics_reports_motion_variation() -> None:
    points = [
        {"x": 0.0, "y": 0.0, "t": 0, "pen_state": 1},
        {"x": 1.0, "y": 0.0, "t": 100, "pen_state": 1},
        {"x": 5.0, "y": 0.0, "t": 200, "pen_state": 1},
        {"x": 6.0, "y": 0.0, "t": 300, "pen_state": 1},
        {"x": 10.0, "y": 0.0, "t": 400, "pen_state": 1},
    ]

    metrics = compute_trajectory_metrics(points)

    assert metrics["velocity_peak_count"] == 1
    assert metrics["max_draw_speed_mm_s"] == 40.0
    assert metrics["draw_speed_cv"] > 0.0
    assert metrics["mean_abs_acceleration_mm_s2"] > 0.0
    assert metrics["mean_abs_jerk_mm_s3"] > 0.0
