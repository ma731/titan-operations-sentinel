# Findings register

Every miss the evaluation has surfaced, what it was, and what was decided. Findings are
referenced from `eval/results/scorecard.md` by scenario id.

**The scorecard currently reports 100%, and that is only meaningful because of how it got
there.** Nothing was ever fixed by editing a label. F-02 in particular went the other way
first: the safety test set was deliberately made adversarial, the gate's score *fell* from
100% recall to 71%, and the rule was rewritten to earn the number back. The right response
to a green suite is to make the set harder, which is what the "known limits" section at
the bottom is for.

---

## F-01 (resolved 2026-09) The risk model ignored its own documented critical threshold

**Status:** fixed.

`tools/rul_predictor.py` classified a confirmed bearing failure only at vibration
>= 7.0 mm/s RMS. Two other places in the system put the critical threshold at 6.0:
`data/assets/asset_profiles.json` (`vibration_threshold_critical_mm_s: 6.0`) and the
reference corpus (`tms-101-spindle-bearing-maintenance#S3`, "Critical: above 6.0"). A
machine reading between the two was above its own documented critical threshold and was
still being routed as LOW risk. Scenario S17 (6.8 mm/s, 74 C) is exactly that band.

**The fix.** A band was added for 6.0 to 7.0 mm/s: same failure mode, a deliberately
wider window (72 to 120 hours) and lower confidence (0.82). The machine is confirmed to
be failing and the timing is less certain than it is at 7.2 mm/s.

**Why this shape and not the alternatives.** Moving the existing 7.0 boundary down to
6.0 would have assigned the 52 to 76 hour window to readings nobody calibrated it for,
which is a stronger claim than the evidence supports. Changing the documented threshold
to 7.0 instead would have made the system agree with itself by lowering the standard.
The added band only ever makes the system more cautious: nothing that was HIGH becomes
LOW, no existing window is lengthened, and the 7.2 mm/s demo path is byte-for-byte
unchanged.

The model underneath is still a band table rather than a fitted one, and it is still
labelled as a heuristic stub everywhere it appears. Fixing an inconsistency is not the
same as making it a real model.

---

## F-02 (resolved 2026-09) The safety rule both over-fired and under-fired

**Status:** fixed, after the test set was made hard enough to show the real problem.

The first version of this entry said the HALT keyword list was too broad, because it
contained the bare token `safety` and so halted "record the safety officer sign-off",
which is a required step of the emergency window procedure
(`tms-450-emergency-maintenance-window#S2`). At that point the scorecard read HALT recall
100%, precision 75%, and the conclusion was that the gate was over-cautious.

That conclusion was wrong, and it was wrong because the test set was easy.

**What the adversarial cases showed.** Seven scenarios were added first, deliberately
sitting on both sides of the rule's stated line: four that defeat a hazard control using
wording other than the obvious one, and three that merely mention the word safety. Re-run
against the unchanged rule, the numbers moved to:

| | Before the rule change, on the harder set |
|---|---|
| HALT recall | **0.71** (2 false negatives) |
| HALT precision | **0.56** (4 false positives) |

The false negatives are the important half. The gate did not catch "jumper the light
curtain so the cell keeps running", or "defeat the two-hand control on the press". A
missed HALT is a safety failure, and the original 100% recall had been an artefact of a
test set that only ever said "bypass" and "interlock".

**The root cause** was one modelling error producing both failure directions. SAFE-01
describes itself as "disables, bypasses, or modifies a safety interlock or guard". That is
a conjunction: an action of defeating, applied to a hazard control. A flat keyword OR
cannot express a conjunction, so the list had to include `safety` to catch anything at
all, and still missed every phrasing not already enumerated.

**The fix.** `tools/safety_gate.py` now supports a `match` block with `all_of` groups
(every group must hit) alongside the existing flat `keywords`, and SAFE-01 uses it: one
group of defeating actions (bypass, disable, defeat, jumper, override, remove, tamper,
tape over, short out, ...) and one group of hazard controls (interlock, guard, e-stop,
light curtain, presence sensing, two-hand control, safety relay, ...). Mentioning safety
is no longer a violation, and an unusual wording is still caught.

| | After |
|---|---|
| HALT recall | **1.00** (0 false negatives) |
| HALT precision | **1.00** (0 false positives) |

`policy.action_tier` was aligned to the same vocabulary, because a plan that tiers an
action AUTO which the gate then halts is its own kind of bug. `tests/test_policy.py` pins
both directions by name, and asserts the two vocabularies stay in step.

**On the process.** The earlier version of this entry said narrowing a safety rule should
not be done quietly by whoever is writing the evaluation. That still holds. What made the
change safe to make was building the adversarial set first, watching the old rule fail it,
and only then changing the rule: the evidence came before the edit, and the test set is
now the thing that would catch a regression.

---

## F-03 (fixed 2026-09) A low-risk run could finish without passing the safety gate

**Status:** fixed. Kept here because the fix is the reason to trust the suite.

`policy.allowed_next` previously returned `["compliance_safety", "FINISH"]` on a non-high
risk path. Both entries are legal choices, so the LLM supervisor was permitted to finish
a low-risk run without the safety gate ever running, while the README claimed
"compliance_safety always gates before FINISH".

