"""
Tests for the numeric groundedness metric.

Two failure modes matter equally here. Missing an invented figure makes the metric
useless. Flagging legitimate arithmetic makes it noisy, and a noisy metric gets ignored,
which is the same as useless with extra steps. Both directions are tested.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from eval.groundedness import score_report, score_run

# A realistic supply-chain tool trace: the numbers an agent genuinely has in hand.
TOOL_RESULTS = [
    {"machine_id": "CNC-07-LEI", "rul_hours": {"min": 52, "max": 76}, "confidence": 0.95},
    {"options_ranked": [{"label": "Schaeffler expedite", "cost_eur": 3200,
                         "lead_time_hours": 18, "roi_ratio": 79.7,
                         "downtime_cost_avoided_eur": 255000}],
     "downtime_cost_per_hour_eur": 7500},
]


def test_a_figure_that_came_from_a_tool_is_grounded():
    r = score_report("The Schaeffler expedite costs EUR 3,200 and arrives in 18 hours.",
                     TOOL_RESULTS)
    assert r["ungrounded"] == []
    assert r["grounded_rate"] == 1.0


def test_an_invented_cost_is_caught():
    r = score_report("The expedite costs EUR 2,850.", TOOL_RESULTS)
    assert 2850.0 in r["ungrounded"]


def test_an_invented_roi_is_caught():
    """The failure that actually reaches a plant manager: a confident ratio no tool
    produced."""
    r = score_report("This gives an ROI of 94.3 to 1, so it clearly pays for itself.",
                     TOOL_RESULTS)
    assert 94.3 in r["ungrounded"]


def test_thousands_separators_and_decimals_are_the_same_number():
    for phrasing in ("3200", "3,200", "3200.0", "EUR 3,200", "€3,200"):
        assert score_report(f"Cost: {phrasing}.", TOOL_RESULTS)["ungrounded"] == [], phrasing


def test_a_rounded_figure_still_counts_as_grounded():
    """An agent writing 79.7 for a computed 79.68 is rounding, not hallucinating."""
    assert score_report("ROI is 79.68:1.", TOOL_RESULTS)["ungrounded"] == []


def test_arithmetic_the_agent_is_supposed_to_do_is_grounded():
    """52 hours at EUR 7,500 an hour is 390,000. The agent computed it; it is not invented."""
    r = score_report("Leaving it 52 hours risks EUR 390,000 of production.", TOOL_RESULTS)
    assert r["ungrounded"] == []


def test_a_unit_conversion_is_grounded():
    """EUR 180,000 a day is EUR 7,500 an hour, which is the conversion the prompt asks for."""
    r = score_report("Downtime runs at EUR 180,000 per day.",
                     [{"production_impact_per_day_eur": 180000}])
    assert r["ungrounded"] == []
    r2 = score_report("That is EUR 7,500 per hour.",
                      [{"production_impact_per_day_eur": 180000}])
    assert r2["ungrounded"] == []


def test_small_counts_are_not_flagged():
    """'two technicians', '5 jobs' and '6h window' are the agent reading its instructions,
    not inventing evidence."""
    r = score_report("Two technicians are required and 5 jobs move.", TOOL_RESULTS)
    assert r["numbers_checked"] == 0
    assert r["ungrounded"] == []


def test_years_are_not_treated_as_claims():
    r = score_report("The machine was installed in 2019.", TOOL_RESULTS)
    assert r["ungrounded"] == []


def test_numbers_quoted_from_the_task_prompt_are_grounded():
    """The agent was told them, so they are not unsupported."""
    r = score_report("Rerouting jobs J4421-J4425 protects EUR 145,000 of output.",
                     TOOL_RESULTS,
                     prompt="Reroute jobs worth 145000 to equivalent machines.")
    assert r["ungrounded"] == []


def test_the_rate_reflects_the_mix():
    r = score_report("Cost EUR 3,200, ROI 94.3:1, lead time 18 hours.", TOOL_RESULTS)
    assert r["numbers_checked"] == 3
    assert r["ungrounded"] == [94.3]
    assert r["grounded_rate"] == round(2 / 3, 4)


def test_a_report_with_no_numbers_is_not_scored():
    r = score_report("The machine needs attention soon.", TOOL_RESULTS)
    assert r["numbers_checked"] == 0
    assert r["grounded_rate"] is None


def test_an_agent_with_no_tool_output_cannot_ground_anything():
    """This is the case worth catching: an agent whose tools all failed, still confidently
    quoting figures."""
    r = score_report("RUL is 61 hours and the fix costs EUR 4,100.", [])
    assert set(r["ungrounded"]) == {61.0, 4100.0}


def test_score_run_aggregates_across_agents():
    out = score_run(
        reports={"reliability": "RUL 52 to 76 hours.",
                 "supply_chain": "Cost EUR 9,999."},
        tool_results_by_agent={"reliability": TOOL_RESULTS, "supply_chain": TOOL_RESULTS},
    )
    assert out["numbers_checked"] == 3
    assert out["ungrounded_numbers"] == 1
    assert out["by_agent"]["reliability"]["ungrounded"] == []
    assert out["by_agent"]["supply_chain"]["ungrounded"] == [9999.0]


def test_booleans_are_not_mistaken_for_numbers():
    """True is 1 in Python. Letting it into the source set would ground every 1."""
    r = score_report("The figure is 1000.", [{"fits_failure_window": True}])
    assert r["ungrounded"] == [1000.0]


# --- does the metric actually have teeth? ---------------------------------- #
def test_the_derivation_rule_does_not_explain_everything():
    """The meta-test, and the reason to trust any number this metric reports.

    A derivation rule that accepts arbitrary arithmetic over n tool values can explain
    almost any figure, at which case groundedness reads 100% and means nothing. This
    samples plausible invented numbers against a realistic tool trace and asserts that the
    large majority are still rejected.

    It is a property of the rule, not of a fixture, so it fails if somebody later widens
    the tolerance or re-admits arbitrary division to make a run look better."""
    import random

    from eval.groundedness import derivable

    sources = set()
    for obj in TOOL_RESULTS:
        from eval.groundedness import _numbers_in_obj
        sources |= _numbers_in_obj(obj)

    rng = random.Random(11)
    # Figures in the shape an agent would actually invent: costs, hours, ratios.
    samples = ([round(rng.uniform(500, 9000), 0) for _ in range(300)]
               + [round(rng.uniform(20, 200), 1) for _ in range(300)]
               + [round(rng.uniform(10, 99), 1) for _ in range(300)])

    accepted = sum(1 for v in samples if derivable(v, sources))
    rate = accepted / len(samples)
    assert rate < 0.15, (
        f"the derivation rule accepts {rate:.1%} of arbitrary plausible numbers as "
        "grounded. Above about 15% the metric stops distinguishing a real figure from an "
        "invented one."
    )


def test_tightening_has_not_broken_legitimate_rounding():
    """The other side of the same coin: too tight and every rounded figure is a false
    positive, the metric becomes noise, and people stop reading it."""
    from eval.groundedness import derivable

    assert derivable(79.68, {79.7})        # agent rounds a tool value
    assert derivable(7500.0, {180000.0})   # per day to per hour
    assert derivable(255000.0, {255000})   # exact restatement
