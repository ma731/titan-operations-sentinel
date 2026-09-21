import json
from pathlib import Path

from .runtime_inputs import current

DATA_DIR = Path(__file__).parent.parent / "data" / "sensors"


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
