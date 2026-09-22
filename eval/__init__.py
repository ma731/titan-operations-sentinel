"""
Evaluation harness: answering "does it work?" with a number instead of a demo.

Three suites, separated by what they cost to run:

  policy_eval.py   Offline. Real tools, real policy, labelled scenarios. No key, no
                   tokens, no flakiness. Runs in CI on every push.
  rag_eval.py      Offline. Recall@k, MRR and precision@k per retriever.
  live_eval.py     Needs a key. Full graph runs scoring tool-call correctness, gate
                   decisions, citation and numeric grounding, tokens and latency.

`python -m eval.run_eval` runs the offline suites and writes results/scorecard.md.
Splitting them is deliberate: guarantees enforced in code should be measured in code,
exactly and every time, not sampled from a handful of expensive agent runs.
"""
from .scenarios import Scenario, load_rag_queries, load_scenarios

__all__ = ["Scenario", "load_scenarios", "load_rag_queries"]
