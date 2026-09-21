# Evaluation scorecard

Generated 2026-09-21 14:59 UTC by `python -m eval.run_eval`. Do not edit by hand: it is overwritten on every run.

Datasets: **34** labelled scenarios (8 in the live subset), **52** labelled retrieval queries (40 direct, 12 paraphrase).

### Headline

| Suite | Result |
|---|---|
| Offline policy | 100.0% of 208 checks |
| Safety HALT recall | 100.0% |
| Retrieval recall@4 (lexical) | 86.5% |
| Live agent suite | not run in this pass |

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

Regenerate with `python -m eval.run_eval` (offline suites) or `python -m eval.run_eval --live` (adds the agent suite). The labelled datasets are in `eval/cases/`.
