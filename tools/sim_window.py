"""Serve a sensor_query window from simulated history (stream/month.py).

A run started from the simulated month hands the tool the raw 10-minute samples before
the wake. This turns them into the same shape as the recorded 72h files, so the agent
sees a real trend instead of one reading. Gaps are reported, not smoothed over:
tms-705#S4 says no life estimate across a gap longer than 10 minutes.
"""
from __future__ import annotations

MAX_POINTS = 37          # same density as data/sensors/CNC-07-LEI_72h.json


def _hours(window: str, default: int) -> int:
    try:
        return max(1, int(str(window).lower().rstrip("h")))
    except ValueError:
        return default


def serve(history: dict, window: str, sensors: list[str]) -> dict:
    samples = history["samples"]
    step_min = history.get("interval_min", 10)
    hours = min(_hours(window, history.get("hours", 72)), history.get("hours", 72))
    keep = samples[-(hours * 60 // step_min + 1):]
    present = [s for s in keep if not s.get("missing")]
    gaps = len(keep) - len(present)

    stride = max(1, len(keep) // (MAX_POINTS - 1))
    picked = [s for i, s in enumerate(keep) if (len(keep) - 1 - i) % stride == 0
              and not s.get("missing")]
    if present and (not picked or picked[-1] is not present[-1]):
        picked.append(present[-1])

    readings, summary = {}, {}
    for name in sensors:
        pts = [{"ts": s["ts"], "v": s[name]} for s in picked if name in s]
        if not pts:
            continue
        readings[name] = pts
        first, last = pts[0]["v"], pts[-1]["v"]
        summary[name] = {"current": last, "baseline": first,
                         "delta_from_baseline": round(last - first, 2),
                         "trend": "rising" if last > first else "falling" if last < first else "flat"}

    detail = (f"simulated month: {len(present)} of {len(keep)} ten-minute samples over the "
              f"last {hours}h, shown every {stride * step_min} minutes")
    if gaps:
        detail += f"; {gaps} samples missing, feed dropped inside the window"
    return {"machine_id": history["machine_id"], "window": f"{hours}h", "readings": readings,
            "summary": summary, "data_timestamp": present[-1]["ts"] if present else None,
            "sensor_status": "INTERRUPTED" if gaps else "OK",
            "sensor_status_detail": detail, "source": "simulation"}
