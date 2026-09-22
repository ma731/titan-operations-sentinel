"""Tests for the RUL model layer.

The leakage test is the important one here. F-07 was a feature that used each unit's
total lifetime, which is only knowable after the unit has failed. Grouped CV did not
catch it because every fold shared the defect; only the held-out benchmark did. The
test below catches that class of bug directly, by checking that a row's features never
change when you append future cycles to the unit.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from ml.cmapss import (
    CACHE,
    SENSORS,
    SETTINGS,
    add_training_rul,
    dead_sensors,
    featurize,
)
from ml.train_rul import phm08_score

HAS_DATA = CACHE.exists() and (CACHE / "train_FD001.txt").exists()
needs_data = pytest.mark.skipif(
    not HAS_DATA, reason="C-MAPSS not downloaded; run scripts/fetch_prognostics_data.py"
)


def _frame(n_units: int = 3, n_cycles: int = 40, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows = []
    for unit in range(1, n_units + 1):
        for cycle in range(1, n_cycles + 1):
            row = {"unit": unit, "cycle": cycle}
            for s in SETTINGS:
                row[s] = float(rng.normal())
            for i, s in enumerate(SENSORS):
                # A couple of sensors drift with age, the rest are noise, one is dead.
                drift = cycle * 0.05 if i < 3 else 0.0
                row[s] = 0.0 if i == 7 else float(rng.normal() + drift)
            rows.append(row)
    return pd.DataFrame(rows)


def test_training_rul_counts_down_to_zero():
    df = add_training_rul(_frame(n_units=2, n_cycles=10), cap=125)
    for _, group in df.groupby("unit"):
        ordered = group.sort_values("cycle")["rul"].to_numpy()
        assert ordered[-1] == 0, "a unit we watched fail has zero life left at its last cycle"
        assert np.all(np.diff(ordered) <= 0), "RUL must never increase as cycles advance"


def test_training_rul_respects_cap():
    df = add_training_rul(_frame(n_units=1, n_cycles=400), cap=125)
    assert df["rul"].max() == 125


def test_dead_sensors_are_found():
    df = _frame()
    assert "s8" in dead_sensors(df)


def test_features_do_not_use_the_future():
    """Truncating a unit must not change the features of the cycles that remain.

    This is the exact property F-07 violated. If any feature is computed from the whole
    unit (its lifetime, a global mean, a max), truncation changes it and this fails.
    """
    full = _frame(n_units=2, n_cycles=60, seed=7)
    keep = SETTINGS + [s for s in SENSORS if s != "s8"]

    cut = 35
    truncated = full[full["cycle"] <= cut].copy()

    f_full = featurize(full, keep)
    f_trunc = featurize(truncated, keep)

    common = f_full[f_full["cycle"] <= cut].reset_index(drop=True)
    later = f_trunc.reset_index(drop=True)

    assert list(common.columns) == list(later.columns)
    pd.testing.assert_frame_equal(common, later, check_exact=False, rtol=1e-9)


def test_phm08_punishes_late_predictions_harder():
    """The benchmark's asymmetry: saying it will last longer than it does is worse."""
    truth = np.array([50.0])
    early = phm08_score(truth, truth - 10)  # predicted failure sooner than reality
    late = phm08_score(truth, truth + 10)  # predicted failure later than reality
    assert late > early > 0


def test_phm08_is_zero_for_perfect_predictions():
    truth = np.array([10.0, 50.0, 100.0])
    assert phm08_score(truth, truth) == pytest.approx(0.0)


@needs_data
def test_build_shapes_line_up():
    from ml.cmapss import build

    train, test_last, y_test, features = build("FD001")
    assert train["unit"].nunique() == 100
    assert len(test_last) == 100
    assert len(y_test) == len(test_last)
    assert "rul" not in features
    assert "unit" not in features
    # One row per test unit, and it must be that unit's last observed cycle.
    assert test_last["unit"].is_unique


@needs_data
def test_no_constant_sensor_survives_into_features():
    from ml.cmapss import build, load_subset

    sub = load_subset("FD001")
    dead = dead_sensors(sub.train)
    assert dead, "FD001 is known to contain constant sensors"
    _, _, _, features = build("FD001")
    for d in dead:
        assert not any(f == d or f.startswith(f"{d}_") for f in features)
