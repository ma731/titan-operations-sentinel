import json
from pathlib import Path

from .runtime_inputs import current

DATA_DIR = Path(__file__).parent.parent / "data" / "alerts"


def alert_triage(plant_id: str) -> dict:
    """
    Triages the raw plant alert stream down to the few actionable, deduplicated alerts.

    Tool catalog:
      Input:  plant_id (str)
      Output: total/severity counts + ranked list of deduplicated critical alerts
      Use when: deciding which of thousands of daily alerts deserve agent attention (challenge 1)
      Do NOT use: to assess a specific machine's health — use sensor_query for that
      Fallback: if stream unavailable, returns {"error": "alert_stream_unavailable"}
      Risk tier: READ (autonomous)
    """
    view = (current().get("plant_view") or {}).get("triage") or {}
    if plant_id in view:                     # a run started from the simulated month
        return view[plant_id]
    f = DATA_DIR / "alert_stream.json"
    if not f.exists():
        return {"error": "alert_stream_unavailable", "plant_id": plant_id}
    with open(f, encoding="utf-8") as fh:
        data = json.load(fh)
    return {
        "plant_id": plant_id,
        "total_alerts_today": data.get("total_alerts_today"),
        "by_severity": data.get("by_severity"),
        "deduplicated_critical_count": data.get("deduplicated_critical"),
        "critical_alerts_ranked": sorted(
            data.get("critical", []), key=lambda a: a.get("priority_score", 0), reverse=True
        ),
    }
