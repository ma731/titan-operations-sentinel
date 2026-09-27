# Build Progress — Session 3 (June 13, 2026): 6-agent brain, all 5 challenges

**Goal change:** make the specialists *real autonomous agents that talk to each other*, and
cover **all five** TMC challenges (not just maintenance + supply chain).

**What changed**
- 2 deterministic nodes → **6 agents**: orchestrator + 5 ReAct specialists (`agents.py`,
  `create_react_agent`), one per challenge. Each agent's LLM picks its own tools; the
  orchestrator (`supervisor` node) controls routing — "autonomous tools, guided handoffs".
- **+9 tools** (18 total) and `tools_lc.py` `@tool` wrappers; +6 data files for challenges 3/4/5.
- **Shared blackboard** (`ops_context`) so agents read each other's findings.
- **Routing policy** (`_allowed_next`) guarantees coverage on HIGH risk and termination
  (compliance_safety always gates before FINISH); LLM picks order when ≥2 agents are allowed.
- **Safety override:** compliance_safety can HALT. **HITL:** `interrupt()` approval gate kept.
- New prompts: production / quality / compliance agents + supervisor.
- Resilience: per-agent try/except (a flaky Llama tool call degrades, doesn't crash the run);
  `SHARED_FOOTER` tells agents to pass plain numeric args (Llama emits `180000/24` otherwise).

**Verified LIVE on Groq:** happy path end-to-end through all 5 agents — reliability (RISK:HIGH)
→ supply_chain → production (autonomously rerouted to CNC-08 to dodge the op_Keller conflict)
→ quality (vibration↔defect correlation) → compliance (VERDICT: SIGN-OFF) → ⏸ approval → complete.
`pytest` flow tests: **happy ✅, edge ✅** live.

**Known limitation found:** Groq free tier = **100k tokens/day**. The 6-agent system is
token-heavy; three full scenarios exhaust it (the escalation flow test failed only because the
quota ran out mid-run, not a logic bug). For rehearsals use Ollama (`TOS_MODEL=ollama:…`) or the
Groq Dev tier; consider trimming agent context. **TODO:** re-verify escalation once quota resets.

---

# Build Progress — Session 2 (June 13, 2026): LangGraph + Groq reframe

**Why:** assignment §14 forbids paid API keys; we have no Anthropic key. Migrated off
the direct Anthropic SDK to **LangGraph** orchestration on **Groq / Llama 3.3 70B**
(free tier), and closed the rubric gaps flagged in the compliance audit.

**What changed**
- `agents/*.py` (Anthropic SDK) **removed** → replaced by `graph.py` (LangGraph `StateGraph`).
- New `llm.py` — provider-agnostic model factory (`TOS_MODEL`), Groq primary, Ollama
  offline fallback, templated stub if no provider (so tools/tests run with no network).
- New `audit_log.py` → `logs/tos_audit.jsonl` (logging/monitoring component, §6).
- Tools reused unchanged except 3 small extensions: `supplier_catalog(scenario=)`,
  `sensor_query` status passthrough, `maintenance_schedule` emergency slots.
- New scenario data: `data/sensors/CNC-07-LEI_dropout.json` (escalation),
  `data/suppliers/supplier_catalog_edge.json` (edge / cross-plant).
- `app.py` rebuilt: live trace + real Approve/Reject buttons wired to `interrupt()`.
- `demo_scenario.py` rebuilt: streams the graph, handles the interrupt; 3 scenarios.
- Tests rewritten — 14 offline tests (tools + all 3 graph paths). **All passing.**
- `docs/tool_catalog.md` added (pre-submission deliverable, §8 format).

**Gaps closed vs the compliance audit**
- Edge path (cross-plant adaptation) + escalation path (telemetry dropout) — now real, demoable.
- Logging/monitoring — JSONL audit log per run.
- HITL — `interrupt()` pauses the graph for human approve/reject (live, not described).
- Memory — `MemorySaver` checkpointer = episodic; labelled deterministic vs model-driven.

**Verified offline (no key):** `pytest` 14/14 green; happy → approval → complete;
edge → adapts to cross-plant MUC (ROI 323.1) → complete; escalation → escalated, no supply.

**Still TODO:** add a real `GROQ_API_KEY` and rehearse the live on-stage run; slides.

---

# Build Progress — Session 1 (June 10, 2026)

Skeleton complete. Agent loop is wired end-to-end. All tools tested and passing. Next person picks up from **Step 1** below.

---

## What was built this session

### Directory structure
Full repo scaffold matching the brainstorm architecture:
```
agents/ tools/ data/ prompts/ tests/ app.py demo_scenario.py
```

### Tools layer — 8 tools, all tested ✅
| File | What it does | Reads from |
|------|-------------|-----------|
| `tools/sensor_query.py` | 72h sensor readings for a machine | `data/sensors/<id>_<window>.json` |
| `tools/rul_predictor.py` | Remaining Useful Life estimate + confidence | historical match in `data/sensors/` |
| `tools/asset_profile.py` | Machine specs, BOM, failure modes | `data/assets/asset_profiles.json` |
| `tools/maintenance_schedule.py` | Scheduled windows per plant | `data/assets/maintenance_schedule.json` |
| `tools/parts_inventory.py` | On-site + warehouse stock | `data/inventory/parts_stock.json` |
| `tools/supplier_catalog.py` | Suppliers, lead times, expedite costs | `data/suppliers/supplier_catalog.json` |
| `tools/expedite_cost.py` | ROI ranking of procurement options | pure calculation |
| `tools/work_order_draft.py` | Draft WO (not committed until human approves) | — |
| `tools/notify.py` | Draft approval notification (not sent until reviewed) | — |

### Agent layer — 3 agents wired ✅
| File | Role |
|------|------|
| `agents/orchestrator.py` | Receives alert, routes to sub-agents, synthesizes final action plan |
| `agents/maintenance_agent.py` | Sensor → RUL → asset profile → schedule check |
| `agents/supply_chain_agent.py` | Inventory → supplier → ROI → draft WO → draft notify |

All agents use direct Anthropic SDK `tool_use` loop. Chain-of-thought exposed via `stream_callback` for Streamlit rendering.

### Data files — Friday Cascade scenario baked in ✅
| File | What's in it |
|------|-------------|
| `data/sensors/CNC-07-LEI_72h.json` | 37 hourly readings, vibration 3.1→7.2 mm/s, bearing temp +14°C, current spikes |
| `data/sensors/CNC-03-LEI_hist.json` | Sept 2023 historical bearing failure — RUL pattern match |
| `data/assets/asset_profiles.json` | CNC-07-LEI specs, BOM (P-4421, P-7803), equivalent machines |
| `data/assets/maintenance_schedule.json` | No LEI window for 9 days. Emergency slot: Sat 06:00 |
| `data/inventory/parts_stock.json` | P-4421: 0 on-site, 3 AMS. P-7803: 1 on-site (need 2), 4 AMS |
| `data/suppliers/supplier_catalog.json` | Schaeffler: 18h expedite €3,200. AMS transfer: 36h €420 |

### Prompts — 5 files, contract-first design ✅
| File | Purpose |
|------|---------|
| `prompts/orchestrator_system.md` | Role, autonomy policy, cost ceiling (€500), output format |
| `prompts/maintenance_agent_system.md` | Tool order enforced, structured output spec |
| `prompts/supply_chain_agent_system.md` | Parts gap → ROI → WO → notify, zero self-approval |
| `prompts/guardrails.md` | Hard constraints + low-confidence escalation template |
| `prompts/self_eval.md` | Per-agent checklist before each response |

### Supporting files ✅
- `CLAUDE.md` — project context and conventions (read this first)
- `demo_scenario.py` — terminal runner for the Friday Cascade
- `app.py` — Streamlit placeholder
- `requirements.txt`, `.env.example`, `.gitignore`

---

## Key decisions locked in

| Decision | Rationale |
|----------|-----------|
| Direct Anthropic SDK (no LangChain) | Chain-of-thought must be visible for the 25pt demo dimension |
| Model: `claude-sonnet-4-6` | All three agents |
| Hierarchical orchestrator pattern | Keeps agent/tool decision boundaries explicit |
| Risk-first sort in `expedite_cost` | Ensures Schaeffler (LOW risk, 18h) ranks above warehouse transfer (MEDIUM risk, 36h) even though warehouse is cheaper |
| `stream_callback` contract | Every agent step emits a typed event — Streamlit subscribes to this |

---

## What's left to build

### Step 1 — Environment setup (anyone, ~5 min)
```bash
pip install -r requirements.txt
cp .env.example .env
# add your ANTHROPIC_API_KEY to .env
python demo_scenario.py   # should run the full Friday Cascade in terminal
```

### Step 2 — Streamlit UI (owner: whoever builds the demo)
`app.py` is a placeholder. Needs:
- Trigger button for the Friday Cascade alert
- Live rendering of `stream_callback` events (reasoning, tool calls, tool results)
- Final action plan display with AUTO/APPROVE/MONITOR color coding
- Edge case toggle (parts unavailable from all suppliers)
- Escalation toggle (sensor dropout mid-analysis)

Reference: brainstorm §3 has the exact demo script. Target: 90s agent run visible on screen.

### Step 3 — Tests (owner: whoever does QA)
`tests/test_tools.py` — unit test each tool with known inputs/outputs
`tests/test_agent_flow.py` — integration test the full orchestrator loop

### Step 4 — Slides (owner: whoever owns presentation)
Brainstorm §8 has the full 6-slide plan. Architecture diagram from CLAUDE.md §2.

---

## How the agent loop works (for teammates)

```
demo_scenario.py
  └── run_orchestrator(alert)              # agents/orchestrator.py
        ├── run_maintenance_agent(alert)   # agents/maintenance_agent.py
        │     tools: sensor_query → rul_predictor → asset_profile → maintenance_schedule
        │     returns: assessment text
        │
        ├── [if high risk] run_supply_chain_agent(assessment)  # agents/supply_chain_agent.py
        │     tools: parts_inventory → supplier_catalog → expedite_cost → work_order_draft → notify
        │     returns: supply chain plan text
        │
        └── _synthesize_action_plan()      # final synthesis call, no tools
              returns: structured [AUTO]/[APPROVE]/[MONITOR] plan
```

Every step emits to `stream_callback` — that's what the Streamlit UI renders live.

---

## Demo scenario values (Friday Afternoon Cascade)

| Field | Value |
|-------|-------|
| Machine | CNC-07-LEI (CNC Machining Center #7, Leipzig) |
| Alert | Vibration 7.2 mm/s RMS, threshold 6.0, rising from 3.1 baseline over 6h |
| RUL prediction | 52–76h (95% confidence), spindle_bearing_failure |
| Parts needed | P-4421 (spindle bearing kit), P-7803 (hydraulic seal set x2) |
| Parts gap | P-4421: 0 on-site. P-7803: 1 on-site, need 2 |
| Recommended option | Schaeffler expedite, 18h, €3,200 (LOW risk) |
| Cost of inaction | €180,000/day = €7,500/hour |
| ROI of recommended plan | 79.7:1 as presented in June; the formula was wrong, see F-09 (now 116h / €870k avoided, upper bound) |
| Emergency window | Saturday 06:00 (requires plant manager approval) |

---

*Session 1 complete. Repo is clean and ready to push.*
