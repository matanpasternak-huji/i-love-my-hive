import numpy as np
import pandas as pd

import find_interactions_by_antennation as m


def test_exit_threshold_measured_from_body_length():
    frame = pd.DataFrame([{"head.x": 0.0, "head.y": 0.0, "abdomen.x": 30.0, "abdomen.y": 40.0}])
    d_exit, d_prox = m.compute_exit_threshold({0: frame})
    assert d_exit == 50 * m.D_EXIT_FACTOR
    assert d_prox == 50 * m.D_PROX_FACTOR


def test_exit_threshold_falls_back_to_a_pair():
    """With no measurable bee (no abdomen points, or no frames at all) it used to
    return a single number and crash the caller."""
    frame = pd.DataFrame([{"head.x": 1.0, "head.y": 2.0, "abdomen.x": np.nan, "abdomen.y": np.nan}])
    for groups in ({0: frame}, {}):
        d_exit, d_prox = m.compute_exit_threshold(groups)
        assert d_exit == m.D_EXIT
        assert d_prox == m.D_EXIT / m.D_EXIT_FACTOR * m.D_PROX_FACTOR
