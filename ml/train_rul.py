"""Train and honestly evaluate a remaining-useful-life model on C-MAPSS.

What this reports and why it is shaped this way:

1. A point estimate (the median model), scored against held-out ground truth.
2. A **one-sided lower bound**: "at least this many cycles remain". For maintenance
   planning that is the decision-relevant number, because the expensive mistake is
   believing you have more time than you do.
3. That bound is **conformalised** on engines the model never trained on, which gives a
   finite-sample coverage guarantee rather than a hope.

There is deliberately no upper bound. The target is clipped at 125 cycles, and about 40%
of training rows sit exactly at the clip, so the 90th percentile of the target is the cap
almost everywhere and a fitted upper quantile is degenerate: it returns the cap for every
engine and can never be violated. Reporting that as an interval would have been a band
that looks calibrated because it cannot fail. See eval/FINDINGS.md F-08.

Validation is grouped by engine throughout. A unit's cycles never straddle a split.
"""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from lightgbm import LGBMRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.model_selection import GroupKFold

from ml.cmapss import RUL_CAP, build

SEED = 20260922
REPO_ROOT = Path(__file__).resolve().parents[1]
MODEL_DIR = REPO_ROOT / "models"
RESULTS_DIR = REPO_ROOT / "eval" / "results"

Q_LOW, Q_MID = 0.1, 0.5

# We want the lower bound to hold this often. 0.9 pairs with the 0.1 quantile.
TARGET_COVERAGE = 0.9

# Training engines are split three ways: fitted on, used to calibrate the bound, and
# held back as an internal test set. Calibration and internal test are built by the same
# truncation process, so they are exchangeable and the conformal guarantee applies.
CALIBRATION_FRACTION = 0.2
INTERNAL_TEST_FRACTION = 0.2

# Random truncation points sampled per engine, for the calibration and internal test
# sets. More points per engine reduces variance; they are correlated within an engine,
# which makes the guarantee approximate.
TRUNCATIONS_PER_UNIT = 10


