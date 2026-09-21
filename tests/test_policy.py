"""
Unit tests for the code-enforced decision policy.

These pin the guarantees the README makes. They run offline with no key. Where a test
encodes a rule that the evaluation suite also measures, the test is the regression guard
and the suite is the report: the test says "this must not change", the scorecard says
"here is how often it is right across the labelled set".
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import policy

AGENTS = ["reliability", "supply_chain", "production", "quality", "compliance_safety"]


# --- risk classification --------------------------------------------------- #
def test_low_confidence_beats_a_confident_failure_mode():
    """Abstention wins. Thin data that happens to look alarming is still thin data."""
    rp = {"failure_mode": "spindle_bearing_failure", "low_confidence_flag": True}
    assert policy.classify_risk(rp) == "ESCALATE"


def test_interrupted_telemetry_escalates_even_without_the_flag():
    assert policy.classify_risk({"failure_mode": "spindle_bearing_failure"},
                                '{"sensor_status": "interrupted"}') == "ESCALATE"


def test_unavailable_data_escalates():
    assert policy.classify_risk({}, '{"error": "data_unavailable"}') == "ESCALATE"


def test_confirmed_bearing_failure_is_high():
    assert policy.classify_risk({"failure_mode": "spindle_bearing_failure"}) == "HIGH"


def test_degradation_is_not_an_emergency():
    assert policy.classify_risk({"failure_mode": "spindle_bearing_degradation"}) == "LOW"


# --- the spend ceiling ----------------------------------------------------- #
def test_under_ceiling_and_fits_window_is_autonomous():
    assert policy.needs_human_approval({"cost_eur": 420, "fits_failure_window": True}) is False


def test_exactly_at_the_ceiling_is_autonomous():
    assert policy.needs_human_approval({"cost_eur": 500, "fits_failure_window": True}) is False


def test_one_euro_over_the_ceiling_needs_a_human():
    assert policy.needs_human_approval({"cost_eur": 501, "fits_failure_window": True}) is True


def test_cheap_option_that_misses_the_window_needs_a_human():
    """A part that arrives after the machine fails is a decision about accepting the
    failure, not an autonomous purchase."""
    assert policy.needs_human_approval({"cost_eur": 180, "fits_failure_window": False}) is True


def test_unknown_cost_needs_a_human():
    assert policy.needs_human_approval({"cost_eur": None, "fits_failure_window": True}) is True


def test_no_option_at_all_needs_a_human():
    assert policy.needs_human_approval(None) is True


def test_approval_reason_names_the_actual_trigger():
    assert "ceiling" in policy.approval_reason({"cost_eur": 3200, "fits_failure_window": True})
    assert "window" in policy.approval_reason({"cost_eur": 180, "fits_failure_window": False})


# --- the safety override --------------------------------------------------- #
def test_structured_halt_verdict_wins():
    assert policy.halt_from_safety({"verdict": "HALT"}) is True
    assert policy.halt_from_safety({"verdict": "ESCALATE"}) is False
    assert policy.halt_from_safety({"verdict": "OK"}) is False


def test_text_fallback_only_applies_without_a_structured_result():
    assert policy.halt_from_safety({}, "VERDICT: HALT") is True
    assert policy.halt_from_safety({"verdict": "OK"}, "VERDICT: HALT") is False


# --- routing guarantees ---------------------------------------------------- #
def test_reliability_always_runs_first():
    assert policy.allowed_next([], None, False, None, AGENTS) == ["reliability"]


def test_escalation_terminates_immediately():
    assert policy.allowed_next(["reliability"], "ESCALATE", True, None, AGENTS) == ["FINISH"]


def test_escalation_is_not_overridden_by_a_pending_followup():
    assert policy.allowed_next(["reliability"], "ESCALATE", True, "supply_chain",
                               AGENTS) == ["FINISH"]


def test_high_risk_must_cover_every_core_agent():
    allowed = policy.allowed_next(["reliability", "supply_chain", "compliance_safety"],
                                  "HIGH", False, None, AGENTS)
    assert set(allowed) == {"production", "quality"}


def test_low_risk_is_still_forced_through_the_safety_gate():
    """Regression guard for F-03: this branch used to offer FINISH alongside the gate,
    which let a low-risk run finish ungated."""
    assert policy.allowed_next(["reliability"], "LOW", False, None,
                               AGENTS) == ["compliance_safety"]


def test_a_followup_is_honoured_once():
    assert policy.allowed_next(["reliability", "supply_chain", "production"], "HIGH",
                               False, "quality", AGENTS) == ["quality"]


def test_a_followup_cannot_loop_past_max_visits():
    visited = ["reliability", "supply_chain", "quality", "production", "quality"]
    allowed = policy.allowed_next(visited, "HIGH", False, "quality", AGENTS)
    assert "quality" not in allowed


def test_an_unknown_followup_target_is_ignored():
    allowed = policy.allowed_next(["reliability", "supply_chain", "production", "quality"],
                                  "HIGH", False, "not_an_agent", AGENTS)
    assert allowed == ["compliance_safety"]


def test_every_permitted_high_risk_path_covers_all_agents_and_terminates():
    """The coverage guarantee over ALL permitted paths, not just the one a run took."""
    from eval.policy_eval import enumerate_routing_paths

    paths = enumerate_routing_paths("HIGH", escalate=False)
    assert paths, "no paths enumerated"
    for path in paths:
        assert path[0] != "NON_TERMINATING", f"policy failed to terminate: {path}"
        agents = [a for a in path if a != "FINISH"]
        assert agents[0] == "reliability"
        assert agents[-1] == "compliance_safety"
        assert set(agents) == set(AGENTS)


# --- action tiering -------------------------------------------------------- #
def test_safety_actions_escalate_even_when_they_mention_money():
    assert policy.action_tier("purchase a jumper to bypass the interlock") == "ESCALATE"


def test_spend_actions_are_approve_tier():
    assert policy.action_tier("authorize an emergency parts purchase") == "APPROVE"
    assert policy.action_tier("open an emergency maintenance window") == "APPROVE"


def test_routine_actions_are_autonomous():
    assert policy.action_tier("reduce spindle speed to the OEM safe limit") == "AUTO"
    assert policy.action_tier("update the condition monitoring log") == "AUTO"
