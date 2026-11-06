# 010. Expose Titan's tools over MCP, without rewiring the agents

**Accepted, November 2026.**

## Context

Titan's five agents call about twenty tools directly, through LangChain wrappers in
`tools/lc.py`. That is the right design for one system built by one team: no extra process,
nothing to host. It stops being right the moment a second agent wants the same tools: a
planner's Copilot, Claude Desktop, another team's assistant. Each one would need its own
integration with each tool. Five apps on five systems is twenty-five integrations.

The Model Context Protocol (MCP) is the standard answer: each system is wrapped once as an
MCP server, any MCP client can discover its tools and call them the same way. Five apps on
five systems becomes five servers plus five clients.

## Decision

**Add an MCP server beside the agents, not under them.** `mcp_server.py` exposes the same
tool functions over stdio. The agents keep calling the tools directly, so the 34 labelled
scenarios, the eval and the demo are untouched.

**Read-only first.** Seventeen tools are exposed as they are, each marked read-only in the
MCP tool annotations. `notify` (sends) and `audit_assemble` (reads other runs' logs) stay
inside.

**One action, and it is only ever a draft.** `draft_work_order` always returns
`DRAFT_PENDING_APPROVAL` with `committed: false`, and names who must approve using the same
`policy.py` functions the graph uses: the safety officer if any action touches a safety
system, the plant manager if the plan costs more than EUR 500, has no cost, or includes a
purchase. An outside agent cannot talk its way past the ceiling, because the ceiling is not
in a prompt.

**Every call is audited**, with `channel: "mcp"`, in the same log the console reads.

**Also a resource and a prompt**, so the server shows all three MCP capabilities:
`titan://policy` (the tiers and the ceiling, for a client to read before acting) and
`investigate_plant` (a standard first look at a plant).

## Consequences

- `python scripts/mcp_demo.py` starts the server as a separate process and runs an
  investigation through it, with no model and no key. Claude Desktop can use the same
  server with a three-line config.
- `tests/test_mcp_server.py` checks the exposed set, the read-only annotations, the ceiling,
  unknown cost, the safety escalation and the audit trail through the MCP boundary.
- Not done: authentication, which a stdio server on one machine does not need but a shared
  HTTP server would; and moving the agents themselves onto MCP clients, which would make
  Titan dogfood its own server at the cost of a process hop per tool call.
