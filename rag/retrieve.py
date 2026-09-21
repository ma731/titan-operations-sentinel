"""
The public retrieval API: `search(query, k, mode)` returns cited passages.

Three modes:
  lexical  BM25 only. Always available, no key, no network. The CI default.
  dense    Embedding cosine similarity. Requires TOS_EMBEDDINGS (see rag/embeddings.py).
  hybrid   Reciprocal rank fusion of the two. Falls back to lexical when dense is off.

Hybrid uses reciprocal rank fusion rather than a weighted score blend because BM25 scores
and cosine similarities are not on comparable scales, and RRF needs no tuning constant per
corpus. The eval in eval/rag_eval.py reports recall@k and MRR for all three so the choice
is backed by a number rather than by taste.
"""
from __future__ import annotations

import os

from . import embeddings as emb
from .index import Chunk, get_index

RRF_K = 60          # the standard reciprocal-rank-fusion damping constant
DEFAULT_K = 4
MAX_PASSAGE_CHARS = 1100    # one section is usually well under this; long tables are clipped

Mode = str          # "lexical" | "dense" | "hybrid"


def default_mode() -> Mode:
    """hybrid when embeddings are configured, lexical otherwise. TOS_RAG_MODE overrides."""
    forced = os.getenv("TOS_RAG_MODE", "").strip().lower()
    if forced in {"lexical", "dense", "hybrid"}:
        return forced
    return "hybrid" if emb.available() else "lexical"


def _dense_ranking(query: str, chunks: list[Chunk]) -> list[tuple[int, float]] | None:
    """Cosine similarity ranking over the whole corpus, or None when dense is unavailable.

    The corpus is ~60 chunks, so a brute-force scan is both simpler and faster than any
    approximate index would be. A vector database here would be architecture theatre."""
    doc_vectors = emb.embed([f"{c.doc_title}\n{c.section_title}\n{c.text}" for c in chunks])
    if doc_vectors is None:
        return None
    q = emb.embed([query])
    if q is None:
        return None
    sims = [(i, emb.cosine(q[0], v)) for i, v in enumerate(doc_vectors)]
    sims.sort(key=lambda x: -x[1])
    return sims


def _rrf(rankings: list[list[int]], k: int) -> list[tuple[int, float]]:
    """Fuse several ranked id lists into one. Score = sum over rankings of 1/(RRF_K+rank)."""
    fused: dict[int, float] = {}
    for ranking in rankings:
        for rank, idx in enumerate(ranking, start=1):
            fused[idx] = fused.get(idx, 0.0) + 1.0 / (RRF_K + rank)
    ordered = sorted(fused.items(), key=lambda x: -x[1])
    return ordered[:k]


def rank(query: str, k: int = DEFAULT_K, mode: Mode | None = None) -> list[tuple[Chunk, float, Mode]]:
    """Rank corpus chunks for a query. Returns (chunk, score, mode_actually_used)."""
    index = get_index()
    chunks = index.chunks
    if not chunks:
        return []
    mode = mode or default_mode()

    if mode == "lexical":
        hits = index.search(query, k=k)
        return [(chunks[i], s, "lexical") for i, s in hits]

    dense = _dense_ranking(query, chunks)
    if dense is None:
        # Dense was asked for but is not configured. Degrade rather than fail, and say so
        # in the returned mode so a caller (and the eval) can tell what actually ran.
        hits = index.search(query, k=k)
        return [(chunks[i], s, "lexical") for i, s in hits]

    if mode == "dense":
        return [(chunks[i], s, "dense") for i, s in dense[:k] if s > 0]

    lex = [i for i, _ in index.search(query, k=max(k * 3, 12))]
    den = [i for i, _ in dense[: max(k * 3, 12)]]
    return [(chunks[i], s, "hybrid") for i, s in _rrf([lex, den], k)]


def search(query: str, k: int = DEFAULT_K, mode: Mode | None = None) -> dict:
    """Retrieve the k most relevant corpus passages, each with its citation.

    The return shape is what the agent sees, so it leads with the citation and the
    provenance label: an agent citing a paraphrase of a regulation should be able to tell
    that it is a paraphrase."""
    ranked = rank(query, k=k, mode=mode)
    passages = []
    for chunk, score, used in ranked:
        p = chunk.to_passage(score)
        text = p["text"]
        if len(text) > MAX_PASSAGE_CHARS:
            p["text"] = text[:MAX_PASSAGE_CHARS].rstrip() + " ...[section truncated]"
        passages.append(p)
    return {
        "query": query,
        "retrieval_mode": ranked[0][2] if ranked else (mode or default_mode()),
        "passages": passages,
        "note": ("Cite the `citation` field for any claim taken from these passages. "
                 "Passages marked public-standard-paraphrase are summaries, not the "
                 "regulatory text: say so when you rely on one."),
    }
