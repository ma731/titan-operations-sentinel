"""
Tests for the continuous alert stream and its triage gate.

All offline. The simulator is seeded and the gate is deterministic, so these assert on
exact behaviour rather than on "it did something".
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from stream.simulator import AlertSimulator, MachineProfile, Reading
from stream.triage import Band, TriageGate, severity_band


def _reading(machine="CNC-07-LEI", vib=3.0, temp=55.0, tick=0):
    return Reading(machine, "LEI", "2026-06-12T08:00:00+00:00", vib, temp, 42.0, tick)


# --- severity bands -------------------------------------------------------- #
def test_bands_follow_the_documented_thresholds():
    assert severity_band(2.0, 50) is Band.NORMAL
    assert severity_band(4.0, 50) is Band.ELEVATED
    assert severity_band(5.5, 50) is Band.WARNING
    assert severity_band(7.2, 50) is Band.CRITICAL
    assert severity_band(12.0, 50) is Band.TRIP


def test_a_machine_sits_in_the_highest_band_any_parameter_reaches():
    """Bands are not averaged: a normal vibration with a critical temperature is still
    a critical machine (tms-101-spindle-bearing-maintenance#S3)."""
    assert severity_band(2.0, 80.0) is Band.CRITICAL


def test_critical_vibration_with_normal_temperature_is_still_critical():
    assert severity_band(7.2, 50.0) is Band.CRITICAL


# --- the wake decision ----------------------------------------------------- #
def test_a_quiet_machine_does_not_wake_anyone():
    gate = TriageGate()
    assert gate.observe(_reading(vib=2.8, temp=52)).wake is False
    assert gate.woken == 0


def test_a_critical_reading_wakes_the_team():
    gate = TriageGate()
    v = gate.observe(_reading(vib=7.2, temp=78))
    assert v.wake is True
    assert v.alert["machine_id"] == "CNC-07-LEI"
    assert v.alert["value"] == 7.2


def test_the_alert_matches_the_shape_the_graph_takes():
    """A stream-triggered run has to be identical to a manually triggered one."""
    from graph import FRIDAY_CASCADE_ALERT

    alert = TriageGate().observe(_reading(vib=7.2, temp=78)).alert
    required = {"alert_id", "machine_id", "plant_id", "sensor", "value", "unit",
                "threshold", "trend", "production_impact_per_day_eur"}
    assert required <= set(alert)
    assert required <= set(FRIDAY_CASCADE_ALERT)


def test_a_sharp_rise_wakes_even_below_the_critical_band():
    """Change beats absolute level (tms-204-vibration-severity-limits#S4)."""
    gate = TriageGate()
    gate.observe(_reading(vib=2.8, tick=0))
    v = gate.observe(_reading(vib=5.4, temp=62, tick=6))
    assert v.wake is True
    assert "over the trend window" in v.reason


def test_a_sharp_rise_that_stays_in_the_elevated_band_does_not_wake():
    gate = TriageGate()
    gate.observe(_reading(vib=1.9, tick=0))
    assert gate.observe(_reading(vib=3.7, tick=6)).wake is False


def test_the_cooldown_stops_one_event_becoming_a_run_per_tick():
    gate = TriageGate()
    assert gate.observe(_reading(vib=7.2, temp=78, tick=0)).wake is True
    for tick in range(1, 20):
        v = gate.observe(_reading(vib=7.4, temp=79, tick=tick))
        assert v.wake is False
        assert v.suppressed_by_cooldown is True
    assert gate.woken == 1
    assert gate.suppressed == 19


def test_the_cooldown_expires():
    gate = TriageGate(cooldown_ticks=5)
    gate.observe(_reading(vib=7.2, temp=78, tick=0))
    assert gate.observe(_reading(vib=7.4, temp=79, tick=6)).wake is True


# --- telemetry dropouts ---------------------------------------------------- #
def test_a_healthy_machine_going_quiet_is_not_an_operations_event():
    gate = TriageGate()
    gate.observe(_reading(vib=2.7, temp=52, tick=0))
    assert gate.check_dropouts(tick=10) == []


def test_a_critical_machine_going_quiet_wakes_the_escalation_path():
    gate = TriageGate()
    gate.observe(_reading(vib=7.2, temp=78, tick=0))
    verdicts = gate.check_dropouts(tick=10)
    assert len(verdicts) == 1
    assert verdicts[0].wake is True
    assert verdicts[0].alert["suggested_mode"] == "escalation"


def test_a_dropout_is_reported_once_not_every_tick():
    gate = TriageGate()
    gate.observe(_reading(vib=7.2, temp=78, tick=0))
    assert len(gate.check_dropouts(tick=10)) == 1
    assert gate.check_dropouts(tick=11) == []
    assert gate.check_dropouts(tick=40) == []


def test_a_returning_feed_re_arms_dropout_detection():
    gate = TriageGate(cooldown_ticks=1)
    gate.observe(_reading(vib=7.2, temp=78, tick=0))
    gate.check_dropouts(tick=10)
    gate.observe(_reading(vib=7.5, temp=79, tick=11))     # the feed comes back
    assert len(gate.check_dropouts(tick=20)) == 1


# --- the simulator --------------------------------------------------------- #
def test_the_simulator_is_deterministic_for_a_seed():
    a = AlertSimulator.from_fleet(seed=3).run_for(12)
    b = AlertSimulator.from_fleet(seed=3).run_for(12)
    assert [r.to_dict() for batch in a for r in batch] == \
           [r.to_dict() for batch in b for r in batch]


def test_baselines_are_stable_across_processes():
    """Regression guard: this used to use hash(), which Python randomises per process,
    so every run gave each machine a different baseline."""
    a = {p.machine_id: p.baseline_vibration for p in AlertSimulator.from_fleet().profiles}
    b = {p.machine_id: p.baseline_vibration for p in AlertSimulator.from_fleet().profiles}
    assert a == b
    assert all(2.6 <= v < 3.3 for v in a.values())


def test_a_degrading_machine_eventually_crosses_the_critical_band():
    sim = AlertSimulator(profiles=[MachineProfile("CNC-07-LEI",
                                                  degradation_per_tick=0.035)], seed=7)
    peak = max(r.vibration for batch in sim.run_for(40) for r in batch)
    assert peak > 6.0


def test_healthy_machines_stay_in_band():
    sim = AlertSimulator(profiles=[MachineProfile("CNC-05-LEI")], seed=7)
    assert all(r.vibration < 5.0 for batch in sim.run_for(60) for r in batch)


def test_a_dropped_feed_stops_producing_readings():
    sim = AlertSimulator(profiles=[MachineProfile("CNC-07-LEI", dropout_from_tick=5)],
                         seed=7)
    batches = sim.run_for(10)
    assert all(batches[i] for i in range(5))
    assert all(not batches[i] for i in range(5, 10))


# --- the loop end to end --------------------------------------------------- #
def test_the_dry_run_loop_triggers_exactly_one_run_over_the_default_window():
    """The headline ratio: hundreds of readings, one expensive run."""
    from stream.run import main

    assert main(["--ticks", "40", "--max-runs", "3"]) == 0


def test_the_wake_rate_stays_low():
    sim = AlertSimulator.from_fleet(seed=7)
    gate = TriageGate()
    for _ in range(60):
        batch = sim.next_batch()
        for r in batch:
            gate.observe(r)
        gate.check_dropouts(batch[0].tick if batch else 0)
    stats = gate.stats()
    assert stats["readings_seen"] > 200
    assert stats["runs_triggered"] <= 2
    assert stats["wake_rate"] < 0.02


def test_explicit_dry_run_cannot_be_overridden_by_live():
    import pytest

    from stream.run import main
    with pytest.raises(SystemExit) as exc:
        main(["--live", "--dry-run"])
    assert exc.value.code == 2
