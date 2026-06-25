"""Trajectory to xDraw A4 G-code for scribing lab."""

from scribing_plotter.config import PlotterConfig
from scribing_plotter.gcode import trajectory_to_gcode
from scribing_plotter.safety import validate_gcode

__all__ = ["PlotterConfig", "trajectory_to_gcode", "validate_gcode", "__version__"]

__version__ = "0.1.0"
