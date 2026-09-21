"""Unit tests for the tools against the baked-in Friday Cascade scenario data.
Fully offline — no model or network required. Run: python -m pytest tests/"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.alert_triage import alert_triage
from tools.asset_profile import asset_profile
from tools.expedite_cost import expedite_cost
from tools.job_reroute import job_reroute
from tools.maintenance_schedule import maintenance_schedule
from tools.notify import notify
from tools.parts_inventory import parts_inventory
from tools.quality_history import quality_history
from tools.robot_cell_status import robot_cell_status
from tools.rul_predictor import rul_predictor
from tools.safety_gate import safety_gate
from tools.sensor_query import sensor_query
from tools.shift_conflict_check import shift_conflict_check
from tools.supplier_catalog import supplier_catalog
from tools.telemetry_correlate import telemetry_correlate
from tools.tier2_supplier_risk import tier2_supplier_risk
from tools.work_order_draft import work_order_draft


def test_sensor_query_happy():
    r = sensor_query("CNC-07-LEI", "72h", ["vibration", "bearing_temp"])
    assert r["sensor_status"] == "OK"
    assert r["summary"]["vibration"]["current"] == 7.2


def test_sensor_query_dropout_is_interrupted():
    r = sensor_query("CNC-07-LEI", "dropout", ["vibration"])
    assert r["sensor_status"] == "INTERRUPTED"


def test_sensor_query_missing_file_errors():
    assert sensor_query("CNC-99-XXX", "72h", ["vibration"]).get("error") == "data_unavailable"


def test_rul_predictor_critical():
    r = rul_predictor("CNC-07-LEI", {"vibration": 7.2, "bearing_temp": 72})
    assert r["failure_mode"] == "spindle_bearing_failure"
    assert r["confidence"] == 0.95
    assert r["low_confidence_flag"] is False
    assert r["rul_hours"] == {"min": 52, "max": 76}


def test_asset_profile_bom():
    p = asset_profile("CNC-07-LEI")
    bom = p["failure_modes"]["spindle_bearing_failure"]["bom"]
    assert {b["part_id"] for b in bom} == {"P-4421", "P-7803"}


def test_parts_inventory_shortage():
    r = parts_inventory(["P-4421", "P-7803"], "LEI")
    assert r["parts"]["P-4421"]["on_site_qty"] == 0
    assert r["parts"]["P-7803"]["on_site_qty"] == 1


def test_supplier_catalog_default_has_options():
    r = supplier_catalog(["P-4421", "P-7803"])
    assert "option_b_schaeffler_expedite" in r["combined_options"]


def test_supplier_catalog_edge_none_fit_window():
    r = supplier_catalog(["P-4421", "P-7803"], scenario="edge")
    leads = [o["lead_time_hours"] for k, o in r["combined_options"].items() if k != "note"]
    assert all(lead > 52 for lead in leads)  # nothing fits the 52h RUL minimum


def test_expedite_cost_prefers_fitting_low_risk_option():
    opts = [
        {"label": "warehouse", "cost_eur": 420, "lead_time_hours": 36, "risk_level": "MEDIUM"},
        {"label": "schaeffler", "cost_eur": 3200, "lead_time_hours": 18, "risk_level": "LOW"},
    ]
    r = expedite_cost(opts, downtime_cost_per_hour=7500, failure_window_hours=52)
    assert r["recommendation"] == "schaeffler"          # LOW risk fits → ranked first
    assert r["options_ranked"][0]["roi_ratio"] == 79.7  # (52-18)*7500/3200


def test_maintenance_schedule_exposes_emergency_slot():
    r = maintenance_schedule("LEI", "7d")
    assert r["emergency_window_slots"]
    assert r["emergency_window_slots"][0]["requires_approval"] is True


# --- challenge 3/4/5 tools ------------------------------------------------- #
def test_alert_triage_filters_noise():
    r = alert_triage("LEI")
    assert r["total_alerts_today"] > 22000
    assert r["deduplicated_critical_count"] == 3
    assert r["critical_alerts_ranked"][0]["alert_id"] == "ALT-22847"  # highest priority first


def test_tier2_risk_flags_schaeffler():
    r = tier2_supplier_risk(["SUP-SCHAEFFLER-DE"])
    assert r["suppliers"]["SUP-SCHAEFFLER-DE"]["overall_tier2_risk"] == "ELEVATED"


def test_job_reroute_uses_equivalent_machines():
    r = job_reroute("CNC-07-LEI", ["J4421", "J4422"])
    assert set(r["proposed_assignment"].values()) <= {"CNC-05-LEI", "CNC-08-LEI"}


def test_robot_cell_status_has_shared_operator():
    cells = {c["cell_id"]: c for c in robot_cell_status("LEI")["cells"]}
    assert cells["CELL-05-LEI"]["operators_assigned"] == cells["CELL-07-LEI"]["operators_assigned"]


def test_shift_conflict_detected():
    assert shift_conflict_check("LEI", ["CNC-05-LEI"])["has_conflict"] is True


def test_quality_and_telemetry_correlation():
    assert quality_history("CNC-07-LEI")["trend"] == "rising"
    assert telemetry_correlate("CNC-07-LEI")["correlation"] == "POSITIVE"


def test_safety_gate_verdicts():
    assert safety_gate("reduce spindle speed to OEM safe limit")["verdict"] == "OK"
    assert safety_gate("bypass the safety interlock")["verdict"] == "HALT"
    assert safety_gate("open the machine for emergency maintenance")["verdict"] == "ESCALATE"


# --- scheduling / draft tools (challenge 1/2 shared) ----------------------- #
def test_work_order_draft_is_pending_approval():
    wo = work_order_draft(
        machine_id="CNC-07-LEI", plant_id="LEI", failure_mode="spindle_bearing_failure",
        parts_required=[{"part_id": "P-4421", "qty": 1}], proposed_window={"start": "Sat 06:00"},
        technicians_required=["mechanical"], estimated_duration_hours=4,
        actions=[{"tier": "APPROVE", "action": "emergency bearing replacement"}],
    )
    assert wo["status"] == "DRAFT_PENDING_APPROVAL"
    assert wo["incomplete_flag"] is False
    assert wo["approval_required_from"] == "plant_manager"


def test_work_order_draft_flags_incomplete():
    wo = work_order_draft(
        machine_id="CNC-07-LEI", plant_id="LEI", failure_mode="spindle_bearing_failure",
        parts_required=[], proposed_window={}, technicians_required=[],
        estimated_duration_hours=0, actions=[],
    )
    assert wo["incomplete_flag"] is True


def test_notify_computes_roi_and_links_wo():
    n = notify(
        recipient_role="plant_manager", subject="Approve emergency procurement",
        situation_summary="CNC-07-LEI spindle bearing failure predicted 52-76h out",
        recommended_actions=[{"tier": "APPROVE", "action": "expedite P-4421"}],
        cost_of_inaction_eur=180000, cost_of_recommended_plan_eur=3200,
        decision_deadline_utc="2026-06-13T08:00:00Z", work_order_id="WO-CNC-07-LEI-202606121432",
    )
    assert n["status"] == "DRAFT_PENDING_SEND"
    assert n["body"]["roi_ratio"] == 56.2                       # 180000 / 3200
    assert n["body"]["linked_work_order"] == "WO-CNC-07-LEI-202606121432"


# --- Learning loop: case memory recall + write-back ---------------------------- #
def test_recall_returns_best_precedent():
    from tools.recall_cases import recall_similar_cases
    r = recall_similar_cases("CNC-07-LEI", "vibration", "spindle-bearing vibration wear")
    assert r["matches"][0]["id"] == "INC-0288"      # closest seeded precedent
    assert r["matches"][0]["match_pct"] >= 90
    assert r["rul_accuracy_pct"] is not None         # computed over closed cases


def test_append_case_grows_library(tmp_path, monkeypatch):
    import json

    import tools.recall_cases as rc
    tmp = tmp_path / "case_library.json"             # temp copy so the seed file isn't polluted
    tmp.write_text(json.dumps({"cases": []}), encoding="utf-8")
    monkeypatch.setattr(rc, "_LIB", tmp)
    assert rc.append_case({"id": "RUN-X", "actual_failure_h": None}) is True
    assert json.loads(tmp.read_text(encoding="utf-8"))["cases"][-1]["id"] == "RUN-X"


# --- Risk: the €500 autonomy ceiling correctly classifies the two scenarios ----- #
def test_cost_ceiling_gates_over_500_runs_autonomous_under():
    from graph import COST_CEILING_EUR
    from tools.expedite_cost import expedite_cost
    edge = expedite_cost([{"label": "MUC transfer", "cost_eur": 420, "lead_time_hours": 36, "risk_level": "LOW"}], 7500, 52)
    assert edge["options_ranked"][0]["cost_eur"] <= COST_CEILING_EUR     # €420 → autonomous
    happy = expedite_cost([{"label": "Schaeffler", "cost_eur": 3200, "lead_time_hours": 18, "risk_level": "LOW"}], 7500, 52)
    assert happy["options_ranked"][0]["cost_eur"] > COST_CEILING_EUR     # €3,200 → needs approval


def test_reconcile_closes_the_loop(tmp_path, monkeypatch):
    import json

    import tools.recall_cases as rc
    tmp = tmp_path / "case_library.json"
    tmp.write_text(json.dumps({"cases": []}), encoding="utf-8")
    monkeypatch.setattr(rc, "_LIB", tmp)
    rc.append_case({"id": "RUN-Z", "predicted_rul_h": [50, 74], "actual_failure_h": None, "in_window": None})
    assert rc.reconcile_case("RUN-Z", 58) is True          # 58h is inside the 50-74h window
    case = json.loads(tmp.read_text(encoding="utf-8"))["cases"][-1]
    assert case["actual_failure_h"] == 58 and case["in_window"] is True
    assert rc.reconcile_case("RUN-Z", 58) is False         # already reconciled


def test_gate_requires_window_fit():
    """A cheap option (under the ceiling) that does NOT fit the failure window must still
    route to a human, not run autonomously."""
    from graph import COST_CEILING_EUR
    from tools.expedite_cost import expedite_cost
    r = expedite_cost([{"label": "slow-cheap", "cost_eur": 300, "lead_time_hours": 60, "risk_level": "LOW"}], 7500, 52)
    top = r["options_ranked"][0]
    autonomous = top["cost_eur"] <= COST_CEILING_EUR and top["fits_failure_window"]
    assert autonomous is False                     # €300 but misses the 52h window → gate


def test_reconcile_due_resolves_known_outcomes(tmp_path, monkeypatch):
    import json

    import tools.recall_cases as rc
    tmp = tmp_path / "case_library.json"
    tmp.write_text(json.dumps({"cases": [{"id": "RUN-D", "predicted_rul_h": [50, 74], "actual_failure_h": None, "in_window": None}]}), encoding="utf-8")
    monkeypatch.setattr(rc, "_LIB", tmp)
    assert rc.reconcile_due({"RUN-D": 60}) == 1     # 60h inside 50-74 window
    assert json.loads(tmp.read_text(encoding="utf-8"))["cases"][0]["in_window"] is True
    assert rc.reconcile_due({}) == 0                # safe no-op without outcomes
