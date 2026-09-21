"""
Titan Operations Sentinel — multi-agent orchestration (LangGraph).

A society of six agents that solve all five TMC challenges by sharing one running
conversation and being routed by an LLM orchestrator:

    perceive → SUPERVISOR ⇄ { reliability, supply_chain, production, quality,
                              compliance_safety }  → finalize(approval) → synthesize

How they communicate (natural language):
- Every specialist writes a natural-language report; it is appended to a SHARED
  TRANSCRIPT that every later agent reads in full. So agents converse through one
  growing dialogue, not isolated handoffs.
- An agent may end its report with `FOLLOWUP: <agent> — <question>` to put a direct
  question to another specialist; the orchestrator honours it (bounded re-routing),
  which is genuine agent-to-agent messaging.
- The SUPERVISOR (LLM) decides who acts next, constrained by a policy that guarantees
  coverage (all cross-domain agents on HIGH risk) and termination (compliance_safety
  gates before FINISH, and each agent runs at most MAX_VISITS times).

Specialists are autonomous ReAct agents (agents.py) — each LLM picks its own tools.
Compliance & Safety can HALT the plan; the approval gate uses interrupt() for HITL.
Three paths via `scenario`: happy / edge / escalation.
"""
from __future__ import annotations

import ast
import json
import logging
import operator
import re
import sys
import time
from pathlib import Path
from typing import Annotated, TypedDict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

import llm
import observability
import policy
from agents import AGENT_NAMES, build_agents
from audit_log import new_run_id, write_event

PROMPTS = Path(__file__).parent / "prompts"

# The code-enforced decision rules live in policy.py so they can be evaluated without
# a model (see eval/policy_eval.py). These names are re-exported for backwards
# compatibility with the tests and the webapp that already import them from here.
COST_CEILING_EUR = policy.COST_CEILING_EUR

# Live run status. The graph emits concise, timestamped progress lines to this logger AS it
# runs (which agent is working, how long it took, tools used, routing, the approval gate) so a
# long run is observable instead of silent. Library default is silent (NullHandler); an
# entrypoint opts in by calling configure_console_logging().
log = logging.getLogger("tos")
log.addHandler(logging.NullHandler())


def configure_console_logging(level: int | str = logging.INFO, stream=None) -> None:
    """Attach a timestamped console handler to the 'tos' status logger (idempotent).

    Call this from an entrypoint (run_demo.py, the webapp backend, a notebook) to watch a
    run live. Safe to call more than once — it won't add duplicate handlers."""
    if any(getattr(h, "_tos_console", False) for h in log.handlers):
        log.setLevel(level)
        return
    handler = logging.StreamHandler(stream or sys.stdout)
    handler.setFormatter(logging.Formatter("%(asctime)s | %(message)s", datefmt="%H:%M:%S"))
    handler._tos_console = True          # tag so we don't attach twice
    log.addHandler(handler)
    log.setLevel(level)
    log.propagate = False                # don't double-print via the root logger
JOBS = ["J4421", "J4422", "J4423", "J4424", "J4425"]
CORE_AGENTS = policy.CORE_AGENTS
MAX_VISITS = policy.MAX_VISITS

# Token budget: the 6-agent transcript is re-sent to every later agent and on every routing
# call, so its size drives cost on the Groq free tier (~100k tokens/day). These caps bound
# that growth while leaving normal-length assessments fully intact.
PEER_REPORT_CHARS = 1400    # how much of each prior agent's report the next agent sees
ROUTE_DIGEST_CHARS = 180    # the supervisor only needs a glance to pick the next agent
REPORT_STORE_CHARS = 2000   # cap a single agent's stored report so one runaway reply
                            # can't bloat the context for everyone downstream


def _prompt(name: str) -> str:
    p = PROMPTS / name
    return p.read_text(encoding="utf-8") if p.exists() else ""


def _merge(a: dict, b: dict) -> dict:
    r = dict(a or {})
    r.update(b or {})
    return r


class OpsState(TypedDict, total=False):
    run_id: str
    alert: dict
    scenario: str
    machine_id: str
    plant_id: str
    transcript: Annotated[list, operator.add]   # [{agent, message}] — the shared dialogue
    ops_context: Annotated[dict, _merge]         # {agent: latest report} — quick lookup
    visited: Annotated[list, operator.add]
    pending_followup: str                        # agent name another agent asked for
    next_agent: str
    risk: str                                    # HIGH | LOW | ESCALATE
    predicted_rul: list                          # [min_h, max_h] from rul_predictor, for case memory
    proposed_actions: list[str]
    escalate: bool
    halt: bool
    needs_approval: bool
    approval: dict
    final_plan: str
    status: str
    trace: Annotated[list, operator.add]


