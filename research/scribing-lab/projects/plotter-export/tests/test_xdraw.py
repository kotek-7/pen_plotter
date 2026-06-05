from plotter_export import XDrawExportConfig, export_xdraw_gcode, validate_xdraw_gcode


def _trajectory() -> list[dict]:
    return [
        {"x": 10.0, "y": 290.0, "t": 0, "pen_state": 0, "pressure": 0.0},
        {"x": 10.0, "y": 290.0, "t": 50, "pen_state": 1, "pressure": 1.0},
        {"x": 20.0, "y": 290.0, "t": 250, "pen_state": 1, "pressure": 0.5},
        {"x": 30.0, "y": 288.0, "t": 500, "pen_state": 1, "pressure": 0.2},
        {"x": 30.0, "y": 288.0, "t": 550, "pen_state": 0, "pressure": 0.0},
    ]


def test_export_xdraw_gcode_contains_setup_and_z_mapping() -> None:
    lines = export_xdraw_gcode(_trajectory())
    text = "\n".join(lines)

    assert "$H" in text
    assert "G92 X0 Y297 Z0" in text
    assert any("Z3.50" in line for line in lines)
    assert any("Z2." in line for line in lines)
    assert any(line.startswith("G1 X") and " Z" in line for line in lines)


def test_validate_xdraw_gcode_accepts_exported_lines() -> None:
    report = validate_xdraw_gcode(export_xdraw_gcode(_trajectory()))

    assert report.ok
    assert report.violations == ()
    assert report.z_min >= 0.5
    assert report.z_max <= 3.5
    assert report.feed_max <= 5000


def test_validate_xdraw_gcode_rejects_unsafe_coordinates() -> None:
    lines = export_xdraw_gcode(_trajectory())
    lines.append("G1 X250 Y10 Z3.5 F1000")

    report = validate_xdraw_gcode(lines)

    assert not report.ok
    assert any(item.startswith("x-out-of-range") for item in report.violations)


def test_export_xdraw_gcode_respects_custom_feed_limits() -> None:
    cfg = XDrawExportConfig(max_draw_feed=600)
    lines = export_xdraw_gcode(_trajectory(), cfg)

    draw_feeds = [
        int(line.split("F")[-1])
        for line in lines
        if line.startswith("G1 X") and "F" in line
    ]
    assert max(draw_feeds) <= 600
