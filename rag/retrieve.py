"""
The retrieval API: `search(query, k, mode)` returns passages with citations.

  lexical  BM25. Always available, no key. The default and the CI baseline.
  prf      BM25 plus pseudo-relevance feedback. Keyless, available, not the default:
           measured, it is worth one query in 52. See F-05 in eval/FINDINGS.md.
  dense    Embedding cosine. Needs TOS_EMBEDDINGS.
  hybrid   Reciprocal rank fusion of lexical and dense.

Hybrid fuses by rank rather than blending scores, because BM25 scores and cosine
similarities are not on comparable scales. eval/rag_eval.py scores every mode.
"""
from __future__ import annotations

import os

from . import embeddings as emb
from .expansion import search as prf_search
from .index import Chunk, get_index

RRF_K = 60          # the standard reciprocal-rank-fusion damping constant
DEFAULT_K = 4
MAX_PASSAGE_CHARS = 1100    # one section is usually well under this; long tables are clipped

Mode = str          # "lexical" | "dense" | "hybrid"


def default_mode() -> Mode:
    """hybrid when embeddings are configured, lexical otherwise. TOS_RAG_MODE overrides.

    Lexical rather than prf is an evaluated decision, not an oversight: prf gains two
    points of recall@4 and loses seven of recall@1, a net of one query in 52. See F-05.
    """
    forced = os.getenv("TOS_RAG_MODE", "").strip().lower()
    if forced in {"lexical", "prf", "dense", "hybrid"}:
        return forced
    return "hybrid" if emb.available() else "lexical"


def _dense_ranking(query: str, chunks: list[Chunk]) -> list[tuple[int, float]] | None:
    """Cosine ranking over the corpus, or None when dense is unavailable.

    Brute force: the corpus is under a hundred chunks, so an approximate index would be
    slower and more to maintain."""
    doc_vectors = emb.embed([f"{c.doc_title}\n{c.section_title}\n{c.text}" for c in chunks])
    if doc_vectors is None:
        return None
    q = emb.embed([query], query=True)
    if q is None:
        return None
    try:
        sims = [(i, emb.cosine(q[0], v)) for i, v in enumerate(doc_vectors)]
    except (ValueError, TypeError):
        return None
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
    if mode not in {"lexical", "prf", "dense", "hybrid"}:
        raise ValueError(f"unknown retrieval mode: {mode}")
    if not query.strip() or k <= 0:
        return []

    if mode == "lexical":
        hits = index.search(query, k=k)
        return [(chunks[i], s, "lexical") for i, s in hits]

    if mode == "prf":
        hits = prf_search(index, query, k=k)
        return [(chunks[i], s, "prf") for i, s in hits]

    dense = _dense_ranking(query, chunks)
    if dense is None:
        # Dense was asked for but is not configured. Degrade rather than fail, and report
        # what actually ran so a caller (and the eval) can tell the difference.
        hits = index.search(query, k=k)
        return [(chunks[i], s, "lexical") for i, s in hits]

    if mode == "dense":
        return [(chunks[i], s, "dense") for i, s in dense[:k] if s > 0]

    lex = [i for i, _ in prf_search(index, query, k=max(k * 3, 12))]
    den = [i for i, _ in dense[: max(k * 3, 12)]]
    return [(chunks[i], s, "hybrid") for i, s in _rrf([lex, den], k)]


def search(query: str, k: int = DEFAULT_K, mode: Mode | None = None) -> dict:
    """The k most relevant passages, each with its citation.

    Leads with the citation and the provenance label so an agent quoting a paraphrase of
    a regulation can tell that it is a paraphrase."""
    ranked = rank(query, k=k, mode=mode)
    passages = []
    for chunk, score, _mode in ranked:
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