def _ev(rid: str, etype: str, agent: str, **detail) -> dict:
    write_event(rid, etype, detail, agent)
    return {"type": etype, "agent": agent, **detail}


# --------------------------------------------------------------------------- #
# Read a ReAct agent's run: surface its tool calls + its full natural-language reply.
# --------------------------------------------------------------------------- #
def _safe(content):
    """Parse a tool's ToolMessage content back into a dict when possible (JSON first, then
    the Python-repr LangChain often emits) so worker decisions can read structured fields
    instead of substring-matching text. Falls back to the raw content."""
    if not isinstance(content, str):
        return content
    try:
        return json.loads(content)
    except (json.JSONDecodeError, TypeError):
        pass
    try:
        return ast.literal_eval(content)
    except (ValueError, SyntaxError):
        return content


def _tool_events(messages, agent, rid):
    events, blob, pending = [], [], {}
    for m in messages:
        for tc in (getattr(m, "tool_calls", None) or []):
            pending[tc["id"]] = (tc["name"], tc.get("args", {}))
        if m.__class__.__name__ == "ToolMessage":
            name, args = pending.get(getattr(m, "tool_call_id", None),
                                     (getattr(m, "name", "?"), {}))
            blob.append(str(m.content))
            events.append(_ev(rid, "tool_call", agent, tool=name, input=args,
                              result=_safe(m.content)))
    # last structured result per tool, for verdict logic that prefers fields over substrings
    results = {e["tool"]: e["result"] for e in events if isinstance(e["result"], dict)}
    return events, " ".join(blob).lower(), results


def _agent_report(messages) -> str:
    """All of the agent's spoken (non-tool) text, joined — so the full assessment reaches
    the transcript, not just the final one-liner (fixes the terse-report bug)."""
    parts = [m.content for m in messages
             if m.__class__.__name__ == "AIMessage"
             and isinstance(m.content, str) and m.content.strip()]
    return "\n".join(parts).strip()


def _detect_followup(report: str, sender: str) -> str | None:
    m = re.search(r"FOLLOWUP:\s*([a-z_]+)", report, re.IGNORECASE)
    if not m:
        return None
    target = m.group(1).lower()
    return target if target in AGENT_NAMES and target != sender else None


# --------------------------------------------------------------------------- #
# Task prompts: each agent sees the FULL shared transcript + its own instruction.
# --------------------------------------------------------------------------- #
def _clip(text: str, limit: int | None) -> str:
    text = text or ""
    if limit and len(text) > limit:
        return text[:limit].rstrip() + " …[trimmed]"
    return text


def _conversation(state: OpsState, per_msg: int | None = None) -> str:
    lines = [f"[{t['agent']}]: {_clip(t['message'], per_msg)}"
             for t in state.get("transcript", [])]
    return "\n\n".join(lines) if lines else "(no messages yet — you are first)"


def _instruction(name: str, state: OpsState) -> str:
    alert = state["alert"]
    mid, pid = state["machine_id"], state["plant_id"]
    scenario = state.get("scenario", "happy")
    window = "dropout" if scenario == "escalation" else "72h"
    downtime_day = alert.get("production_impact_per_day_eur", 180000)

    if name == "reliability":
        return (f"Triage the alert stream at plant {pid}, confirm the critical machine, then "
                f"assess its failure risk, RUL, required parts, and maintenance-window gap. "
                f"Use sensor window '{window}'. Alert: {json.dumps(alert)}")
    if name == "supply_chain":
        downtime_hr = round(downtime_day / 24)
        window_hours = (state.get("predicted_rul") or [52])[0]
        edge = ("\nNOTE: primary supply is DISRUPTED today — call supplier_catalog with "
                "scenario='edge'. If nothing fits the RUL window, find a cross-plant transfer "
                "via parts_inventory at sister plants AMS and MUC."
                if scenario == "edge" else "")
        return (f"Confirm parts availability for {mid} at {pid} (the parts are in the reliability "
                f"report above), check the chosen supplier's Tier-2 risk, and recommend a sourcing "
                f"option ranked by ROI. When you call expedite_cost use downtime_cost_per_hour="
                f"{downtime_hr} and failure_window_hours={window_hours}.{edge}")
    if name == "production":
        return (f"{mid} needs an emergency window, so reroute its jobs {JOBS} to equivalent "
                f"machines and ensure no human-robot or shift conflict at plant {pid}; adapt if "
                f"there is one.")
    if name == "quality":
        return (f"Assess the quality impact of the {mid} failure and whether the reroute targets "
                f"(CNC-05-LEI, CNC-08-LEI) are quality-safe for extra load.")
    if name == "compliance_safety":
        actions = ("reduce spindle speed to OEM safe limit; reroute production jobs to equivalent "
                   "machines; open the machine for emergency maintenance / bearing replacement in a "
                   "Saturday window; authorize an emergency parts purchase")
        if state.get("proposed_actions"):
            actions = "; ".join(state["proposed_actions"])
        return (f"Gate EACH of these proposed actions against safety/OSHA, then assemble the audit "
                f"trail for run {state['run_id']}.\nProposed actions: {actions}")
    return "Proceed."


