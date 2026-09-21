"""
Per-run, per-agent observability: tokens, model calls, latency, and estimated cost.

Two layers, both optional and both off by default so nothing here can break a demo:

1. `UsageTracker` is a LangChain callback handler that counts prompt and completion
   tokens per agent. It is always attached when a run is instrumented, costs nothing, and
   is what the evaluation harness reports tokens and cost from.
2. Langfuse tracing is attached only when LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY are
   present in the environment. It gives a per-agent waterfall in the Langfuse UI. Without
   the keys, `langfuse_handler()` returns None and the run is unaffected.

Why count tokens ourselves rather than read them from Langfuse: the eval has to run in CI
with no network and no account, and a scorecard that only exists when a SaaS is reachable
is not a scorecard.
"""
from __future__ import annotations

import os
import threading
import time
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field

try:
    from langchain_core.callbacks import BaseCallbackHandler
except Exception:  # noqa: BLE001 — keeps this module importable without langchain
    class BaseCallbackHandler:  # type: ignore[no-redef]
        pass


# Indicative prices in EUR per 1M tokens (input, output). These are order-of-magnitude
# figures for reporting a cost column, not a billing system. Free-tier providers are
# priced at zero because that is what the project actually spends.
PRICE_EUR_PER_M = {
    "groq": (0.0, 0.0),
    "google_genai": (0.0, 0.0),
    "openrouter": (0.0, 0.0),
    "ollama": (0.0, 0.0),
    "offline-stub": (0.0, 0.0),
    "openai": (0.14, 0.55),
    "azure_openai": (0.14, 0.55),
    "anthropic": (0.74, 3.70),
    "mistralai": (0.09, 0.28),
}


@dataclass
class AgentUsage:
    calls: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    seconds: float = 0.0

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


@dataclass
class RunUsage:
    by_agent: dict[str, AgentUsage] = field(default_factory=dict)
    wall_seconds: float = 0.0
    provider: str = "unknown"

    def agent(self, name: str) -> AgentUsage:
        return self.by_agent.setdefault(name, AgentUsage())

    @property
    def calls(self) -> int:
        return sum(a.calls for a in self.by_agent.values())

    @property
    def prompt_tokens(self) -> int:
        return sum(a.prompt_tokens for a in self.by_agent.values())

    @property
    def completion_tokens(self) -> int:
        return sum(a.completion_tokens for a in self.by_agent.values())

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens

    def cost_eur(self) -> float:
        pin, pout = PRICE_EUR_PER_M.get(self.provider, (0.0, 0.0))
        return (self.prompt_tokens * pin + self.completion_tokens * pout) / 1_000_000

    def to_dict(self) -> dict:
        return {
            "provider": self.provider,
            "model_calls": self.calls,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "estimated_cost_eur": round(self.cost_eur(), 6),
            "wall_seconds": round(self.wall_seconds, 2),
            "by_agent": {
                name: {
                    "model_calls": a.calls,
                    "prompt_tokens": a.prompt_tokens,
                    "completion_tokens": a.completion_tokens,
                    "total_tokens": a.total_tokens,
                    "seconds": round(a.seconds, 2),
                }
                for name, a in sorted(self.by_agent.items())
            },
        }


def _extract_tokens(response) -> tuple[int, int]:
    """Pull (prompt, completion) tokens out of an LLMResult across provider shapes.

    Providers disagree: some fill llm_output['token_usage'], some only put
    usage_metadata on the message. Try both before giving up, and return zeros rather
    than raising, because a missing token count must never fail a run."""
    out = getattr(response, "llm_output", None) or {}
    usage = out.get("token_usage") or out.get("usage") or {}
    prompt = usage.get("prompt_tokens") or usage.get("input_tokens") or 0
    completion = usage.get("completion_tokens") or usage.get("output_tokens") or 0
    if prompt or completion:
        return int(prompt), int(completion)

    for gen_list in (getattr(response, "generations", None) or []):
        for gen in gen_list:
            msg = getattr(gen, "message", None)
            meta = getattr(msg, "usage_metadata", None) or {}
            if meta:
                return int(meta.get("input_tokens", 0)), int(meta.get("output_tokens", 0))
            rmeta = (getattr(msg, "response_metadata", None) or {}).get("token_usage") or {}
            if rmeta:
                return (int(rmeta.get("prompt_tokens", 0)),
                        int(rmeta.get("completion_tokens", 0)))
    return 0, 0


