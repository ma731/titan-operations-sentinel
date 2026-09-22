# 006. Count tokens in process, not via the tracing SaaS

**Accepted, September 2026.**

## Context

Langfuse already records token usage per call, and reading cost back from it would have
been less code than writing a callback handler.

## Decision

Count tokens with our own LangChain callback (`observability.py`). Langfuse stays as
optional tracing, attached only when the keys are present.

## Consequences

The evaluation reports cost and tokens in CI, with no account, no network and no secret. A
cost figure that only exists when a third party is reachable is not a cost figure, and a
scorecard that silently loses a column when a SaaS is down is worse than one that never
had it.

The cost: our own extraction has to handle three different provider shapes for token
usage, and it returns zeros rather than raising when it cannot find any. A missing token
count must never fail a run, but it does mean a silently-wrong provider integration would
show as zero rather than as an error.
