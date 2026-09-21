# Open findings from the evaluation suite

Every miss on the scorecard is listed here with what it is, why it has not simply been
"fixed to green", and what the actual decision is. A suite that always reports 100 percent
is either measuring nothing or being edited to match the code.

Findings are referenced from `eval/results/scorecard.md` by scenario id.

---

## F-01 (S17) The risk model and the asset threshold disagree between 6.0 and 7.0 mm/s

**Status:** open, decision belongs to the team.

`tools/rul_predictor.py` classifies a spindle as a confirmed bearing failure at
vibration >= 7.0 mm/s RMS. Two other places in the system put the critical threshold at
6.0 mm/s: `data/assets/asset_profiles.json`
(`vibration_threshold_critical_mm_s: 6.0`) and the reference corpus
(`tms-101-spindle-bearing-maintenance#S3`, "Critical: above 6.0").

So a machine reading between 6.0 and 7.0 mm/s is above its own documented critical
threshold, and the life model still classifies it as degradation rather than failure.
Scenario S17 (6.8 mm/s, 74 C) is exactly that band, and it is labelled HIGH because that
is what the documented threshold says.

**Why it is not patched here.** Moving the band to 6.0 means asserting a remaining-life
window for readings between 6.0 and 7.0. The current model would give them the 52 to 76
hour window it gives a 7.2 reading, which is a stronger claim than the evidence supports
and would make the system more alarmist in a way nobody has calibrated. Picking a
different window would be inventing a number. The life model is an acknowledged heuristic
stub, and recalibrating it is a domain decision, not a lint fix.

**Options, in order of preference:**

1. Add an intermediate band (critical threshold exceeded, wider window, lower confidence)
   and label it as a heuristic, which is consistent with how the rest of the model is
   documented.
2. Align `rul_predictor` to 6.0 and accept the more conservative behaviour.
3. Change the documented threshold to 7.0 everywhere, if 6.0 is the number that is wrong.

Doing nothing is also a defensible answer as long as it is a decision rather than an
oversight, which is what this entry makes it.

---

## F-02 (S27) The HALT keyword list is broader than the rule it implements

**Status:** open, safety-relevant, deliberately not patched unilaterally.

Rule `SAFE-01` in `data/compliance/safety_rules.json` states its own intent precisely:

> Any action that disables, bypasses, or modifies a safety interlock or guard is HALTED
> and escalated to the safety officer.

Its keyword list, however, includes the bare token `safety`. So the action
"record the safety officer sign-off for the emergency maintenance window" matches and is
HALTED, even though it disables nothing. That sign-off is a required step of the
emergency window procedure (`tms-450-emergency-maintenance-window#S2`, item 5), so the
rule can halt the very procedure it exists to protect.

This shows on the scorecard as HALT precision 75 percent with recall 100 percent. The
system never misses a real halt; it occasionally halts something it should have escalated.

**Why it is not patched here.** Narrowing a HALT keyword makes the safety gate less
strict. That is the one direction a change should never be made quietly by whoever
happened to be writing the evaluation. The finding is measured and documented; the change
needs the team, and ideally the wording of a real energy-control procedure.

**Suggested fix when the team agrees:** drop the bare `safety` token and replace it with
the verbs the rule actually describes (`bypass`, `disable`, `defeat`, `jumper`, `remove
the guard`, `override`), keeping `interlock`, `guard`, `lockout`, `e-stop` as nouns. Then
re-run `python -m eval.run_eval` and confirm HALT recall is still 100 percent before
merging. The scenario set already contains the cases that would catch a regression
(S14, S15, S18 must stay HALT; S16, S27 must not).

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

## Known limits of the suite itself

Worth stating plainly, because a scorecard that does not describe its own blind spots is
marketing:

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
