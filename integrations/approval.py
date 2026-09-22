"""
Reaching a human who is not sitting in front of the web console.

Three channels, picked in the order they are configured: Slack (Block Kit buttons, the
callback is signature verified), email (SMTP with two links), or console. All of them
resolve through the same /api/decision path the console uses, so a run has one resume
path and one audit record however the answer arrived.

Nothing here decides anything. It carries a question out and an answer back.

Config is all optional, all environment: TOS_APPROVAL_CHANNEL, TOS_PUBLIC_URL,
SLACK_BOT_TOKEN, SLACK_APPROVAL_CHANNEL, SLACK_SIGNING_SECRET, SMTP_*, TOS_APPROVER_EMAIL.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request

DEFAULT_PUBLIC_URL = "http://localhost:8000"
TIMEOUT_SECONDS = 10


def _public_url() -> str:
    return os.getenv("TOS_PUBLIC_URL", DEFAULT_PUBLIC_URL).rstrip("/")


def slack_configured() -> bool:
    return bool(os.getenv("SLACK_BOT_TOKEN") and os.getenv("SLACK_APPROVAL_CHANNEL"))


def email_configured() -> bool:
    return bool(os.getenv("SMTP_HOST") and os.getenv("TOS_APPROVER_EMAIL"))


def approval_channels() -> dict:
    """What is wired up right now. Surfaced by the backend health endpoint so a demo can
    show the channel is real rather than claimed."""
    configured = os.getenv("TOS_APPROVAL_CHANNEL", "auto").lower()
    return {
        "configured": configured,
        "slack": slack_configured(),
        "email": email_configured(),
        "public_url": _public_url(),
        "active": _pick_channel(),
    }


def _pick_channel() -> str:
    forced = os.getenv("TOS_APPROVAL_CHANNEL", "auto").lower()
    if forced in {"slack", "email", "console"}:
        return forced
    if slack_configured():
        return "slack"
    if email_configured():
        return "email"
    return "console"


# --------------------------------------------------------------------------- #
# Message construction
# --------------------------------------------------------------------------- #
def _summary(alert: dict, cost_eur: float | None, reason: str) -> str:
    machine = alert.get("machine_id", "unknown machine")
    value = alert.get("value")
    unit = alert.get("unit", "")
    cost = f"EUR {cost_eur:,.0f}" if cost_eur else "an uncosted option"
    return (f"{machine} is reading {value}{unit} and the recommended response commits "
            f"{cost}. {reason}")


def slack_blocks(run_id: str, alert: dict, cost_eur: float | None, reason: str,
                 deadline: str | None = None) -> list[dict]:
    """Block Kit payload. Both buttons carry the run id, so a late click on an old message
    resolves its own run rather than whatever is pending now."""
    machine = alert.get("machine_id", "unknown")
    fields = [
        {"type": "mrkdwn", "text": f"*Machine*\n{machine}"},
        {"type": "mrkdwn", "text": f"*Plant*\n{alert.get('plant_id', 'LEI')}"},
        {"type": "mrkdwn", "text": f"*Reading*\n{alert.get('value')}{alert.get('unit', '')} "
                                   f"(limit {alert.get('threshold')})"},
        {"type": "mrkdwn", "text": f"*Commitment*\n"
                                   f"{'EUR ' + format(cost_eur, ',.0f') if cost_eur else 'uncosted'}"},
    ]
    blocks = [
        {"type": "header",
         "text": {"type": "plain_text", "text": "Approval needed: emergency response"}},
        {"type": "section", "fields": fields},
        {"type": "section", "text": {"type": "mrkdwn", "text": f"*Why this needs you*\n{reason}"}},
        {"type": "context", "elements": [
            {"type": "mrkdwn",
             "text": f"Run `{run_id}`" + (f" · decide by {deadline}" if deadline else "")}]},
        {"type": "actions", "block_id": f"tos_approval::{run_id}", "elements": [
            {"type": "button", "style": "primary", "action_id": "tos_approve",
             "text": {"type": "plain_text", "text": "Approve"}, "value": f"approve::{run_id}",
             "confirm": {
                 "title": {"type": "plain_text", "text": "Approve this commitment?"},
                 "text": {"type": "mrkdwn", "text": _summary(alert, cost_eur, reason)},
                 "confirm": {"type": "plain_text", "text": "Approve"},
                 "deny": {"type": "plain_text", "text": "Cancel"}}},
            {"type": "button", "style": "danger", "action_id": "tos_reject",
             "text": {"type": "plain_text", "text": "Reject"}, "value": f"reject::{run_id}"},
        ]},
    ]
    return blocks


def email_body(run_id: str, alert: dict, cost_eur: float | None, reason: str) -> str:
    base = _public_url()
    approve = f"{base}/api/decision/link?run_id={urllib.parse.quote(run_id)}&decision=approve"
    reject = f"{base}/api/decision/link?run_id={urllib.parse.quote(run_id)}&decision=reject"
    return (
        "Titan Operations Sentinel needs a decision.\n\n"
        f"{_summary(alert, cost_eur, reason)}\n\n"
        f"Machine:   {alert.get('machine_id')}\n"
        f"Plant:     {alert.get('plant_id', 'LEI')}\n"
        f"Reading:   {alert.get('value')}{alert.get('unit', '')} "
        f"(limit {alert.get('threshold')})\n"
        f"Run id:    {run_id}\n\n"
        f"Approve:   {approve}\n"
        f"Reject:    {reject}\n\n"
        "This request was generated automatically. The commitment is not made until you "
        "choose, and your choice is recorded in the run audit log.\n"
    )


# --------------------------------------------------------------------------- #
# Sending
# --------------------------------------------------------------------------- #
def _post_json(url: str, payload: dict, headers: dict) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={
        "Content-Type": "application/json; charset=utf-8", **headers})
    with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:
        return json.loads(resp.read().decode("utf-8"))


def send_slack(run_id: str, alert: dict, cost_eur: float | None, reason: str) -> dict:
    try:
        result = _post_json(
            "https://slack.com/api/chat.postMessage",
            {"channel": os.environ["SLACK_APPROVAL_CHANNEL"],
             "text": f"Approval needed for {alert.get('machine_id', 'a machine')} "
                     f"(run {run_id})",
             "blocks": slack_blocks(run_id, alert, cost_eur, reason)},
            {"Authorization": f"Bearer {os.environ['SLACK_BOT_TOKEN']}"},
        )
        return {"channel": "slack", "sent": bool(result.get("ok")),
                "error": result.get("error"), "ts": result.get("ts")}
    except (urllib.error.URLError, KeyError, ValueError, TimeoutError) as exc:
        return {"channel": "slack", "sent": False, "error": str(exc)[:200]}


def send_email(run_id: str, alert: dict, cost_eur: float | None, reason: str) -> dict:
    import smtplib
    from email.message import EmailMessage

    try:
        msg = EmailMessage()
        msg["Subject"] = (f"Approval needed: {alert.get('machine_id', 'machine')} "
                          f"emergency response")
        msg["From"] = os.getenv("SMTP_FROM", os.environ["SMTP_USER"])
        msg["To"] = os.environ["TOS_APPROVER_EMAIL"]
        msg.set_content(email_body(run_id, alert, cost_eur, reason))

        host = os.environ["SMTP_HOST"]
        port = int(os.getenv("SMTP_PORT", "587"))
        with smtplib.SMTP(host, port, timeout=TIMEOUT_SECONDS) as s:
            s.starttls()
            if os.getenv("SMTP_USER"):
                s.login(os.environ["SMTP_USER"], os.environ["SMTP_PASSWORD"])
            s.send_message(msg)
        return {"channel": "email", "sent": True}
    except Exception as exc:  # noqa: BLE001 — SMTP raises a wide family
        return {"channel": "email", "sent": False, "error": str(exc)[:200]}


def send_approval_request(run_id: str, alert: dict, cost_eur: float | None = None,
                          reason: str = "") -> dict:
    """Push the approval request to whichever channel is configured. Never raises."""
    reason = reason or "The commitment is above the autonomous ceiling."
    channel = _pick_channel()
    if channel == "slack":
        return send_slack(run_id, alert, cost_eur, reason)
    if channel == "email":
        return send_email(run_id, alert, cost_eur, reason)
    print("\n[approval] " + _summary(alert, cost_eur, reason))
    print(f"[approval] run {run_id}: resolve at "
          f"{_public_url()}/api/decision (or set TOS_APPROVAL_CHANNEL)")
    return {"channel": "console", "sent": True}


def request_approval(run_id: str, alert: dict, default: str = "reject",
                     cost_eur: float | None = None, reason: str = "") -> str:
    """Send the request and return a decision.

    Returns `default` immediately rather than blocking an unattended loop. In a real
    deployment the click resolves the graph through /api/decision and this return value
    is never used, which is why the backend owns the resume path.
    """
    send_approval_request(run_id, alert, cost_eur, reason)
    return default
