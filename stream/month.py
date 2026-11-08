"""
One simulated month of plant telemetry, with answers known in advance.

    python -m stream.month                    # replay the month through triage, score it
    python -m stream.month --export m.jsonl   # also write every labelled reading
    python -m stream.month --live --max-runs 3   # run the agents on the key wakes (tokens)

The scenario (data/sim_month/scenario.json) scripts seven events into a month of healthy
noise across the four CNC machining centres. Each event comes with its answer: when the
bearing really fails, and whether waking the agents is right. The answers come from the
reference corpus, so this checks the code against the plant's written knowledge.

Why it matters: the CNC life estimate is a declared rule with no run-to-failure data
behind it (decision 008). Here every failure has a known time, so for the first time each
estimate can be marked inside, optimistic or conservative.

Open loop on purpose. Nobody repairs a bearing because the agents said so, which is what
keeps each failure time a fixed answer.
"""
from __future__ import annotations

import argparse
import json
import math
import random
import sys
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from stream.simulator import ASSETS, MINUTES_PER_TICK, Reading, _stable_offset  # noqa: E402
from stream.triage import VIB_CRITICAL, VIB_TRIP, TriageGate, TriageVerdict  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
SCENARIO = ROOT / "data" / "sim_month" / "scenario.json"
RESULTS = ROOT / "eval" / "results"
CASES = ROOT / "eval" / "cases" / "sim_month_cases.json"

TICKS_PER_HOUR = 60 // MINUTES_PER_TICK
BASE_CURRENT_A = 12.0        # the recorded CNC-07 fixture runs at about 12 A
TEMP_PER_MM_S = 3.2          # bearing temp rise per mm/s of excess vibration (lags, tms-310#S2)
AMBIENT_C = 30.0
IDLE_VIB, IDLE_CURRENT_A = 0.25, 0.8
COOL_DOWN_H = 2.0            # how fast a stopped spindle cools toward ambient

try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass


