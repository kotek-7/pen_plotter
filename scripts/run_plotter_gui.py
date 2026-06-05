"""xDraw A4 G-code sender GUI entry point."""

from __future__ import annotations

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))


def main() -> None:
    from src.plotter_gui.app import MainWindow

    MainWindow.main()


if __name__ == "__main__":
    main()
