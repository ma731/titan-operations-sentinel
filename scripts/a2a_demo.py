"""
Another agent delegating to Titan over A2A: read the Agent Card, send three tasks.
In-process (no server to start), no model, no key.

    python scripts/a2a_demo.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "webapp" / "backend")]

import main  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


def ask(client, text):
    body = {"jsonrpc": "2.0", "id": "1", "method": "message/send",
            "params": {"message": {"role": "user", "messageId": "m", "parts": [{"kind": "text", "text": text}]}}}
    r = client.post("/a2a", json=body).json()["result"]
    reply = r["artifacts"][0]["parts"][0]["text"] if r.get("artifacts") else r["status"]["message"]["parts"][0]["text"]
    skill = r["artifacts"][0]["name"] if r.get("artifacts") else "-"
    print(f"\n> {text}\n  [{r['status']['state']}, skill: {skill}]\n  {reply}")


def main_() -> int:
    c = TestClient(main.app)
    card = c.get("/.well-known/agent-card.json").json()
    print(f"Found agent: {card['name']} (A2A {card['protocolVersion']}), skills: {', '.join(s['id'] for s in card['skills'])}")
    for q in ["Our steel supplier Ovako just had a furnace outage. What is exposed?",
              "Is it safe to bypass the guard interlock on CNC-07 to finish the batch?",
              "What does CNC-07-LEI depend on?"]:
        ask(c, q)
    return 0


if __name__ == "__main__":
    raise SystemExit(main_())
