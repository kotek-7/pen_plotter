import numpy as np

from src.gcode.finishing import HANE, HARAI, contact_profile


def test_contact_profile_harai_tapers_tail():
    contact = contact_profile(HARAI, n_points=8, lift_points=4)

    assert np.all(contact[:4] == 1.0)
    assert contact[-1] < contact[-2] < contact[-3]


def test_contact_profile_hane_tapers_tail():
    contact = contact_profile(HANE, n_points=8, lift_points=4)

    assert contact[-1] < 1.0
    assert np.all(contact >= 0.0)