def phm08_score(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """The benchmark's own asymmetric penalty.

    Predicting failure later than it happens is punished harder than predicting it
    early, because in the real setting a late warning means the machine broke.
    """
    d = np.asarray(y_pred, dtype=float) - np.asarray(y_true, dtype=float)
    return float(np.sum(np.where(d < 0, np.exp(-d / 13.0) - 1.0, np.exp(d / 10.0) - 1.0)))


@dataclass
class RulResults:
    subset: str
    n_fit_units: int
    n_calibration_units: int
    n_internal_test_units: int
    n_official_test_units: int
    cv_rmse_mean: float
    cv_rmse_std: float
    test_rmse: float
    test_mae: float
    test_phm08: float
    baseline_rmse_mean_predictor: float
    lower_bound_target_coverage: float
    # Exchangeable with the calibration set: the conformal guarantee applies here.
    internal_coverage_raw: float
    internal_coverage_conformal: float
    # The benchmark's own test units. Truncated toward later life, so the calibration
    # set is NOT exchangeable with it and the guarantee does not transfer.
    official_coverage_raw: float
    official_coverage_conformal: float
    official_fraction_at_cap: float
    calibration_fraction_at_cap: float
    conformal_adjustment_cycles: float
    mean_lower_bound_slack: float
    rul_cap: int


def _model(alpha: float | None) -> LGBMRegressor:
    common = {
        "n_estimators": 600,
        "learning_rate": 0.05,
        "num_leaves": 31,
        "min_child_samples": 40,
        "subsample": 0.9,
        "subsample_freq": 1,
        "colsample_bytree": 0.8,
        "reg_lambda": 1.0,
        "random_state": SEED,
        "n_jobs": -1,
        "verbose": -1,
    }
    if alpha is None:
        return LGBMRegressor(objective="regression", **common)
    return LGBMRegressor(objective="quantile", alpha=alpha, **common)


def cross_validate(X: pd.DataFrame, y: pd.Series, groups: pd.Series, folds: int = 5):
    """Grouped CV over the fitting engines. An in-sample estimate, nothing more."""
    rmses = []
    splitter = GroupKFold(n_splits=folds)
    for train_idx, val_idx in splitter.split(X, y, groups):
        m = _model(Q_MID)
        m.fit(X.iloc[train_idx], y.iloc[train_idx])
        pred = m.predict(X.iloc[val_idx])
        rmses.append(float(np.sqrt(mean_squared_error(y.iloc[val_idx], pred))))
    return float(np.mean(rmses)), float(np.std(rmses))


def split_units(units: np.ndarray, seed: int = SEED):
    """Split engine ids three ways. Cycles from one engine must stay together."""
    rng = np.random.default_rng(seed)
    shuffled = rng.permutation(np.unique(units))
    n = len(shuffled)
    n_cal = max(1, int(round(n * CALIBRATION_FRACTION)))
    n_int = max(1, int(round(n * INTERNAL_TEST_FRACTION)))
    return (
        set(shuffled[: n_cal].tolist()),
        set(shuffled[n_cal : n_cal + n_int].tolist()),
        set(shuffled[n_cal + n_int :].tolist()),
    )


def truncate_sample(df: pd.DataFrame, per_unit: int, seed: int) -> pd.DataFrame:
    """Emulate how a test engine is produced: stop it at a random point in its life.

    Both the calibration set and the internal test set are built this way, which is what
    makes them exchangeable with one another.
    """
    rng = np.random.default_rng(seed)
    picks = []
    for _, group in df.groupby("unit", sort=False):
        idx = group.index.to_numpy()
        take = min(per_unit, len(idx))
        picks.append(rng.choice(idx, size=take, replace=False))
    return df.loc[np.concatenate(picks)]


def conformal_offset(lower_pred: np.ndarray, truth: np.ndarray, coverage: float) -> float:
    """How far to push the bound down so it holds at least `coverage` of the time.

    Split conformal: the score is how badly the raw bound overshot on calibration
    engines. Taking the ceil((n+1)*coverage)/n quantile of those scores gives the
    finite-sample guarantee rather than an asymptotic one.
    """
    scores = lower_pred - truth  # positive when the bound was too optimistic
    n = len(scores)
    k = math.ceil((n + 1) * coverage)
    if k > n:
        # Too few calibration points to certify this level. Fall back to the worst case.
        return float(np.max(scores))
    return float(np.sort(scores)[k - 1])


def run(subset: str = "FD001", save: bool = True) -> RulResults:
    train, test_last, y_test, features = build(subset)

    cal_units, int_units, fit_units = split_units(train["unit"].to_numpy())

    fit_df = train[train["unit"].isin(fit_units)]
    cal_df = truncate_sample(
        train[train["unit"].isin(cal_units)], TRUNCATIONS_PER_UNIT, SEED + 1
    )
    int_df = truncate_sample(
        train[train["unit"].isin(int_units)], TRUNCATIONS_PER_UNIT, SEED + 2
    )

    X_fit, y_fit, g_fit = fit_df[features], fit_df["rul"], fit_df["unit"]

    cv_mean, cv_std = cross_validate(X_fit, y_fit, g_fit)

    models = {}
    for tag, alpha in (("low", Q_LOW), ("mid", Q_MID)):
        m = _model(alpha)
        m.fit(X_fit, y_fit)
        models[tag] = m

    # Calibrate the lower bound on engines the model never saw.
    #
    # Every cycle of a calibration engine is used, not just its last. Training engines
    # run all the way to failure, so their final cycle always has RUL near zero, while
    # the test engines are truncated at points spread across the whole life range.
    # Calibrating on last cycles only would tune the bound on a distribution the model
    # never meets. Using every cycle matches how a test point is generated: stop here,
    # this much life remains.
    #
    # Cycles within one engine are correlated, so the conformal guarantee here is
    # approximate rather than exact. The engines themselves are disjoint from the
    # fitting set, which is the part that matters most.
    cal_low = models["low"].predict(cal_df[features])
    delta = conformal_offset(cal_low, cal_df["rul"].to_numpy(dtype=float), TARGET_COVERAGE)

    int_low = np.clip(models["low"].predict(int_df[features]), 0, RUL_CAP)
    int_truth = int_df["rul"].to_numpy(dtype=float)

    Xt = test_last[features]
    p_low_raw = np.clip(models["low"].predict(Xt), 0, RUL_CAP)
    p_mid = np.clip(models["mid"].predict(Xt), 0, RUL_CAP)
    p_low_conformal = np.clip(p_low_raw - delta, 0, RUL_CAP)

    truth = y_test.to_numpy(dtype=float)
    naive = np.full_like(truth, float(y_fit.mean()))

    results = RulResults(
        subset=subset,
        n_fit_units=int(fit_df["unit"].nunique()),
        n_calibration_units=int(cal_df["unit"].nunique()),
        n_internal_test_units=int(int_df["unit"].nunique()),
        n_official_test_units=int(test_last["unit"].nunique()),
        cv_rmse_mean=round(cv_mean, 3),
        cv_rmse_std=round(cv_std, 3),
        test_rmse=round(float(np.sqrt(mean_squared_error(truth, p_mid))), 3),
        test_mae=round(float(mean_absolute_error(truth, p_mid)), 3),
        test_phm08=round(phm08_score(truth, p_mid), 1),
        baseline_rmse_mean_predictor=round(
            float(np.sqrt(mean_squared_error(truth, naive))), 3
        ),
        lower_bound_target_coverage=TARGET_COVERAGE,
        internal_coverage_raw=round(float((int_truth >= int_low).mean()), 3),
        internal_coverage_conformal=round(
            float((int_truth >= np.clip(int_low - delta, 0, RUL_CAP)).mean()), 3
        ),
        official_coverage_raw=round(float((truth >= p_low_raw).mean()), 3),
        official_coverage_conformal=round(float((truth >= p_low_conformal).mean()), 3),
        official_fraction_at_cap=round(float((truth >= RUL_CAP).mean()), 3),
        calibration_fraction_at_cap=round(
            float((cal_df["rul"].to_numpy(dtype=float) >= RUL_CAP).mean()), 3
        ),
        conformal_adjustment_cycles=round(delta, 2),
        mean_lower_bound_slack=round(float(np.mean(truth - p_low_conformal)), 2),
        rul_cap=RUL_CAP,
    )

    if save:
        MODEL_DIR.mkdir(exist_ok=True)
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        import joblib

        for tag, m in models.items():
            joblib.dump(m, MODEL_DIR / f"rul_{subset}_{tag}.joblib")
        joblib.dump(features, MODEL_DIR / f"rul_{subset}_features.joblib")
        joblib.dump({"conformal_delta": delta, "target_coverage": TARGET_COVERAGE},
                    MODEL_DIR / f"rul_{subset}_calibration.joblib")

        path = RESULTS_DIR / f"rul_backtest_{subset}.json"
        path.write_text(json.dumps(asdict(results), indent=2) + "\n", encoding="utf-8")

    return results


if __name__ == "__main__":
    import sys

    target = sys.argv[1] if len(sys.argv) > 1 else "FD001"
    r = run(target)
    for k, v in asdict(r).items():
        print(f"{k:34} {v}")
