"""
LangChain @tool wrappers for the TOS tool functions.

The ReAct agents in agents/factory.py bind these. The docstrings here are what the LLM
reads to decide *which* tool to call and *when* — so they are written for the model,
not for humans (the human-facing spec lives in docs/tool_catalog.md). Each wrapper
just calls the pure function in tools/; no logic lives here.
"""
from __future__ import annotations

import ast
import operator

from langchain_core.tools import tool

from . import knowledge_graph as _kg
from .alert_triage import alert_triage as _alert_triage
from .asset_profile import asset_profile as _asset_profile
from .audit_assemble import audit_assemble as _audit_assemble
from .doc_search import search_technical_docs as _search_technical_docs
from .expedite_cost import expedite_cost as _expedite_cost
from .job_reroute import job_reroute as _job_reroute
from .maintenance_schedule import maintenance_schedule as _maintenance_schedule
from .notify import notify as _notify
from .parts_inventory import parts_inventory as _parts_inventory
from .quality_history import quality_history as _quality_history
from .recall_cases import recall_similar_cases as _recall_similar_cases
from .robot_cell_status import robot_cell_status as _robot_cell_status
from .rul_predictor import rul_predictor as _rul_predictor
from .safety_gate import safety_gate as _safety_gate
from .sensor_query import sensor_query as _sensor_query
from .shift_conflict_check import shift_conflict_check as _shift_conflict_check
from .supplier_catalog import supplier_catalog as _supplier_catalog
from .telemetry_correlate import telemetry_correlate as _telemetry_correlate
from .tier2_supplier_risk import tier2_supplier_risk as _tier2_supplier_risk
from .work_order_draft import work_order_draft as _work_order_draft

# Mistake-proof numbers (the "poka-yoke" tool design in Anthropic's Building Effective
# Agents). Models often write a number as arithmetic, e.g. 180000/24. As a raw JSON value
# that is invalid and the provider rejects the whole tool call; as a string it is fine.
# So numeric arguments accept a number OR a simple arithmetic string, computed safely
# here (numbers and + - * / only, no names, no calls), instead of only being asked for
# plain numbers in the prompt.
_OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
        ast.Div: operator.truediv, ast.USub: operator.neg, ast.UAdd: operator.pos}


