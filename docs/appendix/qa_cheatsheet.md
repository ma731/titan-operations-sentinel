# Q&A Cheat Sheet — everyone must be able to answer any of these

Appendix artifact (rubric: *Clarity & Presentation*, 20 pts — graded on **individual** delivery;
the professor can ask **anyone** about **any** part). Roles from brief §18.

> Rule: the grader probes your *weakest* presenter. Every member should be fluent on the
> **Universal** questions below, and own their role section cold.

---

## Universal — everyone answers these (brief §15)

**Why an agent, not a dashboard or RPA?**
> A dashboard describes and waits; RPA does one fixed thing. Our agent reasons across 5 domains,
> decides, and produces one costed, safety-gated plan — and *escalates* when data is bad. (See
> `why_agent_not_dashboard.md`.)

**Why this model / architecture?**
> Multi-agent LangGraph: one ReAct specialist per challenge (each picks its own tools), an LLM
> supervisor routes between them. Gemini on the free tier — no paid keys, per the brief. Multi-agent
> over single-agent because the domains need separate expertise + the routing *is* the visible reasoning.

**What happens when a tool returns wrong/incomplete data?**
> Per-agent `try/except` → the run degrades gracefully, doesn't crash. Reliability **fails toward
> caution** (error ⇒ HIGH risk). Interrupted telemetry ⇒ **escalation**, not a guessed plan.

**Where exactly is the human in the loop?**
> The `interrupt()` approval gate: any spend > €500 or production-affecting action pauses for a
> plant-manager approve/reject. Compliance can HALT independently. (See the approval-tier matrix.)

**Top 3 risks + mitigations?**
> (1) Hallucination → reasons only over tool data + compliance gate. (2) Unauthorized spend → €500
> ceiling + human gate. (3) Overconfidence on thin data → escalation/abstain. (Full: `risk_matrix.md`.)

**How would you measure success in production?**
> Three layers: time-to-plan & completion (product), tool-accuracy & escalation calibration (agent),
> downtime-cost-avoided & ROI (business). All derivable from the audit log. (See `evaluation_metrics.md`.)

**What's V2?**
> Trained RUL model (vs heuristic), live SCADA/ERP connectors, multi-provider failover, learned
> routing.

**Why is it feasible now?**
> It runs today on **free-tier** infrastructure with a recorded-replay fallback — zero paid keys,
> demonstrable end-to-end.

---

## Per-role deep questions

**1 — Problem & Business Case**
- Quantify the pain: €180k/day (€7,500/h) downtime; the Friday Cascade persona (plant ops engineer).
- Why is this *specifically* an agent problem? (planning + cross-domain trade-offs + abstention)

**2 — Architecture & Model Choices**
- Draw the graph: perceive → supervisor ⇄ {5 agents} → approval → synthesize.
- Deterministic vs model-driven: routing policy guarantees coverage/termination; the LLM picks
  *order* when ≥2 agents are allowed. ReAct (not plan-execute) because tool needs are discovered, not known.
- Why Gemini: free tier, big context, function calling; one-line `TOS_MODEL` swap to Groq/Ollama.

**3 — Tools, Prompts & Workflow**
- The agent/tool split: tools `fetch / compute / draft / check` — they never decide.
- Frame the 18 tools as **5 capability clusters** (one per agent), not 18 loose tools.
- Prompt pack: system + task + guardrails (composed onto every agent) + self-eval. All four are live.

**4 — Demo & Risk Mitigation**
- Walk the 3 paths: happy (full team → approval), edge (cross-plant adaptation), escalation (dropout → human review).
- Be ready to point to the audit log and the HALT/approval mechanics live.

**5 — Benefits & KPIs / Q&A coordination**
- Four value types: business (downtime avoided), user (time saved), operational (consistency), strategic (free-tier feasibility, audit trail).
- Own the metrics table; field the "how do you know it works" questions.

---

## Traps to rehearse (likely investor-style pushes)
- *"Your data is simulated."* → Mostly yes, and we label it. Schemas are production-shaped; swapping in live SCADA/ERP is a connector, not a redesign. One asset (`TRB-01-LEI`) runs on real NASA benchmark telemetry so the fitted path is exercised on data with a known answer.
- *"RUL is a heuristic."* → For the CNC assets, yes, and every one of those predictions says `declared_thresholds`. There is also a real fitted model, backtested on 707 held-out engines, serving `TRB-01-LEI`. The point is that the system never presents the two as the same kind of claim.
- *"Your model looks wrong on the demo asset."* → It is, on that engine: the bound says at least 34.4 cycles and the truth is 26. The engine was picked before training, by remaining life alone, and kept rather than swapped for a flattering one. That miss is what a measured 80% coverage means in practice.
- *"What if Gemini is down on demo day?"* → Recorded replay runs with zero API calls; backoff handles transient 429s.
- *"18 tools seems like a lot."* → They're 5 clusters of capability, each justified in `tool_catalog.md`, each with a fallback.
