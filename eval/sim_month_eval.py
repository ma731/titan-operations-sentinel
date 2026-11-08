"""
Offline suite over the simulated month (eval/cases/sim_month_cases.json).

No model, no key. For every wake in the month it runs the real rul_predictor and the real
risk rule, then asks two questions:

  1. Does the predicted interval contain the true remaining life?
  2. Is the risk call the one the corpus says is right?

The true remaining life comes from the simulator. So this validates the code against
the simulator's own physics, which follows the corpus rule of thumb, not against real
bearings. Kept separate from the 34 policy scenarios so their numbers do not move.
"""
from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import policy  # noqa: E402
from tools.rul_predictor import rul_predictor  # noqa: E402

from .metrics import Tally  # noqa: E402
from .scenarios import CASES_DIR  # noqa: E402

CASES_PATH = CASES_DIR / "sim_month_cases.json"


def _evidence(status: str) -> str:
    """The same telemetry blob the policy sees in the graph (see Scenario.evidence_blob)."""
    if status.upper() == "INTERRUPTED":
        return '{"sensor_status": "interrupted"}'
    return '{"sensor_status": "ok"}'


def run(path: Path | str = CASES_PATH) -> dict:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    risk = Tally("risk_on_simulated_wakes")
    life, errors = [], []
    for c in data["cases"]:
        rp = rul_predictor(c["machine_id"], c["readings"])
        got = policy.classify_risk(rp, _evidence(c["telemetry_status"]))
        risk.add(got == c["expected"]["risk"], c["id"], c["expected"]["risk"], got,
                 note=c["expected"].get("source", ""))

        truth = c.get("true_hours_to_failure")
        if truth is None or c["telemetry_status"] != "OK":
            continue                      # no failure ahead, or an estimate is not allowed
        lo, hi = rp["rul"]["min"], rp["rul"]["max"]
        verdict = "inside" if lo <= truth <= hi else ("optimistic" if truth < lo else "conservative")
        life.append({"case": c["id"], "predicted_h": [lo, hi], "true_h": truth,
                     "verdict": verdict, "source": rp.get("source")})
        mid = (lo + hi) / 2
        errors.append(mid - truth)

    n = len(life)
    count = {v: sum(x["verdict"] == v for x in life) for v in ("inside", "optimistic", "conservative")}
    return {
        "cases": len(data["cases"]),
        "basis": "simulated month: validates against the simulator's physics, not real failures",
        "risk": risk.to_dict(),
        "rul_interval": {
            "checked": n,
            **count,
            "coverage": round(count["inside"] / n, 4) if n else None,
            # positive = the midpoint promised more life than was left
            "median_midpoint_error_h": round(statistics.median(errors), 1) if errors else None,
            "estimates": life,
        },
    }


if __name__ == "__main__":
    r = run()
    li = r["rul_interval"]
    print(f"{r['cases']} cases | risk {r['risk']['correct']}/{r['risk']['total']} | "
          f"RUL coverage {li['inside']}/{li['checked']} ({li['optimistic']} optimistic)")
