"""Renders the evaluation results as the Markdown scorecard published in the README."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

RESULTS_DIR = Path(__file__).parent / "results"
SCORECARD_MD = RESULTS_DIR / "scorecard.md"
SCORECARD_JSON = RESULTS_DIR / "scorecard.json"
BADGE_JSON = RESULTS_DIR / "badge.json"


def _pct(v) -> str:
    return "n/a" if v is None else f"{v * 100:.1f}%"


def _verdict(v, floor: float = 1.0) -> str:
    if v is None:
        return "n/a"
    return "pass" if v >= floor else "review"


# Scenario id -> the entry in eval/FINDINGS.md that explains it. A miss on the scorecard
# should never look like something nobody noticed.
FINDING_REFS = {
    "S17-speed-reduction-is-autonomous": "F-01",
    "S27-safety-signoff-is-not-a-safety-bypass": "F-02",
}


def _finding_ref(case: str) -> str:
    ref = FINDING_REFS.get(case)
    return f" See [{ref}](../FINDINGS.md#{ref.lower().replace('-', '-')})." if ref else ""


def _policy_section(r: dict) -> list[str]:
    lines = [
        "## 1. Offline policy suite (no key, no tokens, deterministic)",
        "",
        f"`{r['checks']}` checks across `{r['scenarios']}` labelled scenarios. "
        f"Overall **{_pct(r['overall_accuracy'])}**.",
        "",
        "| Metric | Score | Checks | Verdict |",
        "|---|---:|---:|---|",
    ]
    for name, m in r["metrics"].items():
        if not m["total"]:
            continue
        lines.append(
            f"| `{name}` | {_pct(m['accuracy'])} | {m['correct']}/{m['total']} | "
            f"{_verdict(m['accuracy'])} |"
        )
    h = r["halt_detection"]
    lines += [
        "",
        "### Safety HALT class",
        "",
        "The two error types are not equally bad, so this class is reported as precision "
        "and recall rather than accuracy. A missed HALT is a safety failure. A spurious "
        "HALT is an availability cost.",
        "",
        "| | Value |",
        "|---|---:|",
        f"| recall (HALTs caught) | {_pct(h['recall'])} |",
        f"| precision (HALTs that were real) | {_pct(h['precision'])} |",
        f"| false negatives | {h['fn']} |",
        f"| false positives | {h['fp']} |",
        "",
    ]

    misses = [(name, miss) for name, m in r["metrics"].items() for miss in m["misses"]]
    if misses or h["errors"]:
        lines += [
            "### Open findings",
            "",
            "Each one is written up in [eval/FINDINGS.md](../FINDINGS.md) with what it is, "
            "why it has not simply been edited to green, and what the actual decision is.",
            "",
        ]
        for name, miss in misses:
            lines.append(
                f"- **{miss['case']}** (`{name}`): expected `{miss['expected']}`, "
                f"got `{str(miss['actual'])[:200]}`.{_finding_ref(miss['case'])}"
            )
        for err in h["errors"]:
            lines.append(
                f"- **{err['case']}** (`halt_detection`): {err['error']}."
                f"{_finding_ref(err['case'])}"
            )
        lines.append("")
    return lines


def _rag_section(r: dict) -> list[str]:
    c = r["corpus"]
    lines = [
        "## 2. Retrieval suite (no key, no tokens, deterministic)",
        "",
        f"{c['documents']} documents, {c['chunks']} section-level chunks, "
        f"{c['vocabulary']} terms. Scored at k={r['report_k']}, the default the "
        "`search_technical_docs` tool uses.",
        "The legacy metric name `recall@k` denotes an any-relevant-passage hit rate. "
        "It does not measure retrieval of every relevant section.",
        "",
        "| Retriever | recall@1 | recall@4 | MRR | precision@4 | Status |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for mode, m in r["modes"].items():
        if not m.get("available"):
            lines.append(f"| `{mode}` | | | | | not configured |")
            continue
        rk = m["recall_at_k"]
        lines.append(
            f"| `{mode}` | {_pct(rk['recall@1'])} | {_pct(rk['recall@4'])} | "
            f"{m['mrr']:.3f} | {_pct(m['precision_at_4'])} | scored |"
        )

    lex = r["modes"].get("lexical", {})
    if lex.get("by_difficulty"):
        lines += [
            "",
            "### By query difficulty",
            "",
            "`direct` queries use the target section's own vocabulary. `paraphrase` "
            "queries deliberately avoid it and ask the way an operator would. The gap "
            "between the two splits is the argument for embeddings, measured rather "
            "than asserted.",
            "",
            "| Split | Queries | recall@4 | MRR |",
            "|---|---:|---:|---:|",
        ]
        for split, d in lex["by_difficulty"].items():
            lines.append(
                f"| {split} | {d['queries']} | {_pct(d['recall@4'])} | {d['mrr']:.3f} |"
            )
        misses = lex["by_difficulty"].get("paraphrase", {}).get("misses", [])
        if misses:
            lines += ["", f"Lexical misses on the paraphrase split: {', '.join(misses)}."]
    lines.append("")
    return lines


def _live_section(r: dict | None) -> list[str]:
    if r and r.get("error"):
        return ["## 3. Live agent suite", "", f"**Failed to run:** {r['error']}", ""]
    if not r:
        return [
            "## 3. Live agent suite (needs a model key)",
            "",
            "Not run in this pass. Run it with `python -m eval.run_eval --live` once a "
            "provider key is in `.env`. It is excluded from the on-every-push CI job "
            "because it costs tokens and depends on a third-party API being up; the "
            "nightly workflow runs it when a key is available as a repository secret.",
            "",
        ]
    lines = [
        "## 3. Live agent suite (real model, real graph)",
        "",
        f"Provider `{r['provider']}`, {r['runs']} scenario runs, {r['errors']} run errors.",
        "",
        "| Metric | Score | Checks |",
        "|---|---:|---:|",
    ]
    for name, m in r["metrics"].items():
        lines.append(f"| `{name}` | {_pct(m['accuracy'])} | {m['correct']}/{m['total']} |")
    t = r["tool_call_correctness"]
    lines += [
        f"| `tool_call_recall` | {_pct(t['recall'])} | {t['matched']}/{t['expected_total']} |",
        f"| `tool_call_precision` | {_pct(t['precision'])} | {t['matched']}/{t['predicted_total']} |",
        f"| `tool_call_f1` | {_pct(t['f1'])} | |",
    ]
    g = r["grounding"]
    lines += [
        f"| `citation_rate` | {_pct(g['citation_rate'])} | "
        f"{g['reports_with_a_valid_citation']}/{g['grounded_reports']} |",
        f"| `numeric_groundedness` | {_pct(g.get('numeric_groundedness'))} | "
        f"{g.get('numbers_checked', 0) - g.get('ungrounded_numbers', 0)}"
        f"/{g.get('numbers_checked', 0)} |",
        "",
        "Citations count only when present in the corpus and retrieved by that agent. "
        "This checks provenance, not whether the passage entails the claim. An invented "
        f"citation counts against the score rather than for it "
        f"({len(g['invented_citations'])} invented). Numeric groundedness traces every "
        "figure in a report back to a tool result, or to arithmetic on tool results: a "
        "cost or an ROI that no tool produced is the failure that actually reaches a "
        "plant manager.",
        "Plan-tier consistency is a keyword-policy check on tagged action lines, "
        "not a judgement of whether the plan is operationally correct.",
        "",
        "### Cost and latency per run",
        "",
        "| | Value |",
        "|---|---:|",
        f"| tokens | {r['efficiency']['tokens_per_run']:.0f} |",
        f"| estimated cost | EUR {r['efficiency']['estimated_cost_eur_per_run']:.4f} |",
        f"| wall time | {r['efficiency']['seconds_per_run']:.1f} s |",
        "",
    ]
    return lines


def render(policy_result: dict, rag_result: dict, live_result: dict | None,
           meta: dict) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    header = [
        "# Evaluation scorecard",
        "",
        f"Generated {now} by `python -m eval.run_eval`. "
        "Do not edit by hand: it is overwritten on every run.",
        "",
        f"Datasets: **{meta['scenarios']}** labelled scenarios "
        f"({meta['live_subset']} in the live subset), **{meta['rag_queries']}** "
        f"labelled retrieval queries ({meta.get('rag_direct', 0)} direct, "
        f"{meta.get('rag_paraphrase', 0)} paraphrase).",
        "",
        "### Headline",
        "",
        "| Suite | Result |",
        "|---|---|",
        f"| Offline policy | {_pct(policy_result['overall_accuracy'])} of "
        f"{policy_result['checks']} checks |",
        f"| Safety HALT recall | {_pct(policy_result['halt_detection']['recall'])} |",
        f"| Retrieval recall@4 (lexical) | "
        f"{_pct(rag_result['modes']['lexical']['recall_at_k']['recall@4'])} |",
        f"| Live agent suite | "
        f"{'run, see below' if live_result else 'not run in this pass'} |",
        "",
        "How to read this: the offline suites measure the parts of the system that are "
        "enforced in code, exhaustively and for free. The live suite measures what the "
        "model does, on a subset, and costs tokens. A claim backed only by the live "
        "suite is a sample; a claim backed by the offline suite is a check.",
        "",
        "---",
        "",
    ]
    return "\n".join(
        header + _policy_section(policy_result) + ["---", ""]
        + _rag_section(rag_result) + ["---", ""]
        + _live_section(live_result)
        + ["---", "",
           "Regenerate with `python -m eval.run_eval` (offline suites) or "
           "`python -m eval.run_eval --live` (adds the agent suite). "
           "The labelled datasets are in `eval/cases/`.", ""]
    )


def _write_badge(policy_result: dict) -> None:
    """A shields.io endpoint payload so the README badge reads the real score.

    The badge used to be a hardcoded string. A hardcoded number in a README about
    measurement is exactly the thing this project is arguing against, and it would have
    gone stale the first time a metric moved."""
    accuracy = policy_result.get("overall_accuracy") or 0.0
    checks = policy_result.get("checks") or 0
    colour = ("brightgreen" if accuracy >= 0.98 else
              "green" if accuracy >= 0.95 else
              "yellow" if accuracy >= 0.90 else "orange")
    BADGE_JSON.write_text(json.dumps({
        "schemaVersion": 1,
        "label": "eval",
        "message": f"{accuracy * 100:.1f}% of {checks} checks",
        "color": colour,
    }), encoding="utf-8")


def write(policy_result: dict, rag_result: dict, live_result: dict | None,
          meta: dict) -> tuple[Path, Path]:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    SCORECARD_MD.write_text(render(policy_result, rag_result, live_result, meta),
                            encoding="utf-8")
    SCORECARD_JSON.write_text(
        json.dumps({"generated_utc": datetime.now(timezone.utc).isoformat(),
                    "datasets": meta, "policy": policy_result, "retrieval": rag_result,
                    "live": live_result}, indent=2, default=str),
        encoding="utf-8",
    )
    _write_badge(policy_result)
    return SCORECARD_MD, SCORECARD_JSON