def _task_for(name: str, state: OpsState) -> str:
    return (f"CONVERSATION SO FAR (what the other agents have reported):\n"
            f"{_conversation(state, per_msg=PEER_REPORT_CHARS)}\n\n"
            f"YOUR TASK:\n{_instruction(name, state)}\n\n"
            f"If you need input from another specialist, end your reply with a line: "
            f"`FOLLOWUP: <agent_name> — <your question>` (agents: {', '.join(AGENT_NAMES)}).")


# --------------------------------------------------------------------------- #
# Nodes
# --------------------------------------------------------------------------- #
def perceive(state: OpsState) -> dict:
    alert = state["alert"]
    try:                                  # self-closing learning loop: resolve any cases
        from tools.recall_cases import reconcile_due  # whose outcome is now known
        from tools.runtime_inputs import current
        done = 0 if current() else reconcile_due()
        if done:
            log.info("LEARN         | reconciled %d prior case(s) against known outcomes", done)
    except Exception:  # noqa: BLE001
        pass
    log.info("PERCEIVE      | %s on %s (%s=%s%s, threshold %s, trend %s) [scenario=%s]",
             alert.get("alert_id", "?"), alert["machine_id"], alert.get("sensor", "?"),
             alert.get("value", "?"), alert.get("unit", ""), alert.get("threshold", "?"),
             alert.get("trend", "?"), state.get("scenario", "happy"))
    ev = _ev(state["run_id"], "perception", "orchestrator",
             message="Alert received. Orchestrator will route across specialist agents.",
             alert=alert)
    return {"machine_id": alert["machine_id"], "plant_id": alert.get("plant_id", "LEI"),
            "status": "perceiving", "trace": [ev]}


