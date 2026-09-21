"""
The continuous loop: watch the stream, wake the agents when it matters.

    python -m stream.run --dry-run            # no model calls: shows what it WOULD run
    python -m stream.run --ticks 60           # simulate 10 hours of plant time
    python -m stream.run --live               # actually invoke the graph on a wake
    python -m stream.run --live --interval 2  # pace it for a live demo

Dry run is the default, deliberately. An autonomous loop that starts spending tokens the
first time somebody runs it is a bad default, and the interesting number (how many
readings produce how many runs) does not need a model to compute.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from stream.simulator import AlertSimulator  # noqa: E402
from stream.triage import TriageGate, TriageVerdict  # noqa: E402

STREAM_LOG = Path(__file__).resolve().parents[1] / "logs" / "stream.jsonl"

try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass


def _log(event: dict) -> None:
    try:
        STREAM_LOG.parent.mkdir(exist_ok=True)
        with open(STREAM_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": datetime.now(timezone.utc).isoformat(), **event}) + "\n")
    except OSError:
        pass


def trigger_run(verdict: TriageVerdict, live: bool, auto_decision: str = "reject") -> dict:
    """Start a graph run for a triaged alert, or describe what would have been started."""
    alert = verdict.alert or {}
    mode = alert.get("suggested_mode", "happy")
    if not live:
        return {"triggered": False, "dry_run": True, "machine_id": verdict.machine_id,
                "mode": mode, "alert_id": alert.get("alert_id")}

    from langgraph.types import Command

    import observability
    from graph import build_graph, make_initial_state

    graph = build_graph()
    state = make_initial_state(mode, alert=alert)
    cfg = {"configurable": {"thread_id": state["run_id"]}, "recursion_limit": 50}

    interrupted = False
    from tools.runtime_inputs import runtime_inputs

    readings = {"vibration": alert.get("value", 0)}
    if "bearing_temp_c" in alert:
        readings["bearing_temp"] = alert["bearing_temp_c"]
    with runtime_inputs(alert["machine_id"], readings,
                        "INTERRUPTED" if mode == "escalation" else "OK"), observability.instrument_run() as usage:
        for chunk in graph.stream(state, cfg):
            if "__interrupt__" in chunk:
                interrupted = True
        if interrupted:
            # This CLI is a simulator, not the web server's human approval queue.
            # Default to rejecting; an explicit demo override is recorded as automated.
            decision = auto_decision
            for _chunk in graph.stream(Command(resume={"decision": decision,
                                                       "approver": "simulation default (not a human)"}), cfg):
                pass
        final = graph.get_state(cfg).values

    return {"triggered": True, "run_id": state["run_id"], "machine_id": verdict.machine_id,
            "mode": mode, "status": final.get("status"), "risk": final.get("risk"),
            "reached_gate": interrupted, "usage": usage.to_dict()}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Continuous alert stream with triage-gated agent runs.")
    ap.add_argument("--ticks", type=int, default=48,
                    help="simulated ticks to run (1 tick = 10 minutes of plant time)")
    ap.add_argument("--interval", type=float, default=0.0,
                    help="real seconds to wait between ticks (use 1-2 for a live demo)")
    ap.add_argument("--live", action="store_true",
                    help="actually invoke the agent graph on a wake (costs tokens)")
    ap.add_argument("--dry-run", action="store_true", default=None,
                    help="the default: triage only, no model calls")
    ap.add_argument("--degrading", default="CNC-07-LEI", help="machine put on a failure profile")
    ap.add_argument("--dropout", default=None, help="machine whose telemetry feed drops out")
    ap.add_argument("--dropout-tick", type=int, default=26,
                    help="tick at which that feed goes silent (default 26, by which point "
                         "a degrading machine is above the critical band)")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--max-runs", type=int, default=2,
                    help="stop triggering after this many runs (token budget guard)")
    ap.add_argument("--decision", default="reject", choices=["approve", "reject"],
                    help="simulation decision; defaults to reject, approve is demo-only")
    args = ap.parse_args(argv)

    if args.live and args.dry_run:
        ap.error("--live and --dry-run are mutually exclusive")
    if args.ticks < 1 or args.interval < 0 or args.max_runs < 0:
        ap.error("ticks must be positive; interval and max-runs must be non-negative")
    live = bool(args.live)
    sim = AlertSimulator.from_fleet(degrading=args.degrading, seed=args.seed,
                                    dropout=args.dropout, dropout_tick=args.dropout_tick)
    gate = TriageGate()

    print("TITAN OPERATIONS SENTINEL - continuous stream")
    print(f"fleet={len(sim.profiles)} machines  ticks={args.ticks}  "
          f"mode={'LIVE (agents will run)' if live else 'DRY RUN (triage only)'}")
    print(f"degrading={args.degrading}  dropout={args.dropout or 'none'}  seed={args.seed}\n")

    runs = 0
    for _ in range(args.ticks):
        batch = sim.next_batch()
        tick = batch[0].tick if batch else sim.tick - 1

        verdicts = [gate.observe(r) for r in batch]
        verdicts += gate.check_dropouts(tick)

        hot = [v for v in verdicts if v.wake]
        watch = [v for v in verdicts if not v.wake and v.priority >= 0.45]

        if hot:
            for v in sorted(hot, key=lambda x: -x.priority):
                print(f"\ntick {tick:>3} | WAKE  {v.machine_id}  p={v.priority}  "
                      f"band={v.band.value}\n          reason: {v.reason}")
                _log({"event": "wake", "tick": tick, "machine_id": v.machine_id,
                      "band": v.band.value, "priority": v.priority, "reason": v.reason})
                if runs >= args.max_runs:
                    print(f"          (run budget of {args.max_runs} reached: not starting "
                          f"another run)")
                    continue
                result = trigger_run(v, live, auto_decision=args.decision)
                runs += 1
                _log({"event": "run", "tick": tick, **{k: v2 for k, v2 in result.items()
                                                       if k != "usage"}})
                if result.get("triggered"):
                    u = result.get("usage", {})
                    print(f"          run {result['run_id']} -> status={result['status']} "
                          f"risk={result['risk']} gate={'hit' if result['reached_gate'] else 'no'}"
                          f"  {u.get('total_tokens', 0)} tokens")
                else:
                    print(f"          would start a '{result['mode']}' run for "
                          f"{result['alert_id']} (dry run)")
        elif watch:
            names = ", ".join(f"{v.machine_id}@{v.priority}" for v in watch[:3])
            print(f"tick {tick:>3} | watching {names}")

        if args.interval:
            time.sleep(args.interval)

    s = gate.stats()
    print("\n" + "=" * 62)
    print(f"readings seen            {s['readings_seen']}")
    print(f"agent runs triggered     {s['runs_triggered']}")
    print(f"{'agent runs started' if live else 'dry-run starts':24s} {runs}")
    print(f"suppressed by cooldown   {s['suppressed_by_cooldown']}")
    print(f"wake rate                {(s['wake_rate'] or 0) * 100:.2f}% of readings")
    print("=" * 62)
    print("That ratio is the point: the stream is mostly noise, and the expensive path "
          "runs\nonly on the readings that clear a documented severity band.")
    _log({"event": "summary", **s})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
