from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PlotterConfig:
    """xDraw A4 / GRBL machine parameters.

    Values follow the machine-verified root G-code generator: homing then
    ``G92 X0 Y297 Z0`` paper origin, pen control on the Z axis (not M3/M5),
    and feed rates in mm/min.
    """

    paper_width: float = 210.0
    paper_height: float = 297.0
    travel_speed: float = 5000.0
    pen_up_command: str = "G1G90 Z0.5 F5000"
    pen_down_command: str = "G1G90 Z3.5 F5000"
    pen_up_z: float = 0.5
    pen_down_z: float = 3.5
    # Terminal lift target for low-pressure points (pen_up_z < finish_lift_z < pen_down_z).
    finish_lift_z: float = 2.0
    min_draw_feed: int = 300
    max_draw_feed: int = 1800
    decimal_places: int = 2
