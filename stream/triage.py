"""
The wake gate: decide whether a reading is worth running six agents over.

This is the cheap, deterministic layer between a continuous sensor stream and an
expensive multi-agent run. It answers three questions in order:

  1. Is this reading past a documented severity band? (tms-101-spindle-bearing-maintenance#S3)
  2. Is it a genuine change, or has this machine always read like this?
     (tms-204-vibration-severity-limits#S4: change beats absolute level)
  3. Have we already woken the team for this machine recently?

Only a yes-yes-no starts a run. The third question is the one people forget: a degrading
machine stays over threshold for hours, so without a cooldown one event becomes a run
every tick and the token bill is the same shape as the alert noise problem the project
exists to solve.

A telemetry dropout is treated as a wake condition in its own right, not as silence. A
sensor that stops reporting on a machine that was trending upward is exactly the case the
abstention path exists for (tms-705-telemetry-data-quality-and-abstention#S6).
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
    history: list[tuple[int, float]] = field(default_factory=list)   # (tick, vibration)
    last_seen_tick: int = -1
    last_wake_tick: int | None = None
    baseline: float | None = None
    dropout_reported: bool = False


@dataclass
class TriageGate:
    """Stateful per-machine triage over a reading stream."""

    cooldown_ticks: int = COOLDOWN_TICKS
    trend_factor: float = TREND_FACTOR
    seen: int = 0
    woken: int = 0
    suppressed: int = 0
    _state: dict[str, _MachineState] = field(default_factory=dict, repr=False)

    def _machine(self, machine_id: str) -> _MachineState:
        return self._state.setdefault(machine_id, _MachineState())

    def observe(self, reading) -> TriageVerdict:
        """Score one reading and decide whether to wake the agent team."""
        self.seen += 1
        st = self._machine(reading.machine_id)
        st.last_seen_tick = reading.tick
        st.dropout_reported = False          # the feed is back
        st.history.append((reading.tick, reading.vibration))
        st.history = st.history[-(TREND_WINDOW_TICKS + 1):]
        if st.baseline is None:
            st.baseline = reading.vibration        # first clean reading is the reference

        band = severity_band(reading.vibration, reading.bearing_temp)
        window_start = next((v for t, v in st.history
                             if t >= reading.tick - TREND_WINDOW_TICKS), reading.vibration)
        rise = reading.vibration / window_start if window_start else 1.0

        reasons = []
        if band in (Band.CRITICAL, Band.TRIP):
            reasons.append(f"{band.value} band ({reading.vibration:.1f} mm/s, "
                           f"{reading.bearing_temp:.0f} C)")
        if rise >= self.trend_factor and band not in (Band.NORMAL, Band.ELEVATED):
            reasons.append(f"vibration up {rise:.1f}x over the trend window")

        if not reasons:
            return TriageVerdict(reading.machine_id, False, band,
                                 "below the wake threshold", self._priority(band, rise))

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

        A feed that stops on a machine that was already elevated is a wake condition: the
        system should abstain loudly rather than fall silent with it."""
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
            # A feed that dies on a machine already in the critical band is new
            # information, not a repeat of the alert that woke us, so it is exempt from
            # the cooldown. The dropout_reported flag is what stops it repeating instead.
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
                    "machine_id": machine_id, "plant_id": "LEI",
                    "sensor": "vibration", "value": round(last_vib, 2),
                    "unit": "mm/s_RMS", "threshold": VIB_CRITICAL,
                    "trend": "feed_lost", "production_impact_per_day_eur": 180000,
                    "triage_reason": "telemetry dropout on a machine above threshold",
                    "suggested_mode": "escalation",
                },
            ))
        return out

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
            "production_impact_per_day_eur": 180000,
            "triage_band": band.value,
        }

    def stats(self) -> dict:
        return {
            "readings_seen": self.seen,
            "runs_triggered": self.woken,
            "suppressed_by_cooldown": self.suppressed,
            "wake_rate": round(self.woken / self.seen, 5) if self.seen else None,
        }
