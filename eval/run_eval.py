"""
Evaluation CLI.

    python -m eval.run_eval                 # offline suites only (free, no key, CI default)
    python -m eval.run_eval --live          # adds the live agent suite (needs a key)
    python -m eval.run_eval --live --limit 3
    python -m eval.run_eval --fail-under 0.95   # non-zero exit if the offline suite drops

The exit code is what CI reads: 0 when the offline suite meets the floor, 1 when it does
not. The floor defaults to 0 (report only) so a normal run never fails a build by
surprise; the CI workflow sets it explicitly.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from . import policy_eval, rag_eval, scorecard  # noqa: E402
from .scenarios import dataset_meta  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Run the Titan Operations Sentinel evaluation suites.")
    ap.add_argument("--live", action="store_true",
                    help="also run the live agent suite (needs a model key; costs tokens)")
    ap.add_argument("--limit", type=int, default=None,
                    help="cap the number of live scenarios (token budget control)")
    ap.add_argument("--fail-under", type=float, default=0.0,
                    help="exit non-zero if offline policy accuracy is below this (0-1)")
    ap.add_argument("--quiet", action="store_true", help="write the scorecard, print less")
    args = ap.parse_args(argv)

    print("Running the offline policy suite ...")
    policy_result = policy_eval.run()
    print(f"  {policy_result['passed']}/{policy_result['checks']} checks, "
          f"{policy_result['overall_accuracy'] * 100:.1f}%")

    print("Running the retrieval suite ...")
    rag_result = rag_eval.run()
    lex = rag_result["modes"]["lexical"]
    print(f"  lexical recall@4={lex['recall_at_k']['recall@4']:.3f} mrr={lex['mrr']:.3f}")
    for mode in ("dense", "hybrid"):
        if not rag_result["modes"][mode].get("available"):
            print(f"  {mode}: not configured (set TOS_EMBEDDINGS to score it)")

    live_result = None
    if args.live:
        print("Running the live agent suite (this costs tokens) ...")
        try:
            from . import live_eval
            live_result = live_eval.run(limit=args.limit)
            print(f"  {live_result['runs']} runs, {live_result['errors']} errors, "
                  f"{live_result['efficiency']['tokens_per_run']:.0f} tokens/run")
        except Exception as exc:  # noqa: BLE001 — a missing key must not lose the offline results
            print(f"  live suite could not run ({str(exc)[:160]}). "
                  "The offline results below are unaffected.")

    md, js = scorecard.write(policy_result, rag_result, live_result, dataset_meta())
    print(f"\nScorecard written to {md.relative_to(Path.cwd()) if md.is_relative_to(Path.cwd()) else md}")
    if not args.quiet:
        print(f"Raw results       {js.name}")

    acc = policy_result["overall_accuracy"] or 0.0
    if args.fail_under and acc < args.fail_under:
        print(f"\nFAIL: offline policy accuracy {acc:.3f} is below the floor "
              f"{args.fail_under:.3f}.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
