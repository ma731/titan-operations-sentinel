# 009. Apply the patterns from "Building Effective Agents"

**Accepted, November 2026.**

## Context

Anthropic's [Building Effective Agents](https://www.anthropic.com/research/building-effective-agents)
names a small set of patterns: the augmented model (retrieval, tools, memory), prompt
chaining, routing, parallelisation, orchestrator-workers and evaluator-optimizer. Its
advice is to use the simplest pattern that works, to keep guarantees out of the model, and
to design tools so mistakes are hard to make.

Mapping Titan onto that list showed three gaps:

1. **No evaluator.** `prompts/self_eval.md` existed and the README said it "scores each plan
   today". No code loaded it. Each agent's own prompt carries a self-check, but nothing
   checked the final plan. The claim was false.
2. **The number problem was fixed in the prompt, not the tool.** Models write `180000/24`
   as a tool argument; as raw JSON that is invalid and the provider rejects the call. The
   fix was a line in every agent's prompt asking for plain numbers.
3. **Everything ran in sequence**, including supply chain and production, which do not
   need each other's reports.

## Decision

**Evaluator-optimizer, with the evaluator in code.** After the plan is written,
`policy.check_plan` scores it against the tier rules: no spend or purchase tagged [AUTO],
nothing that touches a safety system below [ESCALATE], a [MONITOR] line on HIGH risk. If it
fails, the model gets one revision with the exact violations. If that still fails, the
tiers are corrected in code. Every step is a logged decision event. The evaluator is code,
not a second model, because this is a guarantee, and decision 001 puts guarantees in code
where the offline suite can test them.

**Mistake-proof numeric tool arguments.** `expedite_cost`, `work_order_draft` and `notify`
accept a number or a simple arithmetic string (`"180000/24"`), computed by a small safe
evaluator (numbers and + - * / only). Anything else returns a clear error naming the
argument. The prompt line stays, as a hint rather than the only defence.

**Parallel sectioning, opt-in.** With `TOS_PARALLEL=1`, supply chain and production run in
the same step after reliability, then a join node merges their follow-up requests. Quality
and compliance still run after both and read both reports. The default stays sequential.

## Why parallel is not the default

In sequential mode production can read supply chain's report before it reroutes, and in
the recorded run production asks quality a direct question before committing. Running the
pair in parallel trades that context for latency. Which matters more is a question for a
live benchmark, which has not been run (see the README: live cost and latency are not
measured). Until then the flag exists, is tested on all 34 labelled scenarios with the same
guarantees, and is off.

## Consequences

- The README claim about `self_eval` is corrected; the console's Learning page says what
  runs today.
- Writing the plan check exposed a bug in `policy.action_tier`: markers matched inside
  words, so "buys runway" tiered as a purchase. Markers now match whole words. The offline
  evaluation did not move (208 of 208 checks), because no labelled action contained such
  a word, which is itself a gap in the labels ([F-10](../../eval/FINDINGS.md)).
- 59 new tests in `tests/test_effective_agents.py`, including the full labelled set in
  parallel mode.
