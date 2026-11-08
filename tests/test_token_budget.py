"""Offline guards for the transcript token-budget caps.

The 6-agent transcript is re-sent to every later agent and on every routing call, so its
size dominates token spend on the Groq free tier. These tests pin the clipping behaviour
and assert the caps actually shrink a realistic full run, so the optimisation can't be
silently removed. No model or API key needed.

Requires the declared deps (langgraph) to import `graph`. Run: python -m pytest tests/
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import graph  # noqa: E402


def test_clip_leaves_short_text_untouched():
    assert graph._clip("short", 1000) == "short"
    assert graph._clip("anything", None) == "anything"   # no limit = no change


def test_clip_truncates_and_marks_long_text():
    out = graph._clip("X" * 5000, 100)
    assert out.endswith("…[trimmed]")
    assert len(out) < 200                                  # ~limit + marker, not 5000


def test_conversation_respects_per_message_cap():
    state = {"transcript": [{"agent": "reliability", "message": "Y" * 5000}]}
    full = graph._conversation(state)                      # default: no cap
    capped = graph._conversation(state, per_msg=300)
    assert len(capped) < len(full)
    assert "[reliability]:" in capped                      # label preserved


def _full_run_transcript_chars(store_cap, peer_cap, route_cap):
    """Sum the transcript chars sent to the model across one HIGH-risk run:
    5 agent-task reads + 2 routing reads + 1 synthesis read."""
    order = ["reliability", "supply_chain", "production", "quality", "compliance_safety"]
    raw = "X" * 3500                                       # a verbose ReAct reply
    total, reports = 0, []

    def state():
        return {"transcript": [{"agent": a, "message": m} for a, m in reports]}

    for name in order:
        total += len(graph._conversation(state(), per_msg=peer_cap))
        if name in ("reliability", "supply_chain"):       # routing fires when >=2 allowed
            total += len(graph._conversation(state(), per_msg=route_cap))
        reports.append((name, graph._clip(raw, store_cap) if store_cap else raw))
    total += len(graph._conversation(state(), per_msg=peer_cap))
    return total


def test_caps_cut_full_run_transcript_by_at_least_half():
    before = _full_run_transcript_chars(None, None, None)
    # The shipped defaults; a .env may raise them for a verbose model on purpose.
    after = _full_run_transcript_chars(
        graph.DEFAULT_REPORT_STORE_CHARS, graph.DEFAULT_PEER_REPORT_CHARS, graph.ROUTE_DIGEST_CHARS)
    assert after < before
    assert (before - after) / before >= 0.5               # measured ~62% on 3.5k reports
