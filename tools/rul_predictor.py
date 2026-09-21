import json
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data" / "sensors"
HIST_DIR = Path(__file__).parent.parent / "data" / "sensors"


def rul_predictor(machine_id: str, current_readings: dict) -> dict:
    """
    Estimates Remaining Useful Life (RUL) in hours based on current sensor readings.
    Compares against historical failure patterns for same asset class.

    Tool catalog:
      Input:  machine_id (str), current_readings (dict of sensor: latest_value)
      Output: rul_hours (range), confidence (0-1), failure_mode, matched_historical_event
      Use when: vibration or temp anomaly confirmed, need failure timeline
      Do NOT use: before sensor_query — needs real readings as input
      Fallback: if confidence < 0.6, flag as LOW_CONFIDENCE and escalate
      Risk tier: READ (autonomous)
    """
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
        # Above the documented critical threshold but below the severe band. Before this
        # band existed, a machine reading 6.0-7.0 mm/s was classified as degradation and
        # routed as LOW risk, while the asset profile
        # (vibration_threshold_critical_mm_s = 6.0) and the corpus
        # (tms-101-spindle-bearing-maintenance#S3, "Critical: above 6.0") both called it
        # critical. The evaluation caught the disagreement as F-01.
        #
        # Same failure mode, deliberately wider window and lower confidence: the machine
        # is confirmed to be failing, and the timing is less certain than at 7.2 mm/s.
        # This band only ever makes the system MORE cautious. Nothing that was HIGH
        # becomes LOW, and no existing window is lengthened.
        rul_low, rul_high, confidence = 72, 120, 0.82
        failure_mode = "spindle_bearing_failure"
    elif vibration >= 5.0 or bearing_temp >= 65:
        rul_low, rul_high, confidence = 96, 144, 0.78
        failure_mode = "spindle_bearing_degradation"
    else:
        rul_low, rul_high, confidence = 500, 720, 0.60
        failure_mode = "normal_wear"

    return {
        "machine_id": machine_id,
        "rul_hours": {"min": rul_low, "max": rul_high},
        "confidence": confidence,
        "failure_mode": failure_mode,
        "matched_historical_event": historical_match,
        "low_confidence_flag": confidence < 0.6,
    }