def _make_worker(name: str):
    def node(state: OpsState) -> dict:
        rid = state["run_id"]
        log.info("RUN   %-17s| working… (reads %d prior reports)",
                 name, len(state.get("transcript", [])))
        t0 = time.perf_counter()
        try:
            agents = build_agents()
            # Tokens, latency and (when configured) the Langfuse trace are attributed to
            # this agent for the duration of its ReAct loop. Uninstrumented runs get an
            # empty callback list, so this is free on the default path.
            with observability.instrumented_agent(name):
                result = agents[name].invoke(
                    {"messages": [("user", _task_for(name, state))]},
                    config={"callbacks": observability.callbacks(name),
                            "recursion_limit": 30},
                )
            msgs = result["messages"]
        except Exception as exc:  # noqa: BLE001 — a flaky tool call must not kill the run
            log.warning("FAIL  %-17s| after %.1fs — %s", name, time.perf_counter() - t0,
                        str(exc)[:120])
            ev = _ev(rid, "agent_error", name, error=str(exc)[:300])
            report = f"[{name} could not complete autonomously: {str(exc)[:200]}]"
            update = {"ops_context": {name: report}, "visited": [name],
                      "transcript": [{"agent": name, "message": report}],
                      "pending_followup": "", "status": f"{name}_error",
                      "trace": [ev, _ev(rid, "agent_report", name, report=report)]}
            if name == "reliability":
                update.update(risk="ESCALATE", escalate=True)
            if name == "supply_chain":
                update["needs_approval"] = True
            if name == "compliance_safety":
                update["halt"] = True
            return update

        events, blob, results = _tool_events(msgs, name, rid)
        tool_names = [e["tool"] for e in events]
        full_report = _agent_report(msgs)
        followup = _detect_followup(full_report, name)   # detect on FULL text first…
        report = _clip(full_report, REPORT_STORE_CHARS)  # …then cap what we store/forward
        events.append(_ev(rid, "agent_report", name, report=report))
        update: dict = {"ops_context": {name: report}, "visited": [name],
                        "transcript": [{"agent": name, "message": report}],
                        "pending_followup": followup or "",
                        "status": f"{name}_done", "trace": events}
        log.info("DONE  %-17s| %.1fs, %d tool calls [%s]", name, time.perf_counter() - t0,
                 len(tool_names), ", ".join(tool_names) or "—")
        if followup:
            log.info("  ↳ %s asks %s a direct follow-up", name, followup)
            update["trace"].append(_ev(rid, "decision", name,
                                       message=f"{name} asks {followup} a direct follow-up."))

        # The three verdicts below are the code-enforced layer. They read structured tool
        # fields, not the agent's prose, and the rules themselves live in policy.py so the
        # offline evaluation can score them directly.
        if name == "reliability":
            rp = results.get("rul_predictor", {})
            rh = rp.get("rul_hours") or {}
            if rh.get("min") is not None:
                update["predicted_rul"] = [rh["min"], rh.get("max", rh["min"])]
            risk = (policy.classify_risk(rp, blob)
                    if rp.get("failure_mode") and not rp.get("error") else "ESCALATE")
            update["risk"] = risk
            if risk == "ESCALATE":
                update["escalate"] = True
            log.info("  ↳ reliability verdict: risk=%s", risk)
        if name == "supply_chain":
            top = (results.get("expedite_cost", {}).get("options_ranked") or [{}])[0]
            update["needs_approval"] = policy.needs_human_approval(top, COST_CEILING_EUR)
            log.info("  ↳ supply_chain gate: %s (%s)",
                     "needs approval" if update["needs_approval"] else "autonomous",
                     policy.approval_reason(top, COST_CEILING_EUR))
        if name == "compliance_safety":
            safety = [e["result"] for e in events if e.get("tool") == "safety_gate"]
            # A later PROCEED must never erase an earlier HALT; no valid gate is not clearance.
            valid = {"OK", "PROCEED", "ESCALATE", "SIGN-OFF", "HALT"}
            update["halt"] = bool(state.get("halt")) or not safety or any(
                not isinstance(s, dict) or str(s.get("verdict", "")).upper() not in valid
                or "unavailable" in str(s.get("reason", "")).lower()
                or policy.halt_from_safety(s) for s in safety
            )
            log.info("  ↳ compliance verdict: %s", "HALT" if update["halt"] else "cleared")
        return update
    return node


def _allowed_next(state: OpsState) -> list[str]:
    """The agents the supervisor may choose from. The rules live in policy.allowed_next so
    they can be evaluated without a model; this is the graph-state adapter for them."""
    return policy.allowed_next(
        visited=state.get("visited", []),
        risk=state.get("risk"),
        escalate=bool(state.get("escalate")),
        pending_followup=state.get("pending_followup"),
        agent_names=AGENT_NAMES,
        core_agents=CORE_AGENTS,
        max_visits=MAX_VISITS,
    )


def _llm_route(state: OpsState, allowed: list[str]) -> str:
    resp = llm.complete(
        _prompt("supervisor_system.md"),
        f"Alert: {json.dumps(state['alert'])}\nAgents already done: {state.get('visited', [])}\n"
        f"Conversation so far:\n{_conversation(state, per_msg=ROUTE_DIGEST_CHARS)}\n\nChoose the NEXT agent to run. "
        f"Respond with exactly one of: {allowed}",
    ).lower()
    for a in allowed:
        if a.lower() in resp:
            return a
    return allowed[0]


def supervisor(state: OpsState) -> dict:
    allowed = _allowed_next(state)
    choice = allowed[0] if len(allowed) == 1 else _llm_route(state, allowed)
    how = "forced" if len(allowed) == 1 else "LLM-picked"
    log.info("ROUTE         | → %s  (%s; allowed=%s)",
             "FINISH" if choice == "FINISH" else choice, how, allowed)
    ev = _ev(state["run_id"], "route", "orchestrator",
             message=f"Orchestrator routes → {choice}", allowed=allowed, to=choice, how=how)
    return {"next_agent": choice, "trace": [ev]}