def _parse(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def load_scenario(path: Path = SCENARIO) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


@dataclass
class Machine:
    machine_id: str
    plant_id: str
    baseline_vib: float
    baseline_temp: float


def fleet() -> list[Machine]:
    """The CNC machining centres from the asset profiles, with the same per-machine
    baselines the short simulator uses."""
    assets = json.loads(ASSETS.read_text(encoding="utf-8"))
    return [Machine(mid, a.get("plant_id", "LEI"),
                    2.6 + _stable_offset(mid, 7) / 10, 52.0 + _stable_offset(mid, 9))
            for mid, a in assets.items() if a.get("asset_class") == "cnc_machining_center"]


class MonthSimulator:
    """Seeded month of readings. `truth` holds the computed answer for every event."""

    def __init__(self, scenario: dict, machines: list[Machine] | None = None):
        self.scenario = scenario
        self.start = _parse(scenario["start"])
        self.ticks = int(scenario["days"]) * 24 * TICKS_PER_HOUR
        self.machines = machines or fleet()
        self._by_id = {m.machine_id: m for m in self.machines}
        self._rng = random.Random(scenario.get("seed", 11))
        self.truth = {e["id"]: self._truth(e) for e in scenario["events"]}
        self._last_temp: dict[str, float] = {}   # so a stopped spindle cools from where it was
        self.samples: dict[str, dict[int, Reading]] = {}   # what was reported, by tick

    # --- timing ----------------------------------------------------------- #
    def hours(self, ts: str) -> float:
        return (_parse(ts) - self.start).total_seconds() / 3600

    def at(self, hours: float) -> str:
        return (self.start + timedelta(hours=hours)).isoformat()

    def _truth(self, e: dict) -> dict:
        """Event timeline in hours from the start of the month, plus the window a wake
        has to fall in to count as being about this event."""
        m = self._by_id[e["machine_id"]]
        kind = e["kind"]
        if kind == "bearing":
            crit = self.hours(e["critical_at"])
            onset = crit - e["doubling_h"] * math.log2(VIB_CRITICAL / m.baseline_vib)
            fail = crit + e["failure_window_h"]
            back = fail + e["repair_downtime_h"]
            t = {"onset_h": onset, "critical_h": crit, "failure_h": fail, "back_h": back,
                 "window": (onset, back)}
            if "dropout_after_critical_h" in e:
                d0 = crit + e["dropout_after_critical_h"]
                t["dropout"] = (d0, d0 + e["dropout_duration_h"])
            return t
        if kind == "heavy_cut":
            s = self.hours(e["start_at"])
            return {"window": (s, s + 2 * e["ramp_h"] + e["hold_h"])}
        if kind == "dropout":
            s = self.hours(e["start_at"])
            return {"dropout": (s, s + e["duration_h"]),
                    "window": (s, s + e["duration_h"] + 0.5)}
        if kind == "sensor_rail":
            s = self.hours(e["start_at"])
            return {"window": (s, s + (e["ticks"] + 1) / TICKS_PER_HOUR)}
        if kind == "slow_drift":
            return {"window": (0.0, self.ticks / TICKS_PER_HOUR)}
        raise ValueError(f"unknown event kind {kind!r}")

    def _events(self, machine_id: str) -> list[dict]:
        return [e for e in self.scenario["events"] if e["machine_id"] == machine_id]

    # --- physics ---------------------------------------------------------- #
    def _signal(self, m: Machine, h: float) -> dict:
        """Noise-free state of one machine at hour h, and what is true about it."""
        base = m.baseline_vib
        sig = {"vib": base, "temp_extra": 0.0, "current_x": 1.0, "label": "healthy",
               "reporting": True, "stopped": False}
        events = self._events(m.machine_id)

        for e in events:                       # slow wear moves the healthy level itself
            if e["kind"] == "slow_drift":
                sig["vib"] = base * (1 + e["weekly_growth"]) ** (h / 168)
                sig["label"] = "slow_drift"

        for e in events:
            t = self.truth[e["id"]]
            if e["kind"] == "bearing" and t["onset_h"] <= h < t["back_h"]:
                if h >= t["failure_h"]:
                    sig.update(stopped=True, since_fail_h=h - t["failure_h"],
                               label="stopped_after_failure")
                elif h >= t["critical_h"]:
                    frac = (h - t["critical_h"]) / e["failure_window_h"]
                    sig.update(vib=VIB_CRITICAL * (VIB_TRIP / VIB_CRITICAL) ** frac,
                               label="bearing_critical")
                else:
                    sig.update(vib=base * 2 ** ((h - t["onset_h"]) / e["doubling_h"]),
                               label="bearing_degrading")
            elif e["kind"] == "heavy_cut":
                s, end = t["window"]
                if s <= h < end:
                    ramp = e["ramp_h"]
                    w = min(1.0, (h - s) / ramp, max(0.0, (end - h) / ramp)) if ramp else 1.0
                    sig["cut_x"] = 1 + (e["vibration_factor"] - 1) * w
                    sig["current_x"] = 1 + (e["current_factor"] - 1) * w
                    sig["temp_extra"] = 3.0 * w
                    sig["label"] = "heavy_cut"
            elif e["kind"] == "sensor_rail":
                s, end = t["window"]
                if s <= h < s + e["ticks"] / TICKS_PER_HOUR:
                    sig.update(rail=e["rail_value"], label="sensor_rail")

            drop = t.get("dropout")
            if drop and drop[0] <= h < drop[1]:
                sig["reporting"] = False
                sig["label"] += "+feed_lost"
        return sig

    def batch(self, tick: int) -> tuple[list[Reading], dict[str, str]]:
        """Readings for one tick, plus the true state of every machine (reporting or not).
        Call it tick by tick in order: the noise stream and the cooling are sequential."""
        h = tick / TICKS_PER_HOUR
        ts = self.at(h)
        out, labels = [], {}
        for m in self.machines:
            # Three draws per machine every tick, reporting or not, so moving one event
            # never reshuffles the noise anywhere else.
            n_vib, n_temp, n_cur = (self._rng.gauss(0, 0.06), self._rng.gauss(0, 0.5),
                                    self._rng.gauss(0, 0.25))
            sig = self._signal(m, h)
            labels[m.machine_id] = sig["label"]
            if sig["stopped"]:
                t_fail = self._last_temp.get(m.machine_id, m.baseline_temp)
                vib = IDLE_VIB * (1 + n_vib)
                temp = (AMBIENT_C + (t_fail - AMBIENT_C) * math.exp(-sig["since_fail_h"] / COOL_DOWN_H)
                        + n_temp)
                cur = IDLE_CURRENT_A + n_cur * 0.2
            else:
                clean = sig["vib"]
                temp = (m.baseline_temp + max(0.0, clean - 1.4 * m.baseline_vib) * TEMP_PER_MM_S
                        + sig["temp_extra"] + n_temp)
                vib = clean * sig.get("cut_x", 1.0) * (1 + n_vib)
                if "rail" in sig:
                    vib = sig["rail"]          # a pinned channel reads exactly the rail value
                cur = BASE_CURRENT_A * sig["current_x"] + n_cur
                self._last_temp[m.machine_id] = temp
            if sig["reporting"]:
                r = Reading(m.machine_id, m.plant_id, ts, max(vib, 0.05), temp, cur, tick)
                out.append(r)
                self.samples.setdefault(m.machine_id, {})[tick] = r
        return out, labels

    def history(self, machine_id: str, end_tick: int, hours: int = 72) -> dict:
        """The raw samples a run started at `end_tick` would have had, for sensor_query
        (tools/sim_window.py). Only ticks already generated, so nothing from the future."""
        rec = self.samples.get(machine_id, {})
        first = max(0, end_tick - hours * TICKS_PER_HOUR)
        rows = []
        for t in range(first, end_tick + 1):
            r = rec.get(t)
            ts = self.at(t / TICKS_PER_HOUR)
            rows.append({"ts": ts, "missing": True} if r is None else
                        {"ts": ts, "vibration": round(r.vibration, 2),
                         "bearing_temp": round(r.bearing_temp, 1),
                         "spindle_current": round(r.spindle_current, 2)})
        return {"machine_id": machine_id, "interval_min": MINUTES_PER_TICK, "hours": hours,
                "samples": rows}


# --- the plant at a moment, for alert_triage and maintenance_schedule ------- #
_SEVERITY = {"elevated": "info", "warning": "warning", "critical": "critical", "trip": "critical"}


def _triage_view(sim: MonthSimulator, plant: str, tick: int, recent, wake_alert: dict) -> dict:
    """The last 24h at one plant, shaped like data/alerts/alert_stream.json: counts by
    severity, then one entry per machine that reached the warning band, highest first."""
    counts = {"info": 0, "warning": 0, "critical": 0}
    per_machine: dict[str, dict] = {}
    for t, v, r in recent:
        if not any(m.machine_id == v.machine_id and m.plant_id == plant for m in sim.machines):
            continue
        sev = _SEVERITY.get(v.band.value)
        if sev:
            counts[sev] += 1
        if v.band.value not in ("warning", "critical", "trip"):
            continue
        dropout = (v.alert or {}).get("trend") == "feed_lost"
        prev = per_machine.get(v.machine_id)
        first_value = prev["_first"] if prev else (r.vibration if r else None)
        value = round(r.vibration, 2) if r else (v.alert or {}).get("value")
        per_machine[v.machine_id] = {
            "alert_id": f"ALT-{v.machine_id}-{t}", "machine_id": v.machine_id,
            "sensor": "vibration", "value": value, "unit": "mm/s_RMS", "threshold": 6.0,
            "trend": "feed_lost" if dropout else (
                "rising" if first_value and value and value > first_value * 1.05 else "stable"),
            "priority_score": max(v.priority, prev["priority_score"] if prev else 0.0),
            "band": v.band.value, "last_seen": sim.at(t / TICKS_PER_HOUR),
            "reason": v.reason, "_first": first_value,
        }
    mid = wake_alert.get("machine_id")
    if mid in per_machine:                   # same id and trend as the alert that woke the run
        per_machine[mid]["alert_id"] = wake_alert.get("alert_id")
        per_machine[mid]["trend"] = wake_alert.get("trend", per_machine[mid]["trend"])
    ranked = sorted(per_machine.values(), key=lambda a: a["priority_score"], reverse=True)
    for a in ranked:
        a.pop("_first", None)
    return {
        "plant_id": plant,
        "data_timestamp": sim.at(tick / TICKS_PER_HOUR),
        "total_alerts_today": sum(counts.values()),
        "by_severity": counts,
        "deduplicated_critical_count": len(ranked),
        "critical_alerts_ranked": ranked,
        "source": "simulation",
        "note": (f"Simulated month: readings above normal at {plant} over the last 24h, "
                 "deduplicated to one entry per machine."),
    }


def schedule_view(sim: MonthSimulator, hours: float, horizon_days: int = 14) -> dict:
    """Each plant's maintenance calendar seen from `hours` into the month, from the
    weekly windows in the scenario. Open loop: repairs after a failure are not on it."""
    now = sim.start + timedelta(hours=hours)
    out = {}
    for plant, cal in (sim.scenario.get("maintenance_calendar") or {}).items():
        windows = []
        day = now.replace(hour=0, minute=0, second=0, microsecond=0)
        for d in range(horizon_days + 1):
            date = day + timedelta(days=d)
            start = date + timedelta(hours=cal["start_hour"])
            if date.weekday() != cal["weekday"] or start <= now:
                continue
            windows.append({
                "window_id": f"MW-{plant}-{start:%Y-%m-%d}",
                "start": start.isoformat(),
                "end": (start + timedelta(hours=cal["hours"])).isoformat(),
                "duration_hours": cal["hours"], "type": "scheduled_preventive",
                "technicians_available": cal["technicians"], "status": "confirmed"})
        nxt = windows[0] if windows else None
        emergency = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=12)
        out[plant] = {
            "plant_id": plant, "plant_name": cal["plant_name"],
            "existing_windows": windows,
            "next_available_slot": nxt and {
                "window_id": nxt["window_id"], "start": nxt["start"],
                "days_from_now": round((_parse(nxt["start"]) - now).total_seconds() / 86400, 1)},
            "emergency_window_slots": [{
                "earliest_possible": emergency.isoformat(), "duration_available_hours": 8,
                "technicians_available": cal["technicians"][:2], "requires_approval": True,
                "approval_authority": "plant_manager"}],
            "data_timestamp": now.isoformat(),
            "source": "simulation",
        }
    return out


