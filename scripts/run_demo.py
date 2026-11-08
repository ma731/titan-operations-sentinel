"""
Titan Operations Sentinel — terminal demo runner.

Streams the LangGraph live, prints every perception / tool call / decision, then
pauses at the human-in-the-loop approval gate and resumes with the decision.

Usage (from the repo root):
    python scripts/run_demo.py                 # happy path, auto-approves
    python scripts/run_demo.py edge            # cross-plant adaptation path
    python scripts/run_demo.py escalation      # telemetry dropout → human review
    python scripts/run_demo.py happy reject    # happy path but reject the procurement
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # repo root → import tos

from langgraph.types import Command

from graph import build_graph, configure_console_logging, make_initial_state
from tools.sim_clock import sim_clock

# Windows consoles default to cp1252 and can't encode the trace glyphs (→, ⏸, …).
try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

SCENARIOS = {"happy", "edge", "escalation"}


def render(event: dict):
    t = event.get("type")
    agent = event.get("agent", "")
    if t == "perception":
        a = event["alert"]
        print(f"\n[PERCEPTION] {a['machine_id']} | {a['sensor']}={a['value']}{a['unit']} "
              f"(threshold {a['threshold']}, trend {a['trend']})")
        print(f"  → {event['message']}")
    elif t == "route":
        print(f"\n[ORCHESTRATOR] routes → {event['allowed']} ⇒ {event['message'].split('→')[-1].strip()}")
    elif t == "tool_call":
        print(f"    [TOOL] {agent}.{event['tool']}({_short(event['input'], 90)})")
        print(f"           ↳ {_short(event['result'], 130)}")
    elif t == "agent_report":
        # The agent's full natural-language assessment — this is what it "says" to the others.
        print(f"\n  ┌─ {agent.upper()} REPORT " + "─" * max(0, 48 - len(agent)))
        for line in (event["report"] or "(no report)").splitlines():
            print(f"  │ {line}")
        print("  └" + "─" * 56)
    elif t == "decision":
        print(f"\n[DECISION · {agent}] {event['message']}")
    elif t == "escalation":
        print(f"\n[ESCALATION · {agent}] {event['message']}  (reason: {event.get('reason')})")
    elif t == "approval_request":
        print(f"\n[⏸ APPROVAL GATE] {event['question']}  (ceiling €{event['ceiling_eur']})")
    elif t == "human_decision":
        print(f"\n[HUMAN] decision = {event['decision']}")
    elif t == "plan":
        print("\n" + "=" * 64 + "\n*** FINAL ACTION PLAN ***\n" + "=" * 64)
        print(event["plan"])


def _short(obj, n=160):
    s = str(obj)
    return s if len(s) <= n else s[:n] + " …"


def drain(stream):
    """Print trace deltas from a graph stream; return the interrupt payload if any."""
    interrupted = None
    for chunk in stream:
        if "__interrupt__" in chunk:
            interrupted = chunk["__interrupt__"][0].value
            render(interrupted)
            continue
        for _node, update in chunk.items():
            for ev in (update or {}).get("trace", []):
                render(ev)
    return interrupted


def main():
    args = [a.lower() for a in sys.argv[1:]]
    scenario = next((a for a in args if a in SCENARIOS), "happy")
    decision = "reject" if "reject" in args else "approve"

    print("TITAN OPERATIONS SENTINEL")
    print(f"Scenario: {scenario.upper()} | human will: {decision.upper()}\n")

    # Live status logging — concise, timestamped progress as the graph runs (set TOS_LOG=0 to mute).
    if os.getenv("TOS_LOG", "1") != "0":
        configure_console_logging()

    graph = build_graph()
    state = make_initial_state(scenario)
    # recursion_limit headroom for agent-to-agent follow-ups (default 25 is too low).
    config = {"configurable": {"thread_id": state["run_id"]}, "recursion_limit": 50}

    # The scenario is set on 12 June; run the drafts on that clock, not today's.
    with sim_clock(state["alert"].get("timestamp")):
        paused = drain(graph.stream(state, config))

        if paused is not None:
            # Resume the paused graph with the human decision.
            resume = {"decision": decision, "approver": "Plant Manager Schmidt (demo)"}
            drain(graph.stream(Command(resume=resume), config))

    final = graph.get_state(config).values
    print(f"\nFINAL STATUS: {final.get('status')}")


if __name__ == "__main__":
    main()
