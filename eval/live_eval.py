"""
Live evaluation: run the real six-agent graph and score what the model actually did.

This is the expensive half of the harness, so it runs on a labelled subset
(`in_live_subset` in scenarios.json) rather than all 27 scenarios, and it is not part of
the CI-on-every-push suite. What it measures that the offline suite cannot:

  routing_coverage     did every required agent actually run, in a legal order
  tool_call_*          did each agent pick the tools its job needs (micro P / R / F1)
  gate_decision        did the run reach the human approval gate when it should have
  terminal_status      did the run end in the right state
  citation_rate        do the grounded agents cite a real corpus section, or just assert
  tokens / cost / s    what one run costs, per agent

The human decision is auto-answered with "approve" so the run completes unattended. That
is a measurement choice, not a claim that the gate is optional: the gate firing at all is
itself one of the scored metrics.
"""
from __future__ import annotations

import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import observability                                  # noqa: E402
from .metrics import SetScore, Tally                  # noqa: E402
from .scenarios import Scenario, load_scenarios       # noqa: E402

CITATION_RE = re.compile(r"\b([a-z0-9][a-z0-9-]{4,})#(S\d+)\b")
GROUNDED_AGENTS = ("reliability", "compliance_safety")
RESUME_DECISION = {"decision": "approve", "approver": "evaluation harness (automated)"}


def _valid_citations(text: str, known: set[str]) -> list[str]:
    """Citations in an agent report that actually exist in the corpus.

    Checking against the real index matters: an agent that invents a plausible-looking
    citation is worse than one that cites nothing, and a citation-rate metric that counts
    any `doc#S3`-shaped string would reward exactly that."""
    found = {f"{m.group(1)}#{m.group(2)}" for m in CITATION_RE.finditer(text or "")}
    return sorted(found & known)


def _hallucinated_citations(text: str, known: set[str]) -> list[str]:
    found = {f"{m.group(1)}#{m.group(2)}" for m in CITATION_RE.finditer(text or "")}
    return sorted(found - known)


def run_one(scenario: Scenario, timeout_note: str = "") -> dict:
    """Execute one scenario end to end and return the observations plus usage."""
    from langgraph.types import Command

    from graph import build_graph, make_initial_state

    graph = build_graph()
    state = make_initial_state(scenario.mode, alert=scenario.alert)
    cfg = {"configurable": {"thread_id": state["run_id"]}, "recursion_limit": 50}

    events: list[dict] = []
    interrupted = False
    error = None
    started = time.perf_counter()

    with observability.instrument_run() as usage:
        def drain(stream):
            nonlocal interrupted
            for chunk in stream:
                if "__interrupt__" in chunk:
                    interrupted = True
                    continue
                for _node, upd in chunk.items():
                    events.extend((upd or {}).get("trace") or [])

        try:
            drain(graph.stream(state, cfg))
            if interrupted:
                drain(graph.stream(Command(resume=RESUME_DECISION), cfg))
            final = graph.get_state(cfg).values
        except Exception as exc:  # noqa: BLE001 — a failed run is a result, not a crash
            error = str(exc)[:300]
            final = {}

    elapsed = time.perf_counter() - started

    tools_by_agent: dict[str, set[str]] = {}
    reports: dict[str, str] = {}
    visited: list[str] = []
    for e in events:
        if e.get("type") == "tool_call":
            tools_by_agent.setdefault(e.get("agent", "?"), set()).add(e.get("tool", "?"))
        elif e.get("type") == "agent_report":
            agent = e.get("agent", "?")
            reports[agent] = e.get("report", "")
            if agent not in visited:
                visited.append(agent)

    return {
        "id": scenario.id,
        "title": scenario.title,
        "mode": scenario.mode,
        "error": error,
        "timeout_note": timeout_note,
        "visited": visited,
        "tools_by_agent": {a: sorted(t) for a, t in tools_by_agent.items()},
        "reports": reports,
        "reached_approval_gate": interrupted,
        "status": final.get("status"),
        "risk": final.get("risk"),
        "halt": bool(final.get("halt")),
        "final_plan": final.get("final_plan", ""),
        "seconds": round(elapsed, 2),
        "usage": usage.to_dict(),
    }


def run(scenarios: list[Scenario] | None = None, limit: int | None = None) -> dict:
    scenarios = scenarios if scenarios is not None else load_scenarios(live_only=True)
    if limit:
        scenarios = scenarios[:limit]

    try:
        from rag.index import get_index
        known_citations = {c.citation for c in get_index().chunks}
    except Exception:  # noqa: BLE001
        known_citations = set()

    routing_t = Tally("routing_coverage")
    gate_t = Tally("gate_decision")
    status_t = Tally("terminal_status")
    halt_t = Tally("halt_decision")
    tool_score = SetScore("tool_call_correctness")

    runs, cited, grounded_reports, hallucinated = [], 0, 0, []
    total_tokens = total_cost = total_seconds = 0.0
    errors = 0

    for s in scenarios:
        obs = run_one(s)
        runs.append(obs)
        if obs["error"]:
            errors += 1
        exp = s.expected

        required = set(exp["agents_required"])
        routing_t.add(required.issubset(set(obs["visited"])), s.id,
                      sorted(required), obs["visited"])

        gate_t.add(obs["reached_approval_gate"] == exp["needs_approval"], s.id,
                   exp["needs_approval"], obs["reached_approval_gate"])
        status_t.add(obs["status"] == exp["terminal_status"], s.id,
                     exp["terminal_status"], obs["status"])
        halt_t.add(obs["halt"] == bool(exp.get("halt")), s.id,
                   bool(exp.get("halt")), obs["halt"])

        for agent, expected_tools in (exp.get("tool_calls") or {}).items():
            tool_score.add(set(expected_tools), set(obs["tools_by_agent"].get(agent, [])),
                           f"{s.id}:{agent}")

        for agent in GROUNDED_AGENTS:
            report = obs["reports"].get(agent)
            if report is None:
                continue
            grounded_reports += 1
            good = _valid_citations(report, known_citations)
            bad = _hallucinated_citations(report, known_citations)
            if good:
                cited += 1
            if bad:
                hallucinated.append({"case": s.id, "agent": agent, "invented": bad})

        total_tokens += obs["usage"]["total_tokens"]
        total_cost += obs["usage"]["estimated_cost_eur"]
        total_seconds += obs["seconds"]

    n = len(runs) or 1
    tallies = [routing_t, gate_t, status_t, halt_t]
    return {
        "suite": "live_agents",
        "runs": len(runs),
        "errors": errors,
        "provider": runs[0]["usage"]["provider"] if runs else None,
        "metrics": {t.name: t.to_dict() for t in tallies},
        "tool_call_correctness": tool_score.to_dict(),
        "grounding": {
            "grounded_reports": grounded_reports,
            "reports_with_a_valid_citation": cited,
            "citation_rate": round(cited / grounded_reports, 4) if grounded_reports else None,
            "invented_citations": hallucinated,
        },
        "efficiency": {
            "tokens_per_run": round(total_tokens / n, 1),
            "estimated_cost_eur_per_run": round(total_cost / n, 6),
            "seconds_per_run": round(total_seconds / n, 2),
            "total_tokens": int(total_tokens),
        },
        "per_run": [
            {k: v for k, v in r.items() if k not in ("reports", "final_plan")} for r in runs
        ],
    }


if __name__ == "__main__":
    import json
    out = run()
    print(json.dumps({k: v for k, v in out.items() if k != "per_run"}, indent=2))
