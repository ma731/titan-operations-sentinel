"""
What the system costs to run, computed rather than asserted.

Two halves, and they are not equally solid:

  Measured. The triage wake rate comes from actually running the gate over a simulated
  plant day. It is deterministic and needs no model, so it is exact. Token cost per run
  comes from the last live evaluation when one exists, and from the documented figure
  otherwise, labelled either way.

  Assumed. The value side is the case study's own numbers (production at risk, alert
  volume). Those are inputs to the scenario, not results this system produced, and the
  report says so.

Kept separate on purpose: the first number is ours to defend, the second is not.
"""
from __future__ import annotations

import json
from pathlib import Path

RESULTS = Path(__file__).parent / "results" / "scorecard.json"

# From data/alerts/alert_stream.json and data/assets/asset_profiles.json. Case study
# inputs, not measurements.
ALERTS_PER_DAY = 22431
DEDUPLICATED_CRITICAL_PER_DAY = 3
PRODUCTION_VALUE_PER_DAY_EUR = 180_000

# Measured on earlier live runs and quoted in the README. The live suite overwrites this
# when it has run; see `_tokens_per_run`.
DOCUMENTED_TOKENS_PER_RUN = 18_000
DOCUMENTED_CALLS_PER_RUN = 40


def _tokens_per_run() -> tuple[float, str]:
    """Tokens for one full run, preferring a real measurement over the documented figure."""
    try:
        live = json.loads(RESULTS.read_text(encoding="utf-8")).get("live")
        per_run = (live or {}).get("efficiency", {}).get("tokens_per_run")
        if per_run:
            return float(per_run), "measured by the live evaluation suite"
    except Exception:  # noqa: BLE001 - no scorecard yet is not an error
        pass
    return float(DOCUMENTED_TOKENS_PER_RUN), "from earlier live runs, not re-measured"


def measure_wake_rate(ticks: int = 144, seed: int = 7) -> dict:
    """Run the triage gate over a simulated day and count how often it wakes the agents.

    Deterministic and model-free, so this is an exact number rather than an estimate.
    144 ticks at ten minutes each is a 24 hour plant day.
    """
    from stream.simulator import AlertSimulator
    from stream.triage import TriageGate

    sim = AlertSimulator.from_fleet(seed=seed)
    gate = TriageGate()
    for _ in range(ticks):
        batch = sim.next_batch()
        for reading in batch:
            gate.observe(reading)
        gate.check_dropouts(batch[0].tick if batch else 0)
    stats = gate.stats()
    return {
        "readings": stats["readings_seen"],
        "runs": stats["runs_triggered"],
        "suppressed_by_cooldown": stats["suppressed_by_cooldown"],
        "wake_rate": stats["wake_rate"],
        "machines": len(sim.profiles),
        "simulated_hours": round(ticks * 10 / 60, 1),
    }


def cost_per_run(provider: str, tokens: float) -> float:
    """Model cost for one run. Free-tier providers are zero because that is what we spend."""
    from observability import PRICE_EUR_PER_M

    price_in, price_out = PRICE_EUR_PER_M.get(provider, (0.0, 0.0))
    # Roughly 3:1 input to output across a run: the transcript is re-sent to every agent.
    return (tokens * 0.75 * price_in + tokens * 0.25 * price_out) / 1_000_000


def run(providers: tuple[str, ...] = ("groq", "google_genai", "openai", "anthropic")) -> dict:
    tokens, token_source = _tokens_per_run()
    wake = measure_wake_rate()

    # Runs per day come from the case study's deduplicated critical count, not from
    # scaling the wake rate against the raw alert volume. A "reading" here is one sensor
    # sample per machine per tick, which is not the same unit as a plant alert, and
    # multiplying the two gives a number that looks precise and means nothing.
    #
    # Worth noting as a cross-check: the simulated fleet independently produced
    # wake["runs"] runs in 24 hours, which is the same order as the case study's figure.
    runs_per_day = DEDUPLICATED_CRITICAL_PER_DAY

    per_provider = {}
    for p in providers:
        per_run = cost_per_run(p, tokens)
        per_provider[p] = {
            "eur_per_run": round(per_run, 5),
            "eur_per_plant_day": round(per_run * runs_per_day, 3),
            "eur_per_1000_alerts": round(
                per_run * runs_per_day * 1000 / ALERTS_PER_DAY, 5),
        }

    return {
        "measured": {
            "triage": wake,
            "tokens_per_run": tokens,
            "tokens_per_run_source": token_source,
            "model_calls_per_run": DOCUMENTED_CALLS_PER_RUN,
            "runs_per_plant_day": runs_per_day,
            "runs_per_plant_day_source": "case study deduplicated critical alerts",
            "simulator_cross_check_runs_per_day": wake["runs"],
        },
        "cost_by_provider": per_provider,
        "case_study_inputs": {
            "alerts_per_day": ALERTS_PER_DAY,
            "deduplicated_critical_per_day": DEDUPLICATED_CRITICAL_PER_DAY,
            "production_value_per_day_eur": PRODUCTION_VALUE_PER_DAY_EUR,
            "note": "Inputs from the case study, not results this system produced.",
        },
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
