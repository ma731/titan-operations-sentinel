# 004. Do not make query expansion the default

**Rejected on measurement, September 2026. The code ships; the default does not.**

## Context

Retrieval evaluation showed a clear weakness: BM25 answers 100% of queries that use the
corpus vocabulary and 41.7% of paraphrases that deliberately avoid it. Classic lexical
vocabulary mismatch.

Embeddings are the usual fix and need an API key that CI does not have. RM3
pseudo-relevance feedback is the keyless alternative, so we built it with literature
defaults and expansion terms drawn from the corpus rather than the query set.

## Decision

Keep it as an available mode (`TOS_RAG_MODE=prf`), scored on every run. Do not make it the
default.

## Consequences

Paraphrase recall@4 went from 41.7% to 50.0%, which is the number you would put in a
README. The whole picture:

| Mode | recall@1 | recall@4 | recall@8 | MRR |
|---|---:|---:|---:|---:|
| lexical | **0.788** | 0.865 | 0.885 | **0.820** |
| prf | 0.712 | **0.885** | **0.904** | 0.777 |

It fixes two queries, breaks one, and costs 7.5 points of recall@1. Net, one query out of
52. That is inside the noise of a set this size.

The harness earned its keep here by stopping a change rather than catching a bug.
Embeddings remain the right answer; the dense and hybrid rows are wired and waiting.

Full write-up in [F-05](../../eval/FINDINGS.md).
