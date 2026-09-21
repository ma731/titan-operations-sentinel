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
