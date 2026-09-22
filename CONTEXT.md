# CONTEXT — handoff for the team

> **Historical snapshot, June 2026. Do not read this first.**
>
> This was the handoff note when the project moved to LangGraph, and it is kept because it
> records why that decision was taken. It has since gone out of date: the branch it names
> is merged, the repository has been renamed to `titan-operations-sentinel`, and the tool
> and test counts below are lower than the current ones.
>
> For the current state start with [`README.md`](README.md), then
> [`CLAUDE.md`](CLAUDE.md) for conventions and
> [`eval/results/scorecard.md`](eval/results/scorecard.md) for what the system measurably
> does.

**Branch at the time:** `feat/multi-agent-langgraph` (since merged).

---

## TL;DR — what changed and why

The repo started as a 2-agent skeleton built on the **Anthropic SDK**. I reframed it into a
**6-agent operations brain on LangGraph + Groq (Llama 3.3 70B, free tier)**, covering **all five**
Titan challenges instead of just two. Two reasons:

1. The assignment forbids **paid API keys** in the demo (§14) — we had no Anthropic key, so we moved
   to Groq's free tier.
2. We decided the agents should be **real autonomous agents that talk to each other**, and that the
   system should address **all five** case-study challenges, not just maintenance + supply chain.

Everything runs with **no paid keys**. Tool logic and tests run fully offline.

---

## What the system does now

One sensor alert triggers a team of agents that reason across every domain and produce a single,
costed action plan for a human to approve.

| Agent | Challenge | What it does |
|-------|-----------|--------------|
| Orchestrator | coordination | routes between agents (guided), synthesises the final plan |
| Reliability | 1 maintenance | triage 22k alerts → RUL → failure mode → parts needed |
| Supply Chain | 2 supply | parts gap, supplier + Tier-2 risk, sourcing ROI |
| Production & Human-Robot | 3 coordination | reroute jobs without breaking shift/robot constraints |
| Quality & Traceability | 4 quality | correlate defects with telemetry; protect reroute targets |
| Compliance & Safety | 5 safety/audit | OSHA-gate every action (can HALT); assemble audit trail |

**Key mechanics:** each specialist is an autonomous ReAct agent (picks its own tools); the
orchestrator decides who runs next; agents communicate in **natural language** through a shared
transcript and can send a `FOLLOWUP:` to each other; Compliance can **HALT** the plan; any spend
> €500 pauses for a **human approve/reject**; every step is written to an audit log.

See the diagram at the top of `README.md`.

---

## How to run it (from the repo root)

```bash
pip install -r requirements.txt
cp .env.example .env                   # add your own free GROQ_API_KEY (console.groq.com)

python scripts/run_demo.py             # happy path (terminal, auto-approves)
python scripts/run_demo.py edge        # cross-plant adaptation
python scripts/run_demo.py escalation  # telemetry dropout → escalate
python scripts/view_run.py             # REPLAY a recorded run — no tokens, great to just "see it"
python -m pytest tests/test_tools.py   # 17 offline tests, no key needed

cd webapp/frontend && npm install && npm run dev   # live UI with the approve/reject button (see webapp/README.md)
```

> **Important — Groq free tier is ~100k tokens/day.** The 6-agent system is token-heavy; a few full
> runs exhaust it. To demo without burning quota, use `scripts/view_run.py` to replay a past run, or
> set `TOS_MODEL=ollama:llama3.1:8b` in `.env` to run a local model.

---

## Where things live

```
graph.py            the orchestrator (routing, transcript, HALT, approval gate)
agents/factory.py   builds the 5 ReAct agents from a prompt + a tool group
tools/              18 tools (one file each) + lc.py (the @tool wrappers)
prompts/            each agent's system prompt + supervisor + guardrails
data/               all the simulated scenario data (per challenge)
llm.py              model selection (Groq default; Ollama/offline fallback)
audit_log.py        writes logs/tos_audit.jsonl
scripts/            run_demo.py, view_run.py
webapp/             web console (React/Vite + FastAPI SSE) — see webapp/README.md
tests/              tool tests (offline) + flow tests (need a key)
docs/               brief, brainstorm, case study, tool_catalog.md, architecture.mmd, PROGRESS.md
```

To change an agent's **behaviour** → edit its prompt in `prompts/`.
To change its **tools** → edit its group in `tools/lc.py`.
To add an **agent** → add to `AGENT_SPECS` (agents/factory.py) + a prompt + a tool group + a node and
routing entry in `graph.py`.

---

## Status

**Done & verified**
- All 5 challenges implemented; 18 tools; full audit log; web console.
- 17/17 offline tool tests pass.
- Happy + edge paths verified **live on Groq** end-to-end (incl. the production agent adapting a
  reroute to avoid an operator conflict, and Compliance returning a sign-off verdict).

**Honest limitations (say these in Q&A)**
- RUL comes from **two estimators, and every prediction says which one produced it**. The
  CNC assets use declared thresholds (a heuristic, never backtested). `TRB-01-LEI` uses a
  model fitted to NASA C-MAPSS run-to-failure data, scored on 707 held-out engines
  (`eval/results/rul_backtest.md`). Do not claim the CNC numbers are measured.
- **Most data is simulated** (realistic schemas, no live SCADA/SAP). The exception is
  `TRB-01-LEI`, whose telemetry is real C-MAPSS benchmark data with a known true answer.
- Live runs are bounded by the **Groq daily token budget**.

---

## Open tasks (pick one up)

- [ ] **Slides** (~6, per the brief) — not started. Architecture diagram is in `docs/architecture.mmd`.
- [ ] **Live-verify the escalation path** on Groq (only failed earlier because the daily quota ran out).
- [ ] **Polish the escalation output** — it currently routes through the synthesiser; could restore a
      crisp "INSUFFICIENT DATA — human review" message (see `graph.py`).
- [ ] **Trim token usage** if we want more live runs on the free tier (smaller transcript/context).
- [ ] **Review the PR** and merge to `main`.

Questions on any part — everything is documented in `README.md` (project) and `docs/tool_catalog.md`
(every tool's spec).
