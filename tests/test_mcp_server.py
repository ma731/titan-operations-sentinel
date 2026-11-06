"""The MCP server: what it exposes, and that the guarantees survive crossing the boundary."""
import asyncio
import json

import pytest

pytest.importorskip("mcp.server.mcpserver")

import mcp_server as m  # noqa: E402


def run(coro):
    return asyncio.run(coro)


def call(name, args):
    return json.loads(run(m.server.call_tool(name, args)).content[0].text)


def draft(actions, plan_cost_eur=None):
    args = {"machine_id": "CNC-07-LEI", "plant_id": "LEI", "failure_mode": "spindle bearing",
            "parts_required": [{"part_id": "P-4421", "qty": 1}], "proposed_window": {"start": "next stop"},
            "technicians_required": ["maintenance_lead"], "estimated_duration_hours": 6, "actions": actions}
    if plan_cost_eur is not None:
        args["plan_cost_eur"] = plan_cost_eur
    return call("draft_work_order", args)


def test_exposes_the_agent_tools_and_nothing_that_sends_or_commits():
    names = {t.name for t in run(m.server.list_tools())}
    assert {"alert_triage", "sensor_query", "parts_inventory", "safety_gate", "draft_work_order"} <= names
    assert not names & {"notify", "audit_assemble", "work_order_draft"}
    assert len(names) == len(m.EXPOSED) + 1


def test_every_tool_but_the_draft_is_marked_read_only():
    tools = {t.name: t for t in run(m.server.list_tools())}
    assert all(t.annotations.read_only_hint for n, t in tools.items() if n != "draft_work_order")
    assert tools["draft_work_order"].annotations.read_only_hint is False
    assert tools["draft_work_order"].annotations.destructive_hint is False


def test_tools_answer_like_the_agents_see_them():
    alerts = call("alert_triage", {"plant_id": "LEI"})
    assert alerts["critical_alerts_ranked"][0]["machine_id"] == "CNC-07-LEI"


def test_the_ceiling_holds_through_mcp():
    wo = draft([{"description": "Expedite bearing kit from Amsterdam", "cost_eur": 3200}])
    assert wo["status"] == "DRAFT_PENDING_APPROVAL" and wo["committed"] is False
    assert wo["approval_required_from"] == "plant_manager"
    assert "exceeds the autonomous ceiling of EUR 500" in wo["approval_reason"]


def test_unknown_cost_is_never_treated_as_cheap():
    wo = draft([{"description": "Replace bearing kit"}])
    assert wo["approval_required_from"] == "plant_manager"
    assert "no costed option" in wo["approval_reason"]


def test_safety_actions_go_to_the_safety_officer_even_when_cheap():
    wo = draft([{"description": "Bypass the spindle guard interlock during the swap", "cost_eur": 0}])
    assert wo["approval_required_from"] == "safety_officer"


def test_a_cheap_routine_plan_is_still_only_a_draft():
    wo = draft([{"description": "Reroute jobs to CNC-08", "cost_eur": 0}], plan_cost_eur=120)
    assert wo["status"] == "DRAFT_PENDING_APPROVAL" and wo["committed"] is False


def test_policy_resource_and_prompt():
    pol = json.loads(list(run(m.server.read_resource("titan://policy")))[0].content)
    assert pol["cost_ceiling_eur"] == 500 and "ESCALATE" in pol["tiers"]
    assert "investigate_plant" in {p.name for p in run(m.server.list_prompts())}


def test_mcp_calls_are_audited(tmp_path):
    import audit_log
    call("parts_inventory", {"parts": ["P-4421"], "plant_id": "LEI"})
    draft([{"description": "Expedite bearing kit", "cost_eur": 900}])
    events = [json.loads(x) for x in audit_log.LOG_FILE.read_text(encoding="utf-8").splitlines()]
    assert any(e["detail"].get("tool") == "parts_inventory" and e["detail"].get("channel") == "mcp" for e in events)
    assert any(e["type"] == "decision" and e["detail"].get("approver") == "plant_manager" for e in events)
