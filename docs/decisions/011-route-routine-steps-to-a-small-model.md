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
TOS_MODEL=azure_openai:<large deployment> python -m eval.run_eval --live
TOS_MODEL=azure_openai:<large deployment> TOS_MODEL_SMALL=azure_openai:<small deployment> python -m eval.run_eval --live
```

Compare cost per run AND the quality metrics (routing, risk, gate, tier consistency,
groundedness). Routing is only worth keeping if the cost falls and the quality does not.
Not yet run: it needs a key, and the numbers belong in the scorecard, not in this record.
