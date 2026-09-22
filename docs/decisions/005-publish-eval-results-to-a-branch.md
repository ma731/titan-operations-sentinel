# 005. Publish evaluation results to a branch

**Accepted, September 2026.**

## Context

The nightly evaluation committed the refreshed scorecard back to `main`. Once branch
protection was enabled it started failing every night:

```
remote: - Changes must be made through a pull request.
```

The evaluation was fine. Only the commit-back failed.

## Decision

Publish `scorecard.md`, `scorecard.json` and `badge.json` to a dedicated `eval-results`
branch, started from an empty tree. The README badge reads from there.

Only commit when the metrics move: the scorecard carries a generated timestamp, so
comparing the file would produce a commit every night that says nothing. The step
fingerprints the metrics with the timestamp stripped.

## Consequences

Fully automatic with no PR to approve, and it would have kept working with protection on.
CI pushing to a protected `main` was the wrong shape regardless.

The branch also gives a day-by-day history of the numbers without filling the main log
with bot commits.

The cost: results on `main` are now a snapshot from whenever a human last ran the eval,
not the latest. The badge points at the live branch to avoid that confusion.
