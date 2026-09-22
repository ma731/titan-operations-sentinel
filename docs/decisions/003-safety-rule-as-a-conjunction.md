# 003. Express the safety rule as a conjunction

**Accepted, September 2026. Replaces a flat keyword list.**

## Context

`SAFE-01` halts any action that "disables, bypasses, or modifies a safety interlock or
guard". It was implemented as a flat keyword OR, which forced the bare token `safety` into
the list to catch anything at all.

The scorecard reported HALT recall 100%, precision 75%, and we read that as an
over-cautious gate.

## Decision

Support `match.all_of` groups in the rule format and rewrite SAFE-01 as what it actually
says: a defeating action (bypass, disable, defeat, jumper, tape over, short out) applied
to a hazard control (interlock, guard, e-stop, light curtain, two-hand control).

## Consequences

Adding adversarial cases **first** showed the original conclusion was wrong. Against the
harder set the old rule scored:

| | Old rule | New rule |
|---|---:|---:|
| HALT recall | 0.71 | **1.00** |
| HALT precision | 0.56 | **1.00** |

It was missing "jumper the light curtain" and "defeat the two-hand control" entirely. The
100% recall had been an artefact of a test set that only ever said "bypass" and
"interlock".

`policy.action_tier` has to stay in step with the same vocabulary, or the plan tiers an
action AUTO that the gate then halts. A test asserts they agree.

Full write-up in [F-02](../../eval/FINDINGS.md).
