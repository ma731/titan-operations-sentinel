# What carries to the next problem

This was built for one case study about a factory. Most of it is not about factories.

The split below is the honest one: what you would throw away on a different problem, what
you would keep and reconfigure, and what you would keep untouched. It matters because the
interesting question about any agent system is not whether it works on the demo, it is how
much of it survives contact with a different domain.

---

## Throw away: the domain

Roughly 30% of the repo. All of it is data or vocabulary, none of it is mechanism.

| | What it is |
|---|---|
| `data/` | Simulated sensors, suppliers, shifts, quality records, safety rules |
| `tools/` (17 of 20) | Domain tools: `sensor_query`, `expedite_cost`, `job_reroute`, ... |
| `rag/corpus/` | Maintenance standards, OSHA and ISO paraphrases |
| `prompts/` | Five specialist system prompts |
| `stream/simulator.py` | The fleet degradation model |

On a new problem these are replaced wholesale. That is the expected cost of entry.

---

## Keep and reconfigure: the scaffolding

The part that took the longest to get right and is the part worth reusing.

### `policy.py` — the decision layer

The idea transfers even though the specific rules do not: keep the guarantees in
deterministic code and let the model choose only inside what that code allows.

What you change: the thresholds, the tier vocabulary, which agents are mandatory.
What you keep: the shape. Risk classification, an approval ceiling, a safety override, an
abstention path, and a routing policy that returns the permitted set rather than the
answer.

This is what makes the guarantees testable at all. Everything below depends on it.

### `eval/` — the harness

The most transferable thing here, and the part most agent projects never build.

| Piece | Transfers as-is? |
|---|---|
| `metrics.py` | Yes. Tally, confusion matrix, micro-averaged set scores, recall@k, MRR |
| `scorecard.py` | Yes. Generated Markdown plus a shields endpoint |
| `groundedness.py` | Yes. Checks numbers in output against numbers the tools returned |
| `policy_eval.py` | Reconfigure. The exhaustive routing walk is generic; the labels are not |
| `rag_eval.py` | Yes, given a labelled query set |
| `live_eval.py` | Reconfigure. Tool-call correctness and citation checking are generic |
| `cases/*.json` | Replace. The schema transfers, the labels do not |

The labelled-scenario format is the reusable asset. Each case carries an input, the
expected routing, expected tool calls, gate decisions and plan tiers, which is enough to
score any orchestrated agent system.

### `integrations/approval.py` — human-in-the-loop routing

Slack, email or console, all resolving through one write-once path. Nothing in it knows
about factories. Change the message copy and it works for any approval.

### `observability.py` — cost and latency

A LangChain callback counting tokens per agent, plus optional tracing. Provider-agnostic
and domain-free.

### `stream/triage.py` — the wake gate

The idea generalises further than the thresholds do: put something cheap and
deterministic between a high-volume signal and an expensive agent run, and make it
enforce a cooldown. Any system reacting to a stream needs this or it will run constantly.

---

## Keep untouched: the plumbing

`graph.py` (orchestration shape), `llm.py` (provider switching and fallback),
`audit_log.py`, the CI workflows, Docker, and the console shell. Configuration, not
rewriting.

---

## What it would actually take

Moving this to a new domain, in rough order:

1. Replace the tools and their data. Biggest chunk of the work.
2. Rewrite the five system prompts.
3. Retune `policy.py`: thresholds, tiers, which agents are mandatory.
4. Write 20 to 30 labelled scenarios in the existing schema. **Do this before tuning
   anything**, or you are tuning against impressions.
5. Swap the corpus and write a labelled query set for it.
6. Everything else is configuration.

Steps 1 to 3 are days. Step 4 is the one people skip, and it is the one that tells you
whether steps 1 to 3 worked.

---

## The honest caveat

This has been carried across exactly one domain: zero. Everything above is an argument
from how the code is separated, not from having done it. The separation is real and the
dependency direction is enforced by the tests, but "reusable" is a claim that only a
second domain can settle.