# --- replay and scoring --------------------------------------------------- #
def replay(sim: MonthSimulator, gate: TriageGate | None = None,
           export: Path | None = None) -> tuple[list[dict], TriageGate]:
    """Run the whole month through the wake gate. Returns every wake."""
    gate = gate or TriageGate()
    wakes = []
    recent: deque = deque()                 # (tick, verdict, reading) over the last 24h
    fh = open(export, "w", encoding="utf-8") if export else None
    try:
        for tick in range(sim.ticks):
            batch, labels = sim.batch(tick)
            if fh:
                seen = {r.machine_id for r in batch}
                for r in batch:
                    fh.write(json.dumps({**r.to_dict(), "spindle_current": round(r.spindle_current, 2),
                                         "truth": labels[r.machine_id]}) + "\n")
                for mid in labels.keys() - seen:
                    fh.write(json.dumps({"machine_id": mid, "timestamp": sim.at(tick / TICKS_PER_HOUR),
                                         "tick": tick, "missing": True,
                                         "truth": labels[mid]}) + "\n")
            by_id = {r.machine_id: r for r in batch}
            verdicts = [gate.observe(r) for r in batch] + gate.check_dropouts(tick)
            for v in verdicts:
                r = by_id.get(v.machine_id)
                recent.append((tick, v, r))
            while recent and recent[0][0] <= tick - 24 * TICKS_PER_HOUR:
                recent.popleft()
            for v in verdicts:
                if not v.wake:
                    continue
                r = by_id.get(v.machine_id)
                dropout = (v.alert or {}).get("trend") == "feed_lost"
                alert = dict(v.alert or {})
                alert.setdefault("timestamp", sim.at(tick / TICKS_PER_HOUR))
                wakes.append({
                    "tick": tick, "hours": tick / TICKS_PER_HOUR, "at": alert["timestamp"],
                    "machine_id": v.machine_id, "band": v.band.value, "reason": v.reason,
                    "kind": "dropout" if dropout else "reading",
                    "vibration": round(r.vibration, 2) if r and not dropout else alert.get("value"),
                    "bearing_temp": round(r.bearing_temp, 1) if r and not dropout else None,
                    "verdict": TriageVerdict(v.machine_id, True, v.band, v.reason, v.priority,
                                             alert=alert),
                    # What alert_triage would have shown at this moment, per plant.
                    "triage_view": {p: _triage_view(sim, p, tick, recent, alert)
                                    for p in sorted({m.plant_id for m in sim.machines})},
                })
    finally:
        if fh:
            fh.close()
    return wakes, gate


