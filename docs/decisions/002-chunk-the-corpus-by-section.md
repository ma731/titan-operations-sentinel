# 002. Chunk the corpus by section, not by fixed window

**Accepted, September 2026.**

## Context

The retrieval corpus needed splitting into chunks. The default approach is a sliding
window of N tokens with some overlap.

## Decision

One chunk per `## S<n>` section instead.

## Consequences

The documents are already written as self-contained clauses, so a fixed window would cut
a severity table in half for no benefit. Sections also give a stable citation: every
passage is `doc_id#S<n>`, which a reader can open and check.

The cost is that chunk sizes are uneven, from a two-line clause to a full table. On a
corpus of 78 chunks that does not matter. On a corpus of 50,000 it would, and this would
need revisiting.

This only works because we control the corpus. Retrieval over arbitrary client PDFs would
need the sliding window back.