class UsageTracker(BaseCallbackHandler):
    """Counts model calls and tokens, attributed to whichever agent is currently running.

    The graph is sequential (one agent node at a time), so a single current-label field is
    accurate. The lock is there because LangChain may deliver callbacks from a worker
    thread, not because two agents run at once."""

    def __init__(self, provider: str = "unknown"):
        self.usage = RunUsage(provider=provider)
        self._label = "orchestrator"
        self._lock = threading.Lock()

    def set_agent(self, name: str) -> None:
        with self._lock:
            self._label = name or "orchestrator"

    @contextmanager
    def agent(self, name: str):
        """Attribute everything inside the block to `name`, including its wall time."""
        previous = self._label
        self.set_agent(name)
        started = time.perf_counter()
        try:
            yield self
        finally:
            elapsed = time.perf_counter() - started
            with self._lock:
                self.usage.agent(name).seconds += elapsed
                self._label = previous

    # --- LangChain callback surface -------------------------------------- #
    def on_llm_end(self, response, **kwargs) -> None:  # noqa: D102
        prompt, completion = _extract_tokens(response)
        with self._lock:
            a = self.usage.agent(self._label)
            a.calls += 1
            a.prompt_tokens += prompt
            a.completion_tokens += completion

    def on_llm_error(self, error, **kwargs) -> None:  # noqa: D102
        with self._lock:
            self.usage.agent(self._label).calls += 1


def langfuse_handler():
    """Langfuse CallbackHandler when configured, else None.

    Set LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY and (for EU) LANGFUSE_HOST. The free
    tier is enough for this project. Any failure here degrades to no tracing rather than
    to a broken run."""
    if not (os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY")):
        return None
    try:
        from langfuse.langchain import CallbackHandler
        return CallbackHandler()
    except Exception:  # noqa: BLE001 — older package layout
        try:
            from langfuse.callback import CallbackHandler  # type: ignore[no-redef]
            return CallbackHandler()
        except Exception as exc:  # noqa: BLE001
            print(f"[observability] Langfuse configured but unavailable ({exc}); tracing off.")
            return None


# One tracker per execution context, set by instrument_run(). The graph reads it through
# callbacks() so nodes do not have to thread a tracker object through the graph state.
_ACTIVE: ContextVar[UsageTracker | None] = ContextVar("tos_usage", default=None)


def active_tracker() -> UsageTracker | None:
    return _ACTIVE.get()


@contextmanager
def instrument_run(provider: str | None = None):
    """Instrument everything inside the block. Yields the RunUsage, filled on exit.

    Usage:
        with instrument_run() as usage:
            graph.stream(...)
        print(usage.to_dict())
    """
    if provider is None:
        try:
            import llm
            provider = llm.active_provider()
        except Exception:  # noqa: BLE001
            provider = "unknown"
    tracker = UsageTracker(provider=provider)
    token = _ACTIVE.set(tracker)
    started = time.perf_counter()
    try:
        yield tracker.usage
    finally:
        tracker.usage.wall_seconds = time.perf_counter() - started
        _ACTIVE.reset(token)


@contextmanager
def instrumented_agent(name: str):
    """Attribute tokens and wall time inside the block to `name`. A no-op when the run is
    not instrumented, so graph nodes can wrap themselves unconditionally."""
    active = active_tracker()
    if active is None:
        yield None
        return
    with active.agent(name) as tracker:
        yield tracker


def callbacks(agent: str | None = None) -> list:
    """The callback list to pass in a LangChain/LangGraph config.

    Returns [] when the run is not instrumented and Langfuse is not configured, so the
    default path adds no overhead at all."""
    handlers: list = []
    active = active_tracker()
    if active is not None:
        if agent:
            active.set_agent(agent)
        handlers.append(active)
    lf = _langfuse_singleton()
    if lf is not None:
        handlers.append(lf)
    return handlers


_LANGFUSE_CACHED: list = []     # a one-slot cache; [] means "not yet resolved"


def _langfuse_singleton():
    if not _LANGFUSE_CACHED:
        _LANGFUSE_CACHED.append(langfuse_handler())
    return _LANGFUSE_CACHED[0]


def status() -> dict:
    """What instrumentation is active right now, for a health endpoint or the README."""
    return {
        "usage_tracking": active_tracker() is not None,
        "langfuse": _langfuse_singleton() is not None,
        "langfuse_host": os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com"),
    }
