"""Loading and typing for the labelled evaluation datasets."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

CASES_DIR = Path(__file__).parent / "cases"
SCENARIOS_PATH = CASES_DIR / "scenarios.json"
RAG_QUERIES_PATH = CASES_DIR / "rag_queries.json"


@dataclass
class Scenario:
    id: str
    title: str
    challenges: list[int]
    mode: str
    in_live_subset: bool
    alert: dict
    fixture: dict
    expected: dict

    @property
    def readings(self) -> dict:
        return self.fixture.get("readings") or {}

    @property
    def telemetry_status(self) -> str:
        return self.fixture.get("telemetry_status") or "OK"

    @property
    def sourcing(self) -> dict | None:
        return self.fixture.get("sourcing")

    @property
    def proposed_actions(self) -> list[str]:
        return self.fixture.get("proposed_actions") or []

    @property
    def routing_probe(self) -> dict | None:
        return self.fixture.get("routing_probe")

    def evidence_blob(self) -> str:
        """The lowercased tool-output text the policy layer sees for telemetry health.

        The graph builds this from the concatenated ToolMessage contents of the agent's
        run. Reproducing it here from the labelled telemetry status keeps the offline
        evaluation faithful to the real code path without needing a model to produce it."""
        status = self.telemetry_status.upper()
        if status == "INTERRUPTED":
            return '{"sensor_status": "interrupted", "sensor_status_detail": "feed dropped mid-window"}'
        if status == "DATA_UNAVAILABLE":
            return '{"error": "data_unavailable"}'
        return '{"sensor_status": "ok"}'


@dataclass
class RagQuery:
    id: str
    query: str
    relevant: list[str]
    asked_by: str
    difficulty: str = "direct"    # "direct" | "paraphrase" (see rag_queries.json)


def load_scenarios(path: Path | str = SCENARIOS_PATH, live_only: bool = False) -> list[Scenario]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    out = [
        Scenario(
            id=s["id"], title=s["title"], challenges=s.get("challenges", []),
            mode=s.get("mode", "happy"), in_live_subset=bool(s.get("in_live_subset")),
            alert=s["alert"], fixture=s.get("fixture", {}), expected=s["expected"],
        )
        for s in data["scenarios"]
    ]
    return [s for s in out if s.in_live_subset] if live_only else out


def load_rag_queries(path: Path | str = RAG_QUERIES_PATH) -> list[RagQuery]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return [
        RagQuery(id=q["id"], query=q["query"], relevant=q["relevant"],
                 asked_by=q.get("asked_by", "unknown"),
                 difficulty=q.get("difficulty", "direct"))
        for q in data["queries"]
    ]


def dataset_meta() -> dict:
    scenarios = json.loads(SCENARIOS_PATH.read_text(encoding="utf-8"))
    rag = json.loads(RAG_QUERIES_PATH.read_text(encoding="utf-8"))
    return {
        "scenarios": len(scenarios["scenarios"]),
        "live_subset": sum(1 for s in scenarios["scenarios"] if s.get("in_live_subset")),
        "rag_queries": len(rag["queries"]),
        "rag_direct": sum(1 for q in rag["queries"] if q.get("difficulty", "direct") == "direct"),
        "rag_paraphrase": sum(1 for q in rag["queries"] if q.get("difficulty") == "paraphrase"),
        "scenarios_version": scenarios.get("version"),
        "rag_version": rag.get("version"),
    }
