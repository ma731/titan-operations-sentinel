"""
The decision rules the model does not get a vote on.

Pure and deterministic so eval/policy_eval.py can score them without an API key. These
are the guarantees: coverage, termination, the spend ceiling, the safety override, and
abstention on thin data. The model picks inside what these allow.

graph.py is the only caller. Change a rule and re-run the eval to see what moved.
"""
from __future__ import annotations

import math
from collections import Counter

COST_CEILING_EUR = 500
MAX_VISITS = 2                 # cap re-engagement per agent so follow-ups cannot loop
CORE_AGENTS = ["supply_chain", "production", "quality"]


# --------------------------------------------------------------------------- #
# 1. Risk classification (Reliability agent verdict)
# --------------------------------------------------------------------------- #
def classify_risk(rul_result: dict | None, evidence: str = "") -> str:
    """HIGH | LOW | ESCALATE from the rul_predictor result.

    Order matters: a low-confidence flag beats a confident failure mode. Thin data that
    looks alarming is still thin data.
    """
    rp = rul_result or {}
    blob = (evidence or "").lower()
    failure_mode = str(rp.get("failure_mode", "")).lower()

    if rp.get("low_confidence_flag") or "interrupted" in blob or "data_unavailable" in blob:
        return "ESCALATE"
    # asset_profile and recall_similar_cases both mention past bearing failures, so the
    # text blob lies. Only fall back to it when there is no structured verdict at all.
    if "bearing_failure" in failure_mode or (not failure_mode and "spindle_bearing_failure" in blob):
        return "HIGH"
    return "LOW"


# --------------------------------------------------------------------------- #
# 2. Spend ceiling (Supply Chain agent -> human approval gate)
# --------------------------------------------------------------------------- #
def needs_human_approval(top_option: dict | None, ceiling_eur: int = COST_CEILING_EUR) -> bool:
    """True if a human must approve before this option is committed.

    Gates on cost over the ceiling, unknown cost, or an option that arrives after the
    predicted failure. The last two are the easy ones to miss.
    """
    opt = top_option or {}
    cost = opt.get("cost_eur")
    fits_window = opt.get("fits_failure_window", True)
    if isinstance(cost, bool) or not isinstance(cost, (int, float)) or not math.isfinite(cost) or cost < 0:
        return True
    if not fits_window:
        return True
    return cost > ceiling_eur


def approval_reason(top_option: dict | None, ceiling_eur: int = COST_CEILING_EUR) -> str:
    """Why the gate decided what it decided, for the audit log and the approval request."""
    opt = top_option or {}
    cost = opt.get("cost_eur")
    if isinstance(cost, bool) or not isinstance(cost, (int, float)) or not math.isfinite(cost) or cost < 0:
        return "no costed option available from expedite_cost"
    if not opt.get("fits_failure_window", True):
        return f"recommended option (EUR {cost}) does not fit the failure window"
    if cost > ceiling_eur:
        return f"EUR {cost} exceeds the autonomous ceiling of EUR {ceiling_eur}"
    return f"EUR {cost} is within the autonomous ceiling and fits the failure window"


# --------------------------------------------------------------------------- #
# 3. Safety override (Compliance & Safety agent)
# --------------------------------------------------------------------------- #
def halt_from_safety(safety_result: dict | None, report_text: str = "", evidence: str = "") -> bool:
    """True if Compliance & Safety halted the plan.

    Prefers the structured safety_gate verdict. The text fallback is narrow on purpose,
    for the case where the agent stated a verdict but the tool result did not parse.
    """
    sg = safety_result or {}
    if sg:
        return str(sg.get("verdict", "")).upper() == "HALT"
    blob = (evidence or "").lower()
    text = (report_text or "").lower()
    return '"verdict": "halt"' in blob or "verdict: halt" in text


# --------------------------------------------------------------------------- #
# 4. Routing policy (what the supervisor is allowed to choose)
# --------------------------------------------------------------------------- #
def allowed_next(
    visited: list[str],
    risk: str | None,
    escalate: bool,
    pending_followup: str | None,
    agent_names: list[str],
    core_agents: list[str] | None = None,
    max_visits: int = MAX_VISITS,
) -> list[str]:
    """Which agents the supervisor may route to next. The model picks from this list.

    Reliability runs first. An escalation ends the run. Follow-ups are honoured up to
    max_visits so two agents cannot ping-pong. A HIGH-risk run must cover every core
    agent, and compliance_safety gates before FINISH on any path that reaches a plan.

    A one-element list means the choice was forced; graph.py logs that distinction.
    """
    core_agents = core_agents or CORE_AGENTS
    visited = visited or []
    counts = Counter(visited)

    if "reliability" not in visited:
        return ["reliability"]
    if escalate:
        return ["FINISH"]

    fu = pending_followup
    if fu and fu in agent_names and counts[fu] < max_visits:
        return [fu]

    if risk != "HIGH":
        # Forced, not offered. This used to also return FINISH, so a low-risk run could
        # legally skip the gate. The exhaustive path check in the eval caught it.
        return ["compliance_safety"] if "compliance_safety" not in visited else ["FINISH"]

    missing = [a for a in core_agents if a not in visited]
    if missing:
        return missing                       # the model picks the ORDER among these
    if "compliance_safety" not in visited:
        return ["compliance_safety"]
    return ["FINISH"]


# --------------------------------------------------------------------------- #
# 5. Action tiering (the reference the final plan is scored against)
# --------------------------------------------------------------------------- #
# Keep in step with SAFE-01 in data/compliance/safety_rules.json, or the plan will tier
# an action AUTO that the gate then halts. test_policy.py asserts the two agree.
_ESCALATE_MARKERS = (
    "interlock", "guard", "guarding", "lockout", "tagout", "e-stop", "emergency stop",
    "light curtain", "presence sensing", "safety mat", "two-hand control",
    "safety system", "safety device", "safety control", "safety relay",
    "protective separation", "bypass", "defeat", "jumper", "tamper",
    "override safety", "disable safety", "tape over",
)
_APPROVE_MARKERS = (
    # Verb phrases, not bare nouns: "order" alone matched "work order" and tiered filing
    # a document as a spend.
    "purchase", "buy", "order the", "place an order", "raise an order", "purchase order",
    "expedite", "rush", "procure", "procurement",
    "emergency maintenance", "maintenance window", "overtime", "premium",
    "freight", "transfer", "replace the bearing", "bearing replacement",
)


def action_tier(action_description: str) -> str:
    """AUTO | APPROVE | ESCALATE for a proposed action.

    The reference the live eval scores the model plan against. Keyword-driven on purpose:
    it encodes the written tiers, nothing more. Safety is checked first so an action that
    touches a hazard control escalates even when it also mentions money.
    """
    text = (action_description or "").lower()
    if any(m in text for m in _ESCALATE_MARKERS):
        return "ESCALATE"
    if any(m in text for m in _APPROVE_MARKERS):
        return "APPROVE"
    return "AUTO"


def summary() -> dict:
    """The active policy constants, for the health endpoint and the eval scorecard."""
    return {
        "cost_ceiling_eur": COST_CEILING_EUR,
        "max_visits_per_agent": MAX_VISITS,
        "core_agents": list(CORE_AGENTS),
        "guarantees": [
            "reliability runs first on every path",
            "an escalation terminates the run without a synthesised plan",
            "every core agent runs before a HIGH-risk run can finish",
            "compliance_safety gates before FINISH on every planning path",
            "spend above the ceiling, of unknown cost, or outside the failure window "
            "requires a named human decision",
        ],
    }
