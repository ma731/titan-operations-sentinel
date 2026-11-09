import json
import math
import statistics
from datetime import datetime
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


# --- tms-101#S4: life from the vibration rate -------------------------------- #
VIB_WARNING, VIB_CRITICAL = 5.0, 6.0      # tms-101#S3, same as stream/triage.py
TEMP_WARNING = 65
MIN_CLEAN_H = 4.0                         # S4: under 4h of clean telemetry is not valid
SMOOTH_MIN = 60                           # trailing median, so one noisy sample is not a trend
RISE = 1.5                                # time a 50% rise takes, scaled to a doubling
LOAD_RISE = 1.15                          # current 15% over its window median: a heavier cut (S2)

# Doubling time (hours) -> failure window once Critical (hours). S4 only states three
# regimes. The gaps between them (6 to 24h, and 72h up to a 20%-a-week drift) take the
# shorter neighbouring window, so a gap never buys extra life.
FAST, MEDIUM, SLOW = (40, 80), (100, 200), (500, 720)
SLOW_WEEKLY_GROWTH = 0.20


def _t(ts: str) -> float:
    return datetime.fromisoformat(str(ts).replace("Z", "+00:00")).timestamp() / 3600


def _points(series) -> list[tuple[float, float]]:
    """[{"ts", "v"}, ...] (the sensor_query shape) -> sorted (hours, value), gaps dropped."""
    out = []
    for p in series or []:
        if isinstance(p, dict) and p.get("ts") and isinstance(p.get("v"), (int, float)):
            out.append((_t(p["ts"]), float(p["v"])))
    return sorted(out)


def _segments(pts: list[tuple[float, float]]) -> list[list[tuple[float, float]]]:
    """Split where the feed dropped. A rate is never read across a gap (tms-705#S4)."""
    if len(pts) < 2:
        return [pts] if pts else []
    step = statistics.median(b[0] - a[0] for a, b in zip(pts, pts[1:], strict=False))
    segs, cur = [], [pts[0]]
    for a, b in zip(pts, pts[1:], strict=False):
        if b[0] - a[0] > 1.5 * step:
            segs.append(cur)
            cur = []
        cur.append(b)
    segs.append(cur)
    return segs


def _smooth(seg: list[tuple[float, float]]) -> list[tuple[float, float]]:
    out = []
    for i, (t, _) in enumerate(seg):
        win = [v for tt, v in seg[: i + 1] if t - tt < SMOOTH_MIN / 60]
        out.append((t, statistics.median(win)))
    return out


def _fastest_doubling(seg: list[tuple[float, float]]) -> float | None:
    """Shortest doubling time inside one clean stretch. Read from the fastest 50% rise,
    so a bearing that has only just started climbing already shows its rate."""
    best = None
    for j in range(len(seg)):
        tj, vj = seg[j]
        for i in range(j - 1, -1, -1):
            if seg[i][1] <= vj / RISE:
                d = tj - seg[i][0]
                best = d if best is None or d < best else best
                break
    return best * math.log(2) / math.log(RISE) if best is not None else None


def _vibration_trend(series: dict) -> dict | None:
    """Read the rate S4 asks for from a trailing window. None if no vibration series."""
    pts = _points(series.get("vibration"))
    if not pts:
        return None
    segs = [_smooth(s) for s in _segments(pts)]
    clean = [s for s in segs if s[-1][0] - s[0][0] >= MIN_CLEAN_H]
    trend = {"window_h": round(pts[-1][0] - pts[0][0], 1), "clean_stretches": len(segs)}
    if not clean:
        trend["usable"] = False
        trend["why"] = f"under {MIN_CLEAN_H:g}h of continuous clean telemetry (tms-101#S4)"
        return trend

    doubling = min((d for d in map(_fastest_doubling, clean) if d is not None), default=None)
    if doubling is None and clean[-1] is not segs[-1]:
        # The stretch ending now is too short, and an older flat one cannot vouch for it.
        trend["usable"] = False
        trend["why"] = (f"under {MIN_CLEAN_H:g}h of clean telemetry since the feed came back "
                        "(tms-101#S4, tms-705#S4)")
        return trend
    if doubling is None:                  # no 50% rise: extrapolate the latest stretch
        last = clean[-1]
        span, ratio = last[-1][0] - last[0][0], last[-1][1] / last[0][1]
        doubling = span * math.log(2) / math.log(ratio) if ratio > 1 else math.inf
    weekly = 2 ** (168 / doubling) - 1 if math.isfinite(doubling) else 0.0
    if doubling <= 24:
        regime, window = "fast", FAST
    elif doubling <= 72 or weekly >= SLOW_WEEKLY_GROWTH:
        regime, window = "medium", MEDIUM
    else:
        regime, window = "slow", SLOW

    # S4 counts the window from entering Critical, so take off the hours already spent
    # there. If the crossing is older than the window we only know a lower bound.
    smoothed = [p for s in segs for p in s]
    now = smoothed[-1]
    below = [t for t, v in smoothed if v < VIB_CRITICAL]
    if now[1] < VIB_CRITICAL:
        in_critical, crossing_seen = 0.0, True
    elif below:
        after = [t for t, _ in smoothed if t > below[-1]]
        in_critical, crossing_seen = now[0] - after[0], True
    else:
        in_critical, crossing_seen = now[0] - smoothed[0][0], False

    # S2: a rise that tracks spindle current is a process effect, not a bearing finding.
    cur = _points(series.get("spindle_current"))
    load_ratio = None
    if len(cur) >= 3:
        base = statistics.median(v for _, v in cur)
        load_ratio = round(cur[-1][1] / base, 2) if base > 0 else None

    trend.update(usable=True, doubling_h=round(doubling, 1) if math.isfinite(doubling) else None,
                 weekly_growth=round(weekly, 3), regime=regime, regime_window_h=list(window),
                 hours_in_critical=round(in_critical, 1), crossing_seen=crossing_seen,
                 smoothed_vibration=round(now[1], 2), load_ratio=load_ratio,
                 load_driven=load_ratio is not None and load_ratio >= LOAD_RISE)
    return trend


