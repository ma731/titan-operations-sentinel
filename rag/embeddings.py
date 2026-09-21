"""
The dense half of the retriever: optional embeddings with an on-disk cache.

Design constraint: the whole project has to run offline, free, and in CI. So dense
retrieval is strictly opt-in. When no embedding provider is configured, `available()`
returns False and `rag/retrieve.py` falls back to lexical-only search. Nothing breaks and
the eval simply reports the lexical row of the scorecard.

Vectors are cached to rag/index/embeddings.json keyed by (model, sha1(text)), so a second
run, and the retrieval eval in particular, costs nothing. The cache is committed so a
reviewer can reproduce the dense numbers without a key.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
from functools import lru_cache
from pathlib import Path

CACHE_PATH = Path(__file__).parent / "index" / "embeddings.json"

# provider id -> (env keys, default embedding model)
EMBEDDING_PROVIDERS = {
    "google_genai": (["GOOGLE_API_KEY", "GEMINI_API_KEY"], "models/text-embedding-004"),
    "openai": (["OPENAI_API_KEY"], "text-embedding-3-small"),
    "mistralai": (["MISTRAL_API_KEY"], "mistral-embed"),
    "ollama": ([], "nomic-embed-text"),
}


def _cache_key(model: str, text: str, kind: str = "document") -> str:
    return f"{model}::{kind}::{hashlib.sha1(text.encode('utf-8')).hexdigest()}"


@lru_cache(maxsize=1)
def _cache() -> dict:
    try:
        return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 — a missing or corrupt cache is not an error
        return {}


def _save_cache(cache: dict) -> None:
    try:
        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        CACHE_PATH.write_text(json.dumps(cache), encoding="utf-8")
    except OSError:
        pass


def resolve_embedding_model() -> str | None:
    """'provider:model' for embeddings, or None when dense retrieval is unavailable.

    Set TOS_EMBEDDINGS explicitly (e.g. `google_genai:models/text-embedding-004`), or
    TOS_EMBEDDINGS=auto to pick the first provider whose key is present. Unset means
    lexical-only, which is the default so a clone with no keys behaves predictably."""
    forced = os.getenv("TOS_EMBEDDINGS", "").strip()
    if not forced:
        return None
    if forced.lower() in {"0", "off", "false", "none"}:
        return None
    if forced.lower() != "auto":
        return forced
    for pid, (keys, default) in EMBEDDING_PROVIDERS.items():
        if keys and any(os.getenv(k) for k in keys):
            return f"{pid}:{default}"
    return None


def available() -> bool:
    return resolve_embedding_model() is not None


@lru_cache(maxsize=4)
def _client(spec: str):
    """Build the LangChain embeddings client for the resolved provider, or None."""
    if not spec:
        return None
    provider, _, model = spec.partition(":")
    try:
        if provider == "google_genai":
            from langchain_google_genai import GoogleGenerativeAIEmbeddings
            return GoogleGenerativeAIEmbeddings(model=model)
        if provider == "openai":
            from langchain_openai import OpenAIEmbeddings
            return OpenAIEmbeddings(model=model)
        if provider == "mistralai":
            from langchain_mistralai import MistralAIEmbeddings
            return MistralAIEmbeddings(model=model)
        if provider == "ollama":
            from langchain_ollama import OllamaEmbeddings
            return OllamaEmbeddings(model=model)
    except Exception as exc:  # noqa: BLE001 — missing package or bad config → lexical only
        print(f"[rag] embeddings unavailable ({exc}); falling back to lexical retrieval.")
    return None


def embed(texts: list[str], *, query: bool = False) -> list[list[float]] | None:
    """Embed a batch, using the cache for anything already seen. Returns None when dense
    retrieval is unavailable, which callers treat as 'lexical only'."""
    spec = resolve_embedding_model()
    if not spec:
        return None
    kind = "query" if query else "document"
    cache = _cache()
    missing = list(dict.fromkeys(t for t in texts if _cache_key(spec, t, kind) not in cache))
    if missing:
        client = _client(spec)
        if client is None:
            return None
        try:
            fresh = ([client.embed_query(t) for t in missing] if query else
                     client.embed_documents(missing))
            if len(fresh) != len(missing) or not all(
                vec and all(isinstance(x, (int, float)) and math.isfinite(x) for x in vec)
                for vec in fresh
            ):
                return None
        except Exception as exc:  # noqa: BLE001
            print(f"[rag] embedding call failed ({exc}); falling back to lexical retrieval.")
            return None
        for text, vec in zip(missing, fresh, strict=True):
            cache[_cache_key(spec, text, kind)] = vec
        _save_cache(cache)
    return [cache[_cache_key(spec, t, kind)] for t in texts]


def cosine(a: list[float], b: list[float]) -> float:
    if len(a) != len(b) or not a:
        raise ValueError("embedding dimensions must match and be non-empty")
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def cache_stats() -> dict:
    return {"model": resolve_embedding_model(), "cached_vectors": len(_cache())}
