"""
Tests for the evaluation harness itself.

A harness that silently drifts is worse than no harness, so the things that would make
the scorecard lie are pinned here: the datasets must stay well formed, the metrics must
compute what they claim, and the offline suite must stay above its floor.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from eval import policy_eval, rag_eval
from eval.metrics import (
    BinaryConfusion,
    SetScore,
    Tally,
    precision_at_k,
    recall_at_k,
    reciprocal_rank,
)
from eval.scenarios import dataset_meta, load_rag_queries, load_scenarios

VALID_RISK = {"HIGH", "LOW", "ESCALATE"}
VALID_STATUS = {"complete", "halted", "escalated"}
VALID_TIER = {"AUTO", "APPROVE", "ESCALATE"}
VALID_AGENTS = {"reliability", "supply_chain", "production", "quality", "compliance_safety"}

# The floor the CI job enforces. Raising it is a deliberate act; the two open findings in
# eval/FINDINGS.md account for the gap between this and 1.0.
OFFLINE_ACCURACY_FLOOR = 0.97


# --- dataset integrity ----------------------------------------------------- #
def test_scenario_ids_are_unique():
    ids = [s.id for s in load_scenarios()]
    assert len(ids) == len(set(ids))


def test_every_scenario_is_well_formed():
    for s in load_scenarios():
        exp = s.expected
        assert exp["risk"] in VALID_RISK, s.id
        assert exp["terminal_status"] in VALID_STATUS, s.id
        assert set(exp["agents_required"]) <= VALID_AGENTS, s.id
        assert isinstance(exp["needs_approval"], bool), s.id
        assert len(exp.get("action_tiers", [])) == len(s.proposed_actions), s.id
        assert set(exp.get("action_tiers", [])) <= VALID_TIER, s.id
        assert set(exp.get("tool_calls") or {}) <= VALID_AGENTS, s.id


def test_expected_labels_are_internally_consistent():
    """An escalating scenario cannot also be labelled complete, and so on. This catches a
    hand-edited label before it quietly changes a headline number."""
    for s in load_scenarios():
        exp = s.expected
        if exp["risk"] == "ESCALATE":
            assert exp["escalates"] is True, s.id
            assert exp["terminal_status"] == "escalated", s.id
            assert exp["agents_required"] == ["reliability"], s.id
        if exp.get("halt"):
            assert exp["terminal_status"] == "halted", s.id
        if exp["risk"] == "HIGH":
            assert set(exp["agents_required"]) == VALID_AGENTS, s.id


def test_expected_tool_calls_name_real_tools():
    from tools import lc

    known = {t.name for group in (lc.RELIABILITY_TOOLS, lc.SUPPLY_CHAIN_TOOLS,
                                  lc.PRODUCTION_TOOLS, lc.QUALITY_TOOLS,
                                  lc.COMPLIANCE_TOOLS) for t in group}
    for s in load_scenarios():
        for agent, tools in (s.expected.get("tool_calls") or {}).items():
            for tool in tools:
                assert tool in known, f"{s.id}/{agent}: unknown tool {tool}"


def test_rag_labels_point_at_real_corpus_sections():
    from rag.index import get_index

    known = {c.citation for c in get_index().chunks}
    for q in load_rag_queries():
        assert q.relevant, q.id
        for citation in q.relevant:
            assert citation in known, f"{q.id}: {citation} is not in the corpus"


def test_dataset_meta_matches_the_files():
    meta = dataset_meta()
    assert meta["scenarios"] == len(load_scenarios())
    assert meta["rag_queries"] == len(load_rag_queries())
    assert meta["rag_direct"] + meta["rag_paraphrase"] == meta["rag_queries"]


def test_the_live_subset_is_not_empty_and_spans_the_paths():
    subset = load_scenarios(live_only=True)
    assert subset
    assert {s.mode for s in subset} >= {"happy", "edge", "escalation"}


# --- metric arithmetic ----------------------------------------------------- #
def test_tally_counts_and_records_misses():
    t = Tally("x")
    t.add(True, "a")
    t.add(False, "b", expected=1, actual=2)
    assert (t.correct, t.total) == (1, 2)
    assert t.accuracy == 0.5
    assert t.misses[0]["case"] == "b"


def test_binary_confusion_separates_the_two_error_types():
    c = BinaryConfusion("halt")
    c.add(True, True)          # caught
    c.add(True, False)         # missed a real halt
    c.add(False, True)         # halted something it should not have
    c.add(False, False)
    assert (c.tp, c.fn, c.fp, c.tn) == (1, 1, 1, 1)
    assert c.precision == 0.5
    assert c.recall == 0.5


def test_set_score_is_micro_averaged():
    s = SetScore("tools")
    s.add({"a", "b"}, {"a"}, "case1")
    s.add({"c"}, {"c", "d"}, "case2")
    assert s.matched == 2
    assert s.recall == pytest.approx(2 / 3)
    assert s.precision == pytest.approx(2 / 3)


def test_recall_at_k_is_any_hit_not_full_coverage():
    assert recall_at_k(["a", "b"], ["b", "z"], 2) == 1.0
    assert recall_at_k(["a", "b"], ["z"], 2) == 0.0
    assert recall_at_k(["a", "b"], ["b"], 1) == 0.0


def test_precision_at_k_and_reciprocal_rank():
    assert precision_at_k(["a", "b", "c", "d"], ["b"], 4) == 0.25
    assert reciprocal_rank(["a", "b", "c"], ["b"]) == 0.5
    assert reciprocal_rank(["a"], ["z"]) == 0.0


# --- the suites themselves ------------------------------------------------- #
def test_offline_policy_suite_stays_above_its_floor():
    result = policy_eval.run()
    assert result["checks"] > 100
    assert result["overall_accuracy"] >= OFFLINE_ACCURACY_FLOOR, (
        f"offline accuracy dropped to {result['overall_accuracy']}: "
        f"{[m['misses'] for m in result['metrics'].values() if m['misses']]}"
    )


def test_the_safety_gate_never_misses_a_real_halt():
    """Recall on the HALT class is the one metric that is not allowed to slip. A false
    positive is an availability cost; a false negative is a safety failure."""
    assert policy_eval.run()["halt_detection"]["recall"] == 1.0


def test_routing_guarantees_hold_on_every_permitted_path():
    result = policy_eval.run()
    routing = result["metrics"]["routing_coverage_all_paths"]
    assert routing["accuracy"] == 1.0, routing["misses"]


def test_retrieval_suite_reports_lexical_without_a_key():
    result = rag_eval.run()
    lexical = result["modes"]["lexical"]
    assert lexical["available"] is True
    assert lexical["recall_at_k"]["recall@4"] >= 0.8


def test_direct_retrieval_split_does_not_regress():
    lexical = rag_eval.run()["modes"]["lexical"]
    assert lexical["by_difficulty"]["direct"]["recall@4"] == 1.0


def test_scorecard_renders_without_a_live_result():
    from eval import scorecard

    md = scorecard.render(policy_eval.run(), rag_eval.run(), None, dataset_meta())
    assert "# Evaluation scorecard" in md
    assert "not run in this pass" in md
