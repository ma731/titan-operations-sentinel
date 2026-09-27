# Evidence Checklist — what proves each requirement

A fast map from every grading dimension and design-thinking pillar to the exact file /
feature that proves it, plus a one-line talking point. Use it to build the deck and to
field Q&A. Honest caveats are listed so no one over-claims.

---

## Part A — Grading rubric (100 pts)

### 1. Problem Framing, Agent Goals & Prompt — 15
- **Proof:** `docs/agentic_assignment_brief.md`, `docs/appendix/why_agent_not_dashboard.md`, `data/assets/asset_profiles.json` (€180,000/day), prompt pack (`docs/appendix/prompt_pack.md`).
- **Say:** "One plant manager, one alert, €180,000/day of downtime at risk; the agent hands back one costed, safety-gated plan: 116h of downtime avoided for a €3,200 expedite."

### 2. Agentic System Architecture — 10
- **Proof:** `graph.py` (LangGraph `StateGraph`, supervisor + 5 ReAct workers, conditional edges, `MemorySaver`), `docs/architecture.mmd`, `docs/appendix/sequence_diagram.md`.
- **Say:** "Orchestrator + 5 autonomous specialists. Guided autonomy: a policy guarantees coverage and termination; the LLM picks order. Migrated from direct SDK to LangGraph for the interrupt + checkpointer."

### 3. Tools, Actions & Feasibility — 15
- **Proof:** `tools/` (19 pure functions), `tools/lc.py` (`@tool` wrappers, grouped per agent), `docs/tool_catalog.md` (when / when-NOT / fallback / auth tier).
- **Say:** "Agents decide, tools act. Writes are drafts (`work_order_draft` → DRAFT_PENDING_APPROVAL); `safety_gate` is a hard control. Runs free-tier, so it's feasible."

### 4. Agentic Thinking & Autonomy — 25 (highest)
- **Proof:** the live demo (web console), `agents/factory.py` (`create_react_agent`), `graph.py` (`approval_gate` `interrupt()`, `_escalation_plan`, FOLLOWUP), the three scenarios in `webapp/frontend/src/cascade.js`, the Learning view + `tools/recall_cases.py` + `append_case` in `graph.synthesize`.
- **Say:** "Perceive → reason → act → learn. Three paths: Cascade gates a human, Edge adapts autonomously under €500, Escalation refuses to act on bad data. It recalls precedent and logs every closed run back to case memory."

### 5. Risk Awareness & Mitigation — 15
- **Proof:** `docs/appendix/risk_matrix.md`, `failure_modes.md`, `confidence_policy.md`; in code: `COST_CEILING_EUR` **code-enforced** in `graph.py` supply_chain, compliance HALT, fail-toward-caution (reliability error → risk HIGH), `tests/test_tools.py` (ceiling test).
- **Say:** "The €500 ceiling is enforced in code, not just the prompt — sub-ceiling runs autonomously, over-ceiling gates. Compliance can HALT. On thin data it abstains."

### 6. Clarity, Presentation Quality & Creativity — 20
- **Proof:** the web console (orchestration graph, presenter mode, ⌘K, fleet, Run History, Learning view), `docs/appendix/qa_cheatsheet.md`, this checklist.
- **Caveat (do this):** slides + each member presenting and answering Q&A are what this dimension actually grades. Build the deck and rehearse one section per person — ideally a section you did NOT build.

---

## Part B — The 8 design-thinking pillars → slides

| # | Pillar | Evidence pointer | Slide |
|---|--------|------------------|-------|
| 1 | Agent goals | brief + why_agent_not_dashboard + €180k/day, 116h avoided | Problem |
| 2 | Input & context | `data/` (telemetry, inventory, suppliers, quality, compliance); memory = transcript + checkpointer + case library | Problem / Architecture |
| 3 | Tools & actions | `docs/tool_catalog.md`, `tools/lc.py` | Architecture |
| 4 | Lifecycle (Perceive→Reason→Act→Learn) | `graph.py` + Learning view + `tools/recall_cases.py` | Demo |
| 5 | Architecture pattern | `graph.py`, `architecture.mmd`, `sequence_diagram.md` | Architecture |
| 6 | Risks, guardrails, HITL | risk_matrix / failure_modes / confidence_policy; code-enforced ceiling + HALT + interrupt | Risks |
| 7 | Example run | the Friday Cascade (3 paths) — the live demo / Replay | Demo |
| 8 | Tech stack | Python + LangGraph + FastAPI + React/Vite; provider-agnostic LLM (Gemini/Groq/Azure) | Solution / Next steps |

---

## Part C — Honest caveats (answer these without flinching)

- **RUL predictor is a heuristic** (threshold table in `tools/rul_predictor.py`), not a trained model — say so; the architecture is the contribution, the model is swappable.
- **Replay is a recording** (`cascade.js`); Live is the real LLM. Lead with that — it reads as discipline (zero-cost, can't-fail demo).
- **Learning:** recall + write-back + the decision tally are live; reflection-replay and automatic signature down-weighting are the production *design* (badged "design" in the UI).
- **Routing** is "guided autonomy": deterministic policy guarantees coverage/termination; the LLM picks order and the specialists choose their own tools.
- **Episodic memory** = the LangGraph checkpointer (in-process for the demo).

---

## Demo-day runbook (90 seconds)
1. Sign in as a presenter → showcase → **Launch console**.
2. **Replay → Cascade**, approve the €500 gate, show the costed plan + ROI.
3. **Edge** → note it runs autonomously (under €500). **Escalation** → note it abstains.
4. Open **Learning** (precedent + write-back) and **Agent Chat** (type a crisis).
5. Optional: flip to **Live** (Gemini/Groq/Azure) for one run as the "it's real" proof.
