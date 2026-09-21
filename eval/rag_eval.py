"""
Retrieval evaluation: recall@k, MRR and precision@k over the labelled query set.

Runs the same `rag.retrieve.search` path the `search_technical_docs` tool calls, so the
number on the scorecard is the number the agents actually get.

All three retrievers are scored side by side. The lexical row always runs (no key, no
network, deterministic, so it is the CI number). The dense and hybrid rows run only when
TOS_EMBEDDINGS is configured, and are reported as "not configured" otherwise rather than
being silently omitted, so nobody reads a lexical-only scorecard as a hybrid result.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from rag import embeddings as emb  # noqa: E402
from rag.index import corpus_stats  # noqa: E402
from rag.retrieve import rank  # noqa: E402

from .metrics import mean, precision_at_k, recall_at_k, reciprocal_rank  # noqa: E402
from .scenarios import RagQuery, load_rag_queries  # noqa: E402

K_VALUES = (1, 3, 4, 8)
REPORT_K = 4          # the tool's default k, so this is the row that matters operationally


def _retrieve_citations(query: str, mode: str, k: int) -> tuple[list[str], str]:
    """Citations in rank order plus the mode that actually ran (dense degrades to lexical
    when embeddings are unavailable, and we record which one it was)."""
    ranked = rank(query, k=k, mode=mode)
    used = ranked[0][2] if ranked else mode
    return [c.citation for c, _s, _m in ranked], used


def evaluate_mode(queries: list[RagQuery], mode: str) -> dict:
    max_k = max(K_VALUES)
    recalls: dict[int, list[float]] = {k: [] for k in K_VALUES}
    precisions: list[float] = []
    rrs: list[float] = []
    per_query = []
    degraded = False

    for q in queries:
        citations, used = _retrieve_citations(q.query, mode, max_k)
        if used != mode:
            degraded = True
        for k in K_VALUES:
            recalls[k].append(recall_at_k(citations, q.relevant, k))
        precisions.append(precision_at_k(citations, q.relevant, REPORT_K))
        rr = reciprocal_rank(citations, q.relevant)
        rrs.append(rr)
        per_query.append({
            "id": q.id, "query": q.query, "asked_by": q.asked_by,
            "relevant": q.relevant,
            "retrieved_top4": citations[:REPORT_K],
            "reciprocal_rank": round(rr, 4),
            "hit_at_4": bool(recall_at_k(citations, q.relevant, REPORT_K)),
        })

    if degraded and mode != "lexical":
        return {"mode": mode, "available": False,
                "note": "not configured: set TOS_EMBEDDINGS to score this retriever "
                        "(see rag/embeddings.py). Reported as unavailable rather than "
                        "silently falling back to lexical."}

    by_split = {}
    for split in ("direct", "paraphrase"):
        ids = {q.id for q in queries if q.difficulty == split}
        rows = [p for p in per_query if p["id"] in ids]
        if not rows:
            continue
        by_split[split] = {
            "queries": len(rows),
            f"recall@{REPORT_K}": round(mean([1.0 if r["hit_at_4"] else 0.0 for r in rows]) or 0.0, 4),
            "mrr": round(mean([r["reciprocal_rank"] for r in rows]) or 0.0, 4),
            "misses": [r["id"] for r in rows if not r["hit_at_4"]],
        }

    return {
        "mode": mode,
        "available": True,
        "queries": len(queries),
        "recall_at_k": {f"recall@{k}": round(mean(recalls[k]) or 0.0, 4) for k in K_VALUES},
        f"precision_at_{REPORT_K}": round(mean(precisions) or 0.0, 4),
        "mrr": round(mean(rrs) or 0.0, 4),
        "by_difficulty": by_split,
        "misses_at_4": [p for p in per_query if not p["hit_at_4"]],
        "per_query": per_query,
    }


def run(queries: list[RagQuery] | None = None) -> dict:
    queries = queries if queries is not None else load_rag_queries()
    results = {mode: evaluate_mode(queries, mode) for mode in ("lexical", "dense", "hybrid")}
    best = max(
        (r for r in results.values() if r.get("available")),
        key=lambda r: r["recall_at_k"][f"recall@{REPORT_K}"],
        default=None,
    )
    return {
        "suite": "retrieval",
        "corpus": corpus_stats(),
        "embeddings": emb.cache_stats(),
        "report_k": REPORT_K,
        "modes": results,
        "best_available_mode": best["mode"] if best else None,
    }


if __name__ == "__main__":
    import json
    out = run()
    for mode, r in out["modes"].items():
        if not r.get("available"):
            print(f"{mode:8s} {r['note']}")
            continue
        print(f"{mode:8s} recall@4={r['recall_at_k']['recall@4']}  mrr={r['mrr']}  "
              f"p@4={r[f'precision_at_{REPORT_K}']}  misses={len(r['misses_at_4'])}")
    print(json.dumps(out["corpus"], indent=2))
