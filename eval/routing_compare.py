"""
Measure model routing on a live model: the same live scenarios twice, one model for
everything, then routine steps on the small model. Writes the comparison and a verdict.

    python -m eval.routing_compare            # check the setup and estimate the cost, runs nothing
    python -m eval.routing_compare --run      # run both suites (costs tokens)
    python -m eval.routing_compare --run --limit 3   # a cheaper first look

Reads the model settings from the environment or .env (TOS_MODEL, TOS_MODEL_SMALL and the
provider's own variables). Never prints a key: only whether one is set.

Routing is worth keeping only if the cost per run falls AND no quality metric drops.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "eval" / "results"
TOKENS_PER_SCENARIO = 35_000      # from earlier live runs: three scenarios used about 100k tokens
INPUT_SHARE = 0.9                  # agent runs are mostly prompt (transcript, tool results)
# The live suite's own metric names (eval/live_eval.py).
QUALITY = ["routing_coverage", "routing_order", "risk_classification", "gate_decision", "terminal_status",
           "halt_decision", "plan_tier_consistency"]


def _load_env() -> None:
    try:
        from dotenv import load_dotenv
        load_dotenv(ROOT / ".env")
    except Exception:  # noqa: BLE001
        pass


def preflight() -> dict:
    """What would run, without revealing any secret."""
    _load_env()
    sys.path.insert(0, str(ROOT))
    import llm
    import observability

    large, small = llm.resolve_model(), (os.getenv("TOS_MODEL_SMALL", "").strip() or None)
    provider = (large or "").split(":", 1)[0]
    info = {"large": large, "small": small, "provider": provider or None, "problems": []}
    if not large:
        info["problems"].append("No model configured: set TOS_MODEL=azure_openai:<deployment> and the Azure variables in .env.")
    if provider == "azure_openai":
        endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", "")
        info["azure"] = {"AZURE_OPENAI_API_KEY": "set" if os.getenv("AZURE_OPENAI_API_KEY") else "MISSING",
                         "AZURE_OPENAI_ENDPOINT": urllib.parse.urlparse(endpoint).netloc or ("set" if endpoint else "MISSING"),
                         "OPENAI_API_VERSION": os.getenv("OPENAI_API_VERSION") or "default 2024-10-21"}
        for k in ("AZURE_OPENAI_API_KEY", "AZURE_OPENAI_ENDPOINT"):
            if info["azure"][k] == "MISSING":
                info["problems"].append(f"{k} is not set.")
    if small and small.split(":", 1)[0] != provider:
        info["problems"].append("TOS_MODEL_SMALL uses a different provider from TOS_MODEL; allowed, but check both keys are set.")
    if not small:
        info["note"] = "TOS_MODEL_SMALL is not set: only the one-model baseline can run. Set it to your small deployment to compare."
    from eval.scenarios import load_scenarios
    n = len(load_scenarios(live_only=True))
    info["scenarios"] = n

    def est(model):
        pin, pout = observability.price_for(model)
        tok = TOKENS_PER_SCENARIO * n
        return tok * (INPUT_SHARE * pin + (1 - INPUT_SHARE) * pout) / 1e6
    info["estimate_eur"] = {"one_model_suite": round(est(large), 3) if large else None}
    return info


def _run_suite(routed: bool, small: str | None, limit: int | None, out: Path) -> dict:
    """One live suite in a fresh process, so cached models never leak between the two runs.
    The parent sets TOS_MODEL_SMALL ('' for the one-model run); .env never overrides it."""
    env = dict(os.environ, TOS_MODEL_SMALL=(small or "") if routed else "")
    cmd = [sys.executable, "-m", "eval.routing_compare", "--child", "--out", str(out)]
    if limit:
        cmd += ["--limit", str(limit)]
    print(f"  running the {'routed' if routed else 'one-model'} suite ...", flush=True)
    subprocess.run(cmd, cwd=ROOT, env=env, check=True)
    return json.loads(out.read_text(encoding="utf-8"))


def _child(limit: int | None, out: str) -> int:
    _load_env()
    sys.path.insert(0, str(ROOT))
    from eval import live_eval
    Path(out).write_text(json.dumps(live_eval.run(limit=limit), default=str), encoding="utf-8")
    return 0


def _acc(r: dict, k: str):
    m = (r.get("metrics") or {}).get(k) or {}
    return m.get("accuracy")


def _tools(r: dict):
    """Tool-call F1 (recall when nothing was called, so F1 is undefined)."""
    t = r.get("tool_call_correctness") or {}
    return t.get("f1") if t.get("f1") is not None else t.get("recall")


def compare(base: dict, routed: dict) -> dict:
    cb, cr = base["efficiency"]["estimated_cost_eur_per_run"], routed["efficiency"]["estimated_cost_eur_per_run"]
    drops = [k for k in QUALITY if _acc(base, k) is not None and _acc(routed, k) is not None and _acc(routed, k) < _acc(base, k)]
    for k in ("citation_rate", "numeric_groundedness"):
        b, r = base["grounding"].get(k), routed["grounding"].get(k)
        if b is not None and r is not None and r < b:
            drops.append(k)
    tb, tr = _tools(base), _tools(routed)
    if tb is not None and tr is not None and tr < tb:
        drops.append("tool_call_correctness")
    cheaper = cr < cb
    errors = base["errors"] or routed["errors"]
    verdict = ("Keep routing: cheaper, and no quality metric dropped." if cheaper and not drops and not errors else
               "Do not keep routing yet: " + "; ".join(
                   (["it was not cheaper"] if not cheaper else []) + ([f"quality dropped on {', '.join(drops)}"] if drops else [])
                   + (["a suite had errors"] if errors else [])) + ".")
    return {"cost_per_run": {"one_model": cb, "routed": cr, "saving_pct": round(100 * (cb - cr) / cb, 1) if cb else None},
            "drops": drops, "verdict": verdict}


def report(base: dict, routed: dict | None, info: dict) -> str:
    L = ["# Model routing on a live model", "",
         f"Generated by `python -m eval.routing_compare --run`. Main model `{info['large']}`; "
         f"small model `{info['small'] or 'not set'}`. Same {base['runs']} live scenarios each way. "
         "Costs use the indicative prices in `observability.py`.", ""]
    cols = ["One model"] + (["Routed"] if routed else [])
    L += ["| | " + " | ".join(cols) + " |", "|---|" + "---:|" * len(cols)]

    def row(label, f):
        L.append(f"| {label} | " + " | ".join(f(r) for r in [base] + ([routed] if routed else [])) + " |")
    row("runs / errors", lambda r: f"{r['runs']} / {r['errors']}")
    row("cost per run", lambda r: f"EUR {r['efficiency']['estimated_cost_eur_per_run']:.4f}")
    row("tokens per run", lambda r: f"{r['efficiency']['tokens_per_run']:,.0f}")
    row("seconds per run", lambda r: f"{r['efficiency']['seconds_per_run']:.1f}")
    for k in QUALITY:
        row(k.replace("_", " "), lambda r, k=k: "n/a" if _acc(r, k) is None else f"{_acc(r, k):.0%}")
    row("tool-call F1", lambda r: "n/a" if _tools(r) is None else f"{_tools(r):.0%}")
    row("citation rate", lambda r: "n/a" if r['grounding'].get('citation_rate') is None else f"{r['grounding']['citation_rate']:.0%}")
    row("numeric groundedness", lambda r: "n/a" if r['grounding'].get('numeric_groundedness') is None else f"{r['grounding']['numeric_groundedness']:.0%}")
    if routed:
        c = compare(base, routed)
        L += ["", f"**{c['verdict']}**" + (f" Cost per run {c['cost_per_run']['saving_pct']}% lower." if c['cost_per_run']['saving_pct'] is not None else "")]
    return "\n".join(L) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", action="store_true", help="run the live suites (costs tokens)")
    ap.add_argument("--limit", type=int, default=None, help="run only the first N live scenarios")
    ap.add_argument("--child", action="store_true", help=argparse.SUPPRESS)
    ap.add_argument("--out", help=argparse.SUPPRESS)
    args = ap.parse_args(argv)
    if args.child:
        return _child(args.limit, args.out)

    info = preflight()
    print(f"Main model:  {info['large'] or 'NOT SET'}")
    print(f"Small model: {info['small'] or 'not set'}")
    for k, v in (info.get("azure") or {}).items():
        print(f"  {k}: {v}")
    n = args.limit or info["scenarios"]
    if info["estimate_eur"]["one_model_suite"] is not None:
        scale = n / info["scenarios"]
        print(f"Live scenarios: {n}. Estimated cost: about EUR {info['estimate_eur']['one_model_suite'] * scale:.2f} "
              f"for the one-model suite, less for the routed one (rough: ~{TOKENS_PER_SCENARIO // 1000}k tokens a scenario).")
    if info.get("note"):
        print("Note: " + info["note"])
    for p in info["problems"]:
        print("Problem: " + p)
    if not args.run:
        print("\nNothing was run. When the above looks right: python -m eval.routing_compare --run")
        return 0 if not info["problems"] else 1
    if info["problems"]:
        print("Fix the problems above first.")
        return 1

    RESULTS.mkdir(parents=True, exist_ok=True)
    base = _run_suite(False, None, args.limit, RESULTS / "live_one_model.json")
    routed = _run_suite(True, info["small"], args.limit, RESULTS / "live_routed.json") if info["small"] else None
    out = RESULTS / "routing_comparison.md"
    out.write_text(report(base, routed, info), encoding="utf-8")
    print(out.read_text(encoding="utf-8"))
    print(f"Written to {out}. To put the live results on the main scorecard too: python -m eval.run_eval --live")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
