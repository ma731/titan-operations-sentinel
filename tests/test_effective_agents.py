"""The patterns from Anthropic's 'Building Effective Agents', each tested without a model:
evaluator-optimizer (plan check + one revision), mistake-proof tool arguments, and
parallel sectioning of supply chain and production (TOS_PARALLEL=1).
"""
import pytest
from langgraph.types import Command

import graph
import policy
from eval.scenarios import load_scenarios
from tests.test_graph_offline import ScriptedAgent
from tools import lc
from tools.runtime_inputs import runtime_inputs

RECORDED_PLAN = """[AUTO] Throttle CNC-07-LEI spindle to 60% within OEM safe limits (buys runway to the window).
[AUTO] Reroute jobs J4421-J4425 to CNC-08-LEI; notify shift lead.
[APPROVE] Authorized, Schaeffler P-4421 expedite, 18h, EUR 3,200.
[APPROVE] Authorized, Saturday 06:00 emergency bearing replacement window.
[MONITOR] Watch vibration + bearing temp hourly until parts land; re-trigger if RUL shortens."""


# ---------- evaluator: policy.check_plan ----------
def test_the_recorded_demo_plan_passes_the_check():
    assert policy.check_plan(RECORDED_PLAN, risk="HIGH") == []


@pytest.mark.parametrize("line, required", [
    ("[AUTO] Place an order for bearing kit P-4421 from Schaeffler", "APPROVE"),
    ("[AUTO] Ship the seal set, cost EUR 2,000", "APPROVE"),
    ("[APPROVE] Bypass the guard interlock to keep CNC-07 running", "ESCALATE"),
    ("[AUTO] Disable safety light curtain on cell 2", "ESCALATE"),
])
def test_under_tiered_actions_are_caught(line, required):
    issues = policy.check_plan(line + "\n[MONITOR] watch it", risk="HIGH")
    assert [i["required"] for i in issues if i["rule"] == "tier"] == [required]


def test_more_cautious_tiers_are_allowed():
    assert policy.check_plan("[APPROVE] Reroute jobs to CNC-08\n[MONITOR] watch", risk="HIGH") == []


def test_high_risk_needs_a_monitor_line_and_format_is_required():
    assert policy.check_plan("[AUTO] Reroute jobs to CNC-08", risk="HIGH")[0]["rule"] == "monitor"
    assert policy.check_plan("Order the part and fix it.", risk="LOW")[0]["rule"] == "format"


def test_enforce_plan_corrects_tiers_in_code():
    bad = "[AUTO] Purchase bearing kit P-4421\n[AUTO] Reroute jobs"
    fixed = policy.enforce_plan(bad, policy.check_plan(bad, risk="HIGH"))
    assert "[APPROVE] Purchase bearing kit P-4421" in fixed
    assert policy.check_plan(fixed, risk="HIGH") == []


# ---------- optimizer loop inside the graph ----------
def _state():
    return {"run_id": "RUN-TEST-EVAL", "risk": "HIGH"}


def test_a_good_plan_is_left_alone(monkeypatch):
    calls = []
    monkeypatch.setattr(graph.llm, "complete", lambda *a, **k: calls.append(1) or "x")
    plan, events = graph._evaluate_and_revise(_state(), RECORDED_PLAN)
    assert plan == RECORDED_PLAN and not calls
    assert events[0]["check"] == "passed"


def test_a_bad_plan_gets_one_revision(monkeypatch):
    monkeypatch.setattr(graph.llm, "complete", lambda *a, **k: RECORDED_PLAN)
    plan, events = graph._evaluate_and_revise(_state(), "[AUTO] Purchase bearing kit\n[MONITOR] watch")
    assert plan == RECORDED_PLAN
    assert [e["check"] for e in events] == ["failed", "revised"]


