"""
End-to-end tests for the FastAPI backend, driven through real HTTP.

These close a gap that was honestly stated in the README for a while: the Slack approval
path was unit tested at the level of message construction and signature maths, but the
endpoint had never actually received a Slack-shaped request. That is exactly the kind of
integration nobody discovers is broken until it is being demonstrated.

So these post the real payload shape, form-encoded, with a genuine HMAC signature, and
assert the paused run is resolved. No network: the FastAPI TestClient drives the app in
process.
"""
import hashlib
import hmac
import json
import sys
import threading
import time
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "webapp" / "backend"))

import main
import pytest
from fastapi.testclient import TestClient

SIGNING_SECRET = "test-signing-secret"


@pytest.fixture
def client():
    return TestClient(main.app)


@pytest.fixture
def pending_run():
    """Register a run that is waiting at the approval gate, the way /api/run does."""
    run_id = "RUN-TEST-0001"
    event = threading.Event()
    main._decision_ready[run_id] = event
    yield run_id, event
    main._decision_ready.pop(run_id, None)
    main._decision_value.pop(run_id, None)


def _slack_request(client, run_id: str, action: str, secret: str = SIGNING_SECRET,
                   timestamp: str | None = None, user: str = "m.schmidt"):
    """Build and send a request shaped exactly like Slack's interactivity POST."""
    payload = {
        "type": "block_actions",
        "user": {"id": "U123", "username": user},
        "actions": [{"action_id": f"tos_{action}", "type": "button",
                     "value": f"{action}::{run_id}"}],
    }
    body = urllib.parse.urlencode({"payload": json.dumps(payload)}).encode()
    ts = timestamp or str(int(time.time()))
    signature = "v0=" + hmac.new(secret.encode(),
                                 b"v0:" + ts.encode() + b":" + body,
                                 hashlib.sha256).hexdigest()
    return client.post(
        "/api/slack/interactions",
        content=body,
        headers={"Content-Type": "application/x-www-form-urlencoded",
                 "X-Slack-Request-Timestamp": ts,
                 "X-Slack-Signature": signature},
    )


# --- health ---------------------------------------------------------------- #
def test_health_reports_what_is_actually_wired_up(client):
    body = client.get("/api/health").json()
    assert body["ok"] is True
    assert body["policy"]["cost_ceiling_eur"] == 500
    assert body["retrieval"]["documents"] >= 10
    assert body["approval"]["active"] in {"console", "slack", "email"}


# --- the Slack approval path, end to end ----------------------------------- #
def test_a_signed_slack_approve_resolves_the_paused_run(client, pending_run, monkeypatch):
    run_id, event = pending_run
    monkeypatch.setenv("SLACK_SIGNING_SECRET", SIGNING_SECRET)

    response = _slack_request(client, run_id, "approve")

    assert response.status_code == 200
    assert "APPROVE" in response.json()["text"]
    assert event.is_set(), "the graph was never released"
    assert main._decision_value[run_id] == "approve"


def test_a_signed_slack_reject_resolves_the_run_as_a_rejection(client, pending_run,
                                                               monkeypatch):
    run_id, event = pending_run
    monkeypatch.setenv("SLACK_SIGNING_SECRET", SIGNING_SECRET)

    _slack_request(client, run_id, "reject")

    assert event.is_set()
    assert main._decision_value[run_id] == "reject"


def test_the_deciding_user_is_named_back_into_the_channel(client, pending_run, monkeypatch):
    """Who approved a spend is the point of an audit trail, so it goes back into Slack."""
    run_id, _ = pending_run
    monkeypatch.setenv("SLACK_SIGNING_SECRET", SIGNING_SECRET)

    text = _slack_request(client, run_id, "approve", user="plant.manager").json()["text"]
    assert "plant.manager" in text
    assert run_id in text


def test_an_unsigned_request_cannot_approve_a_spend(client, pending_run, monkeypatch):
    """Without this the endpoint is a URL that authorises money."""
    run_id, event = pending_run
    monkeypatch.setenv("SLACK_SIGNING_SECRET", SIGNING_SECRET)

    body = urllib.parse.urlencode({"payload": json.dumps(
        {"actions": [{"value": f"approve::{run_id}"}], "user": {"username": "attacker"}})}
    ).encode()
    response = client.post("/api/slack/interactions", content=body,
                           headers={"Content-Type": "application/x-www-form-urlencoded"})

    assert "Signature verification failed" in response.json()["text"]
    assert not event.is_set()


