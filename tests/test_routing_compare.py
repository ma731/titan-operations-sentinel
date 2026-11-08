"""The routing comparison: verdict rules and the report, on made-up suite results (no model)."""
from eval import routing_compare as rc


def suite(cost, acc=1.0, errors=0, cite=1.0):
    return {"runs": 8, "errors": errors,
            "efficiency": {"estimated_cost_eur_per_run": cost, "tokens_per_run": 35000, "seconds_per_run": 40.0},
            "metrics": {k: {"accuracy": acc} for k in rc.QUALITY},
            "tool_call_correctness": {"f1": 1.0, "recall": 1.0},
            "grounding": {"citation_rate": cite, "numeric_groundedness": 1.0}}


def test_keep_routing_only_when_cheaper_and_nothing_drops():
    c = rc.compare(suite(0.08), suite(0.05))
    assert c["verdict"].startswith("Keep") and c["cost_per_run"]["saving_pct"] == 37.5


def test_a_quality_drop_vetoes_the_saving():
    c = rc.compare(suite(0.08), suite(0.03, acc=0.875))
    assert c["verdict"].startswith("Do not keep") and "routing_coverage" in c["drops"]
    c = rc.compare(suite(0.08), suite(0.03, cite=0.5))
    assert "citation_rate" in c["drops"]


def test_not_cheaper_or_errors_also_veto():
    assert rc.compare(suite(0.05), suite(0.06))["verdict"].startswith("Do not keep")
    assert "errors" in rc.compare(suite(0.08), suite(0.05, errors=1))["verdict"]


def test_report_states_models_and_verdict():
    info = {"large": "azure_openai:gpt-4.1", "small": "azure_openai:gpt-4.1-mini"}
    md = rc.report(suite(0.08), suite(0.05), info)
    assert "gpt-4.1-mini" in md and "Keep routing" in md and "| cost per run | EUR 0.0800 | EUR 0.0500 |" in md


def test_preflight_never_prints_the_key(monkeypatch, capsys):
    monkeypatch.setenv("TOS_MODEL", "azure_openai:gpt-4.1")
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "sk-very-secret-value")
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://res.openai.azure.com/")
    rc.main([])
    out = capsys.readouterr().out
    assert "sk-very-secret-value" not in out and "AZURE_OPENAI_API_KEY: set" in out


def test_metric_names_match_what_the_live_suite_reports():
    """The comparison must read the live suite's real metric names, or it compares nothing."""
    import inspect

    from eval import live_eval
    src = inspect.getsource(live_eval)
    for k in rc.QUALITY:
        assert f'"{k}"' in src, k
