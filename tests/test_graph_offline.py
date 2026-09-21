"""Real LangGraph transitions and interrupts with scripted specialist messages.

Tools execute normally on labelled inputs; only model choice/prose is replaced. These
tests measure integration, not model quality, and require no provider or network.
"""
import json

import pytest
from langchain_core.messages import AIMessage, ToolMessage
from langgraph.types import Command

import graph
from eval.scenarios import load_scenarios
from tools.expedite_cost import expedite_cost
from tools.rul_predictor import rul_predictor
from tools.runtime_inputs import runtime_inputs
from tools.safety_gate import safety_gate
from tools.sensor_query import sensor_query
from tools.supplier_catalog import supplier_catalog


def messages(results):
    out = []
    for i, (name, result) in enumerate(results):
        out += [AIMessage(content="", tool_calls=[{"id": str(i), "name": name, "args": {}}]),
                ToolMessage(content=json.dumps(result), tool_call_id=str(i))]
    return out + [AIMessage(content="Assessment recorded.")]


class ScriptedAgent:
    def __init__(self, name, scenario):
        self.name, self.scenario = name, scenario

    def invoke(self, *args, **kwargs):
        s = self.scenario
        mid = s.alert["machine_id"]
        results = []
        if self.name == "reliability":
            sensor = sensor_query(mid, "72h", list(s.readings))
            readings = {k: v[-1] for k, v in sensor.get("readings", {}).items()}
            results = [("sensor_query", sensor), ("rul_predictor", rul_predictor(mid, readings))]
        elif self.name == "supply_chain":
            quotes = supplier_catalog([])["combined_options"]
            results = [("expedite_cost", expedite_cost(
                quotes, s.sourcing["downtime_cost_per_hour"], s.sourcing["failure_window_hours"]))]
        elif self.name == "compliance_safety":
            results = [("safety_gate", safety_gate(a)) for a in s.proposed_actions]
        return {"messages": messages(results)}


@pytest.fixture
def offline(monkeypatch):
    monkeypatch.setattr(graph.llm, "complete", lambda *a, **k: "[MONITOR] Reviewed findings.")
    monkeypatch.setenv("TOS_APPROVAL_CHANNEL", "console")


@pytest.mark.parametrize("scenario", load_scenarios(), ids=lambda s: s.id)
def test_labelled_scenarios_through_real_graph(scenario, monkeypatch, offline):
    s = scenario
    monkeypatch.setattr(graph, "build_agents", lambda: {
        name: ScriptedAgent(name, s) for name in graph.AGENT_NAMES})
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


@pytest.mark.parametrize("name", ["reliability", "compliance_safety"])
@pytest.mark.parametrize("failure", ["initialization", "invocation", "missing_tool"])
def test_critical_worker_failure_is_closed(name, failure, monkeypatch, offline):
    class Broken:
        def invoke(self, *a, **k):
            if failure == "invocation":
                raise RuntimeError("provider unavailable")
            return {"messages": [AIMessage(content="Everything looks fine.")]}

    def build():
        if failure == "initialization":
            raise RuntimeError("missing provider")
        return {name: Broken()}

    monkeypatch.setattr(graph, "build_agents", build)
    update = graph._make_worker(name)(graph.make_initial_state())
    assert update.get("escalate") if name == "reliability" else update.get("halt")


def test_earlier_halt_cannot_be_overwritten_by_later_ok(monkeypatch, offline):
    class Agent:
        def invoke(self, *a, **k):
            return {"messages": messages([
                ("safety_gate", {"verdict": "HALT"}), ("safety_gate", {"verdict": "OK"})])}
    monkeypatch.setattr(graph, "build_agents", lambda: {"compliance_safety": Agent()})
    assert graph._make_worker("compliance_safety")(graph.make_initial_state())["halt"]


@pytest.mark.parametrize("decision", ["reject", "unknown", None])
def test_unapproved_plan_never_reaches_synthesis_model(decision, monkeypatch):
    def forbidden(*a, **k):
        raise AssertionError("blocked plans must not be synthesized by a model")
    monkeypatch.setattr(graph.llm, "complete", forbidden)
    state = graph.make_initial_state()
    state.update(needs_approval=True, approval={"decision": decision})
    result = graph.synthesize(state)
    assert result["status"] == "rejected"
    assert "[AUTO]" not in result["final_plan"]


def test_halted_plan_never_reaches_synthesis_model(monkeypatch):
    monkeypatch.setattr(graph.llm, "complete", lambda *a, **k: pytest.fail("model called"))
    state = graph.make_initial_state()
    state["halt"] = True
    assert graph.synthesize(state)["status"] == "halted"


def test_supply_instruction_uses_assessed_failure_window():
    state = graph.make_initial_state()
    state.update(machine_id="CNC-07-LEI", plant_id="LEI", predicted_rul=[72, 120])
    assert "failure_window_hours=72" in graph._instruction("supply_chain", state)


def test_live_harness_uses_fixture_inputs_without_modifying_memory(monkeypatch, offline,
                                                                  isolate_case_library):
    from eval.live_eval import run_one
    scenario = next(s for s in load_scenarios() if s.expected["risk"] == "LOW")
    before = isolate_case_library.read_bytes()
    monkeypatch.setattr(graph, "build_agents", lambda: {
        name: ScriptedAgent(name, scenario) for name in graph.AGENT_NAMES})
    result = run_one(scenario)
    assert result["risk"] == "LOW"
    assert result["status"] == "complete"
    assert not result["reached_approval_gate"]
    assert isolate_case_library.read_bytes() == before
