"""
Titan as an MCP server: the same tools the agents use, for any MCP client.

    python mcp_server.py            # stdio, for Claude Desktop or any MCP host

Titan's own agents still call their tools directly (tools/lc.py). This server is the
reuse path: write each connector once, and any agent (Claude Desktop, a Copilot, another
team's planner) can discover the tools and call them the same way. See decision 010.

What crosses the boundary, and what does not:
  * Read-only tools are exposed as they are, marked read-only.
  * The one action, drafting a work order, always comes back DRAFT_PENDING_APPROVAL and is
    tiered by policy.py: the EUR 500 ceiling and the safety escalation hold here exactly as
    they do inside Titan, because they live in code, not in a prompt.
  * Nothing that sends, commits or bypasses a person is exposed: no notify, no approval.
  * Every call is written to the audit log with channel "mcp".
"""
from __future__ import annotations

import inspect
import json

from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations

import audit_log
import policy
from tools import lc

READ_ONLY = ToolAnnotations(read_only_hint=True, destructive_hint=False, idempotent_hint=True, open_world_hint=False)
DRAFT_ONLY = ToolAnnotations(read_only_hint=False, destructive_hint=False, idempotent_hint=False, open_world_hint=False)

# The tools any outside agent may use, unchanged. notify and audit_assemble stay inside.
EXPOSED = [
    lc.alert_triage, lc.sensor_query, lc.rul_predictor, lc.asset_profile, lc.recall_similar_cases,
    lc.maintenance_schedule, lc.search_technical_docs,
    lc.parts_inventory, lc.supplier_catalog, lc.expedite_cost, lc.tier2_supplier_risk,
    lc.job_reroute, lc.robot_cell_status, lc.shift_conflict_check,
    lc.quality_history, lc.telemetry_correlate, lc.safety_gate,
]

SESSION_RUN = "MCP-SESSION"

server = MCPServer(
    "titan-operations-sentinel",
    instructions=(
        "Titan's plant operations tools: alerts, sensors, remaining useful life, stock, suppliers, "
        "rerouting, quality and safety for the Leipzig, Amsterdam and Munich plants. Start with "
        "alert_triage. Read the titan://policy resource before proposing any action: purchases over "
        "EUR 500 need the plant manager, anything touching safety goes to the safety officer, and "
        "work orders you draft are never committed without a person."
    ),
)


def _audited(tool):
    """Wrap a LangChain tool's function so every MCP call lands in the audit log."""
    fn = tool.func

    def call(**kwargs):
        result = fn(**kwargs)
        try:
            audit_log.write_event(SESSION_RUN, "tool_call", {"tool": tool.name, "input": kwargs, "channel": "mcp"},
                                  agent="mcp_client")
        except Exception:  # noqa: BLE001 - logging must never break a tool call
            pass
        return result

    call.__name__ = tool.name
    call.__doc__ = fn.__doc__
    call.__signature__ = inspect.signature(fn)
    call.__annotations__ = dict(getattr(fn, "__annotations__", {}))
    return call


for _t in EXPOSED:
    server.add_tool(_audited(_t), name=_t.name, description=_t.description, annotations=READ_ONLY)


@server.tool(annotations=DRAFT_ONLY)
def draft_work_order(machine_id: str, plant_id: str, failure_mode: str, parts_required: list[dict],
                     proposed_window: dict, technicians_required: list[str], estimated_duration_hours: float,
                     actions: list[dict], plan_cost_eur: float | None = None) -> dict:
    """Draft a maintenance work order for a person to approve. It is NEVER committed here.
    Each action = {"description": ..., "cost_eur": ...}. The result says who must approve:
    the plant manager for any purchase or a plan over EUR 500 (or with no cost), the safety
    officer for anything touching a safety system. Call after expedite_cost picked an option."""
    wo = lc.work_order_draft.func(machine_id, plant_id, failure_mode, parts_required, proposed_window,
                                  technicians_required, estimated_duration_hours, actions)
    tiers = [{"action": a.get("description", ""), "tier": policy.action_tier(a.get("description", ""))}
             for a in actions if isinstance(a, dict)]
    costs = [a["cost_eur"] for a in actions if isinstance(a, dict) and isinstance(a.get("cost_eur"), (int, float))]
    cost = plan_cost_eur if plan_cost_eur is not None else (sum(costs) if costs else None)
    option = {"cost_eur": cost}
    if any(x["tier"] == "ESCALATE" for x in tiers):
        approver, why = "safety_officer", "an action touches a safety system"
    elif policy.needs_human_approval(option):
        approver, why = "plant_manager", policy.approval_reason(option)
    elif any(x["tier"] == "APPROVE" for x in tiers):
        approver, why = "plant_manager", "the plan includes a purchase or a production window"
    else:
        approver, why = "plant_manager", "every work order is released by a person"
    wo.update({"status": "DRAFT_PENDING_APPROVAL", "approval_required_from": approver, "approval_reason": why,
               "action_tiers": tiers, "plan_cost_eur": cost, "cost_ceiling_eur": policy.COST_CEILING_EUR,
               "committed": False, "channel": "mcp"})
    try:
        audit_log.write_event(SESSION_RUN, "decision", {"tool": "draft_work_order", "work_order_id": wo["work_order_id"],
                                                         "approver": approver, "reason": why, "channel": "mcp"},
                              agent="mcp_client")
    except Exception:  # noqa: BLE001
        pass
    return wo


@server.resource("titan://policy", name="policy", description="The rules every action is held to: tiers, the EUR 500 ceiling, the safety override.",
                 mime_type="application/json")
def policy_resource() -> str:
    return json.dumps({**policy.summary(), "tiers": {
        "AUTO": "throttle within OEM limits, reroute jobs, update logs, draft a work order",
        "APPROVE": "any purchase, or a maintenance window that affects production: plant manager",
        "ESCALATE": "anything touching a safety system: safety officer"}}, indent=1)


@server.prompt(name="investigate_plant", description="A standard first look at a plant: alert, evidence, parts, plan.")
def investigate_plant(plant_id: str = "LEI") -> str:
    return (f"Investigate plant {plant_id}. 1) Call alert_triage and pick the critical alert. 2) Pull sensor_query "
            "and rul_predictor for that machine, and say which numbers are measured and which are estimated. "
            "3) Check parts_inventory, then supplier_catalog and expedite_cost. 4) Run safety_gate on every action. "
            "5) Read titan://policy, then call draft_work_order. Finish with who must approve and why.")


def main() -> None:
    server.run("stdio")


if __name__ == "__main__":
    main()