It was never observed in a demo, because the supervisor happened to pick the gate. The
exhaustive path check in `eval/policy_eval.py` found it immediately: it enumerates every
sequence the policy permits rather than sampling the one a run took.

The branch now returns `["compliance_safety"]` until the gate has run. `S25` pins the
behaviour.

---

## F-04 (fixed 2026-09) `expedite_cost` crashed on an option with no quoted cost

**Status:** fixed.

The tool documented the fallback "if cost data missing, return options unranked with
data_missing flag" and did not implement it: a `None` cost went straight into a division
and raised a `TypeError`. A pending quote is an ordinary state during a supply
disruption, so this was reachable.

Options with missing cost or lead time now carry `data_missing`, rank below costed
options, and are read by `policy.needs_human_approval` as "a human decides", which is the
correct reading of an unknown cost. `S09` pins the behaviour.

---

## F-05 (2026-09) Query expansion was built, measured, and not adopted

**Status:** implemented, evaluated, deliberately not made the default.

The retrieval evaluation identified a specific weakness: BM25 finds the answer for 100%
of queries that use the corpus's own vocabulary and 41.7% of queries that deliberately
avoid it. That is classic lexical vocabulary mismatch.

The textbook fix is embeddings, which need an API key that CI does not have. So the
keyless alternative was built instead: RM3-style pseudo-relevance feedback in
`rag/expansion.py`, using literature default parameters, with expansion terms harvested
from the corpus and never from the query set.

**What it actually did:**

| Mode | recall@1 | recall@4 | recall@8 | MRR |
|---|---:|---:|---:|---:|
| lexical | **0.788** | 0.865 | 0.885 | **0.820** |
| prf | 0.712 | **0.885** | **0.904** | 0.777 |

On the paraphrase split it lifted recall@4 from 41.7% to 50.0%, which is the headline
number somebody would want to put in a README. Underneath, it fixed two queries (Q46,
Q49), broke one (Q45), and cost seven and a half points of recall@1.

**The decision.** Net, that is one query out of 52. On a set that size it is noise, and
the top-1 regression is real. Making it the default on the strength of "41.7% to 50.0%"
would be exactly the selective reporting this harness exists to prevent, so the default
stays plain lexical. PRF ships as an available mode (`TOS_RAG_MODE=prf`), is scored on
every run so the decision can be revisited when the corpus grows, and hybrid fusion uses
it when embeddings are configured.

**What this finding is really for.** The harness paid for itself here by preventing a
change, not by catching a bug. A convincing-looking improvement was proposed, measured
properly, and rejected on the evidence. That is the loop working.

**Still open:** the paraphrase gap itself. Embeddings remain the right answer, the dense
and hybrid rows are wired and waiting, and the moment a key exists as a repository secret
the nightly run fills them in. Until then the scorecard says "not configured" rather than
quietly reporting a lexical number under a hybrid label.

---

## F-06 (fixed 2026-09-21) Policy unit results did not prove graph integration

The original 190 passing tests missed four integration failures: historical failure text
overrode a current LOW risk verdict; the last safety tool result could erase a HALT;
missing safety output could clear a run; and rejection still entered model synthesis.
All 34 labelled scenarios now traverse the real graph with scripted specialist messages
and real tools. Separate failure tests cover construction, invocation and missing evidence.
No labels were changed. Rejection and HALT now produce deterministic withheld plans.

The live harness also ignored scenario fixtures and reread the demo files. Scoped tool
inputs now supply telemetry and quotes, and labelled actions reach compliance instructions.
Synthetic runs cannot modify case memory or send approval notifications. Citation credit
requires retrieval by the reporting agent, while dense queries use the query embedding
method and a separate cache namespace. See [the review](../docs/END_TO_END_REVIEW.md).

---

## F-07 (fixed 2026-09-22) Cross-validation said RMSE 11, held-out ground truth said 74

The first RUL model looked excellent and was broken.

Grouped 5-fold CV over the training engines reported RMSE 11.0 cycles, which is better
than published results for this benchmark. Scored against the held-out test engines and
their true remaining-life labels, the same model reported RMSE 73.7. The naive baseline,
predicting the training mean for every engine, scored 41.9. The model was more than
twice as bad as doing nothing.

**The cause.** A feature called `cycle_norm`, defined as a unit's current cycle divided
by that unit's last cycle. In training that denominator is the engine's total lifetime,
which is only knowable once the engine has already failed, so the feature encoded the
target almost directly. At inference the test engines are truncated, so every unit's most
recent cycle divides by itself and scores exactly 1.0, which the model had learnt to read
as "at failure". It predicted near-zero remaining life for all 100 test engines.

**Why cross-validation did not catch it.** Every fold shared the defect. Splitting by
engine prevents a unit straddling the boundary; it does nothing about a feature that is
computed from the whole of each unit's future. Grouped CV is not a leakage detector, and
treating it as one is how this survived to the first real evaluation.

