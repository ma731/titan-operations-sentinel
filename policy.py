"""
The code-enforced decision policy: the parts of this system that are NOT the model.

Everything here is deterministic and pure. It is the layer that gives the guarantees the
README claims: coverage of every cross-domain agent on a high-risk event, termination,
the spend ceiling, the safety override, and abstention on thin data. The model chooses
inside the space this policy allows; it cannot choose outside it.

These functions used to be inline in graph.py. They live here so the evaluation harness
can score them directly, with no API key, no tokens and no flakiness: a policy that
guarantees something should be tested as a policy, not inferred from watching a few
agent runs.

graph.py is the only production caller. If you change a rule here, the offline evaluation
in `eval/policy_eval.py` will tell you what it moved.
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
    """HIGH | LOW | ESCALATE from the rul_predictor result, with text as a fallback.

    The order matters and is a safety choice: a low-confidence flag beats a confident
    failure mode. If the data is too thin to trust, we abstain even when the thin data
    happens to look alarming, because acting on an untrustworthy estimate is the failure
    mode the escalation path exists to prevent.
    """
    rp = rul_result or {}
    blob = (evidence or "").lower()
    failure_mode = str(rp.get("failure_mode", "")).lower()

    if rp.get("low_confidence_flag") or "interrupted" in blob or "data_unavailable" in blob:
        return "ESCALATE"
    # Historical matches in the tool output can describe a failed bearing even when
    # the current assessment is normal. Structured current evidence wins.
    if "bearing_failure" in failure_mode or (not failure_mode and "spindle_bearing_failure" in blob):
        return "HIGH"
    return "LOW"


# --------------------------------------------------------------------------- #
# 2. Spend ceiling (Supply Chain agent -> human approval gate)
# --------------------------------------------------------------------------- #
def needs_human_approval(top_option: dict | None, ceiling_eur: int = COST_CEILING_EUR) -> bool:
    """True when a human must decide before the recommended option is committed.

    Three ways to land in the human gate, and the second two are the ones people miss:
      1. The cost exceeds the autonomous ceiling.
      2. The cost is unknown. An unknown cost is not a small cost.
      3. The option does not fit the failure window. A cheap option that arrives after
         the machine fails is not an autonomous action, it is a decision about accepting
         the failure, and that belongs to a person.
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
    """True when Compliance & Safety halted the plan.

    The structured tool field wins. Text matching is only a fallback for the case where
    the agent reported a verdict without a parseable safety_gate result, and it is
    deliberately narrow: a HALT is too consequential to infer from a loose keyword.
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
    """The set of agents the supervisor may route to next.

    The model picks from this list. It never picks the list. That is the whole point:
      - Reliability always runs first, because nothing downstream is meaningful without
        a failure assessment.
      - An escalation ends the run. There is nothing to plan from untrusted data.
      - A direct agent-to-agent follow-up is honoured, but only up to max_visits, so a
        pair of agents cannot ping-pong forever.
      - A HIGH risk event must cover every core agent before it can finish. This is the
        cross-silo guarantee, and it is the reason the system is not just five chatbots.
      - Compliance & Safety always gates before FINISH, on every path that reaches a plan.

    Returns a single-element list when the choice is forced, which is how graph.py
    distinguishes a forced route from an LLM-picked one in the trace.
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
        # The safety gate is forced, not offered. Until 2026-09 this branch returned
        # ["compliance_safety", "FINISH"], which let the supervisor finish a low-risk run
        # without gating it at all, contradicting the documented guarantee. The exhaustive
        # routing check in eval/policy_eval.py found it; this is the fix.
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
# Kept deliberately in step with SAFE-01 in data/compliance/safety_rules.json. If the
# safety rule learns a new way of saying "defeat a hazard control", the tiering policy has
# to learn it too, or the plan would tier an action AUTO that the gate then halts.
_ESCALATE_MARKERS = (
    "interlock", "guard", "guarding", "lockout", "tagout", "e-stop", "emergency stop",
    "light curtain", "presence sensing", "safety mat", "two-hand control",
    "safety system", "safety device", "safety control", "safety relay",
    "protective separation", "bypass", "defeat", "jumper", "tamper",
    "override safety", "disable safety", "tape over",
)
_APPROVE_MARKERS = (
    # "order" on its own matched "work order", which tiered filing a document as a spend.
    # Committing money reads as a verb phrase, so the markers are verb phrases.
    "purchase", "buy", "order the", "place an order", "raise an order", "purchase order",
    "expedite", "rush", "procure", "procurement",
    "emergency maintenance", "maintenance window", "overtime", "premium",
    "freight", "transfer", "replace the bearing", "bearing replacement",
)


def action_tier(action_description: str) -> str:
    """AUTO | APPROVE | ESCALATE for a proposed action, by the documented autonomy tiers.

    This is the reference classifier the live evaluation scores the model's final plan
    against. It is intentionally simple and keyword-driven: its job is to encode the
    written policy in docs/appendix, not to be clever. Safety markers are checked first
    so that anything touching a safety system escalates even when it also mentions money.
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
