"""
Tests for the out-of-app approval channels.

Offline: message construction and channel selection are tested, delivery is not. Nothing
here opens a socket, and the tests clear the relevant environment so a developer with a
real SLACK_BOT_TOKEN in their shell does not accidentally post to a channel.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from integrations import approval

ENV_KEYS = ["TOS_APPROVAL_CHANNEL", "SLACK_BOT_TOKEN", "SLACK_APPROVAL_CHANNEL",
            "SLACK_SIGNING_SECRET", "SMTP_HOST", "TOS_APPROVER_EMAIL", "TOS_PUBLIC_URL"]

ALERT = {"alert_id": "ALT-22847", "machine_id": "CNC-07-LEI", "plant_id": "LEI",
         "sensor": "vibration", "value": 7.2, "unit": "mm/s_RMS", "threshold": 6.0}


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for key in ENV_KEYS:
        monkeypatch.delenv(key, raising=False)


# --- channel selection ----------------------------------------------------- #
def test_console_is_the_fallback_with_nothing_configured():
    assert approval.approval_channels()["active"] == "console"


def test_slack_is_picked_when_configured(monkeypatch):
    monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-test")
    monkeypatch.setenv("SLACK_APPROVAL_CHANNEL", "#ops-approvals")
    assert approval.approval_channels()["active"] == "slack"


def test_email_is_picked_when_only_smtp_is_configured(monkeypatch):
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("TOS_APPROVER_EMAIL", "manager@example.com")
    assert approval.approval_channels()["active"] == "email"


def test_an_explicit_channel_overrides_detection(monkeypatch):
    monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-test")
    monkeypatch.setenv("SLACK_APPROVAL_CHANNEL", "#ops")
    monkeypatch.setenv("TOS_APPROVAL_CHANNEL", "console")
    assert approval.approval_channels()["active"] == "console"


# --- Slack message --------------------------------------------------------- #
def test_slack_blocks_carry_the_run_id_on_both_buttons():
    """A late click on an old message must resolve the run it belongs to, not whatever
    happens to be pending now."""
    blocks = approval.slack_blocks("RUN-123", ALERT, 3200, "over the ceiling")
    actions = [b for b in blocks if b["type"] == "actions"][0]
    values = [e["value"] for e in actions["elements"]]
    assert values == ["approve::RUN-123", "reject::RUN-123"]
    assert actions["block_id"].endswith("RUN-123")


def test_slack_blocks_are_json_serialisable():
    json.dumps(approval.slack_blocks("RUN-1", ALERT, 3200, "reason"))


def test_the_approve_button_asks_for_confirmation():
    blocks = approval.slack_blocks("RUN-1", ALERT, 3200, "reason")
    approve = [b for b in blocks if b["type"] == "actions"][0]["elements"][0]
    assert "confirm" in approve
    assert "3,200" in approve["confirm"]["text"]["text"]


def test_an_uncosted_option_is_labelled_not_zeroed():
    blocks = approval.slack_blocks("RUN-1", ALERT, None, "quote pending")
    text = json.dumps(blocks)
    assert "uncosted" in text
    assert "EUR 0" not in text


# --- email message --------------------------------------------------------- #
def test_email_body_contains_both_decision_links_with_the_run_id(monkeypatch):
    monkeypatch.setenv("TOS_PUBLIC_URL", "https://tos.example.com/")
    body = approval.email_body("RUN-9", ALERT, 3200, "over the ceiling")
    assert "https://tos.example.com/api/decision/link?run_id=RUN-9&decision=approve" in body
    assert "https://tos.example.com/api/decision/link?run_id=RUN-9&decision=reject" in body


def test_email_body_states_that_nothing_is_committed_yet():
    body = approval.email_body("RUN-9", ALERT, 3200, "reason")
    assert "not made until you choose" in body


# --- the caller-facing entry point ----------------------------------------- #
def test_request_approval_returns_the_default_without_blocking(capsys):
    assert approval.request_approval("RUN-1", ALERT, default="reject") == "reject"
    assert "RUN-1" in capsys.readouterr().out


def test_send_approval_request_never_raises_on_a_bad_slack_config(monkeypatch):
    """A notification failure must not take the approval gate down with it."""
    monkeypatch.setenv("TOS_APPROVAL_CHANNEL", "slack")
    result = approval.send_approval_request("RUN-1", ALERT, 3200, "reason")
    assert result["sent"] is False
    assert result["channel"] == "slack"


# --- backend signature verification ---------------------------------------- #
def test_slack_signature_rejects_an_unsigned_request(monkeypatch):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "webapp" / "backend"))
    import main

    monkeypatch.delenv("SLACK_SIGNING_SECRET", raising=False)
    assert main._slack_signature_valid(b"body", "1750000000", "v0=deadbeef") is False


def test_slack_signature_accepts_a_correctly_signed_request(monkeypatch):
    import hashlib
    import hmac
    import time

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "webapp" / "backend"))
    import main

    secret = "test-signing-secret"
    monkeypatch.setenv("SLACK_SIGNING_SECRET", secret)
    body = b"payload=%7B%7D"
    ts = str(int(time.time()))
    sig = "v0=" + hmac.new(secret.encode(), b"v0:" + ts.encode() + b":" + body,
                           hashlib.sha256).hexdigest()
    assert main._slack_signature_valid(body, ts, sig) is True


def test_slack_signature_rejects_a_replayed_request(monkeypatch):
    import hashlib
    import hmac

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "webapp" / "backend"))
    import main

    secret = "test-signing-secret"
    monkeypatch.setenv("SLACK_SIGNING_SECRET", secret)
    body = b"payload=%7B%7D"
    stale = "1600000000"        # well outside the five minute window
    sig = "v0=" + hmac.new(secret.encode(), b"v0:" + stale.encode() + b":" + body,
                           hashlib.sha256).hexdigest()
    assert main._slack_signature_valid(body, stale, sig) is False
