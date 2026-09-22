"""Serve remaining-useful-life predictions from a fitted model, with its error attached.

The point of this module is provenance. A number that came out of a model validated
against held-out ground truth and a number someone typed into a threshold table are not
the same kind of claim, and the system should never present them as if they were. Every
prediction returned here carries the measured error of the model that produced it.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    import pandas as pd

# numpy, pandas, lightgbm, scikit-learn and joblib are imported lazily inside the
# functions that need them. tools/rul_predictor.py imports provenance_for_rule_based
# from here, and the demo and the offline suite must keep running without the ML stack
# installed. See requirements-ml.txt.

REPO_ROOT = Path(__file__).resolve().parents[1]
MODEL_DIR = REPO_ROOT / "models"
RESULTS_DIR = REPO_ROOT / "eval" / "results"

# Asset classes that have a model fitted to real run-to-failure data.
# CNC spindle bearings are deliberately absent: no public run-to-failure dataset for
# that asset exists, so those predictions stay rule-based and are labelled as such.
MODEL_BY_ASSET_CLASS = {"turbofan": "FD001"}

SOURCE_FITTED = "fitted_model"
SOURCE_DECLARED = "declared_thresholds"


class ModelUnavailable(RuntimeError):
    """Raised when a fitted model was asked for but is not on disk."""


@lru_cache(maxsize=8)
def _load(model_id: str):
    import joblib

    paths = {tag: MODEL_DIR / f"rul_{model_id}_{tag}.joblib" for tag in ("low", "mid")}
    paths["features"] = MODEL_DIR / f"rul_{model_id}_features.joblib"
    paths["calibration"] = MODEL_DIR / f"rul_{model_id}_calibration.joblib"

    missing = [str(v.name) for v in paths.values() if not v.exists()]
    if missing:
        raise ModelUnavailable(
            f"missing {missing} in {MODEL_DIR}. Run: python -m ml.train_rul {model_id}"
        )

    models = {tag: joblib.load(paths[tag]) for tag in ("low", "mid")}
    features = joblib.load(paths["features"])
    calibration = joblib.load(paths["calibration"])
    return models, features, calibration


@lru_cache(maxsize=8)
def backtest_metrics(model_id: str) -> dict:
    """The model's measured error, read from the committed backtest result."""
    path = RESULTS_DIR / f"rul_backtest_{model_id}.json"
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {
        "backtest_subset": data.get("subset"),
        "test_rmse_cycles": data.get("test_rmse"),
        "test_mae_cycles": data.get("test_mae"),
        "lower_bound_target_coverage": data.get("lower_bound_target_coverage"),
        # Coverage where the conformal guarantee applies, and on the benchmark's own
        # test engines, which are not exchangeable with the calibration set. Both are
        # carried so a consumer cannot quote the flattering one alone. See F-08.
        "internal_coverage": data.get("internal_coverage_conformal"),
        "official_coverage": data.get("official_coverage_conformal"),
        "n_test_units": data.get("n_official_test_units"),
    }


def has_model(asset_class: str) -> bool:
    model_id = MODEL_BY_ASSET_CLASS.get(asset_class)
    if not model_id:
        return False
    try:
        _load(model_id)
    except ModelUnavailable:
        return False
    return True


def predict_interval(asset_class: str, history: pd.DataFrame) -> dict:
    """Predict RUL for one unit from its own cycle history.

    `history` must be that unit's readings up to now, oldest first, in the raw C-MAPSS
    column layout. Only the last row is scored; the earlier rows exist so the rolling
    features have something to look back at.
    """
    model_id = MODEL_BY_ASSET_CLASS.get(asset_class)
    if not model_id:
        raise ModelUnavailable(f"no fitted model for asset class {asset_class!r}")

    from ml.cmapss import SENSORS, SETTINGS, dead_sensors, featurize

    models, features, calibration = _load(model_id)

    df = history.copy()
    if "unit" not in df.columns:
        df["unit"] = 1

    dead = dead_sensors(df)
    keep = SETTINGS + [s for s in SENSORS if s not in dead]
    feat = featurize(df, keep)

    last = feat.iloc[[-1]]
    # A model trained on a different set of live sensors would otherwise fail silently.
    for col in features:
        if col not in last.columns:
            last[col] = 0.0
    X = last[features]

    raw_low = float(models["low"].predict(X)[0])
    mid = float(models["mid"].predict(X)[0])

    # Apply the same conformal offset the backtest measured. Without it the reported
    # bound would be the raw quantile, which covers less often than it claims.
    delta = float(calibration.get("conformal_delta", 0.0))
    lower = max(raw_low - delta, 0.0)

    return {
        "rul_cycles": {"min": round(lower, 1), "max": None},
        "rul_median_cycles": round(max(mid, 0.0), 1),
        "bound": "lower",
        "conformal_delta_cycles": round(delta, 2),
        "source": SOURCE_FITTED,
        "model_id": model_id,
        **backtest_metrics(model_id),
    }


def provenance_for_rule_based(reason: str) -> dict:
    """The provenance block attached to a threshold-derived prediction."""
    return {
        "source": SOURCE_DECLARED,
        "model_id": None,
        "provenance_note": reason,
    }
