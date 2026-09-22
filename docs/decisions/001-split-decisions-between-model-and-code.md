# 001. Split the decisions between the model and code

**Accepted, June 2026.**

## Context

Everything started inside `graph.py`: routing, the spend ceiling, the safety verdict, the
abstention rule. All of it mixed in with the agent calls. That made the guarantees in the
README untestable, because checking any of them meant running the model and hoping.

## Decision

Anything that is a judgement call stays with the model: who acts next, what an assessment
says, which tool to call, how the plan reads. Anything that is a guarantee moves to
`policy.py`: coverage, termination, the EUR 500 ceiling, the safety override, abstention
on thin data.

The model picks from what the policy allows. It never picks the policy.

## Consequences

`eval/policy_eval.py` can score the guarantees with no API key, no tokens and no
flakiness, which is why the offline suite runs on every push.

It also let us verify routing **exhaustively** rather than by sampling. That immediately
found a low-risk run could legally finish without the safety gate, which no demo had ever
triggered. See F-03.

The cost: two files instead of one, and a rule that "do not put a guarantee in a prompt"
has to be enforced in review.
