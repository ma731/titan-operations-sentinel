"""
Talk to Titan's MCP server the way Claude Desktop does: start it as a separate process,
discover its tools, read the policy, and run a short investigation. No model, no key.

    python scripts/mcp_demo.py
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

ROOT = Path(__file__).resolve().parents[1]


def _json(result) -> dict:
    return json.loads(result.content[0].text)


async def main() -> int:
    params = StdioServerParameters(command=sys.executable, args=[str(ROOT / "mcp_server.py")], cwd=str(Path.home()))
    async with stdio_client(params) as (read, write), ClientSession(read, write) as s:
        await s.initialize()
        tools = (await s.list_tools()).tools
        print(f"Connected. {len(tools)} tools discovered, none written for this client:")
        print("  " + ", ".join(sorted(t.name for t in tools)))
        pol = json.loads((await s.read_resource("titan://policy")).contents[0].text)
        print(f"Policy: autonomous ceiling EUR {pol['cost_ceiling_eur']}.")

        alerts = _json(await s.call_tool("alert_triage", {"plant_id": "LEI"}))
        top = alerts["critical_alerts_ranked"][0]
        print(f"1. alert_triage: {alerts['total_alerts_today']:,} alerts today, top one on {top['machine_id']}.")
        stock = _json(await s.call_tool("parts_inventory", {"parts": ["P-4421"], "plant_id": "LEI"}))
        print(f"2. parts_inventory: {json.dumps(stock)[:140]}...")
        gate = _json(await s.call_tool("safety_gate", {"action_description": "Bypass the spindle guard interlock to keep running"}))
        print(f"3. safety_gate on a bypass: {gate.get('verdict')}.")
        wo = _json(await s.call_tool("draft_work_order", {
            "machine_id": top["machine_id"], "plant_id": "LEI", "failure_mode": "spindle bearing",
            "parts_required": [{"part_id": "P-4421", "qty": 1}], "proposed_window": {"start": "next scheduled stop"},
            "technicians_required": ["maintenance_lead"], "estimated_duration_hours": 6,
            "actions": [{"description": "Expedite bearing kit from Amsterdam", "cost_eur": 3200}]}))
        print(f"4. draft_work_order: {wo['status']}, needs the {wo['approval_required_from']} ({wo['approval_reason']}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
