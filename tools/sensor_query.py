import json
from pathlib import Path

from .runtime_inputs import current
from .sim_window import serve as serve_history

DATA_DIR = Path(__file__).parent.parent / "data" / "sensors"
TEMPLATE = DATA_DIR / "CNC-07-LEI_72h.json"   # reference degradation curve for other machines


def _history(machine_id: str, window: str, values: dict, sensors: list[str]) -> dict:
    """A scenario gives one reading per sensor. One reading is not a trend, and the
    telemetry standard (tms-705) says to abstain on it, which a careful model does. So
    rescale the recorded 72h curve (this machine's, else the reference one) to end exactly
    at the scenario's reading. Labelled as such: it is a fixture, not raw telemetry."""
    own = DATA_DIR / f"{machine_id}_72h.json"
    src = own if own.exists() else TEMPLATE
    raw = json.loads(src.read_text(encoding="utf-8"))
    readings, summary = {}, {}
    for s in sensors:
        series, target = raw["readings"].get(s), values.get(s)
        if series and isinstance(target, (int, float)):
            v0, v1 = series[0]["v"], series[-1]["v"]
            k = (target - v0) / (v1 - v0) if v1 != v0 else 0.0
            pts = [{**p, "v": round(v0 + (p["v"] - v0) * k, 2)} for p in series]
            pts[-1]["v"] = target
        elif series and src == own and s not in values:
            pts = series                                # recorded, not overridden by the scenario
        elif isinstance(target, (int, float)):
            pts = [{"ts": raw.get("data_timestamp"), "v": target}]
        else:
            continue
        readings[s] = pts
        first, last = pts[0]["v"], pts[-1]["v"]
        summary[s] = {"current": last, "baseline": first, "delta_from_baseline": round(last - first, 2),
                      "trend": "rising" if last > first else "falling" if last < first else "flat"}
    return {"machine_id": machine_id, "window": window, "readings": readings, "summary": summary,
            "data_timestamp": raw.get("data_timestamp"), "sensor_status": "OK",
            "sensor_status_detail": (f"run-scoped fixture: the recorded 72h curve from {src.stem} "
                                     "rescaled to end at this scenario's readings"),
            "source": "simulation"}


def sensor_query(machine_id: str, window: str, sensors: list[str]) -> dict:
    """
    Returns time-series sensor readings for a machine over the requested window.

    Tool catalog:
      Input:  machine_id (str), window ("24h"/"48h"/"72h"), sensors (list of sensor names)
      Output: dict with per-sensor readings array + summary stats
      Use when: assessing current machine health or trending anomalies
      Do NOT use: to make predictions — that's rul_predictor's job
      Fallback: if file missing, returns {"error": "data_unavailable", "machine_id": machine_id}
      Risk tier: READ (autonomous)
    """
    inputs = current()
    if inputs and inputs["machine_id"] == machine_id:
        if inputs["telemetry_status"] == "DATA_UNAVAILABLE":
            return {"error": "data_unavailable", "machine_id": machine_id, "window": window}
        if inputs.get("history"):                    # a run started from the simulated month
            return serve_history(inputs["history"], window, sensors)
        if inputs["telemetry_status"] == "OK" and window != "dropout":
            return _history(machine_id, window, inputs["readings"], sensors)
        readings = {s: [v] for s, v in inputs["readings"].items() if s in sensors}
        return {"machine_id": machine_id, "window": window, "readings": readings,
                "summary": {s: {"latest": vs[-1]} for s, vs in readings.items()},
                "sensor_status": inputs["telemetry_status"],
                "sensor_status_detail": "run-scoped simulated snapshot",
                "source": "simulation"}
    filename = DATA_DIR / f"{machine_id}_{window}.json"
    if not filename.exists():
        return {"error": "data_unavailable", "machine_id": machine_id, "window": window}

    with open(filename, encoding="utf-8") as f:
        raw = json.load(f)

    filtered = {k: v for k, v in raw["readings"].items() if k in sensors}
    return {
        "machine_id": machine_id,
        "window": window,
        "readings": filtered,
        "summary": raw.get("summary", {}),
        "data_timestamp": raw.get("data_timestamp"),
        # sensor_status surfaces telemetry health. "INTERRUPTED" means the feed
        # dropped mid-window — the agent must NOT predict on partial data (escalation path).
        "sensor_status": raw.get("sensor_status", "OK"),
        "sensor_status_detail": raw.get("sensor_status_detail"),
    }
