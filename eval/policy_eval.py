"""
Offline evaluation of the tool layer plus the code-enforced policy.

No model, no key, no network, no randomness. Runs the same tools and policy functions the
graph runs, over the labelled scenarios, and scores: risk classification, the approval
gate, safety verdicts, HALT precision and recall, action tiering, terminal status, and
routing.

The routing metric enumerates every sequence the policy allows rather than sampling one
run. A coverage guarantee that only holds on the path the model picked is not a guarantee.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import policy  # noqa: E402
from tools.expedite_cost import expedite_cost  # noqa: E402
from tools.rul_predictor import rul_predictor  # noqa: E402
from tools.safety_gate import safety_gate  # noqa: E402

from .metrics import BinaryConfusion, Tally  # noqa: E402
from .scenarios import Scenario, load_scenarios  # noqa: E402

AGENT_NAMES = ["reliability", "supply_chain", "production", "quality", "compliance_safety"]
VERDICT_SEVERITY = {"HALT": 0, "ESCALATE": 1, "OK": 2}


# --------------------------------------------------------------------------- #
# Per-scenario deterministic replay of the tool + policy stack
# --------------------------------------------------------------------------- #
def observed_risk(s: Scenario) -> str:
    """What the real rul_predictor plus the real policy produce for this scenario."""
    rp = rul_predictor(s.alert.get("machine_id", "?"), s.readings)
    return policy.classify_risk(rp, s.evidence_blob())


def observed_approval(s: Scenario) -> tuple[bool, str]:
    """(needs_approval, why) from the real expedite_cost ranking plus the real ceiling rule.

    A scenario with no sourcing fixture never reaches the supply chain agent, so the gate
    is not exercised and the answer is False by construction, which matches the graph."""
    src = s.sourcing
    if not src:
        return False, "supply chain never engaged (no sourcing in this scenario)"
    ranked = expedite_cost(src["options"], src["downtime_cost_per_hour"],
                           src["failure_window_hours"])
    top = (ranked.get("options_ranked") or [{}])[0]
    return policy.needs_human_approval(top), policy.approval_reason(top)


def observed_safety(s: Scenario) -> tuple[str | None, bool]:
    """(most restrictive verdict across the proposed actions, halt).

    The graph gates each proposed action separately and a single HALT stops the plan, so
    the scenario-level verdict is the most restrictive one seen."""
    actions = s.proposed_actions
    if not actions:
        return None, False
    verdicts = [safety_gate(a) for a in actions]
    worst = min(verdicts, key=lambda v: VERDICT_SEVERITY.get(str(v.get("verdict", "")).upper(), 3))
    halt = any(policy.halt_from_safety(v) for v in verdicts)
    return str(worst.get("verdict", "")).upper(), halt


def observed_terminal_status(s: Scenario, risk: str, halt: bool) -> str:
    """The status the graph would finish with, by the same rules synthesize() uses."""
    if risk == "ESCALATE":
        return "escalated"
    return "halted" if halt else "complete"


# --------------------------------------------------------------------------- #
# Exhaustive routing verification
# --------------------------------------------------------------------------- #
def enumerate_routing_paths(risk: str, escalate: bool, max_steps: int = 12) -> list[list[str]]:
    """Every agent sequence the policy permits at this risk level.

    Depth-first over allowed_next, branching on each choice. Follow-ups are not simulated
    (the labelled probes cover those) since they depend on agent output. The step cap is
    a termination check, not a search limit: hitting it is a failure."""
    paths: list[list[str]] = []
    overruns: list[list[str]] = []

    def walk(visited: list[str]) -> None:
        if len(visited) > max_steps:
            overruns.append(visited)
            return
        allowed = policy.allowed_next(
            visited=visited, risk=risk, escalate=escalate, pending_followup=None,
            agent_names=AGENT_NAMES,
        )
        for choice in allowed:
            if choice == "FINISH":
                paths.append(visited + ["FINISH"])
            else:
                walk(visited + [choice])

    walk([])
    if overruns:
        paths.append(["NON_TERMINATING"] + overruns[0][:max_steps])
    return paths


def check_routing_guarantees(s: Scenario) -> dict:
    """Do ALL permitted paths satisfy the coverage, ordering and termination guarantees."""
    risk = s.expected["risk"]
    escalate = bool(s.expected.get("escalates"))
    required = set(s.expected["agents_required"])
    paths = enumerate_routing_paths(risk, escalate)

    failures = []
    for path in paths:
        if path and path[0] == "NON_TERMINATING":
            failures.append({"path": path, "reason": "did not terminate within the step cap"})
            continue
        agents = [a for a in path if a != "FINISH"]
        if not agents or agents[0] != "reliability":
            failures.append({"path": path, "reason": "reliability did not run first"})
        if set(agents) != required:
            failures.append({"path": path, "reason": f"visited {sorted(set(agents))}, required {sorted(required)}"})
        if not escalate and agents and agents[-1] != "compliance_safety":
            failures.append({"path": path, "reason": "did not end at the safety gate before FINISH"})
        if escalate and len(agents) > 1:
            failures.append({"path": path, "reason": "an escalation continued past reliability"})
    return {"paths_explored": len(paths), "failures": failures, "ok": not failures}


# --------------------------------------------------------------------------- #
# The suite
# --------------------------------------------------------------------------- #
def run(scenarios: list[Scenario] | None = None) -> dict:
    scenarios = scenarios if scenarios is not None else load_scenarios()

    risk_t = Tally("risk_classification")
    approval_t = Tally("approval_gate")
    verdict_t = Tally("safety_verdict")
    tier_t = Tally("action_tiering")
    status_t = Tally("terminal_status")
    routing_t = Tally("routing_coverage_all_paths")
    probe_t = Tally("routing_allowed_set")
    halt_c = BinaryConfusion("halt_detection", positive_label="HALT")

    per_scenario = []
    for s in scenarios:
        exp = s.expected

        risk = observed_risk(s)
        risk_t.add(risk == exp["risk"], s.id, exp["risk"], risk)

        approval, why = observed_approval(s)
        approval_t.add(approval == exp["needs_approval"], s.id, exp["needs_approval"],
                       approval, note=why)

        verdict, halt = observed_safety(s)
        if exp.get("safety_verdict") is not None:
            verdict_t.add(verdict == exp["safety_verdict"], s.id, exp["safety_verdict"], verdict)
            halt_c.add(bool(exp.get("halt")), halt, s.id,
                       note=f"actions: {'; '.join(s.proposed_actions)[:160]}")

        for action, expected_tier in zip(s.proposed_actions, exp.get("action_tiers", []),
                                        strict=False):
            actual_tier = policy.action_tier(action)
            tier_t.add(actual_tier == expected_tier, f"{s.id}:{action[:48]}",
                       expected_tier, actual_tier)

        status = observed_terminal_status(s, risk, halt)
        status_t.add(status == exp["terminal_status"], s.id, exp["terminal_status"], status)

        routing = check_routing_guarantees(s)
        routing_t.add(routing["ok"], s.id, "all permitted paths satisfy the guarantees",
                      routing["failures"] or "ok")

        probe = s.routing_probe
        if probe:
            actual_allowed = policy.allowed_next(
                visited=probe["visited"], risk=probe["risk"],
                escalate=bool(probe["escalate"]),
                pending_followup=probe.get("pending_followup"),
                agent_names=AGENT_NAMES,
            )
            probe_t.add(actual_allowed == probe["expected_allowed"], s.id,
                        probe["expected_allowed"], actual_allowed)

        per_scenario.append({
            "id": s.id, "title": s.title, "mode": s.mode,
            "risk": {"expected": exp["risk"], "actual": risk},
            "needs_approval": {"expected": exp["needs_approval"], "actual": approval, "why": why},
            "safety_verdict": {"expected": exp.get("safety_verdict"), "actual": verdict},
            "halt": {"expected": bool(exp.get("halt")), "actual": halt},
            "terminal_status": {"expected": exp["terminal_status"], "actual": status},
            "routing_paths_explored": routing["paths_explored"],
            "routing_ok": routing["ok"],
        })

    tallies = [risk_t, approval_t, verdict_t, tier_t, status_t, routing_t, probe_t]
    total_correct = sum(t.correct for t in tallies)
    total_checks = sum(t.total for t in tallies)

    return {
        "suite": "offline_policy",
        "scenarios": len(scenarios),
        "checks": total_checks,
        "passed": total_correct,
        "overall_accuracy": round(total_correct / total_checks, 4) if total_checks else None,
        "metrics": {t.name: t.to_dict() for t in tallies},
        "halt_detection": halt_c.to_dict(),
        "policy": policy.summary(),
        "per_scenario": per_scenario,
    }


if __name__ == "__main__":
    import json
    print(json.dumps({k: v for k, v in run().items() if k != "per_scenario"}, indent=2))
