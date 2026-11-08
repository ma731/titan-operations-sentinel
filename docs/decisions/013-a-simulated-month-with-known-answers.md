# 013. Check the CNC predictions against a simulated month with known answers

**Accepted, November 2026.**

## Context

Three gaps showed up in one live run:

1. The demo data is dated 12 June. The work order and notification drafts stamped the
   real date, so the model saw two "nows" and called the data stale.
2. The agents got one reading per sensor, which is not a trend.
3. The CNC life estimate is a declared rule (decision 008). No public run-to-failure data
   exists for this asset, so none of its predictions could be checked.

## Decision

- **Numbers from a seeded simulator, not a language model.** `stream/month.py` generates
  30 days for the four CNC machining centres at 10 minute resolution, reusing the
  baselines and reading shape of `stream/simulator.py`. A model writing sensor values
  would be neither reproducible nor physically consistent.
- **Answers fixed before anything runs.** `data/sim_month/scenario.json` scripts seven
  events. Each one cites the corpus for its answer: failure windows from tms-101#S4,
  "do not wake" from tms-101#S2 and tms-705#S6, risk labels from tms-101 and tms-705#S5.
  The month is open loop, so each failure time stays a fixed answer.
- **One clock per run.** `tools/sim_clock.py` is a context variable. Inside it the drafts
  use plant time and say `time_basis: simulated_plant_time`; outside it nothing changes.
  The audit log keeps the wall clock, because it records when the software ran.
- **Real windows.** A run started from the month hands `sensor_query` the 72 hours before
  the wake (`tools/sim_window.py`), with gaps reported as an interrupted feed.
- **Separate cases file.** The 27 wakes are labelled in `eval/cases/sim_month_cases.json`
  and scored by `eval/sim_month_eval.py` as section 5 of the scorecard. They are kept out
  of `scenarios.json` so the 34 policy scenarios, and every number already published,
  stay exactly as they were. A test fails if the committed cases drift from the month.

## What it found

- The triage gate catches all three failures 57 to 154 hours ahead and stays silent on the
  quiet days. It does wake on a heavier cut and on a stuck sensor.
- The CNC life interval contains the true remaining life in 4 of 24 checks, and is
  optimistic in 15. It reads the vibration level; tms-101#S4 says the window comes from
  the rate of change.

All three gaps are pinned as strict xfails in `tests/test_sim_month.py`. Fixing one turns
its test red until the xfail is removed, so a fix cannot go unnoticed. None is fixed here:
each one is a change to a rule, and it belongs in its own PR with the eval re-run.

## Cost

The validation is circular in one place: the simulator follows the same rule of thumb the
predictions should follow. So this checks the code against the plant's own documents,
not against real bearings. One seed and seven scripted events are a small sample.
Moving an event in the scenario means regenerating the cases
(`python -m stream.month --write-cases`).
