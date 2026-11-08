"""
Titan as an A2A agent: other vendors' agents can find it and hand it a task.

MCP (mcp_server.py) lets an agent use Titan's TOOLS. A2A, the Agent2Agent protocol, is the
other direction: another agent delegates a TASK to Titan as a peer and gets a result back,
without knowing which tools or models Titan uses inside.

  GET  /.well-known/agent-card.json    the Agent Card: who Titan is, what it can do
  POST /a2a                            JSON-RPC 2.0, method "message/send"

Skills run on the deterministic tools and the knowledge graph, so they answer without a
model key. Ask with a data part, {"skill": "...", "args": {...}}, or in plain text: Titan
picks the skill from what is mentioned. If it cannot tell, the task comes back
`input-required` with the list of skills, which is A2A's way of asking a question back.

Nothing here can spend or approve: a safety screen returns the verdict, it does not act.
"""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone

import policy
from tools import knowledge_graph as kg
from tools.alert_triage import alert_triage
from tools.safety_gate import safety_gate

PROTOCOL_VERSION = "0.3.0"
SKILLS = [
    {"id": "plant_triage", "name": "Plant triage",
     "description": "Cuts a plant's raw alert stream to the few deduplicated critical alerts, ranked.",
     "tags": ["maintenance", "alerts"], "examples": ["What needs attention at Leipzig?", "Triage plant LEI"]},
    {"id": "machine_dependencies", "name": "Machine dependencies",
     "description": "What a machine depends on: parts per failure mode with stock and suppliers, Tier-2 risk, technicians, operators.",
     "tags": ["knowledge graph", "maintenance"], "examples": ["What does CNC-07-LEI depend on?"]},
    {"id": "supplier_impact", "name": "Supplier impact",
     "description": "Everything a Tier-1 or Tier-2 supplier reaches: parts, machines, plants, production value exposed per day.",
     "tags": ["supply chain", "knowledge graph", "risk"], "examples": ["Ovako has a furnace outage. What is exposed?"]},
    {"id": "screen_action", "name": "Screen a proposed action",
     "description": "Safety verdict (OK, ESCALATE, HALT) and approval tier for a proposed action. Screens only; never acts.",
     "tags": ["safety", "governance"], "examples": ["Is it safe to bypass the guard interlock on CNC-07?"]},
]
_PLANTS = {"leipzig": "LEI", "amsterdam": "AMS", "munich": "MUC", "lei": "LEI", "ams": "AMS", "muc": "MUC"}


def agent_card(base_url: str) -> dict:
    return {
        "protocolVersion": PROTOCOL_VERSION,
        "name": "Titan Operations Sentinel",
        "description": ("Plant operations agent for CNC machining: alert triage, machine and supplier dependencies "
                        "from a knowledge graph, and safety screening of proposed actions. Never spends or approves: "
                        "purchases over EUR 500 and anything touching safety go to a person."),
        "url": base_url.rstrip("/") + "/a2a",
        "preferredTransport": "JSONRPC",
        "version": "1.0.0",
        "provider": {"organization": "Titan Operations Sentinel (portfolio project)", "url": "https://github.com/ma731/titan-operations-sentinel"},
        "capabilities": {"streaming": False, "pushNotifications": False},
        "defaultInputModes": ["text/plain", "application/json"],
        "defaultOutputModes": ["text/plain", "application/json"],
        "skills": SKILLS,
    }


# --------------------------------------------------------------------------- skills -- #
def _plant_triage(plant_id: str = "LEI") -> tuple[str, dict]:
    r = alert_triage(plant_id)
    top = r.get("critical_alerts_ranked", [])[:3]
    lines = [f"{r.get('total_alerts_today', 0):,} alerts today at {plant_id}; {r.get('deduplicated_critical_count', len(top))} critical after deduplication."]
    lines += [f"- {a.get('machine_id')}: {a.get('summary') or a.get('message') or a.get('alert_id')}" for a in top]
    return "\n".join(lines), r


def _machine(machine_id: str) -> tuple[str, dict]:
    r = kg.machine_dependencies(machine_id)
    if "error" in r:
        return r["error"], r
    risks = sorted({f"{t['tier2']} ({t['risk']})" for f in r["failure_modes"] for p in f["parts"] for s in p["suppliers"]
                    for t in s["tier2"] if t["risk"] != "LOW"})
    text = (f"{r['machine']} at {r['plant']}, EUR {r['value_per_day_eur'] or 0:,} of production a day. "
            f"{len(r['failure_modes'])} failure modes tracked; equivalent machines: {', '.join(r['equivalent_machines']) or 'none'}."
            + (f" Elevated upstream risk: {', '.join(risks)}." if risks else ""))
    return text, r


def _supplier(supplier_id: str) -> tuple[str, dict]:
    r = kg.supplier_impact(supplier_id)
    if "error" in r:
        return r["error"], r
    text = (f"{r['supplier']} reaches {', '.join(r['machines']) or 'no machine'} at {', '.join(r['plants']) or '-'}: "
            f"EUR {r['production_value_exposed_per_day_eur']:,} of production a day exposed."
            + (f" No other source for: {', '.join(r['parts_without_another_source'])}." if r["parts_without_another_source"] else ""))
    return text, r


