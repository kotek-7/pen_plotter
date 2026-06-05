import numpy as np
import pytest

from src.gcode.config import PlotterConfig
from src.gcode.generator import GCodeGenerator, Stroke


@pytest.fixture
def plotter_config() -> PlotterConfig:
    return PlotterConfig()


@pytest.fixture
def gcode_generator(plotter_config: PlotterConfig) -> GCodeGenerator:
    return GCodeGenerator(plotter_config)


@pytest.fixture
def line_stroke() -> Stroke:
    return np.array([[10.0, 10.0], [20.0, 20.0]])


@pytest.fixture
def square_stroke() -> Stroke:
    return np.array(
        [
            [10.0, 10.0],
            [50.0, 10.0],
            [50.0, 50.0],
            [10.0, 50.0],
            [10.0, 10.0],
        ]
    )
