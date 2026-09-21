"""
Shared test fixtures.

The important one is `isolate_case_library`. `graph.synthesize()` writes every finished
run into data/memory/case_library.json, which is a committed data file that real runs
read back through `recall_similar_cases`. Any test that exercises synthesize() therefore
appended a fake case to it, permanently, on every run: the file had accumulated twenty
copies of a case called RUN-R-TEST before this fixture existed.

That is not only untidy. Case memory is an input to the reliability agent, so a test
suite that writes to it is a test suite that changes what the system recalls in
production.
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

REAL_LIBRARY = Path(__file__).resolve().parents[1] / "data" / "memory" / "case_library.json"


@pytest.fixture(autouse=True)
def isolate_case_library(tmp_path, monkeypatch):
    """Point case-memory writes at a per-test copy of the real library.

    A copy rather than an empty file, so tests that read precedent still see the seeded
    incidents. Autouse, because the leak came from a test that never mentioned case
    memory at all: it just happened to call synthesize()."""
    import tools.recall_cases as rc

    sandbox = tmp_path / "case_library.json"
    try:
        sandbox.write_text(REAL_LIBRARY.read_text(encoding="utf-8"), encoding="utf-8")
    except OSError:
        sandbox.write_text(json.dumps({"cases": []}), encoding="utf-8")

    monkeypatch.setattr(rc, "_LIB", sandbox)
    monkeypatch.setattr(rc, "_OUTCOMES", tmp_path / "outcomes.json")
    yield sandbox


@pytest.fixture(autouse=True)
def isolate_audit_log(tmp_path, monkeypatch):
    """Keep the JSONL audit trail out of logs/ during tests, for the same reason."""
    import audit_log

    monkeypatch.setattr(audit_log, "LOG_DIR", tmp_path / "logs")
    monkeypatch.setattr(audit_log, "LOG_FILE", tmp_path / "logs" / "tos_audit.jsonl")
    yield