def _screen(action: str) -> tuple[str, dict]:
    gate, tier = safety_gate(action), policy.action_tier(action)
    who = {"ESCALATE": "the safety officer", "APPROVE": "the plant manager", "AUTO": "nobody beyond the log"}[tier]
    if gate["verdict"] == "HALT":
        text = "Safety gate: HALT. This action is stopped; only the safety officer can review it."
    else:
        text = f"Safety gate: {gate['verdict']}. Approval tier: {tier}, so {who} must sign off."
    text += f" Rule {gate.get('matched_rule')}: {gate.get('basis')}." if gate.get("matched_rule") else ""
    return text, {"safety": gate, "tier": tier, "ceiling_eur": policy.COST_CEILING_EUR}


RUN = {"plant_triage": lambda a: _plant_triage(a.get("plant_id", "LEI")),
       "machine_dependencies": lambda a: _machine(a["machine_id"]),
       "supplier_impact": lambda a: _supplier(a["supplier_id"]),
       "screen_action": lambda a: _screen(a["action"])}


def pick_skill(text: str) -> tuple[str, dict] | None:
    """Choose a skill from plain text. Deliberately simple and predictable."""
    low = text.lower()
    if re.search(r"\b(safe|allowed|may we|can we|ok to|okay to|screen|bypass|disable|purchase|buy|order)\b", low):
        return "screen_action", {"action": text}
    g = kg.build()
    for nid, n in g.nodes.items():
        if n["kind"] in ("supplier", "tier2_supplier"):
            names = {nid.lower(), str(n.get("name", "")).lower().split(" (")[0]}
            if any(x and x in low for x in names):
                return "supplier_impact", {"supplier_id": nid}
    m = re.search(r"\b([a-z]{3}-\d{2}-[a-z]{3})\b", low)
    if m and g.kind(m.group(1).upper()) == "machine":
        return "machine_dependencies", {"machine_id": m.group(1).upper()}
    if re.search(r"\b(triage|alerts?|attention|what.?s wrong|status)\b", low):
        plant = next((v for k, v in _PLANTS.items() if re.search(rf"\b{k}\b", low)), "LEI")
        return "plant_triage", {"plant_id": plant}
    return None


# --------------------------------------------------------------------------- JSON-RPC -- #
def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _task(context_id: str, state: str, text: str, data: dict | None = None, skill: str | None = None) -> dict:
    tid = str(uuid.uuid4())
    task = {"kind": "task", "id": tid, "contextId": context_id,
            "status": {"state": state, "timestamp": _now(),
                       "message": {"kind": "message", "role": "agent", "messageId": str(uuid.uuid4()),
                                   "parts": [{"kind": "text", "text": text}], "taskId": tid, "contextId": context_id}}}
    if state == "completed":
        parts = [{"kind": "text", "text": text}] + ([{"kind": "data", "data": data}] if data is not None else [])
        task["artifacts"] = [{"artifactId": str(uuid.uuid4()), "name": skill or "result", "parts": parts}]
    return task


def _error(req_id, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}


def handle(payload: dict) -> dict:
    """One JSON-RPC request in, one response out."""
    req_id = payload.get("id") if isinstance(payload, dict) else None
    if not isinstance(payload, dict) or payload.get("jsonrpc") != "2.0":
        return _error(req_id, -32600, "Invalid Request")
    if payload.get("method") != "message/send":
        return _error(req_id, -32601, f"Method not found: {payload.get('method')} (this agent supports message/send)")
    msg = (payload.get("params") or {}).get("message") or {}
    parts = msg.get("parts") or []
    if not parts:
        return _error(req_id, -32602, "Invalid params: message.parts is required")
    context_id = msg.get("contextId") or str(uuid.uuid4())
    data = next((p.get("data") for p in parts if p.get("kind") == "data" and isinstance(p.get("data"), dict)), None)
    text = " ".join(p.get("text", "") for p in parts if p.get("kind") == "text").strip()

    if data and data.get("skill"):
        skill, args = data["skill"], data.get("args") or {}
    else:
        chosen = pick_skill(text)
        if not chosen:
            names = "; ".join(f"{s['id']} ({s['examples'][0]})" for s in SKILLS)
            return {"jsonrpc": "2.0", "id": req_id,
                    "result": _task(context_id, "input-required", f"Which of these do you need? {names}")}
        skill, args = chosen
    if skill not in RUN:
        return {"jsonrpc": "2.0", "id": req_id,
                "result": _task(context_id, "rejected", f"Unknown skill {skill!r}. Skills: {', '.join(RUN)}.")}
    try:
        out_text, out_data = RUN[skill](args)
    except KeyError as exc:
        return {"jsonrpc": "2.0", "id": req_id,
                "result": _task(context_id, "input-required", f"{skill} needs {exc.args[0]!r}.")}
    try:
        import audit_log
        audit_log.write_event("A2A-SESSION", "tool_call", {"skill": skill, "input": args, "channel": "a2a"}, agent="a2a_client")
    except Exception:  # noqa: BLE001 - logging must never break a task
        pass
    return {"jsonrpc": "2.0", "id": req_id, "result": _task(context_id, "completed", out_text, out_data, skill)}
