"""
The CNC rule reads the vibration rate when it has a trend (tms-101#S4).

Synthetic series only, offline. The single-reading call must not move.
"""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import policy  # noqa: E402
from tools.rul_predictor import rul_predictor  # noqa: E402
from tools.runtime_inputs import runtime_inputs  # noqa: E402

T0 = datetime(2026, 10, 9, tzinfo=timezone.utc)


def _series(vib, current=None, hours=72, step_min=10, skip=()):
    """vib(h) and current(h) sampled every step_min over the last `hours`; h=0 is now."""
    n = hours * 60 // step_min
    out = {"vibration": [], "spindle_current": []}
    for i in range(n + 1):
        h = -hours + i * step_min / 60
        if any(a <= h < b for a, b in skip):
            continue
        ts = (T0 + timedelta(hours=h)).isoformat()
        out["vibration"].append({"ts": ts, "v": round(vib(h), 3)})
        out["spindle_current"].append({"ts": ts, "v": round((current or (lambda _: 12.0))(h), 2)})
    return out


def _ramp(doubling_h, crit_at_h, base=2.6, crit=6.0):
    """Flat at `base`, then doubling every doubling_h, reaching `crit` at crit_at_h."""
    def v(h):
        return max(base, crit * 2 ** ((h - crit_at_h) / doubling_h))
    return v


def test_single_reading_call_is_unchanged():
    r = rul_predictor("CNC-07-LEI", {"vibration": 7.2, "bearing_temp": 72})
    assert (r["rul"]["min"], r["rul"]["max"]) == (52, 76)
    assert r["estimate_basis"] == "vibration_level" and "trend" not in r
    assert r["source"] == "declared_thresholds"


def test_a_fast_doubling_gives_the_fast_window():
    s = _series(_ramp(5, crit_at_h=1.0))                 # 1h before Critical, still Warning
    r = rul_predictor("CNC-07-LEI", {"vibration": 5.3, "bearing_temp": 61, "series": s})
    assert r["estimate_basis"] == "vibration_rate" and r["trend"]["regime"] == "fast"
    assert (r["rul"]["min"], r["rul"]["max"]) == (40, 80)
    assert r["source"] == "declared_thresholds"
    assert policy.classify_risk(r) == "HIGH"             # the level rule said LOW here


def test_a_medium_doubling_gives_the_medium_window():
    s = _series(_ramp(36, crit_at_h=2.0))
    r = rul_predictor("CNC-05-LEI", {"vibration": 5.7, "series": s})
    assert r["trend"]["regime"] == "medium"
    assert (r["rul"]["min"], r["rul"]["max"]) == (100, 200)


def test_hours_already_in_critical_come_off_the_window():
    s = _series(_ramp(5, crit_at_h=-20.0))               # crossed Critical 20h ago
    r = rul_predictor("CNC-07-LEI", {"vibration": 7.3, "series": s})
    assert r["trend"]["regime"] == "fast"
    assert abs(r["trend"]["hours_in_critical"] - 20) <= 1
    assert 19 <= r["rul"]["min"] <= 21 and 59 <= r["rul"]["max"] <= 61


def test_a_rise_that_tracks_spindle_current_stays_with_the_level_rule():
    """tms-101#S2: a heavier cut is a process effect, not a bearing finding."""
    def vib(h):
        return 2.6 * (2.2 if h > -0.5 else 1.0)

    def cur(h):
        return 12.0 * (1.45 if h > -0.5 else 1.0)

    r = rul_predictor("CNC-02-AMS", {"vibration": 5.7, "series": _series(vib, cur)})
    assert r["trend"]["load_driven"] and r["estimate_basis"] == "vibration_level"
    assert policy.classify_risk(r) == "LOW"


def test_under_four_clean_hours_is_low_confidence():
    s = _series(_ramp(5, crit_at_h=1.0), hours=3)
    r = rul_predictor("CNC-07-LEI", {"vibration": 5.3, "series": s})
    assert r["trend"]["usable"] is False and r["low_confidence_flag"]
    assert policy.classify_risk(r) == "ESCALATE"


def test_a_rate_is_never_read_across_a_feed_gap():
    """The climb sits inside the gap. Old flat data must not vouch for 500h of life."""
    s = _series(_ramp(5, crit_at_h=1.0), skip=[(-60, -1)])   # only the last hour is clean
    r = rul_predictor("CNC-07-LEI", {"vibration": 5.3, "series": s})
    assert r["trend"]["clean_stretches"] == 2 and r["trend"]["usable"] is False
    assert policy.classify_risk(r) == "ESCALATE"


def test_a_climb_seen_before_a_gap_still_counts():
    """Fast rise, then the feed drops for 10h and is back for 2h: the rise still counts."""
    s = _series(_ramp(4, crit_at_h=-15.0), skip=[(-12, -2)])
    r = rul_predictor("CNC-02-AMS", {"vibration": 6.9, "series": s})
    assert r["trend"]["regime"] == "fast"
    assert abs(r["trend"]["hours_in_critical"] - 15) <= 1
    assert policy.classify_risk(r) == "HIGH"


def test_a_slow_drift_is_planned_maintenance():
    s = _series(lambda h: 5.2 * 1.1 ** (h / 168))       # 10% a week
    r = rul_predictor("CNC-08-LEI", {"vibration": 5.2, "series": s})
    assert r["trend"]["regime"] == "slow" and r["rul"]["min"] >= 500
    assert policy.classify_risk(r) == "LOW"


def test_a_slow_trend_under_a_critical_reading_keeps_the_level_window():
    s = _series(lambda h: 2.7)                           # a pinned channel looks like this
    r = rul_predictor("CNC-05-LEI", {"vibration": 25.4, "series": s})
    assert (r["rul"]["min"], r["rul"]["max"]) == (52, 76)
    assert policy.classify_risk(r) == "HIGH"


def test_a_simulated_month_window_is_read_without_being_passed():
    s = _series(_ramp(5, crit_at_h=1.0))
    hist = {"machine_id": "CNC-07-LEI", "interval_min": 10, "hours": 72,
            "samples": [{"ts": a["ts"], "vibration": a["v"], "spindle_current": b["v"]}
                        for a, b in zip(s["vibration"], s["spindle_current"], strict=True)]}
    with runtime_inputs("CNC-07-LEI", {"vibration": 5.3}, history=hist):
        r = rul_predictor("CNC-07-LEI", {"vibration": 5.3})
        other = rul_predictor("CNC-02-AMS", {"vibration": 5.3})
    assert r["estimate_basis"] == "vibration_rate"
    assert other["estimate_basis"] == "vibration_level"  # another machine's window is not used
