"""
Evaluation harness for Titan Operations Sentinel.

The point of this package is to be able to answer "does it work?" with a number instead
of a demo. It has three layers, and they are separated by what they cost to run:

  policy_eval.py   Offline. Runs the real tools and the real code-enforced policy over 26
                   labelled scenarios. No API key, no tokens, no network, no flakiness.
                   This is what runs in CI on every push.
  rag_eval.py      Offline. Recall@k, MRR and precision@k for the retrieval layer over 40
                   labelled queries, for each of the lexical, dense and hybrid retrievers.
  live_eval.py     Needs a model key. Runs the full six-agent graph on a labelled subset
                   and scores tool-call correctness, routing coverage, gate decisions,
                   citation rate, tokens, cost and latency.

`python -m eval.run_eval` runs the offline layers and writes eval/results/scorecard.md.
`python -m eval.run_eval --live` adds the live layer.

Design note: splitting the deterministic layer out from the live layer is deliberate. The
guarantees this system claims (coverage, termination, the spend ceiling, the safety
override, abstention) are enforced in code, so they should be measured in code, exactly
and every time, not sampled from a handful of expensive agent runs.
"""
from .scenarios import Scenario, load_rag_queries, load_scenarios

__all__ = ["Scenario", "load_scenarios", "load_rag_queries"]
