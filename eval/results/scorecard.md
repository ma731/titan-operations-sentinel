# Evaluation scorecard

Generated 2026-09-22 15:58 UTC by `python -m eval.run_eval`. Do not edit by hand: it is overwritten on every run.

Datasets: **34** labelled scenarios (8 in the live subset), **52** labelled retrieval queries (40 direct, 12 paraphrase).

### Headline

| Suite | Result |
|---|---|
| Offline policy | 100.0% of 208 checks |
| Safety HALT recall | 100.0% |
| Retrieval recall@4 (lexical) | 86.5% |
| Live agent suite | not run in this pass |
| Cost to run | see unit economics below |

How to read this: the offline suites measure the parts of the system that are enforced in code, exhaustively and for free. The live suite measures what the model does, on a subset, and costs tokens. A claim backed only by the live suite is a sample; a claim backed by the offline suite is a check.

---

## 1. Offline policy suite (no key, no tokens, deterministic)

`208` checks across `34` labelled scenarios. Overall **100.0%**.

| Metric | Score | Checks | Verdict |
|---|---:|---:|---|
| `risk_classification` | 100.0% | 34/34 | pass |
| `approval_gate` | 100.0% | 34/34 | pass |
| `safety_verdict` | 100.0% | 31/31 | pass |
| `action_tiering` | 100.0% | 36/36 | pass |
| `terminal_status` | 100.0% | 34/34 | pass |
| `routing_coverage_all_paths` | 100.0% | 34/34 | pass |
| `routing_allowed_set` | 100.0% | 5/5 | pass |

### Safety HALT class

The two error types are not equally bad, so this class is reported as precision and recall rather than accuracy. A missed HALT is a safety failure. A spurious HALT is an availability cost.

| | Value |
|---|---:|
| recall (HALTs caught) | 100.0% |
| precision (HALTs that were real) | 100.0% |
| false negatives | 0 |
| false positives | 0 |

---

## 2. Retrieval suite (no key, no tokens, deterministic)

12 documents, 78 section-level chunks, 1208 terms. Scored at k=4, the default the `search_technical_docs` tool uses.
The legacy metric name `recall@k` denotes an any-relevant-passage hit rate. It does not measure retrieval of every relevant section.

| Retriever | recall@1 | recall@4 | MRR | precision@4 | Status |
|---|---:|---:|---:|---:|---|
| `lexical` | 78.8% | 86.5% | 0.820 | 22.1% | scored |
| `prf` | 71.2% | 88.5% | 0.777 | 22.6% | scored |
| `dense` | | | | | not configured |
| `hybrid` | | | | | not configured |

### By query difficulty

`direct` queries use the target section's own vocabulary. `paraphrase` queries deliberately avoid it and ask the way an operator would. The gap between the two splits is the argument for embeddings, measured rather than asserted.

| Split | Queries | recall@4 | MRR |
|---|---:|---:|---:|
| direct | 40 | 100.0% | 0.969 |
| paraphrase | 12 | 41.7% | 0.322 |

Lexical misses on the paraphrase split: Q42, Q43, Q46, Q47, Q48, Q49, Q50.

---

## 3. Live agent suite (needs a model key)

Not run in this pass. Run it with `python -m eval.run_eval --live` once a provider key is in `.env`. It is excluded from the on-every-push CI job because it costs tokens and depends on a third-party API being up; the nightly workflow runs it when a key is available as a repository secret.

---

## 4. Unit economics

What it costs to run, as opposed to what the case study says it saves. The triage figures are measured by running the real gate over a simulated plant day; it is deterministic and needs no model, so they are exact.

| | Value |
|---|---:|
| Sensor readings per day (4 machines) | 576 |
| Agent runs triggered | **2** |
| Suppressed by the cooldown | 124 |
| Wake rate | 0.35% of readings |
| Tokens per run | 18,000 (from earlier live runs, not re-measured) |

Cost per run, and at the plant's rate of 3 actionable alerts a day:

| Provider | Per run | Per plant day | Per 1,000 alerts |
|---|---:|---:|---:|
| `groq` (free tier) | EUR 0.00000 | EUR 0.000 | EUR 0.00000 |
| `google_genai` (free tier) | EUR 0.00000 | EUR 0.000 | EUR 0.00000 |
| `openai` | EUR 0.00436 | EUR 0.013 | EUR 0.00058 |
| `anthropic` | EUR 0.02664 | EUR 0.080 | EUR 0.00356 |

Runs per day comes from the case study's 3 deduplicated critical alerts, not from scaling the wake rate against raw alert volume: a reading and an alert are different units. As a cross-check, the simulated fleet independently triggered 2 runs in 24 hours, the same order of magnitude.

The value side (EUR 180,000 a day of production at risk, 22,431 alerts a day) is an input from the case study, not a result this system produced.

---

Regenerate with `python -m eval.run_eval` (offline suites) or `python -m eval.run_eval --live` (adds the agent suite). The labelled datasets are in `eval/cases/`.
