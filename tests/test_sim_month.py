"""
The simulated month and the shared clock.

All offline and seeded, so the month replays identically and these assert exact outcomes.
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from stream.month import MonthSimulator, load_scenario, replay, score  # noqa: E402
from stream.triage import VIB_CRITICAL  # noqa: E402
from tools import sim_clock  # noqa: E402
from tools.notify import notify  # noqa: E402
from tools.work_order_draft import work_order_draft  # noqa: E402

CORPUS = Path(__file__).resolve().parents[1] / "rag" / "corpus"


def _wo():
    return work_order_draft("CNC-07-LEI", "LEI", "spindle_bearing_failure",
                            [{"part": "P-4421", "qty": 1}], {"start": "x"}, ["mech"], 6, [])


# --- one clock -------------------------------------------------------------- #
def test_drafts_use_plant_time_inside_a_simulated_run():
    with sim_clock.sim_clock("2026-06-12T14:32:00Z"):
        wo = _wo()
        n = notify("plant_manager", "s", "x", [], 100.0, 10.0, "2026-06-13T08:00:00Z")
    assert wo["generated_at_utc"].startswith("2026-06-12T14:32")
    assert wo["work_order_id"] == "WO-CNC-07-LEI-202606121432"
    assert wo["time_basis"] == n["time_basis"] == "simulated_plant_time"
    assert n["generated_at_utc"].startswith("2026-06-12T14:32")


def test_outside_a_simulated_run_the_wall_clock_is_untouched():
    with sim_clock.sim_clock(None):
        assert _wo()["time_basis"] == "wall_clock"
    with sim_clock.sim_clock("2026-06-12T14:32:00Z"):
        pass
    assert _wo()["time_basis"] == "wall_clock"
    assert not _wo()["generated_at_utc"].startswith("2026-06-12")


def test_plant_time_moves_forward_so_drafts_stay_ordered():
    with sim_clock.sim_clock("2026-06-12T14:32:00"):    # naive input is read as UTC
        a = sim_clock.now()
        b = sim_clock.now()
    assert a.tzinfo is not None and b >= a


# --- the month -------------------------------------------------------------- #
@pytest.fixture(scope="module")
def month():
    sim = MonthSimulator(load_scenario())
    wakes, gate = replay(sim)
    return sim, wakes, gate, score(sim, wakes)


def _event(result, eid):
    return next(r for r in result["events"] if r["id"] == eid)


def test_the_month_is_identical_on_every_run(month):
    sim, wakes, _, _ = month
    again, _ = replay(MonthSimulator(load_scenario()))
    assert [(w["tick"], w["machine_id"]) for w in again] == \
           [(w["tick"], w["machine_id"]) for w in wakes]


def test_every_answer_cites_a_real_corpus_section(month):
    sim = month[0]
    for e in sim.scenario["events"]:
        for ref in e["expected"]["source"].split(";"):
            doc, section = ref.strip().split("#")
            text = (CORPUS / f"{doc}.md").read_text(encoding="utf-8")
            assert f"## {section} " in text, ref


def test_the_scripted_failures_sit_inside_the_corpus_windows(month):
    result = month[3]
    bearings = [r for r in result["events"] if r["kind"] == "bearing"]
    assert len(bearings) == 3 and all(r["truth_matches_corpus"] for r in bearings)


def test_the_slow_drift_never_reaches_the_critical_band(month):
    """Its label (no wake) is only right while it stays below critical. Past 6.0 mm/s
    the corpus says to wake (tms-101#S3), so a drift that got there would be a bad label."""
    sim = month[0]
    m = next(x for x in sim.machines if x.machine_id == "CNC-08-LEI")
    peak = max(sim._signal(m, t / 6)["vib"] for t in range(sim.ticks))
    assert peak < VIB_CRITICAL * 0.85


def test_every_real_failure_is_caught_a_day_or_more_ahead(month):
    result = month[3]
    for eid in ("M01-fast-bearing", "M05-fast-bearing-feed-loss", "M06-medium-bearing"):
        r = _event(result, eid)
        assert r["pass"] and r["lead_h"] >= 24, eid


def test_a_feed_lost_on_a_critical_machine_wakes_with_the_right_plant(month):
    _, wakes, _, result = month
    assert _event(result, "M05-fast-bearing-feed-loss")["dropout_wake"] is True
    drop = [w for w in wakes if w["kind"] == "dropout"]
    assert drop and all(w["verdict"].alert["plant_id"] == "AMS" for w in drop)


def test_healthy_noise_and_a_healthy_feed_loss_wake_nobody(month):
    result = month[3]
    assert result["wakes_on_noise"] == 0
    assert _event(result, "M03-healthy-feed-loss")["pass"]
    assert _event(result, "M07-slow-drift")["pass"]


def test_a_failed_machine_is_stopped_until_the_repair_is_done(month):
    sim = month[0]
    t = sim.truth["M01-fast-bearing"]
    fresh = MonthSimulator(load_scenario())
    seen = {}
    for tick in range(int(t["back_h"] * 6) + 6):
        batch, labels = fresh.batch(tick)
        r = next((x for x in batch if x.machine_id == "CNC-07-LEI"), None)
        seen[tick] = (labels["CNC-07-LEI"], r.vibration if r else None)
    stopped = [v for lab, v in seen.values() if lab == "stopped_after_failure"]
    assert stopped and max(stopped) < 1.0
    assert seen[max(seen)][0] == "healthy"


def test_alerts_carry_spindle_current_for_the_load_check(month):
    _, wakes, _, _ = month
    reading_wake = next(w for w in wakes if w["kind"] == "reading")
    assert "spindle_current_a" in reading_wake["verdict"].alert


def test_life_estimates_are_labelled_as_declared_rules(month):
    result = month[3]
    checks = [c for r in result["events"] for c in r.get("life", [])]
    assert checks and {c["source"] for c in checks} == {"declared_thresholds"}


def test_export_writes_a_labelled_line_per_machine_per_tick(tmp_path):
    out = tmp_path / "m.jsonl"
    sim = MonthSimulator(load_scenario())
    replay(sim, export=out)
    lines = out.read_text(encoding="utf-8").splitlines()
    assert len(lines) == sim.ticks * len(sim.machines)
    rows = [json.loads(x) for x in lines]
    assert any(r.get("missing") for r in rows) and all("truth" in r for r in rows)


# --- known gaps, pinned so a fix shows up -------------------------------- #
@pytest.mark.xfail(strict=True, reason="the gate ignores spindle current, so a heavier "
                   "cut reads like a defect (tms-101#S2)")
def test_a_heavier_cut_does_not_wake_the_agents(month):
    assert _event(month[3], "M02-heavy-cut")["pass"]


@pytest.mark.xfail(strict=True, reason="the gate trusts a single channel pinned at its "
                   "rail value (tms-705#S6)")
def test_a_saturated_sensor_does_not_wake_the_agents(month):
    assert _event(month[3], "M04-sensor-rail")["pass"]


@pytest.mark.xfail(strict=True, reason="the CNC rule reads vibration level, not rate, "
                   "so it promises a fast bearing more life than it has (tms-101#S4)")
def test_the_first_estimate_on_a_fast_bearing_is_not_optimistic(month):
    firsts = month[3]["first_estimates"]
    assert firsts["M01-fast-bearing"] != "optimistic"