def test_a_wrongly_signed_request_is_rejected(client, pending_run, monkeypatch):
    run_id, event = pending_run
    monkeypatch.setenv("SLACK_SIGNING_SECRET", SIGNING_SECRET)

    _slack_request(client, run_id, "approve", secret="the-wrong-secret")
    assert not event.is_set()


def test_a_replayed_request_is_rejected(client, pending_run, monkeypatch):
    """A correctly signed request captured and resent hours later must not still work."""
    run_id, event = pending_run
    monkeypatch.setenv("SLACK_SIGNING_SECRET", SIGNING_SECRET)

    _slack_request(client, run_id, "approve", timestamp="1600000000")
    assert not event.is_set()


def test_no_signing_secret_means_no_slack_approvals(client, pending_run, monkeypatch):
    """Fail closed. An unconfigured deployment must not accept button presses."""
    run_id, event = pending_run
    monkeypatch.delenv("SLACK_SIGNING_SECRET", raising=False)

    _slack_request(client, run_id, "approve")
    assert not event.is_set()


def test_a_click_on_a_stale_message_does_not_resolve_a_different_run(client, monkeypatch):
    """The button carries its own run id, so a late click on yesterday's message must not
    approve whatever happens to be pending now."""
    monkeypatch.setenv("SLACK_SIGNING_SECRET", SIGNING_SECRET)
    current = "RUN-CURRENT"
    event = threading.Event()
    main._decision_ready[current] = event
    try:
        response = _slack_request(client, "RUN-FROM-YESTERDAY", "approve")
        assert "no longer waiting" in response.json()["text"]
        assert not event.is_set(), "a stale click approved the wrong run"
    finally:
        main._decision_ready.pop(current, None)
        main._decision_value.pop(current, None)


# --- the email link path --------------------------------------------------- #
def test_an_email_link_resolves_the_run(client, pending_run):
    run_id, event = pending_run
    response = client.get("/api/decision/link",
                          params={"run_id": run_id, "decision": "approve"})
    assert response.status_code == 200
    assert "Recorded: approve" in response.text
    assert event.is_set()


def test_a_second_click_cannot_flip_a_recorded_decision(client, pending_run):
    """Regression guard. A run stayed writable from the moment it paused until it
    finished, so approving in the email and then clicking reject changed the recorded
    decision after the fact. An approval over money is write-once."""
    run_id, _ = pending_run
    client.get("/api/decision/link", params={"run_id": run_id, "decision": "approve"})

    second = client.get("/api/decision/link",
                        params={"run_id": run_id, "decision": "reject"})

    assert "already" in second.text.lower()
    assert main._decision_value[run_id] == "approve", "the first decision was overwritten"


def test_slack_cannot_flip_a_decision_made_in_the_console(client, pending_run, monkeypatch):
    """The three channels share one write-once resolver, so they cannot fight."""
    run_id, _ = pending_run
    monkeypatch.setenv("SLACK_SIGNING_SECRET", SIGNING_SECRET)
    client.post("/api/decision", json={"run_id": run_id, "decision": "reject"})

    response = _slack_request(client, run_id, "approve")

    assert "already" in response.json()["text"].lower()
    assert main._decision_value[run_id] == "reject"


# --- the console path ------------------------------------------------------ #
def test_the_console_endpoint_resolves_the_same_run(client, pending_run):
    run_id, event = pending_run
    body = client.post("/api/decision",
                       json={"run_id": run_id, "decision": "approve"}).json()
    assert body["ok"] is True
    assert body["decision"] == "approve"
    assert event.is_set()


def test_deciding_with_nothing_pending_is_reported_not_crashed(client):
    body = client.post("/api/decision",
                       json={"run_id": "RUN-NOPE", "decision": "approve"}).json()
    assert body["ok"] is False


def test_all_three_channels_share_one_resume_path():
    """The property that makes the audit trail meaningful: however a decision arrives, it
    is recorded the same way."""
    import inspect

    for route in ("decision", "decision_link", "slack_interactions"):
        source = inspect.getsource(getattr(main, route))
        assert "_resolve(" in source, f"{route} does not go through the shared resolver"