def route_from_supervisor(state: OpsState) -> str:
    nxt = state.get("next_agent", "FINISH")
    return "finalize" if nxt == "FINISH" else nxt


def approval_gate(state: OpsState) -> dict:
    rid = state["run_id"]
    if state.get("escalate"):
        return {}
    if state.get("halt"):
        log.info("GATE          | HALT — compliance stopped the plan; skipping approval")
        return {"trace": [_ev(rid, "decision", "orchestrator",
                              message="Plan HALTED by Compliance & Safety — skipping approval.")]}
    if not state.get("needs_approval"):
        log.info("GATE          | no approval required")
        return {}
    request = {"type": "approval_request",
               "question": "Approve emergency procurement + maintenance window? (approve / reject)",
               "ceiling_eur": COST_CEILING_EUR,
               "supply_summary": str(state.get("ops_context", {}).get("supply_chain", ""))[:400]}
    write_event(rid, "approval_request", request, "orchestrator")

    # Reach the approver wherever they are. Slack or email when configured, console
    # otherwise. This only carries the question out; the decision still comes back
    # through the same interrupt() resume path the web console uses, so there is one
    # place a run can be approved and one place it gets recorded.
    try:
        from integrations.approval import send_approval_request
        from tools.runtime_inputs import current
        delivery = {"channel": "simulation", "sent": False} if current() else send_approval_request(
            rid, state["alert"],
            reason=f"The recommended option exceeds the EUR {COST_CEILING_EUR} "
                   f"autonomous ceiling or does not fit the failure window.",
        )
        if delivery.get("channel") != "console":
            log.info("GATE          | approval request sent via %s (%s)",
                     delivery.get("channel"),
                     "delivered" if delivery.get("sent") else delivery.get("error"))
            write_event(rid, "decision", {"message": "Approval request dispatched",
                                          **delivery}, "orchestrator")
    except Exception as exc:  # noqa: BLE001 — a notification failure must not block the gate
        log.warning("GATE          | approval notification failed: %s", str(exc)[:120])

    log.info("GATE          | ⏸ awaiting human decision (ceiling €%d)…", COST_CEILING_EUR)
    decision = interrupt(request)
    log.info("GATE          | human decided: %s", decision)
    return {"approval": decision,
            "trace": [_ev(rid, "human_decision", "human", decision=decision)]}


def _escalation_plan(state: OpsState) -> str:
    """Crisp, deterministic human-review handoff for the escalation path.

    On escalation the Reliability agent could not establish a confident assessment
    (interrupted / low-confidence telemetry), so there is nothing to act on. We must
    NOT synthesise an [AUTO]/[APPROVE] action plan from data we don't trust -- that is
    exactly the failure mode the escalation path exists to prevent. Building this in
    Python (no LLM call) keeps the message unambiguous and spends zero tokens on the
    one path where the model has nothing reliable to reason over.
    """
    alert = state["alert"]
    reliability = str(state.get("ops_context", {}).get("reliability", "")).strip()
    return (
        "INSUFFICIENT DATA - HUMAN REVIEW REQUIRED\n\n"
        f"Machine: {alert.get('machine_id', 'unknown')} (plant {state.get('plant_id', 'LEI')})\n"
        "The Reliability agent could not establish a confident failure assessment from the "
        "available telemetry, so the orchestrator stopped before recommending any action.\n\n"
        "[ESCALATE] Route to the on-call reliability engineer for manual inspection.\n"
        "[MONITOR]  Keep the alert open; re-run automatically once a clean sensor window exists.\n\n"
        f"Reliability findings on file:\n{reliability or '(none captured)'}"
    )


def _log_closed_case(state: OpsState, status: str) -> None:
    """Append the finished run to case memory so recall/outcome-validation grow over time.
    Outcome is 'pending' until the predicted failure window resolves. Never raises."""
    try:
        from tools.runtime_inputs import current
        if current():
            return  # Synthetic/evaluation inputs must never train the live case memory.
        from datetime import datetime, timezone

        from tools.recall_cases import append_case
        a = state.get("alert", {})
        append_case({
            "id": "RUN-" + str(state.get("run_id", "?")),
            "date": datetime.now(timezone.utc).date().isoformat(),
            "machine_id": a.get("machine_id", "?"),
            "machine_type": "CNC Machining Center",
            "sensor": a.get("sensor", "?"),
            "signature": f"{a.get('sensor', '?')} {a.get('value', '')}{a.get('unit', '')}".strip(),
            "predicted_rul_h": state.get("predicted_rul"),
            "actual_failure_h": None,
            "decision": str(state.get("approval", status)),
            "outcome": "pending (reconciled when the predicted window resolves)",
            "in_window": None,
        })
    except Exception:  # noqa: BLE001 — logging must never break a run
        pass


