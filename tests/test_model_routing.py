"""Model routing (decision 011): routine steps on a small model, money and safety on the main one."""
import inspect

import llm
import observability


def test_routing_is_off_unless_a_small_model_is_set(monkeypatch):
    monkeypatch.delenv("TOS_MODEL_SMALL", raising=False)
    monkeypatch.setenv("TOS_MODEL", "azure_openai:gpt-4.1")
    assert all(llm.route_for(a) == "large" for a in ["supervisor", "production", "quality", "supply_chain"])
    assert llm.model_for("production") == "azure_openai:gpt-4.1"
    assert llm.routing()["enabled"] is False


def test_routine_steps_go_small_and_money_safety_and_the_plan_stay_large(monkeypatch):
    monkeypatch.setenv("TOS_MODEL", "azure_openai:gpt-4.1")
    monkeypatch.setenv("TOS_MODEL_SMALL", "azure_openai:gpt-4.1-mini")
    for a in ["supervisor", "production", "quality"]:
        assert llm.model_for(a) == "azure_openai:gpt-4.1-mini", a
    for a in ["reliability", "supply_chain", "compliance_safety", "orchestrator"]:
        assert llm.model_for(a) == "azure_openai:gpt-4.1", a


def test_prices_follow_the_model_inside_free_text_deployment_names():
    assert observability.price_for("azure_openai:prod-gpt-4o-mini-eu") == (0.14, 0.55)
    assert observability.price_for("azure_openai:gpt-4.1-mini") == (0.37, 1.47)
    assert observability.price_for("azure_openai:gpt-4.1") == (1.84, 7.36)
    assert observability.price_for("groq:llama-3.3-70b-versatile") == (0.0, 0.0)
    assert observability.price_for("azure_openai:my-chat") == observability.PRICE_EUR_PER_M["azure_openai"]


def _usage():
    u = observability.RunUsage(provider="azure_openai")
    for name, (pin, pout) in {"supervisor": (4000, 200), "production": (9000, 900), "quality": (7000, 700),
                              "supply_chain": (15000, 1500), "orchestrator": (8000, 1200)}.items():
        a = u.agent(name)
        a.prompt_tokens, a.completion_tokens = pin, pout
    return u


def test_cost_per_run_drops_when_routing_is_on(monkeypatch):
    monkeypatch.setenv("TOS_MODEL", "azure_openai:gpt-4.1")
    monkeypatch.delenv("TOS_MODEL_SMALL", raising=False)
    one_model = _usage().cost_eur()
    monkeypatch.setenv("TOS_MODEL_SMALL", "azure_openai:gpt-4.1-mini")
    routed = _usage()
    assert routed.cost_eur() < one_model
    d = routed.to_dict()
    assert d["routing"]["enabled"] and d["by_agent"]["production"]["model"] == "azure_openai:gpt-4.1-mini"
    assert d["by_agent"]["supply_chain"]["model"] == "azure_openai:gpt-4.1"


def test_the_supervisor_route_call_is_labelled_so_it_can_be_routed():
    import graph
    assert 'agent="supervisor"' in inspect.getsource(graph._llm_route)


def test_agents_are_built_on_their_routed_model():
    from agents import factory
    assert "route_for(name)" in inspect.getsource(factory.build_agents)
