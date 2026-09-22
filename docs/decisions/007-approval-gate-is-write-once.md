# 007. Make the approval gate write-once

**Accepted, September 2026. Fixes a real bug.**

## Context

A run stayed writable from the moment it paused until it finished. Three channels can
resolve it: the console, a Slack button, an email link.

So approving in the email and then clicking reject changed the recorded decision after the
fact, and the channels could overwrite each other. Found by writing the first end-to-end
test that posted a real Slack-shaped payload.

## Decision

The first decision wins. Later ones are refused and told which decision actually holds.
The check-then-set runs under a lock, because the three channels arrive on different
threads.

## Consequences

An approval over money cannot be last-click-wins, and the audit trail records the decision
that was acted on rather than the last one submitted.

The cost: a user who clicks the wrong button cannot correct it from the same link. That is
the right trade for a financial approval, and the refusal message says what was recorded
so the mistake is at least visible.
