"""The nightly regression watch, with fake before/after scorecards. No GitHub calls."""
import copy
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from eval import regression as r

REPO = "ma731/titan-operations-sentinel"
NOW = datetime(2026, 11, 14, 3, 10, tzinfo=timezone.utc)


def card(approval=1.0, recall4=0.8654, halt_recall=1.0, live_acc=None):
    c = {
        "generated_utc": NOW.isoformat(),
        "datasets": {"scenarios": 34},
        "policy": {
            "checks": 208, "passed": 208, "overall_accuracy": 1.0,
            "metrics": {"approval_gate": {"correct": 34, "total": 34, "accuracy": approval},
                        "risk_classification": {"correct": 34, "total": 34, "accuracy": 1.0}},
            "halt_detection": {"tp": 7, "fn": 0, "precision": 1.0, "recall": halt_recall,
                               "f1": 1.0},
            "per_scenario": [{"id": "S01", "routing_ok": True}],
        },
        "retrieval": {"modes": {"lexical": {"recall_at_k": {"recall@4": recall4},
                                            "mrr": 0.82}}},
        "sim_month": {"rul_interval": {"coverage": 1.0, "median_width_h": 100.0}},
    }
    if live_acc is not None:
        c["live"] = {"accuracy": live_acc}
    return c


def test_extract_keeps_rates_and_drops_counts():
    m = r.extract(card())
    assert m["policy.metrics.approval_gate.accuracy"] == 1.0
    assert m["retrieval.modes.lexical.recall_at_k.recall@4"] == 0.8654
    assert m["sim_month.rul_interval.coverage"] == 1.0
    assert "policy.checks" not in m
    assert "policy.halt_detection.tp" not in m
    assert "sim_month.rul_interval.median_width_h" not in m


def test_live_suite_is_ignored():
    # live runs are a costly sample, not a deterministic check
    assert not any(k.startswith("live") for k in r.extract(card(live_acc=0.5)))
    assert r.decide(card(live_acc=1.0), card(live_acc=0.1), None, REPO, "a" * 40,
                    "b" * 40).kind == "none"


def test_no_change_means_no_action():
    assert r.decide(card(), card(), None, REPO, "a" * 40, "b" * 40).kind == "none"


def test_first_night_without_history_does_nothing():
    assert r.decide(None, card(approval=0.5), None, REPO, "", "b" * 40).kind == "none"


def test_improvement_is_not_a_regression():
    assert r.compare(r.extract(card(recall4=0.8)), r.extract(card(recall4=0.9))) == []


def test_drop_opens_issue_with_metric_numbers_and_range():
    a = r.decide(card(), card(approval=0.9706), None, REPO, "a" * 40, "b" * 40,
                 run_url="https://example.test/run/1")
    assert a.kind == "open"
    assert "approval_gate accuracy" in a.title
    assert "| `policy.metrics.approval_gate.accuracy` | 100.0% | 97.1% |" in a.body
    assert f"https://github.com/{REPO}/compare/{'a' * 40}...{'b' * 40}" in a.body
    assert "https://example.test/run/1" in a.body
    marker = r.parse_marker(a.body)
    assert marker == {"since": "a" * 40,
                      "baseline": {"policy.metrics.approval_gate.accuracy": 1.0}}


def test_several_drops_are_all_listed():
    a = r.decide(card(), card(approval=0.9, recall4=0.5, halt_recall=0.8), None, REPO,
                 "a" * 40, "b" * 40)
    assert a.kind == "open"
    for metric in ("approval_gate.accuracy", "recall@4", "halt_detection.recall"):
        assert metric in a.body


def test_still_broken_updates_the_open_issue_and_keeps_the_original_baseline():
    opened = r.decide(card(), card(approval=0.9), None, REPO, "a" * 40, "b" * 40)
    # The regressed scorecard got published, so "previous" is now the bad one.
    again = r.decide(card(approval=0.9), card(approval=0.9), opened.body, REPO,
                     "b" * 40, "c" * 40)
    assert again.kind == "update"
    assert "| 100.0% | 90.0% |" in again.body
    assert r.parse_marker(again.body)["since"] == "a" * 40  # range starts before the drop
    assert "c" * 7 in again.comment


def test_partial_recovery_is_not_closed():
    opened = r.decide(card(), card(approval=0.9), None, REPO, "a" * 40, "b" * 40)
    assert r.decide(card(approval=0.9), card(approval=0.95), opened.body, REPO,
                    "b" * 40, "c" * 40).kind == "update"


def test_full_recovery_comments_and_closes():
    opened = r.decide(card(), card(approval=0.9), None, REPO, "a" * 40, "b" * 40)
    closed = r.decide(card(approval=0.9), card(), opened.body, REPO, "b" * 40, "c" * 40)
    assert closed.kind == "close"
    assert "recovered" in closed.comment
    assert "back to 100.0%" in closed.comment


def test_issue_without_our_marker_is_not_ours():
    assert r.parse_marker("someone filed this by hand") is None
    assert r.parse_marker("<!-- titan-regression-watch {broken json -->") is None


def test_tiny_float_noise_is_ignored():
    before = r.extract(card(recall4=0.8654))
    after = r.extract(card(recall4=0.8654 - 1e-12))
    assert r.compare(before, after) == []


def test_metric_missing_tonight_is_not_a_drop():
    before = r.extract(card())
    after = r.extract(card())
    del after["sim_month.rul_interval.coverage"]
    assert r.compare(before, after) == []


def test_stale_scorecard_is_skipped():
    fresh = card()
    old = copy.deepcopy(fresh)
    old["generated_utc"] = (NOW - timedelta(days=3)).isoformat()
    assert not r.is_stale(fresh, 6, now=NOW)
    assert r.is_stale(old, 6, now=NOW)
    assert r.is_stale({"generated_utc": "garbage"}, 6, now=NOW)
    assert r.is_stale({}, 6, now=NOW)


def test_dry_run_cli_touches_nothing(tmp_path, capsys):
    import json

    prev, cur = tmp_path / "prev.json", tmp_path / "cur.json"
    prev.write_text(json.dumps(card()), encoding="utf-8")
    now_card = card(approval=0.9)
    now_card["generated_utc"] = datetime.now(timezone.utc).isoformat()
    cur.write_text(json.dumps(now_card), encoding="utf-8")
    assert r.main(["--previous", str(prev), "--current", str(cur), "--repo", REPO,
                   "--before-sha", "a" * 40, "--after-sha", "b" * 40, "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "Regression check: open" in out
    assert "approval_gate" in out
