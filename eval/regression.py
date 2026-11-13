"""
Nightly regression watch: compare tonight's offline scorecard with the last published one
and open, update or close a GitHub issue labelled `regression`.

    python -m eval.regression --previous prev.json --current eval/results/scorecard.json \
        --before-sha <sha> --after-sha <sha> --repo owner/name [--dry-run]

Only the free, deterministic suites are compared. The live suite is a sample and is skipped.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

LABEL = "regression"
MARKER = "titan-regression-watch"
TOLERANCE = 1e-9  # the offline suites are deterministic, so any real drop counts

# Leaf names where higher is better. Counts (tp, fn, totals) are left out on purpose.
_RATE_KEYS = {"accuracy", "overall_accuracy", "precision", "recall", "f1", "mrr", "coverage",
              "precision_at_4"}
_SKIP_SECTIONS = {"live", "datasets", "generated_utc"}


@dataclass(frozen=True)
class Drop:
    metric: str
    before: float
    after: float


@dataclass(frozen=True)
class Action:
    kind: str            # "open", "update", "close" or "none"
    title: str = ""
    body: str = ""
    comment: str = ""


def _is_rate(key: str) -> bool:
    return key in _RATE_KEYS or key.startswith("recall@")


def extract(scorecard: dict) -> dict[str, float]:
    """Flatten a scorecard into {"policy.metrics.approval_gate.accuracy": 1.0, ...}."""
    out: dict[str, float] = {}

    def walk(node, path):
        if isinstance(node, dict):
            for k, v in node.items():
                walk(v, f"{path}.{k}" if path else k)
        elif isinstance(node, (int, float)) and not isinstance(node, bool):
            if _is_rate(path.rsplit(".", 1)[-1]):
                out[path] = float(node)

    for section, node in scorecard.items():
        if section not in _SKIP_SECTIONS:
            walk(node, section)
    return out


def compare(before: dict[str, float], after: dict[str, float],
            tol: float = TOLERANCE) -> list[Drop]:
    """Metrics present in both runs that went down."""
    return [Drop(m, before[m], after[m]) for m in sorted(before.keys() & after.keys())
            if after[m] < before[m] - tol]


_NOISE = {"policy", "metrics", "retrieval", "modes", "recall_at_k", "by_difficulty"}


def short_name(metric: str) -> str:
    """retrieval.modes.lexical.recall_at_k.recall@4 becomes 'lexical recall@4'."""
    parts = [p for p in metric.split(".") if p not in _NOISE]
    return " ".join(parts) or metric


def parse_marker(body: str) -> dict | None:
    m = re.search(rf"<!-- {MARKER} (\{{.*?\}}) -->", body or "", re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except json.JSONDecodeError:
        return None


def _pct(x: float) -> str:
    return f"{x * 100:.1f}%"


def _range(repo: str, before_sha: str, after_sha: str) -> str:
    if not before_sha or before_sha == after_sha:
        return f"`{after_sha[:7]}` (no earlier run to compare with)"
    return (f"[`{before_sha[:7]}...{after_sha[:7]}`]"
            f"(https://github.com/{repo}/compare/{before_sha}...{after_sha})")


def render_body(drops: list[Drop], repo: str, before_sha: str, after_sha: str,
                run_url: str = "") -> str:
    rows = "\n".join(f"| `{d.metric}` | {_pct(d.before)} | {_pct(d.after)} |" for d in drops)
    baseline = {"since": before_sha, "baseline": {d.metric: d.before for d in drops}}
    run_line = f"\nNightly run: {run_url}\n" if run_url else ""
    return (
        "The nightly offline evaluation scored lower than before.\n\n"
        "| Metric | Before | After |\n|---|---:|---:|\n"
        f"{rows}\n\n"
        f"Commits in range: {_range(repo, before_sha, after_sha)}\n"
        f"{run_line}\n"
        "This issue closes itself when every metric above is back to its earlier value.\n\n"
        f"<!-- {MARKER} {json.dumps(baseline, sort_keys=True)} -->\n"
    )


def decide(previous: dict | None, current: dict, open_issue_body: str | None,
           repo: str, before_sha: str, after_sha: str, run_url: str = "") -> Action:
    """Work out what to do with the issue. Pure, so it can be tested without GitHub."""
    cur = extract(current)
    marker = parse_marker(open_issue_body) if open_issue_body is not None else None

    # While an issue is open, hold the bar at the pre-regression numbers, so a drop that
    # got published as last night's result cannot quietly become the new normal.
    reference = extract(previous) if previous else {}
    if marker:
        reference.update(marker.get("baseline", {}))
        before_sha = marker.get("since") or before_sha

    drops = compare(reference, cur)
    if drops:
        names = ", ".join(short_name(d.metric) for d in drops[:3])
        more = f" and {len(drops) - 3} more" if len(drops) > 3 else ""
        title = f"Nightly evaluation regression: {names}{more}"
        body = render_body(drops, repo, before_sha, after_sha, run_url)
        if marker:
            comment = f"Still lower on the run for `{after_sha[:7]}`.\n\n" + body.split("<!--")[0]
            return Action("update", title, body, comment)
        return Action("open", title, body)

    if marker:
        fixed = "\n".join(f"- `{m}`: back to {_pct(cur.get(m, v))}"
                          for m, v in sorted(marker.get("baseline", {}).items()))
        return Action("close", comment=(f"All metrics recovered on `{after_sha[:7]}`.\n\n"
                                        f"{fixed}\n\nClosing."))
    return Action("none")


def is_stale(scorecard: dict, max_age_hours: float, now: datetime | None = None) -> bool:
    """True when the scorecard was not written by this run (e.g. the eval crashed early)."""
    stamp = scorecard.get("generated_utc")
    if not stamp:
        return True
    try:
        made = datetime.fromisoformat(stamp)
    except ValueError:
        return True
    now = now or datetime.now(timezone.utc)
    return now - made > timedelta(hours=max_age_hours)


# --- GitHub side, through the gh CLI --------------------------------------- #
def _gh(*args: str, stdin: str | None = None) -> str:
    return subprocess.run(["gh", *args], input=stdin, text=True, capture_output=True,
                          check=True).stdout


def find_open_issue(repo: str) -> dict | None:
    raw = _gh("issue", "list", "--repo", repo, "--label", LABEL, "--state", "open",
              "--json", "number,body", "--limit", "50")
    for issue in json.loads(raw or "[]"):
        if parse_marker(issue.get("body", "")) is not None:
            return issue
    return None


def apply(action: Action, repo: str, issue: dict | None) -> None:
    if action.kind == "open":
        _gh("label", "create", LABEL, "--repo", repo, "--color", "d73a4a", "--force",
            "--description", "A nightly evaluation metric went down")
        _gh("issue", "create", "--repo", repo, "--title", action.title, "--label", LABEL,
            "--body-file", "-", stdin=action.body)
    elif action.kind == "update" and issue:
        num = str(issue["number"])
        _gh("issue", "edit", num, "--repo", repo, "--title", action.title,
            "--body-file", "-", stdin=action.body)
        _gh("issue", "comment", num, "--repo", repo, "--body-file", "-", stdin=action.comment)
    elif action.kind == "close" and issue:
        num = str(issue["number"])
        _gh("issue", "comment", num, "--repo", repo, "--body-file", "-", stdin=action.comment)
        _gh("issue", "close", num, "--repo", repo)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Open or close a regression issue.")
    ap.add_argument("--previous", type=Path, help="last published scorecard.json")
    ap.add_argument("--current", type=Path, required=True)
    ap.add_argument("--repo", required=True)
    ap.add_argument("--before-sha", default="")
    ap.add_argument("--after-sha", required=True)
    ap.add_argument("--run-url", default="")
    ap.add_argument("--max-age-hours", type=float, default=6.0)
    ap.add_argument("--dry-run", action="store_true", help="print the action, touch nothing")
    args = ap.parse_args(argv)

    current = json.loads(args.current.read_text(encoding="utf-8"))
    if is_stale(current, args.max_age_hours):
        print("Scorecard was not written by this run, skipping the regression check.")
        return 0
    previous = None
    if args.previous and args.previous.exists() and args.previous.stat().st_size:
        previous = json.loads(args.previous.read_text(encoding="utf-8"))

    issue = None if args.dry_run else find_open_issue(args.repo)
    action = decide(previous, current, issue["body"] if issue else None, args.repo,
                    args.before_sha, args.after_sha, args.run_url)
    print(f"Regression check: {action.kind}")
    if action.title:
        print(action.title)
    if args.dry_run:
        print(action.body or action.comment)
        return 0
    apply(action, args.repo, issue)
    return 0


if __name__ == "__main__":
    sys.exit(main())
