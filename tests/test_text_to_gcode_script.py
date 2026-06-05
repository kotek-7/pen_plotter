from pathlib import Path

from scripts.text_to_gcode import main


def test_text_to_gcode_script_writes_file(tmp_path: Path, monkeypatch):
    output = tmp_path / "text.gcode"
    monkeypatch.setattr(
        "sys.argv",
        ["text_to_gcode.py", "--text", "Test", "--output", str(output), "--no-optimize"],
    )

    main()

    text = output.read_text(encoding="utf-8")
    assert "$H" in text
    assert "G1 X" in text
