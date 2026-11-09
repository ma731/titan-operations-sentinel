"""
The wake gate: decide whether a reading is worth running six agents over.

This is the cheap, deterministic layer between a continuous sensor stream and an
expensive multi-agent run. It answers three questions in order:

  1. Is this reading past a documented severity band? (tms-101-spindle-bearing-maintenance#S3)
  2. Is it a genuine change, or has this machine always read like this?
     (tms-204-vibration-severity-limits#S4: change beats absolute level)
  3. Have we already woken the team for this machine recently?

Two checks run first, because a vibration number on its own can lie:

  - Load (tms-101-spindle-bearing-maintenance#S2). Spindle current is the
    load-normalisation signal. When current is up on its own baseline and the bearing
    temperature stays flat, vibration is divided by the load before it is banded, so a
    heavier cut is not read as a defect. A rise the load cannot explain still wakes.
  - Sensor fault (tms-705-telemetry-data-quality-and-abstention#S6). One channel that
    steps onto a rail or flatlines exactly while temperature and current stay normal is
    raised as an instrumentation case, not a machine wake.

Only a yes-yes-no starts a run. The cooldown is the one people forget: a degrading machine
stays over threshold for hours, so without it one event becomes a run every tick.

A dropout is its own wake condition, not silence. A sensor that stops reporting on a
machine that was trending up is the case the abstention path exists for.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

# Severity bands, from tms-101-spindle-bearing-maintenance#S3 and the asset profiles.
VIB_WARNING = 5.0
VIB_CRITICAL = 6.0
VIB_TRIP = 11.0
TEMP_WARNING = 65.0
TEMP_CRITICAL = 75.0
TEMP_MAX = 85.0

# A rise by this factor over the trend window is itself a wake condition even below the
# critical band, because a change from baseline is more diagnostic than the level.
TREND_FACTOR = 1.8
TREND_WINDOW_TICKS = 36            # 6 hours at 10 minutes per tick

COOLDOWN_TICKS = 72                # do not re-wake for the same machine for 12 hours
MISSING_FEED_TICKS = 3             # ticks of silence before a feed counts as dropped

# Load check. Current this far over the machine's own baseline counts as a heavier cut.
LOAD_RISE = 1.15
# Temperature within this of its baseline counts as flat. A defect heats the bearing
# (tms-101#S2: "temperature confirms"), a heavier cut barely does.
TEMP_FLAT_C = 5.0
BASELINE_ALPHA = 1 / 144           # baselines move over about a day of normal running

# Sensor fault check. Bearing wear doubles over hours, never 3x in one 10 minute tick,
# so a step like that into the trip band is the channel hitting its rail.
RAIL_STEP_FACTOR = 3.0
FLATLINE_TICKS = 3                 # identical readings in a row: the channel is frozen


class Band(str, Enum):
    NORMAL = "normal"
    ELEVATED = "elevated"
    WARNING = "warning"
    CRITICAL = "critical"
    TRIP = "trip"


@dataclass
class TriageVerdict:
    machine_id: str
    wake: bool
    band: Band
    reason: str
    priority: float
    alert: dict | None = None
    suppressed_by_cooldown: bool = False
    instrumentation_case: dict | None = None   # set once per sensor fault, never a wake


def severity_band(vibration: float, bearing_temp: float) -> Band:
    """The highest band any single parameter reaches. Bands are not averaged."""
    if vibration > VIB_TRIP or bearing_temp > TEMP_MAX:
        return Band.TRIP
    if vibration > VIB_CRITICAL or bearing_temp > TEMP_CRITICAL:
        return Band.CRITICAL
    if vibration >= VIB_WARNING or bearing_temp >= TEMP_WARNING:
        return Band.WARNING
    if vibration >= 3.5 or bearing_temp >= 60.0:
        return Band.ELEVATED
    return Band.NORMAL


@dataclass
class _MachineState:
    # (tick, vibration after the load check). Readings flagged as sensor faults stay out.
    history: list[tuple[int, float]] = field(default_factory=list)
    last_seen_tick: int = -1
    last_wake_tick: int | None = None
    baseline: float | None = None
    current_baseline: float | None = None
    temp_baseline: float | None = None
    last_raw_vib: float | None = None
    same_count: int = 0                # readings in a row with the exact same vibration
    fault_value: float | None = None   # the value a faulted channel is pinned at
    dropout_reported: bool = False
    plant_id: str = "LEI"


@dataclass
class TriageGate:
    """Stateful per-machine triage over a reading stream."""

    cooldown_ticks: int = COOLDOWN_TICKS
    trend_factor: float = TREND_FACTOR
    seen: int = 0
    woken: int = 0
    suppressed: int = 0
    load_explained: int = 0
    instrumentation_cases: list[dict] = field(default_factory=list)
    _state: dict[str, _MachineState] = field(default_factory=dict, repr=False)

    def _machine(self, machine_id: str) -> _MachineState:
        return self._state.setdefault(machine_id, _MachineState())

    def observe(self, reading) -> TriageVerdict:
        """Score one reading and decide whether to wake the agents."""
        self.seen += 1
        st = self._machine(reading.machine_id)
        st.last_seen_tick = reading.tick
        st.plant_id = reading.plant_id
        st.dropout_reported = False          # the feed is back
        if st.baseline is None:
            st.baseline = reading.vibration        # first clean reading is the reference
            st.current_baseline = reading.spindle_current
            st.temp_baseline = reading.bearing_temp

        fault = self._sensor_fault(st, reading)
        st.last_raw_vib = reading.vibration
        if fault:
            return self._instrumentation_verdict(st, reading, fault)

        vib, load = self._load_check(st, reading)
        st.history.append((reading.tick, vib))
        st.history = st.history[-(TREND_WINDOW_TICKS + 1):]
        band = severity_band(vib, reading.bearing_temp)
        window_start = next((v for t, v in st.history
                             if t >= reading.tick - TREND_WINDOW_TICKS), vib)
        rise = vib / window_start if window_start else 1.0
        self._update_baselines(st, reading, band)

        reasons = []
        if band in (Band.CRITICAL, Band.TRIP):
            reasons.append(f"{band.value} band ({reading.vibration:.1f} mm/s, "
                           f"{reading.bearing_temp:.0f} C)")
        # Under a heavier cut the rise tracks current, so it is not a wake reason on its
        # own. Only the load-adjusted level can wake.
        if rise >= self.trend_factor and band not in (Band.NORMAL, Band.ELEVATED) and not load:
            reasons.append(f"vibration up {rise:.1f}x over the trend window")
        if reasons and load:
            reasons.append(f"still {vib:.1f} mm/s after allowing for spindle load x{load:.2f}")

        if not reasons:
            why = "below the wake threshold"
            raw_band = severity_band(reading.vibration, reading.bearing_temp)
            raw_rise = reading.vibration / window_start if window_start else 1.0
            if load and (raw_band in (Band.CRITICAL, Band.TRIP) or (
                    raw_rise >= self.trend_factor
                    and raw_band not in (Band.NORMAL, Band.ELEVATED))):
                self.load_explained += 1
                why = (f"vibration {reading.vibration:.1f} mm/s tracks spindle current "
                       f"x{load:.2f} with temperature flat: process load, not a bearing "
                       f"finding (tms-101-spindle-bearing-maintenance#S2)")
            return TriageVerdict(reading.machine_id, False, band, why,
                                 self._priority(band, rise))

        if self._in_cooldown(st, reading.tick):
            self.suppressed += 1
            return TriageVerdict(
                reading.machine_id, False, band,
                f"already handled {reading.tick - st.last_wake_tick} ticks ago; in cooldown",
                self._priority(band, rise), suppressed_by_cooldown=True,
            )

        st.last_wake_tick = reading.tick
        self.woken += 1
        return TriageVerdict(
            reading.machine_id, True, band, "; ".join(reasons),
            self._priority(band, rise),
            alert=self._to_alert(reading, band, rise, st.baseline),
        )

    def check_dropouts(self, tick: int) -> list[TriageVerdict]:
        """Machines that were reporting and have gone quiet.

        A feed dying on an elevated machine is a wake condition: abstain loudly rather
        than fall silent with it."""
        out = []
        for machine_id, st in self._state.items():
            if st.last_seen_tick < 0 or tick - st.last_seen_tick < MISSING_FEED_TICKS:
                continue
            if st.dropout_reported:
                continue                    # one report per outage, not one per tick
            last_vib = st.history[-1][1] if st.history else 0.0
            band = severity_band(last_vib, 0.0)
            if band in (Band.NORMAL, Band.ELEVATED):
                continue                    # a healthy machine going quiet is an IT ticket
            if band is Band.WARNING and self._in_cooldown(st, tick):
                continue
            # A dropout on a critical machine is new information, not a repeat, so it
            # skips the cooldown. dropout_reported is what stops it firing every tick.
            st.dropout_reported = True
            st.last_wake_tick = tick
            self.woken += 1
            out.append(TriageVerdict(
                machine_id, True, Band.CRITICAL,
                f"telemetry feed silent for {tick - st.last_seen_tick} ticks while the "
                f"machine was above threshold",
                priority=0.99,
                alert={
                    "alert_id": f"ALT-DROP-{machine_id}-{tick}",
                    "machine_id": machine_id, "plant_id": st.plant_id,
                    "sensor": "vibration", "value": round(last_vib, 2),
                    "unit": "mm/s_RMS", "threshold": VIB_CRITICAL,
                    "trend": "feed_lost", "production_impact_per_day_eur": 180000,
                    "triage_reason": "telemetry dropout on a machine above threshold",
                    "suggested_mode": "escalation",
                },
            ))
        return out

    # --- load and sensor-fault checks -------------------------------------- #
    @staticmethod
    def _temp_flat(st: _MachineState, reading) -> bool:
        return (reading.bearing_temp < TEMP_WARNING
                and reading.bearing_temp - st.temp_baseline < TEMP_FLAT_C)

    @staticmethod
    def _current_normal(st: _MachineState, reading) -> bool:
        ratio = reading.spindle_current / st.current_baseline if st.current_baseline else 1.0
        return 1 / LOAD_RISE < ratio < LOAD_RISE

    def _load_check(self, st: _MachineState, reading) -> tuple[float, float | None]:
        """Vibration divided by spindle load when current is up and temperature is flat.
        Returns (vibration to band on, load factor or None). The trip band is never
        normalised away: past 11 mm/s the spindle stops whatever the cause."""
        if not st.current_baseline or reading.vibration > VIB_TRIP:
            return reading.vibration, None
        load = reading.spindle_current / st.current_baseline
        if load < LOAD_RISE or not self._temp_flat(st, reading):
            return reading.vibration, None
        return reading.vibration / load, load

    @staticmethod
    def _update_baselines(st: _MachineState, reading, band: Band) -> None:
        """Current and temperature baselines learn from normal running only: not under a
        heavier cut, not idle after a failure, not while a bearing degrades."""
        if band is not Band.NORMAL or not TriageGate._current_normal(st, reading):
            return
        st.current_baseline += BASELINE_ALPHA * (reading.spindle_current - st.current_baseline)
        st.temp_baseline += BASELINE_ALPHA * (reading.bearing_temp - st.temp_baseline)

    def _sensor_fault(self, st: _MachineState, reading) -> str | None:
        """'rail', 'flatline' or 'pinned' when the vibration channel looks broken and the
        other two channels say the machine is fine (tms-705#S6). None otherwise."""
        v, prev = reading.vibration, st.last_raw_vib
        st.same_count = st.same_count + 1 if prev is not None and v == prev else 1
        if st.fault_value is not None and v != st.fault_value:
            st.fault_value = None            # the channel moved again
        if not (self._temp_flat(st, reading) and self._current_normal(st, reading)):
            st.fault_value = None            # another channel agrees something is wrong
            return None
        if st.fault_value is not None:
            return "pinned"                  # still on the value it faulted at
        if prev and v > VIB_TRIP and v >= prev * RAIL_STEP_FACTOR:
            st.fault_value = v
            return "rail"
        if st.same_count >= FLATLINE_TICKS:
            st.fault_value = v
            return "flatline"
        return None

    def _instrumentation_verdict(self, st: _MachineState, reading, fault: str) -> TriageVerdict:
        # tms-705#S7: the machine stays in the band of its last valid reading.
        last_valid = st.history[-1][1] if st.history else st.baseline
        band = severity_band(last_valid, reading.bearing_temp)
        case = None
        if fault != "pinned":                # one case per fault, not one per tick
            case = {
                "case_id": f"INS-{reading.machine_id}-{reading.tick}",
                "machine_id": reading.machine_id, "plant_id": reading.plant_id,
                "sensor": "vibration", "value": round(reading.vibration, 2), "fault": fault,
                "timestamp": reading.timestamp,
                "bearing_temp_c": round(reading.bearing_temp, 1),
                "spindle_current_a": round(reading.spindle_current, 2),
                "route": "instrumentation",
                "source": "tms-705-telemetry-data-quality-and-abstention#S6",
            }
            self.instrumentation_cases.append(case)
        what = {"rail": "stepped onto a rail value", "flatline": "flatlined exactly",
                "pinned": "still pinned"}[fault]
        return TriageVerdict(
            reading.machine_id, False, band,
            f"suspected sensor fault: vibration {what} at {reading.vibration:.2f} mm/s while "
            f"temperature and current stay normal; raised against the instrumentation "
            f"(tms-705-telemetry-data-quality-and-abstention#S6)",
            self._priority(band, 1.0), instrumentation_case=case,
        )

    def _in_cooldown(self, st: _MachineState, tick: int) -> bool:
        return st.last_wake_tick is not None and (tick - st.last_wake_tick) < self.cooldown_ticks

    @staticmethod
    def _priority(band: Band, rise: float) -> float:
        base = {Band.NORMAL: 0.05, Band.ELEVATED: 0.2, Band.WARNING: 0.45,
                Band.CRITICAL: 0.85, Band.TRIP: 0.98}[band]
        return round(min(0.99, base + max(0.0, rise - 1.0) * 0.08), 3)

    @staticmethod
    def _to_alert(reading, band: Band, rise: float, baseline: float | None) -> dict:
        """Shape the reading into the alert dict the graph already takes, so a
        stream-triggered run is identical to a manually triggered one."""
        return {
            "alert_id": f"ALT-{reading.machine_id}-{reading.tick}",
            "machine_id": reading.machine_id,
            "plant_id": reading.plant_id,
            "sensor": "vibration",
            "value": round(reading.vibration, 2),
            "unit": "mm/s_RMS",
            "threshold": VIB_CRITICAL,
            "trend": "rising" if rise > 1.05 else "stable",
            "baseline": round(baseline, 2) if baseline else None,
            "trend_window": "6h",
            "timestamp": reading.timestamp,
            "bearing_temp_c": round(reading.bearing_temp, 1),
            # Current is what tells a heavier cut from a bearing defect (tms-101#S2).
            "spindle_current_a": round(reading.spindle_current, 2),
            "production_impact_per_day_eur": 180000,
            "triage_band": band.value,
        }

    def stats(self) -> dict:
        return {
            "readings_seen": self.seen,
            "runs_triggered": self.woken,
            "suppressed_by_cooldown": self.suppressed,
            "explained_by_load": self.load_explained,
            "instrumentation_cases": len(self.instrumentation_cases),
            "wake_rate": round(self.woken / self.seen, 5) if self.seen else None,
        }
