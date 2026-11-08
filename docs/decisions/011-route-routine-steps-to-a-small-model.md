# 011. Route routine steps to a small model; keep money, safety and the plan on the main one

**Accepted, November 2026.**

## Context

Every call in a run went to one model. Many calls do not need it. The supervisor picks the
next agent from a list `policy.allowed_next` has already narrowed, often to one. Production
and Quality mostly read deterministic tool results and summarise them. Paying frontier
prices for those is the pattern Accenture's CIO guide to AI tokenomics describes: most tasks
do not need the most expensive model, and most token spend cannot be traced to an outcome.

## Decision

- `TOS_MODEL_SMALL` turns routing on. Unset, nothing changes: every call uses `TOS_MODEL`.
- `llm.SMALL_ROUTES = {supervisor, production, quality}` run on the small model.
- Reliability, Supply Chain, Compliance and Safety, the final plan and its revision stay on
  the main model: they decide what is spent, what is safe and what a person is asked to sign.
- The guarantees do not depend on which model is used: they are in `policy.py`. A cheaper
  model can make a worse summary; it cannot spend over EUR 500 or skip the safety gate.
- Each agent is priced by the model it ran on (`observability.price_for`, matching model
  families inside free-text Azure deployment names), and the scorecard states the routing.

## How to measure it

```bash
python -m eval.routing_compare          # checks the setup, estimates the cost, runs nothing
python -m eval.routing_compare --run    # the same live scenarios with one model, then routed
```

It runs each suite in a fresh process, compares cost per run and every quality metric (routing,
risk, gate, status, halt, tier consistency, tool-call F1, citations, numeric groundedness), and
writes `eval/results/routing_comparison.md` with a verdict: keep routing only if it is cheaper
and nothing drops. Not yet run: it needs a key, and the numbers belong in that file.
