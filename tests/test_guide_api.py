"""The console's help chat: /api/guide answers with the configured model, grounded in
prompts/guide.md, and says plainly when there is no model so the console can fall back
to its written answers."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "webapp" / "backend"))

import main
import pytest
from fastapi.testclient import TestClient

import llm


class _FakeModel:
    available = True

    def __init__(self):
        self.calls = []

    def complete(self, system, user, agent="orchestrator"):
        self.calls.append((system, user, agent))
        return "The agents may spend up to €500 on their own."


@pytest.fixture
def client():
    return TestClient(main.app)


def test_no_model_says_so(client, monkeypatch):
    monkeypatch.setattr(llm, "get_llm", lambda: llm._StubLLM())
    r = client.post("/api/guide", json={"question": "What does this do?"}).json()
    assert r == {"ok": False, "reason": "no-model"}


def test_answers_from_the_guide_prompt(client, monkeypatch):
    fake = _FakeModel()
    monkeypatch.setattr(llm, "get_llm", lambda: fake)
    r = client.post("/api/guide", json={
        "question": "Why did it stop?",
        "history": [{"role": "user", "text": "hi"}, {"role": "assistant", "text": "hello"}],
    }).json()
    assert r["ok"] is True and "€500" in r["answer"]
    system, user, agent = fake.calls[0]
    assert "€500" in system and "116 hours" in system   # grounded in prompts/guide.md
    assert user.endswith("Visitor: Why did it stop?") and "Guide: hello" in user
    assert agent == "guide"


def test_model_failure_is_not_a_crash(client, monkeypatch):
    class _Broken(_FakeModel):
        def complete(self, *a, **k):
            raise RuntimeError("rate limited")
    monkeypatch.setattr(llm, "get_llm", lambda: _Broken())
    r = client.post("/api/guide", json={"question": "hello"}).json()
    assert r == {"ok": False, "reason": "model-error"}


def test_oversized_requests_are_refused(client, monkeypatch):
    monkeypatch.setattr(llm, "get_llm", lambda: _FakeModel())
    assert client.post("/api/guide", json={"question": "x" * 5000}).status_code == 422
    big = [{"role": "user", "text": "hi"}] * 500
    assert client.post("/api/guide", json={"question": "hi", "history": big}).status_code == 422


def test_decision_channel_is_written_to_the_audit_file(client, monkeypatch):
    import threading
    written = []
    import audit_log
    monkeypatch.setattr(audit_log, "write_event", lambda rid, typ, detail, agent="": written.append((rid, typ, detail, agent)))
    main._decision_ready["RUN-VIA-1"] = threading.Event()
    try:
        r = client.post("/api/decision", json={"decision": "approve", "run_id": "RUN-VIA-1",
                                               "via": "Titan assistant (voice)"}).json()
    finally:
        main._decision_ready.pop("RUN-VIA-1", None)
        main._decision_value.pop("RUN-VIA-1", None)
    assert r["ok"] is True
    assert ("RUN-VIA-1", "decision_channel", {"decision": "approve", "via": "Titan assistant (voice)"}, "human") in written
