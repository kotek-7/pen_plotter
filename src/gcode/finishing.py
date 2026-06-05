from __future__ import annotations

import numpy as np

TOME = "tome"
HANE = "hane"
HARAI = "harai"
NONE = "none"


def contact_profile(
    finish: str,
    n_points: int,
    lift_points: int,
    harai_min: float = 0.15,
    hane_min: float = 0.2,
) -> np.ndarray:
    """Return per-point pen contact ratio for stroke ending effects."""
    contact = np.ones(n_points, dtype=float)
    if n_points < 2 or finish not in (HARAI, HANE):
        return contact

    k = min(lift_points, n_points)
    if k < 1:
        return contact

    if finish == HARAI:
        tail = np.linspace(1.0, harai_min, k)
    else:
        s = np.linspace(0.0, 1.0, k)
        tail = hane_min + (1.0 - hane_min) * (1.0 - s) ** 2
    contact[n_points - k :] = tail
    return contact