def attribute(sim: MonthSimulator, wake: dict) -> str | None:
    """The event a wake is about: the narrowest event window on that machine that
    contains it. None means the gate woke on healthy noise."""
    best, width = None, math.inf
    for e in sim.scenario["events"]:
        if e["machine_id"] != wake["machine_id"]:
            continue
        lo, hi = sim.truth[e["id"]]["window"]
        if lo <= wake["hours"] <= hi and hi - lo < width:
            best, width = e["id"], hi - lo
    return best


def series(sim: MonthSimulator, machine_id: str, end_tick: int, hours: int = 72) -> dict:
    """The trailing window as rul_predictor's optional `series` input (sensor_query shape)."""
    rows = [r for r in sim.history(machine_id, end_tick, hours)["samples"] if not r.get("missing")]
    return {k: [{"ts": r["ts"], "v": r[k]} for r in rows] for k in ("vibration", "spindle_current")}


def _life_check(sim: MonthSimulator, machine_id: str, wake: dict, failure_h: float) -> dict:
    """Score the CNC life estimate at a wake against the known failure time."""
    from tools.rul_predictor import rul_predictor

    est = rul_predictor(machine_id, {"vibration": wake["vibration"],
                                     "bearing_temp": wake["bearing_temp"],
                                     "series": series(sim, machine_id, wake["tick"])})
    lo, hi = est["rul"]["min"], est["rul"]["max"]
    truth = round(failure_h - wake["hours"], 1)
    verdict = "inside" if lo <= truth <= hi else ("optimistic" if truth < lo else "conservative")
    return {"at": wake["at"], "vibration": wake["vibration"], "bearing_temp": wake["bearing_temp"],
            "predicted_h": [lo, hi], "true_h_left": truth, "verdict": verdict,
            "source": est.get("source"), "basis": est.get("estimate_basis"),
            "doubling_h": (est.get("trend") or {}).get("doubling_h")}


