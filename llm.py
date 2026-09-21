"""
LLM factory for Titan Operations Sentinel — provider-agnostic, swap in one line.

Switching providers is deliberately trivial (free tiers hit limits, so you WILL switch):
  • Set TOS_MODEL="provider:model" in .env, OR
  • Just drop a different provider's API key in .env — the factory AUTO-DETECTS the
    first provider below whose key is present (priority order) and uses it.

Supported providers (install the matching package — the common ones are in requirements.txt):
  google_genai : GOOGLE_API_KEY / GEMINI_API_KEY        langchain-google-genai
  groq         : GROQ_API_KEY                            langchain-groq
  openrouter   : OPENROUTER_API_KEY  (ONE key, many FREE models — best for limits)  langchain-openai
  openai       : OPENAI_API_KEY                          langchain-openai
  anthropic    : ANTHROPIC_API_KEY                       langchain-anthropic
  mistralai    : MISTRAL_API_KEY                         langchain-mistralai
  ollama       : (local, no key)                         langchain-ollama + `ollama serve`

If no provider is reachable we fall back to a deterministic templated stub so the graph,
tools, and tests still run end-to-end offline (CI / development).
"""
from __future__ import annotations

import os
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()

# Ordered by auto-detect priority (first present key wins when TOS_MODEL is unset).
PROVIDERS = [
    {"id": "google_genai", "keys": ["GOOGLE_API_KEY", "GEMINI_API_KEY"], "default": "gemini-2.5-flash",
     "pip": "langchain-google-genai", "note": "free tier, low RPM"},
    {"id": "groq", "keys": ["GROQ_API_KEY"], "default": "llama-3.3-70b-versatile",
     "pip": "langchain-groq", "note": "fast, daily token cap"},
    {"id": "openrouter", "keys": ["OPENROUTER_API_KEY"], "default": "meta-llama/llama-3.3-70b-instruct:free",
     "pip": "langchain-openai", "note": "ONE key, many free models — best when limits bite"},
    {"id": "azure_openai", "keys": ["AZURE_OPENAI_API_KEY"], "default": "gpt-4o-mini",
     "pip": "langchain-openai", "note": "Azure credits — paid-tier limits, no throttling"},
    {"id": "openai", "keys": ["OPENAI_API_KEY"], "default": "gpt-4o-mini",
     "pip": "langchain-openai", "note": "paid"},
    {"id": "anthropic", "keys": ["ANTHROPIC_API_KEY"], "default": "claude-haiku-4-5",
     "pip": "langchain-anthropic", "note": "paid"},
    {"id": "mistralai", "keys": ["MISTRAL_API_KEY"], "default": "mistral-small-latest",
     "pip": "langchain-mistralai", "note": "free tier"},
]
PROVIDER_BY_ID = {p["id"]: p for p in PROVIDERS}
MAX_RETRIES = 6                                   # back off on free-tier 429s mid-run
OPENROUTER_BASE = "https://openrouter.ai/api/v1"


def _has_key(p) -> bool:
    return any(os.getenv(k) for k in p["keys"])


def resolve_model() -> str | None:
    """'provider:model' from TOS_MODEL, else auto-detected from whichever key is present."""
    forced = os.getenv("TOS_MODEL", "").strip()
    if forced:
        return forced
    for p in PROVIDERS:
        if _has_key(p):
            return f"{p['id']}:{p['default']}"
    return None


def active_provider() -> str:
    """Human-readable id of the provider currently in use (for UI / logs)."""
    m = resolve_model()
    return m.split(":", 1)[0] if m else "offline-stub"


def supported() -> list[dict]:
    """Provider catalog for a /api/providers endpoint or docs."""
    return [{"id": p["id"], "keys": p["keys"], "default": p["default"], "note": p["note"],
             "ready": _has_key(p)} for p in PROVIDERS]


def _key_error(model_str: str) -> str:
    prov = model_str.split(":", 1)[0]
    p = PROVIDER_BY_ID.get(prov)
    if p:
        return (f"No API key for provider '{prov}'. Set one of {p['keys']} in .env "
                f"(and `pip install {p['pip']}` if missing). Switch any time via "
                f"TOS_MODEL=provider:model, or just drop a different supported key in .env.")
    return (f"Unknown provider in TOS_MODEL='{model_str}'. "
            f"Supported: {', '.join(PROVIDER_BY_ID)} (+ ollama).")