def _runtime_series(machine_id: str) -> dict | None:
    """The window sensor_query serves in a simulated-month run, at full resolution."""
    from .runtime_inputs import current

    inputs = current()
    hist = inputs.get("history") if inputs and inputs.get("machine_id") == machine_id else None
    if not hist:
        return None
    rows = [r for r in hist.get("samples", []) if not r.get("missing")]
    return {k: [{"ts": r["ts"], "v": r[k]} for r in rows if k in r]
            for k in ("vibration", "spindle_current")}


def _from_rate(trend: dict) -> tuple[int, int, float]:
    lo, hi = trend["regime_window_h"]
    e = trend["hours_in_critical"]
    if hi - e <= 0:                       # past the corpus window: treat as imminent
        return 0, 24, 0.80
    lo = 0 if not trend["crossing_seen"] else max(0, lo - e)
    conf = 0.70 if trend["regime"] == "slow" else 0.80
    return round(lo), round(hi - e), conf


def rul_predictor(machine_id: str, current_readings: dict) -> dict:
    """
    Estimates Remaining Useful Life (RUL) based on current sensor readings.

    Two estimators serve this tool and every result says which one produced it:
      - `fitted_model`        a model fitted to real run-to-failure data, with its
                              measured held-out error attached
      - `declared_thresholds` a rule written down in the asset profile and the reference
                              corpus, never backtested against failures of that asset

    Tool catalog:
      Input:  machine_id (str), current_readings (dict of sensor: latest_value).
              Optional current_readings["series"]: sensor_query's "readings" block
              ({"vibration": [{"ts", "v"}, ...], "spindle_current": [...]}). With it, or
              with a simulated-month window in scope, the CNC rule reads the vibration
              rate (tms-101#S4) instead of only the level.
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

    # tms-101#S4: from Warning up, the life comes from the rate, not the level. A trend
    # that tracks spindle current stays with the level rule (tms-101#S2).
    series = current_readings.get("series")
    if not isinstance(series, dict):
        series = _runtime_series(machine_id)
    trend = _vibration_trend(series) if series else None
    basis = "vibration_level"
    warning_or_worse = vibration >= VIB_WARNING or bearing_temp >= TEMP_WARNING
    if trend and warning_or_worse and not trend["usable"]:
        confidence = 0.5                  # S4: an estimate on this little data is low confidence
        basis = "vibration_level_short_trend"
    elif (trend and warning_or_worse and not trend["load_driven"]
          # a slow trend under a Critical reading does not buy 500h: S3 still calls
          # Critical an emergency, and a pinned channel looks exactly like this
          and not (trend["regime"] == "slow" and failure_mode == "spindle_bearing_failure")):
        rul_low, rul_high, confidence = _from_rate(trend)
        basis = "vibration_rate"
        if trend["regime"] != "slow":
            failure_mode = "spindle_bearing_failure"

    # Provenance. These numbers come from thresholds in data/assets/asset_profiles.json
    # and the reference corpus, not from a model fitted to failures of this asset. No
    # public run-to-failure dataset exists for CNC spindle bearings, so the honest move
    # is to label the claim rather than dress it up.
    provenance = provenance_for_rule_based(
        "Thresholds are declared in the asset profile and reference corpus, not learned. "
        "Not backtested against failures of this asset class."
        + (" Window read from the vibration doubling time (tms-101#S4)."
           if basis == "vibration_rate" else "")
    )

    return {
        "machine_id": machine_id,
        "rul_hours": {"min": rul_low, "max": rul_high},
        "rul": {"min": rul_low, "max": rul_high, "unit": "hours", "bound": "interval"},
        "confidence": confidence,
        "failure_mode": failure_mode,
        "matched_historical_event": historical_match,
        "low_confidence_flag": confidence < 0.6,
        "estimate_basis": basis,
        **({"trend": trend} if trend else {}),
        **provenance,
    }
