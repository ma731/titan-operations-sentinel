"""
A seeded fleet sensor simulator.

It emits one reading per machine per tick. Most machines are healthy and produce noise
around a stable baseline. One or more machines are put on a degradation profile so the
stream eventually contains a real event, which is the point: a triage gate that never
sees a true positive proves nothing.

Seeded on purpose. A demo that behaves differently every time cannot be rehearsed, and a
test cannot assert on it.
"""
from __future__ import annotations

import json
import random
import zlib
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

ASSETS = Path(__file__).resolve().parents[1] / "data" / "assets" / "asset_profiles.json"

# One simulated tick represents this much plant time. The loop sleeps for real seconds
# (see run.py --interval), so a 10 minute tick lets a 6 hour degradation play out in
# about half a minute of wall time without changing the physics.
MINUTES_PER_TICK = 10


@dataclass
class Reading:
    machine_id: str
    plant_id: str
    timestamp: str
    vibration: float
    bearing_temp: float
    spindle_current: float
    tick: int

    def to_dict(self) -> dict:
        return {
            "machine_id": self.machine_id, "plant_id": self.plant_id,
            "timestamp": self.timestamp, "tick": self.tick,
            "vibration": round(self.vibration, 3),
            "bearing_temp": round(self.bearing_temp, 2),
            "spindle_current": round(self.spindle_current, 2),
        }


@dataclass
class MachineProfile:
    """How one machine behaves over the run.

    `degradation_per_tick` is the exponential growth rate applied to vibration. A healthy
    machine has 0.0 and just wanders around its baseline. A degrading machine compounds,
    which is what makes the rate-of-change signal that TMS-101 estimates life from."""

    machine_id: str
    plant_id: str = "LEI"
    baseline_vibration: float = 3.0
    baseline_temp: float = 55.0
    baseline_current: float = 42.0
    degradation_per_tick: float = 0.0
    dropout_from_tick: int | None = None      # simulate a telemetry feed failure
    noise: float = 0.08


def _stable_offset(text: str, modulo: int) -> int:
    """A per-machine constant that is the same in every process.

    Python's builtin hash() is randomised per process for strings (PYTHONHASHSEED), so
    using it here would have made the "seeded and deterministic" claim false: every run
    would give each machine a different baseline. crc32 is stable across processes and
    platforms, which is what a reproducible demo and an asserting test both need."""
    return zlib.crc32(text.encode("utf-8")) % modulo


@dataclass
class AlertSimulator:
    """Emits Readings for a fleet. Deterministic for a given seed."""

    profiles: list[MachineProfile]
    seed: int = 7
    tick: int = 0
    start: datetime = field(default_factory=lambda: datetime(2026, 6, 12, 8, 0,
                                                             tzinfo=timezone.utc))
    _rng: random.Random = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._rng = random.Random(self.seed)

    @classmethod
    def from_fleet(cls, degrading: str = "CNC-07-LEI", seed: int = 7,
                   dropout: str | None = None,
                   dropout_tick: int = 26) -> AlertSimulator:
        """Build a fleet from the real asset profiles, with one machine degrading.

        Reading the machine list from data/assets keeps the simulated stream consistent
        with everything else the tools know about the plant, so a triggered run finds a
        real asset rather than an invented id."""
        try:
            assets = json.loads(ASSETS.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001 — a missing profile file must not stop the stream
            assets = {}
        profiles = []
        for mid, a in assets.items():
            if a.get("asset_class") != "cnc_machining_center":
                continue
            profiles.append(MachineProfile(
                machine_id=mid,
                plant_id=a.get("plant_id", "LEI"),
                baseline_vibration=2.6 + _stable_offset(mid, 7) / 10,
                baseline_temp=52.0 + _stable_offset(mid, 9),
                degradation_per_tick=0.035 if mid == degrading else 0.0,
                # Default 26 ticks (about 4.5 hours of plant time) so the feed drops
                # AFTER the machine has climbed above the critical band. A feed that
                # dies while the machine still reads healthy is an instrumentation
                # ticket, not an operations event, and triage treats it as one.
                dropout_from_tick=dropout_tick if mid == dropout else None,
            ))
        if not profiles:
            profiles = [MachineProfile("CNC-07-LEI", degradation_per_tick=0.035)]
        return cls(profiles=profiles, seed=seed)

    def _timestamp(self) -> str:
        return (self.start + timedelta(minutes=MINUTES_PER_TICK * self.tick)).isoformat()

    def next_batch(self) -> list[Reading]:
        """One tick: a reading for every machine that is still reporting."""
        ts = self._timestamp()
        batch = []
        for p in self.profiles:
            if p.dropout_from_tick is not None and self.tick >= p.dropout_from_tick:
                continue                      # the feed has dropped: no reading at all
            growth = (1 + p.degradation_per_tick) ** self.tick
            vib = p.baseline_vibration * growth * (1 + self._rng.gauss(0, p.noise))
            # Temperature lags vibration for a bearing defect (tms-310#S2), so it only
            # starts moving once the vibration has risen meaningfully above baseline.
            excess = max(0.0, vib - p.baseline_vibration * 1.4)
            temp = p.baseline_temp + excess * 6.5 + self._rng.gauss(0, 0.6)
            # Current stays flat on a mechanical defect. That flatness is the signal that
            # distinguishes a defect from a heavier cut (tms-101#S2).
            current = p.baseline_current + self._rng.gauss(0, 0.9)
            batch.append(Reading(p.machine_id, p.plant_id, ts, max(vib, 0.1),
                                 temp, current, self.tick))
        self.tick += 1
        return batch

    def run_for(self, ticks: int) -> list[list[Reading]]:
        return [self.next_batch() for _ in range(ticks)]
