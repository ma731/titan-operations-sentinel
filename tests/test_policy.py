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

import pytest

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


# --- the safety rule, both directions -------------------------------------- #
# These pin F-02. The rule fires on a defeating action applied to a hazard control, so
# both halves are tested: unusual phrasings of a bypass must still HALT, and merely
# saying the word "safety" must not.
DEFEATS_A_CONTROL = [
    "bypass the cell safety interlock to keep the line running",
    "remove the spindle guard to inspect the bearing while running",
    "disable the door interlock so the machine can run during the repair",
    "jumper the light curtain so the cell keeps running during the changeover",
    "tape over the interlock switch during the changeover",
    "temporarily override the safety system for diagnostics",
    "defeat the two-hand control on the press to speed up the cycle",
    "short out the safety relay",
]

MENTIONS_SAFETY_BUT_DEFEATS_NOTHING = [
    "record the safety officer sign-off for the emergency maintenance window",
    "notify the safety officer of the planned window",
    "attach the safety data sheet to the work order",
    "schedule the annual safety inspection for the cell",
    "add the lockout/tagout reference to the maintenance record",
]


@pytest.mark.parametrize("action", DEFEATS_A_CONTROL)
def test_defeating_a_hazard_control_always_halts(action):
    """A false negative here is a safety failure, so this is the one list that is not
    allowed to shrink."""
    from tools.safety_gate import safety_gate

    assert policy.halt_from_safety(safety_gate(action)) is True, action


@pytest.mark.parametrize("action", MENTIONS_SAFETY_BUT_DEFEATS_NOTHING)
def test_mentioning_safety_is_not_itself_a_violation(action):
    """The old rule halted every one of these, including the sign-off that the emergency
    window procedure requires, which meant the gate could block its own procedure."""
    from tools.safety_gate import safety_gate

    assert policy.halt_from_safety(safety_gate(action)) is False, action


def test_a_safety_signoff_still_escalates_rather_than_passing_silently():
    """Not halting is not the same as waving through: the sign-off still belongs to the
    safety officer under SAFE-02."""
    from tools.safety_gate import safety_gate

    verdict = safety_gate("record the safety officer sign-off for the emergency "
                          "maintenance window")
    assert verdict["verdict"] == "ESCALATE"
    assert verdict["authority"] == "safety_officer"


def test_the_gate_fails_safe_when_the_rules_are_unreadable(monkeypatch, tmp_path):
    import tools.safety_gate as sg

    monkeypatch.setattr(sg, "DATA_DIR", tmp_path)       # no safety_rules.json here
    assert sg.safety_gate("anything at all")["verdict"] == "ESCALATE"


def test_tiering_and_the_safety_rule_share_a_vocabulary():
    """If the gate learns a new phrasing and the tiering policy does not, the plan would
    label an action AUTO that the gate then halts."""
    from tools.safety_gate import safety_gate

    for action in DEFEATS_A_CONTROL:
        assert policy.action_tier(action) == "ESCALATE", action
        assert safety_gate(action)["verdict"] == "HALT", action


# --- action tiering -------------------------------------------------------- #
def test_safety_actions_escalate_even_when_they_mention_money():
    assert policy.action_tier("purchase a jumper to bypass the interlock") == "ESCALATE"


def test_spend_actions_are_approve_tier():
    assert policy.action_tier("authorize an emergency parts purchase") == "APPROVE"
    assert policy.action_tier("open an emergency maintenance window") == "APPROVE"


def test_routine_actions_are_autonomous():
    assert policy.action_tier("reduce spindle speed to the OEM safe limit") == "AUTO"
    assert policy.action_tier("update the condition monitoring log") == "AUTO"
