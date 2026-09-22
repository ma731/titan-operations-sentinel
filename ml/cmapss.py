"""Load NASA C-MAPSS and turn it into a supervised RUL problem.

The dataset is 100 to 260 engines per subset, each run from healthy to failure. The
training units run all the way to failure; the test units are cut off partway, and a
separate file gives the true remaining cycles at that cut. That is genuine held-out
ground truth, which is the whole reason for using it.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

CACHE = Path.home() / ".cache" / "prognostics" / "cmapss"

SUBSETS = ["FD001", "FD002", "FD003", "FD004"]

SENSORS = [f"s{i}" for i in range(1, 22)]
SETTINGS = ["os1", "os2", "os3"]
COLUMNS = ["unit", "cycle"] + SETTINGS + SENSORS

# Standard practice on this benchmark. A brand new engine is not usefully described as
# having 300 cycles of life left: degradation is not observable yet, so the target is
# clipped and the model is only asked to be precise once decay has started.
RUL_CAP = 125

ROLLING_WINDOWS = (5, 20)


@dataclass(frozen=True)
class Subset:
    name: str
    train: pd.DataFrame
    test: pd.DataFrame
    test_rul: pd.Series

    def summary(self) -> str:
        return (
            f"{self.name}: train {self.train.unit.nunique():>3} units / "
            f"{len(self.train):>6,} cycles, "
            f"test {self.test.unit.nunique():>3} units"
        )


def _read(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, sep=r"\s+", header=None, names=COLUMNS)


def load_subset(name: str) -> Subset:
    if name not in SUBSETS:
        raise ValueError(f"unknown subset {name!r}, expected one of {SUBSETS}")
    if not CACHE.exists():
        raise FileNotFoundError(
            f"{CACHE} not found. Run scripts/fetch_prognostics_data.py first."
        )

    train = _read(CACHE / f"train_{name}.txt")
    test = _read(CACHE / f"test_{name}.txt")
    rul = pd.read_csv(CACHE / f"RUL_{name}.txt", sep=r"\s+", header=None, names=["rul"])
    rul.index = np.arange(1, len(rul) + 1)  # unit ids are 1-based
    return Subset(name=name, train=train, test=test, test_rul=rul["rul"])


def add_training_rul(df: pd.DataFrame, cap: int = RUL_CAP) -> pd.DataFrame:
    """RUL for a unit that we watched fail: cycles remaining until its last cycle."""
    out = df.copy()
    last = out.groupby("unit")["cycle"].transform("max")
    out["rul"] = (last - out["cycle"]).clip(upper=cap)
    return out


def dead_sensors(df: pd.DataFrame) -> list[str]:
    """Sensors that never move. Feeding them to the model is noise with a column name."""
    return [c for c in SENSORS if df[c].std(ddof=0) < 1e-8]


def featurize(df: pd.DataFrame, keep: list[str]) -> pd.DataFrame:
    """Per-unit rolling statistics.

    Degradation is a trend, not a level, so a single cycle's readings are weak. Rolling
    mean, spread and slope over each unit's own history are what carry the signal. Every
    window is computed within a unit and only ever looks backwards, so no future
    information leaks into a row.
    """
    out = df.copy()
    grouped = out.groupby("unit", sort=False)

    # Base frame carries only the columns we actually model with. Dead sensors are
    # dropped here rather than filtered later, so they cannot reappear as raw columns.
    ids = [c for c in ("unit", "cycle", "rul") if c in out.columns]
    base = out[ids + keep]

    frames = [base]
    for window in ROLLING_WINDOWS:
        roll = grouped[keep].rolling(window, min_periods=1)
        mean = roll.mean().reset_index(level=0, drop=True).add_suffix(f"_mean{window}")
        std = roll.std(ddof=0).reset_index(level=0, drop=True).add_suffix(f"_std{window}")
        frames += [mean, std.fillna(0.0)]

    # Simple backward slope: how far the reading has moved over the window.
    for window in ROLLING_WINDOWS:
        lagged = grouped[keep].shift(window)
        delta = (out[keep] - lagged).add_suffix(f"_delta{window}")
        frames.append(delta.fillna(0.0))

    # NOTE: an earlier version added cycle / unit_lifetime here. It leaked: a unit's
    # total lifetime is only known once it has already failed, so in training it encoded
    # the target, and at inference every truncated unit scored 1.0. Grouped CV did not
    # catch it because every fold had the same defect. Raw cycle count is kept instead,
    # which is genuinely observable at prediction time. See eval/FINDINGS.md F-07.
    return pd.concat(frames, axis=1)


def build(name: str, cap: int = RUL_CAP) -> tuple[pd.DataFrame, pd.DataFrame, pd.Series, list[str]]:
    """Return featurised train rows, featurised test last-cycle rows, true test RUL, features."""
    sub = load_subset(name)

    dead = dead_sensors(sub.train)
    keep = SETTINGS + [s for s in SENSORS if s not in dead]

    train = featurize(add_training_rul(sub.train, cap), keep)

    # The test units are truncated, so only the final observed cycle has a known label.
    test_feat = featurize(sub.test, keep)
    last_idx = test_feat.groupby("unit")["cycle"].idxmax()
    test_last = test_feat.loc[last_idx].sort_values("unit").reset_index(drop=True)

    y_test = sub.test_rul.reindex(test_last["unit"].values).clip(upper=cap)
    y_test.index = test_last.index

    feature_cols = [c for c in train.columns if c not in ("unit", "rul")]
    return train, test_last, y_test, feature_cols