def score(sim: MonthSimulator, wakes: list[dict]) -> dict:
    by_event: dict[str | None, list[dict]] = {}
    for w in wakes:
        w["event"] = attribute(sim, w)
        by_event.setdefault(w["event"], []).append(w)

    events = []
    for e in sim.scenario["events"]:
        exp, t = e["expected"], sim.truth[e["id"]]
        mine = by_event.get(e["id"], [])
        row = {"id": e["id"], "machine_id": e["machine_id"], "kind": e["kind"],
               "title": e["title"], "expected_wake": exp["wake"], "wakes": len(mine),
               "source": exp["source"], "why": exp["why"]}
        if e["kind"] == "bearing":
            before = [w for w in mine if w["hours"] < t["failure_h"]]
            first = before[0] if before else None
            row.update(failure_at=sim.at(t["failure_h"]), critical_at=e["critical_at"],
                       true_window_h=e["failure_window_h"],
                       first_wake_at=first["at"] if first else None,
                       lead_h=round(t["failure_h"] - first["hours"], 1) if first else None,
                       life=[_life_check(sim, e["machine_id"], w, t["failure_h"])
                             for w in before if w["kind"] == "reading"])
            ok = bool(first)
            if exp.get("dropout_wake"):
                row["dropout_wake"] = any(w["kind"] == "dropout" for w in mine)
                ok = ok and row["dropout_wake"]
            # The month's answers must agree with the corpus range they cite.
            lo, hi = exp["failure_window_range_h"]
            row["truth_matches_corpus"] = lo <= e["failure_window_h"] <= hi
        else:
            ok = not mine
            row["first_wake_at"] = mine[0]["at"] if mine else None
            row["first_reason"] = mine[0]["reason"] if mine else None
        row["pass"] = ok
        events.append(row)

    life = [c for r in events for c in r.get("life", [])]
    firsts = [r["life"][0] for r in events if r.get("life")]
    noise = by_event.get(None, [])

    # Quiet days: no scripted event anywhere in the fleet (the month-long slow drift
    # should raise nothing either, so it does not make a day busy). They must stay silent.
    busy = [sim.truth[e["id"]]["window"] for e in sim.scenario["events"]
            if e["kind"] != "slow_drift"]
    quiet = [d for d in range(sim.scenario["days"])
             if not any(lo < (d + 1) * 24 and hi > d * 24 for lo, hi in busy)]
    quiet_wakes = [w for w in wakes if int(w["hours"] // 24) in quiet]
    return {
        "scenario": {"start": sim.scenario["start"], "days": sim.scenario["days"],
                     "seed": sim.scenario.get("seed"), "machines": len(sim.machines),
                     "ticks": sim.ticks},
        "events": events,
        "answers_right": sum(r["pass"] for r in events),
        "answers_total": len(events),
        "wakes_total": len(wakes),
        "wakes_on_noise": len(noise),
        "quiet_days": [sim.at(d * 24)[:10] for d in quiet],
        "wakes_on_quiet_days": len(quiet_wakes),
        "maintenance_resets": [{"machine_id": e["machine_id"], "event": e["id"],
                                "back_in_service": sim.at(sim.truth[e["id"]]["back_h"])}
                               for e in sim.scenario["events"] if e["kind"] == "bearing"],
        "life_checks": len(life),
        "life_inside": sum(c["verdict"] == "inside" for c in life),
        "life_optimistic": sum(c["verdict"] == "optimistic" for c in life),
        "life_conservative": sum(c["verdict"] == "conservative" for c in life),
        "first_estimates": {r["id"]: r["life"][0]["verdict"] for r in events if r.get("life")},
        "first_inside": sum(c["verdict"] == "inside" for c in firsts),
    }


def cases(sim: MonthSimulator, wakes: list[dict]) -> dict:
    """Every wake as a labelled case: the alert, the true hours left, and the risk the
    corpus says is right. eval/sim_month_eval.py scores these offline."""
    events = {e["id"]: e for e in sim.scenario["events"]}
    out, seen = [], {}
    for w in wakes:
        eid = w.get("event") or attribute(sim, w)
        exp = events[eid]["expected"] if eid in events else {}
        seen[eid] = seen.get(eid, 0) + 1
        dropout = w["kind"] == "dropout"
        fail = sim.truth.get(eid, {}).get("failure_h")
        readings = {"vibration": w["vibration"]}
        if w["bearing_temp"] is not None:
            readings["bearing_temp"] = w["bearing_temp"]
        key = "dropout_risk" if dropout and "dropout_risk" in exp else "risk"
        out.append({
            "id": f"SM-{(eid or 'NOISE').split('-')[0]}-{seen[eid]:02d}",
            "event": eid, "machine_id": w["machine_id"], "at": w["at"], "wake_kind": w["kind"],
            "alert": w["verdict"].alert,
            "readings": readings,
            "telemetry_status": "INTERRUPTED" if dropout else "OK",
            "true_hours_to_failure": (round(fail - w["hours"], 1)
                                      if fail is not None and w["hours"] < fail else None),
            "expected": {"risk": exp.get(key, "LOW"),
                         "source": exp.get(f"{key}_source", exp.get("source"))},
            "history_ref": {"machine_id": w["machine_id"], "end_tick": w["tick"], "hours": 72},
        })
    return {
        "dataset": "tos-sim-month-cases",
        "version": "1.0",
        "generated_by": "python -m stream.month --write-cases",
        "description": ("Every wake in the simulated month as a labelled case. The true hours "
                        "to failure come from the simulator; the expected risk comes from the "
                        "corpus section cited on each case. history_ref rebuilds the 72h "
                        "window the run would have had (MonthSimulator.history)."),
        "limits": ("Simulated. These check the code against the simulator's physics, which "
                   "follows the corpus rule of thumb. They are not real bearing failures."),
        "cases": out,
    }


# --- live runs ------------------------------------------------------------ #
def pick_live(sim: MonthSimulator, wakes: list[dict], limit: int) -> list[dict]:
    """The wakes worth spending tokens on: the first per event, real events before
    false alarms. Repeat wakes for the same event teach nothing new."""
    first = {}
    for w in wakes:
        first.setdefault(w.get("event") or attribute(sim, w), w)
    expected = {e["id"]: e["expected"]["wake"] for e in sim.scenario["events"]}
    order = sorted(first.items(), key=lambda kv: (not expected.get(kv[0], False), kv[1]["tick"]))
    picked = [w for _, w in order][:limit]
    # A dropout wake is its own answer (abstain); include it if there is room.
    for w in wakes:
        if w["kind"] == "dropout" and w not in picked and len(picked) < limit:
            picked.append(w)
    return picked


def plant_view(sim: MonthSimulator, wake: dict) -> dict:
    """Triage and calendar at the wake, so every tool in the run sees the same plant."""
    return {"triage": wake["triage_view"], "schedule": schedule_view(sim, wake["hours"])}


def run_live(sim: MonthSimulator, wakes: list[dict], limit: int, decision: str) -> list[dict]:
    from stream.run import trigger_run

    out = []
    for w in pick_live(sim, wakes, limit):
        alert = w["verdict"].alert
        print(f"  live run: {w['event'] or 'noise'} at {w['at']} ({w['machine_id']})")
        res = trigger_run(w["verdict"], live=True, auto_decision=decision,
                          history=sim.history(w["machine_id"], w["tick"]),
                          plant_view=plant_view(sim, w))
        out.append({"event": w["event"], "at": w["at"], "machine_id": w["machine_id"],
                    "mode": alert.get("suggested_mode", "happy"),
                    **{k: res.get(k) for k in ("run_id", "status", "risk", "reached_gate")},
                    "tokens": (res.get("usage") or {}).get("total_tokens")})
    return out


# --- report --------------------------------------------------------------- #
def _hm(ts: str | None) -> str:
    return _parse(ts).strftime("%a %d %b %H:%M") if ts else "none"


def render(result: dict, live: list[dict] | None = None, live_note: str = "") -> str:
    s = result["scenario"]
    L = ["# One simulated month: scored against known answers", "",
         f"Generated by `python -m stream.month`. {s['days']} days from {s['start'][:10]}, "
         f"{s['machines']} CNC machining centres, a reading every {MINUTES_PER_TICK} minutes "
         f"(seed {s['seed']}). The answers come from `data/sim_month/scenario.json`, which "
         "takes each one from the reference corpus before anything runs.", "",
         "## Headline", "",
         f"- Wake decisions right: **{result['answers_right']} of {result['answers_total']}** events.",
         f"- Wakes in the month: {result['wakes_total']}, of which {result['wakes_on_noise']} "
         "on healthy noise.",
         f"- CNC life estimates checked against the true failure time: {result['life_checks']}. "
         f"Inside the predicted range: {result['life_inside']}. Optimistic (more life "
         f"promised than was left): {result['life_optimistic']}. Conservative: "
         f"{result['life_conservative']}.",
         f"- Quiet days (no scripted event anywhere): {len(result['quiet_days'])}. "
         f"Wakes on them: {result['wakes_on_quiet_days']}.",
         "- Maintenance resets: " + "; ".join(
             f"{x['machine_id']} back in service {_hm(x['back_in_service'])}"
             for x in result["maintenance_resets"]) + ".", "",
         "## Events", "",
         "| Event | Machine | Should wake | Woke | First wake | Right? | Source |",
         "|---|---|---|---|---|---|---|"]
    for r in result["events"]:
        extra = ""
        if r["kind"] == "bearing":
            extra = f", {r['lead_h']}h before failure" if r["lead_h"] is not None else ""
            if "dropout_wake" in r:
                extra += f"; feed-loss wake: {'yes' if r['dropout_wake'] else 'no'}"
        L.append(f"| {r['id']} | {r['machine_id']} | {'yes' if r['expected_wake'] else 'no'} | "
                 f"{r['wakes']} | {_hm(r['first_wake_at'])}{extra} | "
                 f"{'yes' if r['pass'] else '**no**'} | `{r['source']}` |")
    L += ["", "Several wakes per real event are expected: the gate re-wakes a machine every "
          "12 hours while it stays critical (the cooldown in `stream/triage.py`).", ""]

    wrong = [r for r in result["events"] if not r["pass"]]
    if wrong:
        L += ["### Where the gate disagrees with the corpus", ""]
        for r in wrong:
            got = (f"it woke ({r.get('first_reason')})" if r["wakes"] else "it did not wake")
            L.append(f"- **{r['id']}**: {r['why']} But {got}. See `{r['source']}`.")
        L.append("")

    L += ["## CNC life estimate vs the true failure time", "",
          "The CNC estimate is a declared rule (`source: declared_thresholds`), never "
          "backtested, because no public run-to-failure data exists for this asset. Here "
          "every failure time is known, so each estimate can be marked.", "",
          "| Event | Wake | Vibration | Temp | Doubling (h) | Predicted hours left | True hours left | Verdict |",
          "|---|---|---|---|---|---|---|---|"]
    for r in result["events"]:
        for c in r.get("life", []):
            lo, hi = c["predicted_h"]
            rate = c.get("doubling_h") if c.get("basis") == "vibration_rate" else None
            L.append(f"| {r['id']} | {_hm(c['at'])} | {c['vibration']} | {c['bearing_temp']} | "
                     f"{rate if rate is not None else 'level rule'} | "
                     f"{lo} to {hi} | {c['true_h_left']} | {c['verdict']} |")
    L += ["", "What the table shows: the rule reads the *rate* (tms-101#S4). The doubling "
          "time over the trailing 72 hours picks the corpus window, less the hours already "
          "spent in Critical. Where the Critical crossing is older than the window, only an "
          "upper bound is known and the range opens to 0.", "",
          "This check is circular. The simulator writes each failure from the same S4 rule, "
          "so a high count says the code follows the corpus, not that it predicts real "
          "bearings. See F-13 in `eval/FINDINGS.md`.", ""]

    if live is not None:
        L += ["## Live agent runs", ""]
        if not live:
            L.append("No runs were started.")
        else:
            L += ["| Event | Wake | Mode | Status | Risk | Reached approval | Tokens |",
                  "|---|---|---|---|---|---|---|"]
            for x in live:
                L.append(f"| {x['event'] or 'noise'} | {_hm(x['at'])} | {x['mode']} | "
                         f"{x['status']} | {x['risk']} | {x['reached_gate']} | {x['tokens']} |")
        L += ["", live_note] if live_note else []
        L.append("")

    L += ["## Limits", "",
          "- Simulated, not measured. The failure windows follow the corpus rule of thumb, "
          "so this checks the code against the plant's own documents, not against real "
          "bearings.",
          "- Open loop: nothing the agents recommend changes the telemetry.",
          "- One seed. The events are scripted; the noise around them is random but fixed.", ""]
    return "\n".join(L)


def _strip(result: dict) -> dict:
    return json.loads(json.dumps(result, default=lambda o: None))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Replay a simulated month and score it.")
    ap.add_argument("--scenario", type=Path, default=SCENARIO)
    ap.add_argument("--export", type=Path, default=None,
                    help="write every labelled reading as JSON lines")
    ap.add_argument("--out", type=Path, default=RESULTS / "sim_month.md")
    ap.add_argument("--live", action="store_true", help="run the agents on key wakes (tokens)")
    ap.add_argument("--max-runs", type=int, default=3)
    ap.add_argument("--decision", default="reject", choices=["approve", "reject"])
    ap.add_argument("--write-cases", action="store_true",
                    help=f"regenerate {CASES.relative_to(ROOT)} from the month")
    args = ap.parse_args(argv)

    sim = MonthSimulator(load_scenario(args.scenario))
    wakes, gate = replay(sim, export=args.export)
    result = score(sim, wakes)
    live = run_live(sim, wakes, args.max_runs, args.decision) if args.live else None

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(render(result, live), encoding="utf-8")
    payload = {**result, "gate": gate.stats(),
               "wakes": [{k: v for k, v in w.items() if k not in ("verdict", "triage_view")}
                         for w in wakes]}
    if live is not None:
        payload["live"] = live
    args.out.with_suffix(".json").write_text(json.dumps(_strip(payload), indent=1),
                                             encoding="utf-8")

    sc = result["scenario"]
    print(f"month: {sc['days']} days from {sc['start'][:10]}, {sc['machines']} machines | "
          f"readings {gate.seen} | wakes {len(wakes)} "
          f"({result['wakes_on_noise']} on noise)")
    for r in result["events"]:
        print(f"  {'ok ' if r['pass'] else 'NO '} {r['id']:<28} woke {r['wakes']:>2}x  "
              f"first {_hm(r['first_wake_at'])}")
    print(f"life estimates: {result['life_inside']} inside, {result['life_optimistic']} "
          f"optimistic, {result['life_conservative']} conservative (of {result['life_checks']})")
    if args.write_cases:
        CASES.write_text(json.dumps(cases(sim, wakes), indent=1) + "\n", encoding="utf-8")
        print(f"wrote {CASES.relative_to(ROOT)}")
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