def as_number(value, name: str = "value") -> float:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be a number, got {value!r}")
    if isinstance(value, (int, float)):
        return value
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a number, got {value!r}")
    text = value.replace(",", "").replace("€", "").replace("EUR", "").strip()

    def ev(node):
        if isinstance(node, ast.Expression):
            return ev(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
            return node.value
        if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
            return _OPS[type(node.op)](ev(node.left), ev(node.right))
        if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
            return _OPS[type(node.op)](ev(node.operand))
        raise ValueError(f"{name} must be a number or simple arithmetic like '180000/24', got {value!r}")
    try:
        return ev(ast.parse(text, mode="eval"))
    except (SyntaxError, ZeroDivisionError) as exc:
        raise ValueError(f"{name} must be a number or simple arithmetic like '180000/24', got {value!r}") from exc


def _numbers(**kw) -> dict:
    """Convert named numeric arguments; None stays None."""
    return {k: (None if v is None else as_number(v, k)) for k, v in kw.items()}


# --- Reliability (challenge 1) -------------------------------------------- #
@tool
def alert_triage(plant_id: str) -> dict:
    """Triage the plant's raw alert stream down to the few deduplicated critical alerts.
    Call first to find which machine actually needs attention."""
    return _alert_triage(plant_id)


@tool
def sensor_query(machine_id: str, window: str, sensors: list[str]) -> dict:
    """Get time-series sensor readings (vibration, bearing_temp, spindle_current) for a
    machine over a window ('72h' or 'dropout'). Use before predicting failure."""
    return _sensor_query(machine_id, window, sensors)


@tool
def rul_predictor(machine_id: str, current_readings: dict) -> dict:
    """Estimate Remaining Useful Life (hours) + confidence from REAL sensor readings.
    Pass the latest values from sensor_query as current_readings. Never guess readings.
    Optionally add current_readings["series"] = sensor_query's "readings" block so the
    estimate reads the vibration rate, not only the level."""
    return _rul_predictor(machine_id, current_readings)


@tool
def asset_profile(machine_id: str) -> dict:
    """Get machine specs, the bill of materials per failure mode, technicians, safe speed
    limits, and equivalent machines."""
    return _asset_profile(machine_id)


@tool
def recall_similar_cases(machine_id: str, sensor: str, signature: str) -> dict:
    """Recall the most similar PAST incidents from case memory (predicted vs actual RUL,
    the decision taken, and the outcome). Call after sensor_query to ground your
    assessment in precedent. Pass the failure signature you observed, e.g.
    'spindle-bearing vibration'."""
    return _recall_similar_cases(machine_id, sensor, signature)


@tool
def maintenance_schedule(plant_id: str, horizon: str = "7d") -> dict:
    """Get the plant's scheduled + emergency maintenance windows over a horizon ('7d'/'14d'/
    '30d'). Compare the next available window against the RUL to find the schedule gap."""
    return _maintenance_schedule(plant_id, horizon)


# --- Shared: retrieval over the technical reference corpus (RAG) ----------- #
@tool
def search_technical_docs(query: str, k: int = 4) -> dict:
    """Search the technical reference corpus (maintenance standards, OSHA lockout/tagout
    and machine guarding, ISO robot safety, IATF traceability, sourcing and reroute
    policy) and return passages WITH citations. Use it to ground a severity band, a
    life-estimate rule, an authority limit, or a safety procedure in the written standard
    instead of asserting it. Ask a full question, e.g. 'may an automated system authorise
    bypassing a safety interlock'. Cite the returned `citation` field in your report."""
    return _search_technical_docs(query, k)


# --- Supply Chain (challenge 2) ------------------------------------------- #
@tool
def parts_inventory(parts: list[str], plant_id: str) -> dict:
    """Check on-site + warehouse stock for parts at a plant. Pass a sister plant id
    (AMS, MUC) to check cross-plant stock."""
    return _parts_inventory(parts, plant_id)


@tool
def supplier_catalog(part_ids: list[str], scenario: str = "default") -> dict:
    """Get supplier lead times, expedite options, and pre-built combined options for parts.
    Use scenario='edge' only if told the default supply is disrupted."""
    return _supplier_catalog(part_ids, scenario)


@tool
def expedite_cost(options: list[dict], downtime_cost_per_hour: float | str,
                  failure_window_hours: float | str, baseline_lead_time_hours: float | str,
                  failure_window_max_hours: float | str | None = None) -> dict:
    """Rank procurement options by fit-to-window, risk, then downtime avoided per euro.
    Each option = {label, cost_eur, lead_time_hours, risk_level}.
    failure_window_hours = RUL minimum; failure_window_max_hours = RUL maximum.
    baseline_lead_time_hours = the standard (non-expedited) lead time from
    supplier_catalog: when the part would arrive if nobody acted.
    Numbers may be plain numbers or simple arithmetic as a string, e.g. "180000/24"."""
    try:
        n = _numbers(downtime_cost_per_hour=downtime_cost_per_hour, failure_window_hours=failure_window_hours,
                     baseline_lead_time_hours=baseline_lead_time_hours, failure_window_max_hours=failure_window_max_hours)
    except ValueError as exc:
        return {"error": str(exc)}
    return _expedite_cost(options, n["downtime_cost_per_hour"], int(round(n["failure_window_hours"])),
                          n["baseline_lead_time_hours"], n["failure_window_max_hours"])


@tool
def tier2_supplier_risk(supplier_ids: list[str]) -> dict:
    """Reveal Tier-2 (supplier's supplier) dependencies and risk for Tier-1 supplier IDs.
    Use to sanity-check a sourcing choice for hidden upstream risk."""
    return _tier2_supplier_risk(supplier_ids)


@tool
def work_order_draft(machine_id: str, plant_id: str, failure_mode: str,
                     parts_required: list[dict], proposed_window: dict,
                     technicians_required: list[str], estimated_duration_hours: float | str,
                     actions: list[dict]) -> dict:
    """Draft a DRAFT_PENDING_APPROVAL work order once the parts plan is confirmed. Not
    committed until a human releases it. Call after expedite_cost picks an option."""
    try:
        hours = int(round(as_number(estimated_duration_hours, "estimated_duration_hours")))
    except ValueError as exc:
        return {"error": str(exc)}
    return _work_order_draft(machine_id, plant_id, failure_mode, parts_required,
                             proposed_window, technicians_required, hours, actions)


@tool
def notify(recipient_role: str, subject: str, situation_summary: str,
           recommended_actions: list[dict], cost_of_inaction_eur: float | str,
           cost_of_recommended_plan_eur: float | str, decision_deadline_utc: str,
           work_order_id: str | None = None) -> dict:
    """Draft an approval-request notification for the decision-maker (e.g. plant_manager).
    Reference the work_order_id from work_order_draft. Drafted, not sent.
    Costs may be plain numbers or simple arithmetic as a string."""
    try:
        n = _numbers(cost_of_inaction_eur=cost_of_inaction_eur, cost_of_recommended_plan_eur=cost_of_recommended_plan_eur)
    except ValueError as exc:
        return {"error": str(exc)}
    return _notify(recipient_role, subject, situation_summary, recommended_actions,
                   n["cost_of_inaction_eur"], n["cost_of_recommended_plan_eur"],
                   decision_deadline_utc, work_order_id)


# --- Intelligence layer: the knowledge graph ------------------------------ #
@tool
def supplier_impact(supplier_id: str) -> dict:
    """Everything that depends on a supplier, Tier-1 or Tier-2: parts, failure modes,
    machines, plants, production value exposed per day, and which parts have no other
    source. Call when tier2_supplier_risk flags ELEVATED, to size what the risk reaches."""
    return _kg.supplier_impact(supplier_id)


@tool
def trace_dependency(source: str, target: str) -> dict:
    """The chain of relationships linking two things, e.g. a Tier-2 supplier and a machine.
    Use it to explain HOW a risk reaches a machine, and cite the path in your report."""
    return _kg.trace_dependency(source, target)


@tool
def machine_dependencies(machine_id: str) -> dict:
    """What one machine depends on: parts per failure mode with stock and suppliers (and
    their Tier-2 risk), technicians, its robot cell and operators, equivalent machines."""
    return _kg.machine_dependencies(machine_id)


@tool
def single_points_of_failure() -> dict:
    """Plant-wide weak spots: parts short on site with one supplier, single-source Tier-2
    dependencies, operators assigned to several cells."""
    return _kg.single_points_of_failure()


# --- Production & Human-Robot (challenge 3) ------------------------------- #
@tool
def job_reroute(machine_id: str, jobs: list[str]) -> dict:
    """Propose how to reroute a down machine's jobs onto equivalent machines with spare
    capacity. Returns candidates + a proposed assignment."""
    return _job_reroute(machine_id, jobs)


@tool
def robot_cell_status(plant_id: str) -> dict:
    """Get robot-cell state: robots, assigned operators, collaborative mode, recent safety
    shutdowns. Use to spot human-robot coordination risk in a reroute."""
    return _robot_cell_status(plant_id)


@tool
def shift_conflict_check(plant_id: str, target_machines: list[str] | None = None) -> dict:
    """Check the shift roster for operator/technician conflicts affecting target machines
    (e.g. one operator double-booked across two cells)."""
    return _shift_conflict_check(plant_id, target_machines)


# --- Quality & Traceability (challenge 4) --------------------------------- #
@tool
def quality_history(machine_id: str) -> dict:
    """Get recent MES/QMS quality metrics (escape rate vs baseline, defects) for a machine."""
    return _quality_history(machine_id)


@tool
def telemetry_correlate(machine_id: str) -> dict:
    """Correlate a machine's quality escapes with its sensor telemetry to find whether a
    mechanical fault is driving the defects (the MES/QMS↔OT link)."""
    return _telemetry_correlate(machine_id)


# --- Compliance & Safety (challenge 5) ------------------------------------ #
@tool
def safety_gate(action_description: str) -> dict:
    """Gate a proposed action against OSHA/machine-safety rules. Returns verdict
    OK | ESCALATE | HALT. HALT overrides every other agent. Call on each proposed action."""
    return _safety_gate(action_description)


@tool
def audit_assemble(run_id: str) -> dict:
    """Reconstruct the full decision timeline for this run from the audit log, for the
    compliance/OSHA trail. Pass the current run_id."""
    return _audit_assemble(run_id)


# Grouped per agent — imported by agents/factory.py.
RELIABILITY_TOOLS = [alert_triage, sensor_query, rul_predictor, recall_similar_cases,
                     asset_profile, maintenance_schedule, search_technical_docs]
SUPPLY_CHAIN_TOOLS = [parts_inventory, supplier_catalog, expedite_cost, tier2_supplier_risk,
                      supplier_impact, trace_dependency, work_order_draft, notify]
PRODUCTION_TOOLS = [job_reroute, robot_cell_status, shift_conflict_check]
QUALITY_TOOLS = [quality_history, telemetry_correlate]
COMPLIANCE_TOOLS = [safety_gate, audit_assemble, search_technical_docs]
