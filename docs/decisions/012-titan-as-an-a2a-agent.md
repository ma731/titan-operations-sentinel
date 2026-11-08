# 012. Publish Titan as an A2A agent, next to the MCP server

**Accepted, November 2026.**

## Context

MCP (decision 010) lets another agent use Titan's tools: the caller does the reasoning and
calls `parts_inventory` itself. Some callers should not need to know Titan's tools at all: a
procurement agent from another vendor wants to ask "our steel supplier has an outage, what
is exposed?" and get an answer. That is delegation between peers, which is what the
Agent2Agent protocol (A2A, now a Linux Foundation project) standardises: an Agent Card at a
well-known URL saying what the agent can do, and JSON-RPC to hand it a task.

## Decision

- `GET /.well-known/agent-card.json` (and the older `/.well-known/agent.json`) serve the
  card: four skills, `plant_triage`, `machine_dependencies`, `supplier_impact` and
  `screen_action`, each with examples.
- `POST /a2a` takes `message/send`. A data part `{"skill", "args"}` is exact; plain text is
  routed to a skill by simple, predictable rules. If Titan cannot tell what is wanted, the
  task comes back `input-required` with the options, which is the protocol's way of asking
  back; a missing argument does the same.
- Skills run on the deterministic tools and the knowledge graph, so they answer without a
  model key and give the same answer twice.
- `screen_action` returns the safety verdict and approval tier. It never acts: nothing
  reachable over A2A spends, approves or commits. Every task is in the audit log with
  `channel: "a2a"`.

## Not done

Streaming and push notifications (`capabilities` says so), authentication (the card would
declare it before this ran outside one machine), and a full agent investigation as a skill,
which would map Titan's human approval onto A2A's `input-required` state: the natural next
step.
