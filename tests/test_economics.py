"""
Tests for the unit-economics report.

The point of these is that the numbers stay honest. A cost model is easy to quietly break
into something that looks precise and means nothing, which is exactly what happened the
first time: the wake rate was scaled against the raw alert count, and a reading and an
alert are not the same unit.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from eval import economics


def test_the_triage_measurement_is_deterministic():
    """It runs the real gate with a fixed seed, so two calls must agree exactly."""
    assert economics.measure_wake_rate() == economics.measure_wake_rate()


def test_a_simulated_day_wakes_the_agents_only_a_handful_of_times():
    w = economics.measure_wake_rate()
    assert w["simulated_hours"] == 24.0
    assert w["readings"] > 300
    assert 0 < w["runs"] <= 5, "a day that triggers more than a few runs is not triaging"
    assert w["wake_rate"] < 0.02


def test_free_tier_providers_cost_nothing():
    """Zero because that is what the project actually spends, not as a placeholder."""
    assert economics.cost_per_run("groq", 18_000) == 0.0
    assert economics.cost_per_run("google_genai", 18_000) == 0.0


def test_a_paid_provider_costs_less_than_a_cent_per_run():
    assert 0 < economics.cost_per_run("openai", 18_000) < 0.01


def test_an_unknown_provider_does_not_raise():
    assert economics.cost_per_run("some-provider-we-never-heard-of", 18_000) == 0.0


def test_runs_per_day_comes_from_alerts_not_from_scaling_readings():
    """Regression guard. Scaling the per-reading wake rate against 22,431 alerts gave 78
    runs a day against a case study that says 3. Different units, precise-looking nonsense."""
    m = economics.run()["measured"]
    assert m["runs_per_plant_day"] == economics.DEDUPLICATED_CRITICAL_PER_DAY
    assert "case study" in m["runs_per_plant_day_source"]


def test_the_simulator_cross_check_is_the_same_order_as_the_case_study():
    """Two independent routes to 'a few runs a day'. If they diverge, one is wrong."""
    m = economics.run()["measured"]
    assert abs(m["simulator_cross_check_runs_per_day"] - m["runs_per_plant_day"]) <= 3


def test_token_source_is_always_labelled():
    """A cost figure whose input nobody can trace is not a cost figure."""
    m = economics.run()["measured"]
    assert m["tokens_per_run"] > 0
    assert m["tokens_per_run_source"]


def test_case_study_inputs_are_labelled_as_inputs():
    inputs = economics.run()["case_study_inputs"]
    assert "not results" in inputs["note"]


def test_cost_scales_with_tokens():
    assert (economics.cost_per_run("openai", 36_000)
            == 2 * economics.cost_per_run("openai", 18_000))
