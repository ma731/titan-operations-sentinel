"""A2A: the Agent Card and message/send, the way another vendor's agent would call Titan."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "webapp" / "backend"))

import main
from fastapi.testclient import TestClient

client = TestClient(main.app)


def send(text=None, data=None, method="message/send"):
    parts = ([{"kind": "text", "text": text}] if text else []) + ([{"kind": "data", "data": data}] if data else [])
    body = {"jsonrpc": "2.0", "id": "1", "method": method,
            "params": {"message": {"role": "user", "messageId": "m1", "parts": parts}}}
    return client.post("/a2a", json=body).json()


def test_agent_card_is_discoverable_on_both_well_known_paths():
    for path in ("/.well-known/agent-card.json", "/.well-known/agent.json"):
        card = client.get(path).json()
        assert card["name"] == "Titan Operations Sentinel" and card["url"].endswith("/a2a")
        assert {s["id"] for s in card["skills"]} == {"plant_triage", "machine_dependencies", "supplier_impact", "screen_action"}


def test_plain_text_is_routed_to_the_right_skill():
    r = send("Ovako has a furnace outage. What is exposed?")["result"]
    assert r["status"]["state"] == "completed" and r["artifacts"][0]["name"] == "supplier_impact"
    assert "CNC-07-LEI" in r["artifacts"][0]["parts"][0]["text"]
    r = send("What does CNC-07-LEI depend on?")["result"]
    assert r["artifacts"][0]["name"] == "machine_dependencies"
    r = send("What needs attention at Leipzig?")["result"]
    assert r["artifacts"][0]["name"] == "plant_triage"


def test_a_safety_question_is_screened_not_acted_on():
    r = send("Is it safe to bypass the guard interlock on CNC-07?")["result"]
    data = r["artifacts"][0]["parts"][1]["data"]
    assert data["safety"]["verdict"] == "HALT" and data["tier"] == "ESCALATE"
    assert "safety officer" in r["artifacts"][0]["parts"][0]["text"]


def test_structured_requests_and_missing_arguments():
    r = send(data={"skill": "supplier_impact", "args": {"supplier_id": "SUP-SCHAEFFLER-DE"}})["result"]
    assert r["status"]["state"] == "completed"
    r = send(data={"skill": "machine_dependencies", "args": {}})["result"]
    assert r["status"]["state"] == "input-required"


def test_unclear_requests_ask_back_and_bad_calls_get_jsonrpc_errors():
    r = send("Tell me a joke")["result"]
    assert r["status"]["state"] == "input-required" and "supplier_impact" in r["status"]["message"]["parts"][0]["text"]
    assert send("hi", method="tasks/cancel")["error"]["code"] == -32601
    assert client.post("/a2a", json={"jsonrpc": "2.0", "id": 2, "method": "message/send", "params": {"message": {}}}).json()["error"]["code"] == -32602
