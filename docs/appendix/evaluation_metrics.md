# Evaluation Metrics — three layers

Appendix artifact (brief §12 — a "standout/high-score" differentiator). How we'd measure success
in production, across product, agent, and business layers. Targets are illustrative but concrete.

> **Status, updated 2026-09.** Some of this is no longer hypothetical. An evaluation
> harness now measures the agent-performance layer for real against labelled data, and
> publishes [`eval/results/scorecard.md`](../../eval/results/scorecard.md) on every run.
> The table at the bottom of this document says exactly which rows are measured, which
> are partly measured, and which are still design-stage, so this appendix cannot be read
> as claiming more than the system does.

---

## Layer 1 — Product metrics
| Metric | Definition | Target |
|---|---|---|
| Task completion rate | runs that reach an approved/recorded plan without manual rescue | ≥ 90% |
| Time-to-plan | alert → costed action plan | < 2 min (vs hours manually) |
| Human time saved per incident | analyst minutes displaced | ≥ 80% reduction |
| Adoption | % of eligible alerts routed through the agent | ≥ 70% in 6 months |

## Layer 2 — Agent-performance metrics
| Metric | Definition | Target |
|---|---|---|
| Tool-selection accuracy | correct tool chosen for the step (vs expert label) | ≥ 95% |
| Plan success rate | plans that, when executed, resolve the issue | ≥ 90% |
| **Escalation rate** | runs correctly handed to a human on low-confidence data | tracked, not minimised — *calibration* matters |
| Hallucination / error rate | recommendations unsupported by tool data | < 2% |
| Safety-gate catch rate | unsafe actions caught by Compliance before execution | 100% (non-negotiable) |

## Layer 3 — Business metrics
| Metric | Definition | Target |
|---|---|---|
| Downtime cost avoided | €/incident vs the €180k/day baseline | primary KPI |
| Expedite ROI realised | actual vs predicted sourcing ROI | within ±15% of estimate |
| SLA / on-time maintenance | windows hit before predicted failure | ≥ 95% |
| Cost to run | LLM spend per incident | < €0.10 (free-tier / pay-as-you-go) |

---

### How we'd actually collect these
Every run already writes a structured **audit log** (`tos_audit.jsonl`: perceptions, tool calls,
decisions, approvals, the final plan). That log is the measurement substrate — tool-selection
accuracy, escalation rate, and time-to-plan are all derivable from it offline, no extra
instrumentation needed. The token-accounting harness adds cost-per-run.


---

## What is actually measured today

The harness in [`eval/`](../../eval/) runs 27 labelled scenarios and 52 labelled retrieval
queries. Three suites, split by what they cost to run: two are free, deterministic and run
in CI on every push; the third needs a model key and runs nightly.

| Metric from the layers above | Status | Where |
|---|---|---|
| Safety-gate catch rate | **measured** — HALT recall 100%, precision 75% | `eval/policy_eval.py`, reported as precision/recall because the two error types are not equally bad |
| Escalation calibration | **measured** — abstention on interrupted and unavailable telemetry | `eval/policy_eval.py`, `risk_classification` and `terminal_status` |
| Tool-selection accuracy | **measured** — micro precision/recall/F1 per agent | `eval/live_eval.py`, `tool_call_correctness` |
| Cost to run | **measured** — tokens and estimated cost per run, per agent | `observability.py`, reported in the scorecard's efficiency block |
| Time-to-plan | **measured** — wall time per run | `eval/live_eval.py` |
| Hallucination rate | **partly measured** — citations are checked against the real corpus index, so an invented citation counts against the score. Unsupported *numeric* claims are not yet checked | `eval/live_eval.py`, `grounding` |
| Task completion rate | **partly measured** — terminal status against the expected one, on 8 live scenarios | `eval/live_eval.py`, `terminal_status` |
| Plan success rate | **not measured** — needs real executions with known outcomes, which simulated data cannot provide | — |
| Downtime cost avoided, expedite ROI realised, SLA | **not measured** — business outcomes need a deployment | — |
| Adoption, human time saved | **not measured** — needs users | — |

Two metrics that were not in the original three layers, and turned out to matter:

| Metric | Why it earned a place |
|---|---|
| **Routing coverage over all permitted paths** | Verified exhaustively rather than sampled. It immediately found that a low-risk run could legally finish without the safety gate, which no demo had ever done. See [F-03](../../eval/FINDINGS.md). |
| **Retrieval recall@k by query difficulty** | Overall recall hid the interesting result. Split by difficulty it reads 100% on direct queries and 41.7% on paraphrases, which is the argument for embeddings stated as a number instead of an opinion. |

### The honest caveats

Listed because an evaluation section without them is marketing. The full version is in
[`eval/FINDINGS.md`](../../eval/FINDINGS.md):

- The offline suite measures the code-enforced layer exactly. Whether an agent writes a
  *good* assessment is only sampled, on eight scenarios, by the live suite.
- Relevance labels for retrieval are single-annotator, with no second pass.
- The live suite auto-approves at the human gate. That the gate fires is scored; what a
  real approver would decide is not modelled.
- Per-token prices are order-of-magnitude constants. Free-tier providers are priced at
  zero because that is what this project actually spends.
