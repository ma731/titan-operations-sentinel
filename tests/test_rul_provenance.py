"""Provenance must survive the whole way out, not just exist in a tool's return value.

A `source` field that only the tool knows about is worth nothing: the thing that matters
is whether a person reading a run can tell a measured prediction from a declared one.
These tests follow it from the tool, through the graph state, into the trace, and into
the audit log on disk.

This is the F-06 lesson applied to today's work: a unit-level result is not integration.
"""

from __future__ import annotations

import json

import pytest
from langchain_core.messages import AIMessage, ToolMessage

import audit_log
import graph
from ml.predict import SOURCE_DECLARED, SOURCE_FITTED
from tools.rul_predictor import rul_predictor

CNC = "CNC-07-LEI"
TURBINE = "TRB-01-LEI"
CRITICAL = {"vibration": 7.2, "bearing_temp": 72}


def _messages(results):
    out = []
    for i, (name, result) in enumerate(results):
        out += [
            AIMessage(content="", tool_calls=[{"id": str(i), "name": name, "args": {}}]),
            ToolMessage(content=json.dumps(result), tool_call_id=str(i)),
        ]
    return out + [AIMessage(content="Assessment recorded.")]


def _run_reliability(monkeypatch, rul_result: dict):
    """Drive the real reliability worker with one scripted rul_predictor result."""

    class Agent:
        def invoke(self, *a, **k):
            return {"messages": _messages([("rul_predictor", rul_result)])}

    monkeypatch.setattr(graph, "build_agents", lambda: {"reliability": Agent()})
    monkeypatch.setattr(graph.llm, "complete", lambda *a, **k: "[MONITOR] Reviewed.")
    state = graph.make_initial_state()
    # perceive normally lifts these out of the alert; we invoke the worker directly.
    state["machine_id"] = state["alert"]["machine_id"]
    state["plant_id"] = state["alert"].get("plant_id", "LEI")
    update = graph._make_worker("reliability")(state)
    assert "agent_error" not in update.get("status", ""), update.get("status")
    return update, state


# --------------------------------------------------------------------------- #
# The tool itself
# --------------------------------------------------------------------------- #
def test_declared_path_is_labelled():
    r = rul_predictor(CNC, CRITICAL)
    assert r["source"] == SOURCE_DECLARED
    assert r["model_id"] is None
    assert "not backtested" in r["provenance_note"].lower()


def test_declared_path_reports_hours_not_cycles():
    r = rul_predictor(CNC, CRITICAL)
    assert r["rul"]["unit"] == "hours"
    # The legacy field stays populated so older consumers keep working.
    assert r["rul_hours"]["min"] == r["rul"]["min"]


def test_every_prediction_carries_a_source():
    """No path may return an unlabelled number."""
    for machine, readings in ((CNC, CRITICAL), (CNC, {}), (TURBINE, {})):
        assert rul_predictor(machine, readings).get("source") in {
            SOURCE_FITTED,
            SOURCE_DECLARED,
        }


# --------------------------------------------------------------------------- #
# The fitted path. Skips cleanly when the ML stack or the fitted model is absent.
# --------------------------------------------------------------------------- #
def _fitted_available() -> bool:
    from ml.predict import has_model

    return has_model("turbofan")


needs_model = pytest.mark.skipif(
    not _fitted_available(),
    reason="fitted RUL model not built; run python -m ml.train_rul FD001",
)


@needs_model
def test_fitted_path_is_labelled_and_carries_measured_error():
    r = rul_predictor(TURBINE, {})
    assert r["source"] == SOURCE_FITTED
    assert r["model_id"] == "FD001"
    assert r["measured_error"]["test_mae_cycles"] > 0
    assert r["rul"]["unit"] == "cycles"
    assert r["rul"]["bound"] == "lower"


@needs_model
def test_fitted_path_reports_a_lower_bound_with_no_upper():
    """The upper quantile is degenerate under the RUL cap, so there is no upper bound."""
    r = rul_predictor(TURBINE, {})
    assert r["rul"]["max"] is None


@needs_model
def test_fitted_telemetry_states_where_it_came_from():
    prov = rul_predictor(TURBINE, {})["telemetry_provenance"]
    assert "C-MAPSS" in prov["dataset"]
    assert prov["true_remaining_cycles"] > 0


@needs_model
def test_the_two_paths_disagree_about_units():
    """Guards against the cycles-relabelled-as-hours mistake."""
    assert rul_predictor(TURBINE, {})["rul"]["unit"] == "cycles"
    assert rul_predictor(CNC, CRITICAL)["rul"]["unit"] == "hours"


# --------------------------------------------------------------------------- #
# Integration: does it actually get out of the graph?
# --------------------------------------------------------------------------- #
def test_provenance_reaches_graph_state(monkeypatch):
    update, _ = _run_reliability(monkeypatch, rul_predictor(CNC, CRITICAL))
    prov = update.get("rul_provenance")
    assert prov, "reliability must publish provenance into state"
    assert prov["source"] == SOURCE_DECLARED
    assert prov["unit"] == "hours"


def test_provenance_reaches_the_trace(monkeypatch):
    update, _ = _run_reliability(monkeypatch, rul_predictor(CNC, CRITICAL))
    events = [e for e in update["trace"] if e["type"] == "provenance"]
    assert len(events) == 1
    assert events[0]["source"] == SOURCE_DECLARED
    assert "declared thresholds" in events[0]["message"].lower()


def test_provenance_reaches_the_audit_log(monkeypatch, tmp_path):
    """The audit log is the record a reviewer reads afterwards. It must say which."""
    log_file = tmp_path / "audit.jsonl"
    monkeypatch.setattr(audit_log, "LOG_FILE", log_file)
    monkeypatch.setattr(audit_log, "LOG_DIR", tmp_path)

    _run_reliability(monkeypatch, rul_predictor(CNC, CRITICAL))

    written = [json.loads(line) for line in log_file.read_text(encoding="utf-8").splitlines()]
    provenance = [e for e in written if e.get("type") == "provenance"]
    assert provenance, "no provenance event was written to the audit log"
    assert provenance[0]["detail"]["source"] == SOURCE_DECLARED


def test_predicted_rul_survives_a_bound_with_no_upper(monkeypatch):
    """A lower-bound-only prediction must not blow up the case-memory field."""
    fake = {
        "machine_id": TURBINE,
        "rul": {"min": 34.4, "max": None, "unit": "cycles", "bound": "lower"},
        "failure_mode": "turbofan_degradation",
        "low_confidence_flag": False,
        "source": SOURCE_FITTED,
        "model_id": "FD001",
        "provenance_note": "fitted",
    }
    update, _ = _run_reliability(monkeypatch, fake)
    assert update["predicted_rul"] == [34.4, 34.4]
    assert update["rul_provenance"]["source"] == SOURCE_FITTED
