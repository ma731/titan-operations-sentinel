"""Retrieval over the technical reference corpus (rag/corpus) with citations.

This is the agent-facing wrapper. The retrieval itself lives in rag/. Keeping the tool
thin means the retrieval evaluation in eval/rag_eval.py measures exactly the function the
agents call, not a parallel implementation.
"""
from __future__ import annotations


def search_technical_docs(query: str, k: int = 4) -> dict:
    """
    Retrieves the most relevant passages from the technical reference corpus.

    Tool catalog:
      Input:  query (str, a natural-language question), k (int, passages to return, 1-8)
      Output: passages, each with citation (doc_id#section), document title, provenance
              label, section text, and retrieval score; plus the retrieval mode used
      Use when: a decision needs a standard, a procedure, a limit, or an authority rule
                (severity bands, OSHA lockout/tagout, robot safety, expedite policy)
      Do NOT use: for live machine data (use sensor_query) or past incidents
                  (use recall_similar_cases). This corpus is documents, not telemetry.
      Fallback: returns an empty passage list if the corpus or index is unavailable
      Risk tier: READ (autonomous)
    """
    try:
        from rag.retrieve import search as _search
    except Exception as exc:  # noqa: BLE001 — retrieval must never break a run
        return {"query": query, "passages": [], "error": f"corpus unavailable: {exc}"}
    try:
        k = max(1, min(int(k), 8))
    except (TypeError, ValueError):
        k = 4
    try:
        return _search(query, k=k)
    except Exception as exc:  # noqa: BLE001
        return {"query": query, "passages": [], "error": f"retrieval failed: {exc}"}