**The fix.** The feature was removed. Raw cycle count replaced it, which is genuinely
observable at prediction time. CV moved to 15.6 and held-out test to 16.5. The two
agreeing is the actual result here; the earlier 11.0 was never real.

**The regression test.** `tests/test_rul_model.py::test_features_do_not_use_the_future`
truncates a unit and asserts that the features of the surviving cycles are unchanged. Any
feature computed from a unit's full history fails it. This is the property that was
violated, tested directly, rather than an assertion about the score.

A second, smaller defect surfaced the same way: constant sensors were being dropped from
the rolling features but survived as raw columns. Harmless to a tree model, and fixed,
but it had gone unnoticed until a test asked the question.

**What this cost and what it bought.** One wrong number, caught before it was reported.
It is also the strongest argument for the work in decision 008: this project had no way
to catch an error like this before, because it had nothing to check a prediction against.

---

## F-08 (fixed 2026-09-22) The RUL interval was a band that could not fail

The first version of the model reported an 80% interval from a pair of quantile models,
10th and 90th percentile, and measured coverage between 0.76 and 0.87. That looked like a
reasonable calibration result. It was not a result at all.

**The upper bound was degenerate.** The RUL target is clipped at 125 cycles and 39.4% of
training rows sit exactly at the clip, so the 90th percentile of the target is the cap
almost everywhere. The fitted upper-quantile model contained zero splits: it returned
125.0 for all 100 test engines. Its saved artifact was 10 KB against 1.7 MB for the lower
model, which is what prompted the check.

Because the truth is clipped at the same 125, the upper bound could never be violated.
The reported "interval coverage" was therefore just P(truth >= lower bound) wearing a
two-sided label, and no number in it was evidence of calibration.

**What replaced it.** A one-sided lower bound, which is the decision-relevant quantity
anyway: for maintenance planning the expensive mistake is believing there is more time
left than there is. The bound is conformalised on engines held out from fitting.

**The second finding, which is the more interesting one.** Split conformal guarantees
coverage only when the calibration points are exchangeable with the points it is applied
to. They are not, by construction of this benchmark:

| | fraction of points at the RUL cap |
|---|---|
| training cycles (calibration pool) | 39.4% |
| official benchmark test points | 11.0% |

The benchmark truncates its test engines toward later life on purpose. Calibrating on a
uniform sample of training cycles tunes the bound on a much easier distribution, so the
guarantee does not transfer. Measured rather than assumed: coverage on the official test
set runs below internal coverage on every subset.

The fix was to stop conflating the two and report both. Training engines are now split
three ways: fitted on, calibration, and an internal test set built by the *same* random
truncation process as the calibration set, so the two are exchangeable and the guarantee
does apply there. The official benchmark is reported separately as an external check
under known shift.

**The third finding.** Even on the exchangeable internal set, realised coverage varies
widely: 0.820, 0.985, 0.890 and 0.900 against a 0.90 target. Coverage on the calibration
set itself is exactly 0.905, so the arithmetic is right. The cause is that cycles within
one engine are heavily correlated. On FD001, per-engine coverage has a median of 0.90 but
three of twenty engines score below 0.5, one at 0.20, and each bad engine drags ten
correlated points down together.

**The effective sample size is the number of engines, not the number of rows.** Twenty
calibration engines cannot pin a 90% guarantee, and the two subsets with fifty-plus
engines land nearer the target. This is reported rather than tuned away, because the
tuning available (raise the quantile until the number looks right on the test set) is
precisely the thing that makes a calibration claim worthless.

## Known limits of the suite itself

Worth stating plainly, because a scorecard that does not describe its own blind spots is
marketing. These are the reasons 100% does not mean finished:

- **The retrieval corpus is small and clean.** Twelve documents with well-separated
  vocabulary is an easy retrieval problem. A recall@4 of 100 percent on the direct split
  says the corpus is well separated, not that retrieval is solved. The paraphrase split
  exists precisely because the direct split was uninformative.
- **Relevance labels are single-annotator.** They were written by reading the corpus, with
  no second pass and no inter-annotator agreement.
- **The offline suite cannot measure judgement.** It measures the code-enforced layer
  exactly. Whether an agent writes a good assessment is only measured by the live suite,
  on eight scenarios, which is a sample and not a guarantee.
- **The live suite auto-approves at the human gate.** That the gate fires is scored; what
  a real approver would decide is not modelled.
- **Cost figures are indicative.** Token counts are real, per-token prices are
  order-of-magnitude constants in `observability.py`, and free-tier providers are priced
  at zero because that is what this project spends.
- **The RUL lower bound is calibrated, not guaranteed, in deployment.** The conformal
  guarantee holds on data exchangeable with the calibration set. Under the shift the
  benchmark itself introduces it degrades measurably, and with few engines it is noisy.
  See F-08.
- **The RUL model is fitted to turbofan data, not to the demo asset.** It shows the method
  works on real degradation data with held-out labels, on 707 units. CNC spindle bearing
  predictions remain threshold-based and are labelled `declared_thresholds` in every tool
  result. Nothing in this repo backtests the demo asset, because no public run-to-failure
  data for it exists. See `eval/results/rul_backtest.md`.
