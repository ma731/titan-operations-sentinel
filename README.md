# Titan Operations Sentinel

**A multi-agent LangGraph system that turns one factory sensor alert into a costed, safety-gated action plan.**

[![tests](https://github.com/ma731/titan-operations-sentinel/actions/workflows/tests.yml/badge.svg)](https://github.com/ma731/titan-operations-sentinel/actions/workflows/tests.yml)
[![nightly evaluation](https://github.com/ma731/titan-operations-sentinel/actions/workflows/eval-nightly.yml/badge.svg)](https://github.com/ma731/titan-operations-sentinel/actions/workflows/eval-nightly.yml)
[![scorecard](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/ma731/titan-operations-sentinel/eval-results/badge.json)](eval/results/scorecard.md)
[![license](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

**[Open the live demo](https://ma731.github.io/titan-operations-sentinel/)** · [Evaluation scorecard](eval/results/scorecard.md) · [Open findings](eval/FINDINGS.md) · [Architecture](#architecture)

![One alert, six agents, a costed and safety-gated plan](docs/demo.gif)

*64 seconds, real time: one sensor alert enters, the supervisor routes five specialists,
the spend hits the 500 EUR ceiling and stops for a human, and the run ends in a tiered
action plan at 79.7:1 ROI. Regenerate it with `python scripts/record_demo.py`, which
drives the real console rather than being a screen capture that quietly goes stale.*

> The demo runs in Replay mode: a recorded run played back in the browser. No API key, no
> cost, nothing to install. The console labels it as a recording rather than passing it off
> as live.

---

## The problem in one paragraph

A Titan plant produces more than 22,000 alerts a day. Exactly one of them, on a Friday
afternoon, is a spindle bearing about to fail on a machine worth 180,000 EUR a day. Finding
it is a triage problem. Responding to it is not: the response needs the maintenance team,
the supply chain, production scheduling, quality and safety to agree inside a few hours,
and today each of them sees only its own slice. A dashboard shows you the data. A rules
engine follows fixed steps. Neither reasons across the silos, which is the actual job.

## What it does

```
22,431 alerts   ->  triage  ->  1 alert worth waking six agents for
                                   |
                                   v
       reliability -> supply chain -> production -> quality -> compliance
        (what is      (what does it   (who makes    (is the    (is any of
         failing,      cost to fix     the parts     backup     this legal
         how long)     in time)        instead)      safe)      and safe)
                                   |
                                   v
                   human approves anything over 500 EUR
                                   |
                                   v
            [AUTO] throttle + reroute   [APPROVE] rush order + window
            [MONITOR] vibration          full audit trail, run saved to memory
```

## Numbers

| | |
|---|---|
| Evaluation | **100%** across **208** offline checks, **34** labelled scenarios ([scorecard](eval/results/scorecard.md)) |
| Safety gate | **100%** recall **and** precision on the HALT class, 0 missed halts, 0 false positives |
| Routing | exhaustive policy checks plus all **34** cases through the real graph with scripted specialists |
| Retrieval | recall@4 **100%** on direct queries, **41.7%** on paraphrases (52 labelled queries) |
| Triage gate | default 48 ticks: **192** readings, **1** wake, **0.52%** wake rate (dry run) |
| Live cost and latency | instrumented per run; provider benchmark not yet measured |
| Tests | **264** passed, **4** provider-dependent tests skipped in the offline validation |

These are measured snapshots from `python -m eval.run_eval`, `python -m pytest`, and
`python -m stream.run`. The scorecard is generated; this table is a summary.
Where the system disagrees with its own documentation, the
[findings register](eval/FINDINGS.md) says so instead of the label being edited to match.

---

## Run it

```bash
docker compose up --build       # console on :5173, API on :8000, no key needed
```

Or without Docker:

```bash
python -m pip install -r requirements-dev.txt
python scripts/run_demo.py              # live specialists require a model key
python -m stream.run                    # continuous alert stream, triage only, no tokens
python -m eval.run_eval                 # regenerate the scorecard
python -m pytest tests/                 # offline regression and graph integration tests
```

The five specialist agents need a real tool-calling model. Drop any supported key in
`.env` (Gemini and Groq are free), or point `TOS_MODEL` at a local Ollama model. Routing
and synthesis have a labelled fallback. With no specialist model, the graph abstains
with a human-review handoff. Replay, tools, retrieval and regression tests work offline.

Docker Compose 2.24+ is required for the optional `.env` file. The default setup binds
to localhost and preserves audit logs and case memory in named volumes. The live backend
is a local demo, not a publicly authenticated service; the hosted Pages demo is static Replay.
See [the end-to-end audit](docs/END_TO_END_REVIEW.md) for validation and remaining gaps.

---

## Architecture

```mermaid
flowchart TB
    STREAM["Continuous sensor stream<br/>22k alerts a day"]
    TRIAGE{{"Triage gate (no model)<br/>severity band + trend + cooldown"}}

    subgraph BRAIN["Titan Operations Sentinel"]
      direction TB
      ORCH{{"Orchestrator<br/>picks who acts next, writes the plan"}}
      REL["Reliability<br/>triage, life estimate, failure mode, parts"]
      SUP["Supply Chain<br/>stock, suppliers, Tier-2 risk, ROI"]
      PRO["Production<br/>reroute jobs, shift and robot conflicts"]
      QUA["Quality<br/>defects vs machine data, protect targets"]
      COM["Compliance and Safety<br/>safety gate (can HALT), audit trail"]
      TRANS[("Shared transcript<br/>agents talk in plain language")]
      MEM[("Case memory<br/>past incidents, outcomes")]
      DOCS[("Technical corpus<br/>retrieval with citations")]

      ORCH --> REL & SUP & PRO & QUA & COM
      REL & SUP & PRO & QUA & COM --> ORCH
      REL & SUP & PRO & QUA & COM -.-> TRANS
      TRANS -.read.-> ORCH
      REL <-.precedent.-> MEM
      REL & COM <-.cited passages.-> DOCS
    end

    POLICY["Code-enforced policy<br/>coverage · termination · 500 EUR ceiling · safety override"]

    STREAM --> TRIAGE -->|"only when it matters"| ORCH
    ORCH --> GATE{{"Human approval<br/>Slack · email · console"}}
    GATE --> PLAN["Tiered action plan<br/>AUTO · APPROVE · MONITOR, with ROI"]
    POLICY -. constrains .-> ORCH
```

The load-bearing idea is the split between the two kinds of decision:

- **The model decides** who acts next, what each assessment says, which tools to call, and
  how the final plan reads. That is judgement, and it is what an agent is for.
- **Code decides** what the model is allowed to choose from. `policy.py` guarantees that
  every cross-domain agent runs on a high-risk event, that the run terminates, that
  spending above 500 EUR reaches a human, that a safety HALT overrides everything, and
  that thin data produces an abstention rather than a confident guess.

So the system is autonomous but cannot run away, and the guarantees are testable without
a model. `eval/policy_eval.py` verifies the routing guarantee by enumerating every path
the policy permits, rather than watching one run and hoping.

---

## My contribution

This is a five-person group project. What I (Marco Ortiz Togashi) built, so you can ask me
about the right things:

**Owned end to end**

- **Orchestration** (`graph.py`, `policy.py`). Replaced the initial skeleton with the
  LangGraph supervisor: the shared transcript, agent-to-agent `FOLLOWUP` messaging bounded
  by `MAX_VISITS`, the routing policy, the code-enforced 500 EUR ceiling with the
  fit-to-window test, structured verdicts read from tool fields rather than prose, and the
  deterministic abstention path that spends no tokens when the telemetry cannot be trusted.
- **Evaluation harness** (`eval/`). The 34 labelled scenarios, the 52 labelled retrieval
  queries, the metrics, the exhaustive routing verification, the generated scorecard and
  the findings register.
- **Retrieval** (`rag/`). The corpus, the section chunker, the BM25 implementation, the
  optional embedding layer, hybrid fusion, and the recall@k evaluation.
- **Web console** (`webapp/`). The React and FastAPI console: the live orchestration
  graph, SSE streaming, the approval gate UI, the learning view, run history, provider
  switching, and the slide deck.
- **Model layer** (`llm.py`). Provider-agnostic factory with auto-detection, retry and
  backoff for free-tier limits, and the offline fallback.
- **Learning loop**. Case-memory write-back and the self-closing reconcile step.
- **Observability, the alert stream and the approval integrations**
  (`observability.py`, `stream/`, `integrations/`), CI, and Docker.

**Built by teammates**

- Marian Garabana: the initial project skeleton, the case study document, and the risk and
  architecture trade-off write-ups.
- David Carrillo: the first pass of the domain tools and their LangChain wrappers, the
  simulated datasets, and the original agent and prompt scaffolding.
- Nuria Diaz: the system-prompt overhaul across all five specialists.
- Ignacio Moreno: presentation and demo preparation.

`git log` backs this up, and the commit history is readable if you want to check.

---

## The agents

| Agent | Challenge | Decides | Key tools |
|-------|-----------|---------|-----------|
| Orchestrator | coordination | who acts next, and the final tiered plan | routing only |
| Reliability | 1 | which alert matters, remaining life, failure mode, parts, precedent | `alert_triage`, `sensor_query`, `rul_predictor`, `recall_similar_cases`, `asset_profile`, `search_technical_docs` |
| Supply Chain | 2 | the parts gap, the best option by ROI, hidden Tier-2 risk | `parts_inventory`, `supplier_catalog`, `expedite_cost`, `tier2_supplier_risk` |
| Production | 3 | how to reroute jobs without a staffing or robot conflict | `job_reroute`, `robot_cell_status`, `shift_conflict_check` |
| Quality | 4 | whether the fault is causing defects, and whether the backup machines are safe | `quality_history`, `telemetry_correlate` |
| Compliance and Safety | 5 | check every action against OSHA (can HALT), build the audit trail | `safety_gate`, `audit_assemble`, `search_technical_docs` |

The agents decide, the tools act. Tools fetch data, do arithmetic, or draft documents.
They never make a decision or commit anything irreversible.

Every agent is a LangGraph `create_react_agent`: its own model picks which of its tools to
call and loops until it is done. Agents communicate by appending their full report to one
shared transcript that every later agent reads, and an agent may end with
`FOLLOWUP: <agent> — <question>` to put a direct question to another specialist.

---

## Grounding: retrieval with citations

The Reliability and Compliance agents can query a technical reference corpus and must cite
the section they relied on.

- **The corpus** (`rag/corpus/`) is 12 documents, 78 section-level chunks: fleet
  maintenance standards, and plain-language paraphrases of OSHA 1910.147 and 1910.212,
  ISO 10218 and ISO/TS 15066, ISO 10816-3 and IATF 16949. Every document declares its
  provenance, so an agent citing a paraphrase can tell that it is a paraphrase.
- **The retriever** (`rag/`) is BM25 by default, which needs no key and no network.
  Embeddings are opt-in through `TOS_EMBEDDINGS` and fuse with BM25 by reciprocal rank.
- **The measurement** (`eval/rag_eval.py`) reports recall@k, MRR and precision@k for each
  retriever over 52 labelled queries, split into two difficulty bands.

The split is where the interesting number is:

| Split | Queries | recall@4 (lexical) | MRR |
|---|---:|---:|---:|
| direct (uses the document's own vocabulary) | 40 | 100% | 0.969 |
| paraphrase (deliberately avoids it) | 12 | 41.7% | 0.322 |

That gap is the case for embeddings, measured rather than asserted. Set `TOS_EMBEDDINGS`
and the scorecard fills in the dense and hybrid rows; without it they are reported as
"not configured" rather than quietly falling back to lexical and being labelled hybrid.

A keyless attempt at closing the gap is also in the repo and is **not** switched on.
Pseudo-relevance feedback (`rag/expansion.py`) lifts paraphrase recall@4 from 41.7% to
50.0%, which sounds good until you look at the whole picture: it fixes two queries, breaks
one, and costs 7.5 points of recall@1. Net, one query out of 52, which is noise. It ships
as an option and is scored on every run, but the default stays plain lexical.
[F-05](eval/FINDINGS.md) has the table. The harness earned its keep there by stopping a
change, not by catching a bug.

**This is separate from case memory.** `recall_similar_cases` matches past incidents in a
structured JSON library. That is case-based memory, not retrieval over documents. Both are
useful, they are different things, and this README keeps them apart on purpose.

---

## Evaluation

The full scorecard is at [`eval/results/scorecard.md`](eval/results/scorecard.md) and is
regenerated by `python -m eval.run_eval`. Three suites, separated by what they cost:

| Suite | Cost | What it measures |
|---|---|---|
| **Offline policy** | free, no key, deterministic | risk classification, the approval gate, safety verdicts, action tiering, terminal status, and routing coverage over every permitted path |
| **Retrieval** | free, no key, deterministic | recall@k, MRR, precision@k per retriever and per difficulty split |
| **Live agents** | tokens | tool-call correctness, routing coverage, gate decisions, citation rate, tokens, cost and latency on an 8-scenario subset |

The first two run in CI on every push with `--fail-under 1.0 --retrieval-fail-under 0.85`, so the scorecard is a gate
and not a decoration. The live suite runs nightly when a provider key is available.

Two things worth knowing about how it is built:

1. **The routing guarantee is verified exhaustively.** `enumerate_routing_paths` walks
   every sequence the policy allows and asserts the coverage, ordering and termination
   properties on all of them. This is how the suite found that a low-risk run could finish
   without ever passing the safety gate, which no demo had ever done but the policy
   permitted ([F-03](eval/FINDINGS.md)).
2. **Misses are fixed or documented, never edited away.** The suite currently reports
   100%, which is only worth anything because of how it got there. The safety test set
   was deliberately made adversarial first, at which point HALT recall fell to 71% and
   precision to 56%: the gate was missing a jumpered light curtain and halting a safety
   sign-off. The rule was then rewritten and both went to 100%. The before and after are
   in [eval/FINDINGS.md](eval/FINDINGS.md). No label was ever changed to make a metric
   pass, and the limits of the suite itself are written down in the same file.

---

## Autonomy and safety

| Tier | Example actions | Who approves |
|------|-----------------|--------------|
| AUTO | throttle within OEM limits, reroute jobs, update logs, draft a work order | nobody, the agent acts |
| APPROVE | any purchase, or an emergency maintenance window | plant manager, through the gate |
| ESCALATE | anything touching a safety system | safety officer |

- **The 500 EUR ceiling is enforced in code.** An option runs autonomously only if it is
  at or under the ceiling *and* fits the failure window. An unknown cost is not a small
  cost, and a cheap part that arrives after the machine fails is a decision about
  accepting the failure, which belongs to a person.
- **A Compliance HALT overrides everything**, including an approved spend and an urgent ROI.
- **It abstains on thin data.** If the telemetry drops out, Reliability refuses to invent a
  life estimate and the run escalates for manual inspection. The final handoff is
  deterministic and spends no additional synthesis tokens.
- **It fails toward caution.** Failed or missing reliability evidence escalates. Failed,
  missing or malformed safety clearance halts. A HALT cannot be erased by a later OK.
  Rejection withholds the action plan in code, without asking a model to honour it.

---

## Autonomous operation

```bash
python -m stream.run                        # triage only, no model calls
python -m stream.run --live --interval 2    # actually run the agents, paced for a demo
python -m stream.run --dropout CNC-07-LEI   # watch a telemetry feed die mid-degradation
```

A seeded fleet simulator emits readings every tick. A cheap deterministic triage gate
decides what is worth waking six agents for: it scores against the documented severity
bands, treats a change from baseline as its own wake condition, and enforces a per-machine
cooldown so a machine that is degrading for hours does not start a run every tick. Over a
default 48-tick window: **192 readings, 1 wake, a 0.52% wake rate.** Dry runs consume no tokens.

Live simulation passes the emitted readings into the sensor tool, rather than reading
the Friday demo snapshot. At an approval interrupt it defaults to **reject**; an explicit
`--decision approve` is a demo-only automated decision, never a human approval. Synthetic
runs do not modify case memory or send Slack/email notifications. Use the web console
for an actual human decision. `--max-runs` limits starts; wake counts are reported separately.

A telemetry dropout on a machine already above threshold is its own wake condition and
routes to the escalation path. A healthy machine going quiet is an instrumentation ticket,
not an operations event.

Spending model tokens to decide whether to spend model tokens is how an autonomous system
quietly becomes expensive, so the gate is deliberately free.

---

## Human approval, outside the app

When the gate trips, the request goes to whoever is configured:

- **Slack**: a Block Kit message with Approve and Reject buttons. Callbacks are signature
  verified with a replay window, and the button carries the run id, so a late click on an
  old message resolves the run it belongs to.
- **Email**: an SMTP message with two links, for when installing a Slack app is not an option.
- **Console**: the default, and what the web console uses.

For web-console runs, all three resolve through the same decision handler, so a run has one resume path and
one audit record however it was approved. Nothing in the integration decides anything: it
carries a question to a person and carries the answer back.

The gate is **write-once**. The first decision stands and later clicks are refused,
whichever channel they arrive on. Before that, a run stayed writable from the moment it
paused until it finished, so approving in the email and then clicking reject changed the
recorded decision after the fact. An approval over money cannot be last-click-wins, and
the audit trail has to hold the decision that was actually acted on.

---

## Observability

Per-agent token, cost and latency tracking is built in (`observability.py`) and is what
the scorecard reports efficiency from. It needs no account and works offline, which
matters: a cost figure that only exists when a SaaS is reachable is not a cost figure.
The live SSE endpoint emits a final `usage` event; concurrent runs have separate trackers.
Prices are indicative constants, not billing quotes. Missing provider usage is not evidence
that a live run was free.

Set `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY` to additionally send traces to
Langfuse for a per-agent waterfall. Both are off by default and neither can break a run.

---

## The learning loop

Perceive, reason, act, learn, without retraining anything.

| Part | Status | What it does |
|---|---|---|
| Case memory recall | live | `recall_similar_cases` pulls the closest past case (predicted vs actual life, the decision, the outcome) into the Reliability agent |
| Write-back | live | ordinary runs append to `data/memory/case_library.json`; evaluation and stream simulation leave it unchanged |
| Outcome validation | live, self-closing | `reconcile_due()` runs at the start of each cycle and closes any case whose outcome is now known, updating life-estimate accuracy |
| Reflection and signature down-weighting | design stage | the `self_eval` prompt scores each plan today; replaying those critiques and down-weighting signatures that miss is the planned next step, and is labelled "design" in the console |

---

## The web console

```bash
cd webapp/frontend && npm install && npm run dev     # Replay: free, no key, cannot fail
python -m uvicorn main:app --app-dir webapp/backend --port 8000   # adds Live mode
```

Live orchestration graph with animated routing, the three scenario paths, the approval
gate, an agent chat, the learning view, the plant fleet inspector, cost and feasibility,
the audit log, run history with Markdown export, presenter auto-play, a command palette, a
Replay/Live toggle, an in-app provider picker, and the slide deck at `/deck.html`. Details
in [`webapp/README.md`](webapp/README.md).

The backend exposes `/api/run` (SSE), `/api/decision`, `/api/decision/link`,
`/api/slack/interactions`, `/api/providers`, `/api/config` and `/api/health`. The health
endpoint reports what is actually wired up: the active provider, the approval channel, the
retrieval mode, the corpus size and the policy constants.

---

## Providers

Provider-agnostic through `init_chat_model`. Switch by setting `TOS_MODEL`, by dropping a
key in `.env`, or from the console's picker.

| Provider | Prefix | Key | Notes |
|---|---|---|---|
| Gemini | `google_genai:` | `GEMINI_API_KEY` or `GOOGLE_API_KEY` | free tier, most headroom for a full run |
| Groq | `groq:` | `GROQ_API_KEY` | free and fast; use `llama-3.3-70b-versatile` |
| OpenRouter | `openrouter:` | `OPENROUTER_API_KEY` | one key, many free models; best when another tier rate-limits |
| Azure OpenAI | `azure_openai:` | `AZURE_OPENAI_API_KEY` plus endpoint and version | paid-tier limits; model name is the deployment name |
| OpenAI, Anthropic, Mistral | `openai:`, `anthropic:`, `mistralai:` | the matching key | paid or free tiers |
| Ollama | `ollama:` | none | fully local, no key |

---

## Repository layout

```
graph.py              orchestration: supervisor, workers, shared transcript, approval gate
policy.py             the code-enforced decision rules (coverage, ceiling, safety, abstention)
observability.py      per-agent tokens, cost, latency; optional Langfuse tracing
llm.py                provider-agnostic model factory
audit_log.py          JSONL audit trail
agents/               the 5 specialist ReAct agents
tools/                20 domain tools plus the @tool wrappers (docs/tool_catalog.md)
rag/                  technical corpus, BM25 + optional embeddings, cited retrieval
eval/                 labelled datasets, metric suites, generated scorecard, findings register
stream/              fleet simulator, triage gate, the continuous loop
integrations/         Slack and email approval routing
prompts/              5 agent prompts plus supervisor, orchestrator, guardrails, self-eval
data/                 simulated scenario data for all five challenges, plus case memory
webapp/               React console and FastAPI SSE backend
scripts/              run_demo.py, view_run.py, record_demo.py (regenerates the GIF)
tests/                offline tests, including all 34 cases through the actual LangGraph
docs/                 brief, case study, tool catalog, architecture, appendix pack
```

---

## Design choices

- **Why many agents, not one.** Five focused agents with about four tools each make better
  tool choices than one agent juggling twenty, and they match the org silos the case study
  is about joining up.
- **Why the policy is in code.** Coverage, termination, the spend ceiling and the safety
  override are promises. A promise that depends on the model happening to choose well is
  not a promise, and it cannot be tested cheaply.
- **Why simulated data.** Real SCADA and SAP integration needs OT access and months of
  pipelines. The tools read realistic JSON shaped like production systems, so the agent
  behaviour is representative even though the data is not real.
- **Honest labelling.** The heuristic life estimate, the Replay recording, the design-stage
  learning parts, the corpus provenance and the open evaluation findings are all labelled
  as what they are, in the code, the docs, the console and the deck.

---

## Status and limitations

- Working: all five challenges, the learning loop, the audit trail, the web console, the
  retrieval layer, the continuous stream, the approval integrations and CI. See the
  validation snapshot above for the current test result.
- The remaining-life estimate is a heuristic, not a trained model. It is an MVP stub and is
  labelled as one. The evaluation found that it ignored its own documented critical
  threshold, which is now fixed ([F-01](eval/FINDINGS.md)); the model underneath is still a
  band table, not a fitted one.
- The safety rule was rewritten after the evaluation showed the old keyword list both
  over-fired and under-fired. It now requires a defeating action *and* a hazard control.
  Both directions are pinned by adversarial scenarios ([F-02](eval/FINDINGS.md)).
- Reflection replay and automatic signature down-weighting are designed, not live.
- The retrieval corpus is small and clean, so the direct-split recall says the corpus is
  well separated rather than that retrieval is solved. The
  [findings register](eval/FINDINGS.md) lists the suite's own blind spots.

---

## Docs

- [Decision records](docs/decisions/) — why it is built this way, including the change we
  measured and rejected, and the two guarantees the evaluation caught us breaking.
- [What carries to the next problem](docs/REUSABILITY.md) — what is domain-specific, what
  is scaffolding, and what it would actually take to move this somewhere else.
- [Evaluation findings](eval/FINDINGS.md) — every miss the suite has surfaced.

[`docs/`](docs/) and [`docs/appendix/`](docs/appendix/): the prompt pack, the tool catalog,
the risk matrix and FMEA, the confidence policy, the sequence diagram and audit log schema,
why an agent rather than a dashboard, the evidence checklist against the assignment rubric,
the anticipated-questions pack, and the recording guide.

## Team

IE University, MBDS, Agentic AI for IT, Team 3. Presented 24 June 2026.
Marco Ortiz Togashi, David Carrillo Aguilera, Nuria Diaz Jimenez, Marian Garabana Garrido,
Ignacio Agustin Moreno.

Licensed MIT.