def synthesize(state: OpsState) -> dict:
    rid = state["run_id"]
    if state.get("escalate"):
        log.info("PLAN          | escalation handoff (deterministic, no LLM)")
        plan = _escalation_plan(state)
        ev = _ev(rid, "plan", "orchestrator", plan=plan)
        _log_closed_case(state, "escalated")
        log.info("END           | status=escalated")
        return {"final_plan": plan, "status": "escalated", "trace": [ev]}
    decision = state.get("approval") or {}
    blocked = state.get("halt") or (
        state.get("needs_approval") and decision.get("decision") != "approve"
    )
    if blocked:
        status = "halted" if state.get("halt") else "rejected"
        reason = ("Safety clearance failed or is unavailable." if state.get("halt") else
                  "The required procurement approval was not granted.")
        plan = (f"PLAN WITHHELD — {reason}\n\n"
                "[ESCALATE] A responsible human must review the findings before any commitment.\n"
                "[MONITOR] Keep the incident open. No proposed action is authorized by this run.")
        _log_closed_case(state, status)
        return {"final_plan": plan, "status": status,
                "trace": [_ev(rid, "plan", "orchestrator", plan=plan)]}
    log.info("PLAN          | composing final action plan…")
    plan = llm.complete(
        _prompt("orchestrator_system.md"),
        f"Synthesise the FINAL action plan in your exact [AUTO]/[APPROVE]/[MONITOR] format, "
        f"integrating ALL specialist findings in the conversation below. Risk={state.get('risk')}. "
        f"Safety halt={state.get('halt', False)}. Human decision on procurement="
        f"{state.get('approval', 'N/A')}.\n\nALERT: {json.dumps(state['alert'])}\n\n"
        f"FULL AGENT CONVERSATION:\n{_conversation(state)}",
    )
    status = "halted" if state.get("halt") else "complete"
    ev = _ev(rid, "plan", "orchestrator", plan=plan)
    _log_closed_case(state, status)
    log.info("END           | status=%s", status)
    return {"final_plan": plan, "status": status, "trace": [ev]}


# --------------------------------------------------------------------------- #
# Graph assembly
# --------------------------------------------------------------------------- #
def build_graph():
    g = StateGraph(OpsState)
    g.add_node("perceive", perceive)
    g.add_node("supervisor", supervisor)
    for name in AGENT_NAMES:
        g.add_node(name, _make_worker(name))
    g.add_node("finalize", approval_gate)
    g.add_node("synthesize", synthesize)

    g.add_edge(START, "perceive")
    g.add_edge("perceive", "supervisor")
    routes = {a: a for a in AGENT_NAMES}
    routes["finalize"] = "finalize"
    g.add_conditional_edges("supervisor", route_from_supervisor, routes)
    for name in AGENT_NAMES:
        g.add_edge(name, "supervisor")
    g.add_edge("finalize", "synthesize")
    g.add_edge("synthesize", END)

    return g.compile(checkpointer=MemorySaver())


FRIDAY_CASCADE_ALERT = {
    "alert_id": "ALT-22847", "machine_id": "CNC-07-LEI", "plant_id": "LEI",
    "plant_name": "Titan Leipzig (Plant 7)", "sensor": "vibration", "value": 7.2,
    "unit": "mm/s_RMS", "threshold": 6.0, "trend": "rising", "baseline": 3.1,
    "trend_window": "6h", "timestamp": "2026-06-12T14:32:00Z",
    "production_impact_per_day_eur": 180000,
}


def make_initial_state(scenario: str = "happy", alert: dict | None = None) -> OpsState:
    """Fresh graph state. `alert` overrides the Friday Cascade default, which is how the
    evaluation harness drives the graph across its labelled scenarios without touching
    the demo entrypoints."""
    return {"run_id": new_run_id(), "alert": dict(alert or FRIDAY_CASCADE_ALERT),
            "scenario": scenario, "ops_context": {}, "visited": [], "transcript": [],
            "trace": []}
