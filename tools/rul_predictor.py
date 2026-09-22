import json
from pathlib import Path

from ml.predict import has_model, provenance_for_rule_based

DATA_DIR = Path(__file__).parent.parent / "data" / "sensors"
HIST_DIR = DATA_DIR
ASSET_DIR = Path(__file__).parent.parent / "data" / "assets"


def _asset_class(machine_id: str) -> str:
    """Look up what kind of thing this is. Drives which estimator serves it."""
    profiles = ASSET_DIR / "asset_profiles.json"
    if not profiles.exists():
        return ""
    with open(profiles, encoding="utf-8") as f:
        return (json.load(f).get(machine_id) or {}).get("asset_class", "")


def _fitted_prediction(machine_id: str, asset_class: str) -> dict | None:
    """Serve a prediction from the fitted model, if this asset has telemetry for it.

    Returns None if anything is missing, so the caller falls back to thresholds rather
    than failing the run. A missing model is a degraded prediction, not an outage.
    """
    telemetry = HIST_DIR / f"{machine_id}_cmapss.json"
    if not telemetry.exists():
        return None

    try:
        import pandas as pd

        from ml.predict import predict_interval
    except ImportError:
        return None

    with open(telemetry, encoding="utf-8") as f:
        payload = json.load(f)

    history = pd.DataFrame(payload["cycles"])
    result = predict_interval(asset_class, history)

    return {
        "machine_id": machine_id,
        "rul": {
            "min": result["rul_cycles"]["min"],
            "max": None,
            "unit": "cycles",
            "bound": "lower",
        },
        "rul_median_cycles": result["rul_median_cycles"],
        "failure_mode": "turbofan_degradation",
        "confidence": None,
        "low_confidence_flag": False,
        "matched_historical_event": None,
        "source": result["source"],
        "model_id": result["model_id"],
        "provenance_note": (
            "Fitted on NASA C-MAPSS run-to-failure data and scored against held-out "
            f"ground truth ({result.get('n_test_units')} engines, "
            f"test MAE {result.get('test_mae_cycles')} cycles). The reported figure is a "
            "conformalised lower bound: at least this many cycles remain."
        ),
        "measured_error": {
            "test_rmse_cycles": result.get("test_rmse_cycles"),
            "test_mae_cycles": result.get("test_mae_cycles"),
            "backtest_subset": result.get("backtest_subset"),
        },
        "telemetry_provenance": payload.get("provenance", {}),
    }


def rul_predictor(machine_id: str, current_readings: dict) -> dict:
    """
    Estimates Remaining Useful Life (RUL) based on current sensor readings.

    Two estimators serve this tool and every result says which one produced it:
      - `fitted_model`        a model fitted to real run-to-failure data, with its
                              measured held-out error attached
      - `declared_thresholds` a rule written down in the asset profile and the reference
                              corpus, never backtested against failures of that asset

    Tool catalog:
      Input:  machine_id (str), current_readings (dict of sensor: latest_value)
      Output: rul (min/max/unit/bound), confidence (0-1 or null), failure_mode,
              source, provenance_note, matched_historical_event
      Use when: vibration or temp anomaly confirmed, need failure timeline
      Do NOT use: before sensor_query — needs real readings as input
      Fallback: if confidence < 0.6, flag as LOW_CONFIDENCE and escalate
      Risk tier: READ (autonomous)
    """
    asset_class = _asset_class(machine_id)
    if has_model(asset_class):
        fitted = _fitted_prediction(machine_id, asset_class)
        if fitted is not None:
            return fitted

    hist_file = HIST_DIR / "CNC-03-LEI_hist.json"
    historical_match = None
    if hist_file.exists():
        with open(hist_file, encoding="utf-8") as f:
            historical_match = json.load(f).get("failure_event")

    vibration = current_readings.get("vibration", 0)
    bearing_temp = current_readings.get("bearing_temp", 0)

    if vibration >= 7.0 or bearing_temp >= 75:
        rul_low, rul_high, confidence = 52, 76, 0.95
        failure_mode = "spindle_bearing_failure"
    elif vibration >= 6.0:
        # Past the critical threshold the asset profile and tms-101#S3 both use, but below
        # the severe band. Wider window, lower confidence. Added for F-01; it only ever
        # makes the system more cautious.
        rul_low, rul_high, confidence = 72, 120, 0.82
        failure_mode = "spindle_bearing_failure"
    elif vibration >= 5.0 or bearing_temp >= 65:
        rul_low, rul_high, confidence = 96, 144, 0.78
        failure_mode = "spindle_bearing_degradation"
    else:
        rul_low, rul_high, confidence = 500, 720, 0.60
        failure_mode = "normal_wear"

    # Provenance. These numbers come from thresholds in data/assets/asset_profiles.json
    # and the reference corpus, not from a model fitted to failures of this asset. No
    # public run-to-failure dataset exists for CNC spindle bearings, so the honest move
    # is to label the claim rather than dress it up.
    provenance = provenance_for_rule_based(
        "Thresholds are declared in the asset profile and reference corpus, not learned. "
        "Not backtested against failures of this asset class."
    )

    return {
        "machine_id": machine_id,
        "rul_hours": {"min": rul_low, "max": rul_high},
        "rul": {"min": rul_low, "max": rul_high, "unit": "hours", "bound": "interval"},
        "confidence": confidence,
        "failure_mode": failure_mode,
        "matched_historical_event": historical_match,
        "low_confidence_flag": confidence < 0.6,
        **provenance,
    }