def _build(model_str: str):
    """Construct a LangChain chat model for 'provider:model' (handles OpenRouter + retries)."""
    from langchain.chat_models import init_chat_model

    if model_str.startswith("openrouter:"):
        name = model_str.split(":", 1)[1]
        return init_chat_model(name, model_provider="openai", temperature=0, max_retries=MAX_RETRIES,
                               base_url=OPENROUTER_BASE, api_key=os.getenv("OPENROUTER_API_KEY"))
    if model_str.startswith("azure_openai:"):
        deployment = model_str.split(":", 1)[1]            # the Azure DEPLOYMENT name
        return init_chat_model(deployment, model_provider="azure_openai", temperature=0, max_retries=MAX_RETRIES,
                               azure_deployment=deployment,
                               api_version=os.getenv("OPENAI_API_VERSION", "2024-10-21"),
                               azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
                               api_key=os.getenv("AZURE_OPENAI_API_KEY"))
    return init_chat_model(model_str, temperature=0, max_retries=MAX_RETRIES)


class _StubLLM:
    """Last-resort offline fallback. Returns the user prompt's own context back as a flat
    summary so downstream nodes still produce output. Clearly labelled so it is never
    mistaken for a real model response."""

    available = False

    def complete(self, system: str, user: str, agent: str = "orchestrator") -> str:
        return (
            "[LLM UNAVAILABLE — TEMPLATED FALLBACK]\n"
            "No model provider was reachable (drop any supported key in .env). "
            "The following is the supplied context, not a validated action plan. "
            "Review tool failures before drawing conclusions.\n\n" + user.strip()
        )


class _ChatLLM:
    available = True

    def __init__(self, model):
        self._model = model

    def complete(self, system: str, user: str, agent: str = "orchestrator") -> str:
        from langchain_core.messages import HumanMessage, SystemMessage
        # Routing and synthesis calls are the orchestrator's own token spend, so they are
        # attributed to it rather than to whichever specialist ran last.
        config = {}
        try:
            import observability
            handlers = observability.callbacks(agent)
            if handlers:
                config["callbacks"] = handlers
        except Exception:  # noqa: BLE001 — instrumentation must never break a call
            pass
        resp = self._model.invoke(
            [SystemMessage(content=system), HumanMessage(content=user)], config=config or None
        )
        return resp.content if hasattr(resp, "content") else str(resp)


@lru_cache(maxsize=1)
def get_llm():
    """Object with .complete(system, user) -> str and .available bool. Used by graph nodes."""
    model_str = resolve_model()
    if not model_str:
        print("[llm] No provider key found — using offline stub. Drop any supported key in .env.")
        return _StubLLM()
    try:
        llm = _ChatLLM(_build(model_str))
        print(f"[llm] provider = {model_str}")
        return llm
    except Exception as exc:  # noqa: BLE001 — any import/config failure → stub
        print(f"[llm] Could not init '{model_str}' ({exc}). Using offline stub.")
        return _StubLLM()


@lru_cache(maxsize=1)
def get_chat_model():
    """Raw LangChain chat model for the ReAct agents (real tool-calling required — no stub)."""
    model_str = resolve_model()
    if not model_str:
        raise RuntimeError(
            "No model provider configured. Drop any supported key in .env "
            f"(one of: {', '.join(k for p in PROVIDERS for k in p['keys'])}) or set TOS_MODEL=ollama:<model>."
        )
    prov = model_str.split(":", 1)[0]
    if prov != "ollama":
        p = PROVIDER_BY_ID.get(prov)
        if p and not _has_key(p):
            raise RuntimeError(_key_error(model_str))
    return _build(model_str)


def complete(system: str, user: str, agent: str = "orchestrator") -> str:
    """Convenience wrapper used by graph nodes. Degrades to the stub on runtime errors
    (dead network / rate limit mid-demo) so a node never hard-crashes."""
    llm = get_llm()
    try:
        return llm.complete(system, user, agent=agent)
    except Exception as exc:  # noqa: BLE001
        print(f"[llm] invoke failed ({exc}); falling back to templated output.")
        return _StubLLM().complete(system, user, agent=agent)