def test_a_revision_that_still_fails_is_corrected_in_code(monkeypatch):
    monkeypatch.setattr(graph.llm, "complete", lambda *a, **k: "[AUTO] Purchase bearing kit\n[MONITOR] watch")
    plan, events = graph._evaluate_and_revise(_state(), "[AUTO] Purchase bearing kit\n[MONITOR] watch")
    assert "[APPROVE] Purchase bearing kit" in plan
    assert events[-1]["check"] == "corrected_in_code"


def test_no_model_means_no_check_and_no_rewrite():
    stub = "[LLM UNAVAILABLE — TEMPLATED FALLBACK]\nsomething"
    plan, events = graph._evaluate_and_revise(_state(), stub)
    assert plan == stub and "skipped" in events[0]["message"]


# ---------- mistake-proof tool arguments ----------
@pytest.mark.parametrize("value, expected", [(7500, 7500), ("7500", 7500), ("180000/24", 7500),
                                             ("1,200", 1200), ("€3,200", 3200), ("-2+5*2", 8)])
def test_numbers_accept_plain_values_and_simple_arithmetic(value, expected):
    assert lc.as_number(value) == pytest.approx(expected)


@pytest.mark.parametrize("value", ["__import__('os').system('x')", "abc", "1/0", True, None, [1]])
def test_anything_else_is_refused_with_a_clear_message(value):
    with pytest.raises(ValueError, match="number"):
        lc.as_number(value, "downtime_cost_per_hour")


def test_expedite_tool_gives_the_same_answer_for_arithmetic_strings():
    opts = [{"label": "A", "cost_eur": 3200, "lead_time_hours": 18, "risk_level": "LOW"}]
    plain = lc.expedite_cost.invoke({"options": opts, "downtime_cost_per_hour": 7500,
                                     "failure_window_hours": 52, "baseline_lead_time_hours": 192})
    text = lc.expedite_cost.invoke({"options": opts, "downtime_cost_per_hour": "180000/24",
                                    "failure_window_hours": "52", "baseline_lead_time_hours": "8*24"})
    assert plain == text
    bad = lc.expedite_cost.invoke({"options": opts, "downtime_cost_per_hour": "a lot",
                                   "failure_window_hours": 52, "baseline_lead_time_hours": 192})
    assert "error" in bad and "downtime_cost_per_hour" in bad["error"]


# ---------- parallel sectioning: the same guarantees on all 34 labelled scenarios ----------
@pytest.mark.parametrize("scenario", load_scenarios(), ids=lambda s: s.id)
def test_parallel_mode_keeps_every_guarantee(scenario, monkeypatch):
    s = scenario
    monkeypatch.setenv("TOS_PARALLEL", "1")
    monkeypatch.setenv("TOS_APPROVAL_CHANNEL", "console")
    monkeypatch.setattr(graph.llm, "complete", lambda *a, **k: "[MONITOR] Reviewed findings.")
    monkeypatch.setattr(graph, "build_agents", lambda: {n: ScriptedAgent(n, s) for n in graph.AGENT_NAMES})
    g = graph.build_graph()
    state = graph.make_initial_state(s.mode, s.alert)
    state["proposed_actions"] = s.proposed_actions
    cfg = {"configurable": {"thread_id": state["run_id"]}, "recursion_limit": 50}
    with runtime_inputs(s.alert["machine_id"], s.readings, s.telemetry_status, s.sourcing):
        first = list(g.stream(state, cfg))
        paused = any("__interrupt__" in c for c in first)
        assert paused == (s.expected["needs_approval"] and not s.expected["halt"])
        if paused:
            list(g.stream(Command(resume={"decision": "approve", "approver": "test"}), cfg))
        final = g.get_state(cfg).values
    assert final["risk"] == s.expected["risk"]
    assert final["status"] == s.expected["terminal_status"]
    assert set(final["visited"]) == set(s.expected["agents_required"])
    assert bool(final.get("halt")) == s.expected["halt"]
    went_parallel = any(e.get("how") == "parallel" for e in final["trace"] if e.get("type") == "route")
    assert went_parallel == (s.expected["risk"] == "HIGH")
    if went_parallel:                                   # compliance still gates last
        assert final["visited"][-1] == "compliance_safety"
