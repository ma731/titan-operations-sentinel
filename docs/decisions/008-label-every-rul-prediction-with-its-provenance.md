# 008. Label every RUL prediction with its provenance

**Accepted, September 2026.**

## Context

`tools/rul_predictor.py` was a 53-line ladder of hand-written thresholds. It returned an
hour range and a confidence value that looked like measurements and were not. Nothing in
the system could tell the difference between that and a real estimate, because there was
nothing real to compare it against: every scenario in `data/` is invented, so no
prediction in this repo had ever been scored against a failure that actually happened.

That was the deepest criticism the project had. An agent that says "52 to 76 hours,
confidence 0.95" is making a claim, and until now the claim rested on nothing.

Two fixes were possible. Fit a model to real run-to-failure data and use it everywhere,
or admit that the demo asset has no such data. The first is not available: there is no
public run-to-failure dataset for CNC spindle bearings, so any model claiming to predict
this specific asset would be the same invention with more arithmetic.

## Decision

Both halves, kept honest and kept apart.

**A real model where real data exists.** `ml/` fits a quantile-regression RUL model on
NASA C-MAPSS, 707 held-out units across four subsets, scored against the benchmark's own
ground-truth labels. It predicts an interval, not a point, because the tool contract
already returns `{min, max}` and an interval whose coverage is measured is worth more
than a point estimate whose error is not.

**Provenance on every prediction.** Every RUL result now carries a `source` field:
`fitted_model` or `declared_thresholds`. A fitted prediction carries the model's measured
test error with it. A rule-based prediction carries a note saying the thresholds were
declared in the asset profile and the reference corpus and were never backtested against
failures of that asset class.

The CNC demo path stays rule-based, and now says so, in the tool output, the agent
transcript and the audit log.

## Consequences

The system can no longer present a guess and a measurement as the same kind of claim.
Anyone reading a run sees which one they are looking at.

The honest answer to "is this backtested" changed from "no" to "the model is, on 707
units, and the demo asset is not, and here is how you tell them apart in the output".

`ml/` depends on lightgbm, scikit-learn, pandas and joblib, which the repo did not
previously require at runtime. They are optional: `tools/rul_predictor.py` imports only
`provenance_for_rule_based`, which has no model dependencies, so the offline suite and
the demo still run without them.

A fitted model that is never retrained will drift, and nothing here retrains it. The
committed backtest is a snapshot with a date on it, not a guarantee about the future.

See `eval/FINDINGS.md` F-07 for the leakage this work surfaced, and
`eval/results/rul_backtest.md` for the numbers.
