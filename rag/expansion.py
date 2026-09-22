"""
Pseudo-relevance feedback: fixing vocabulary mismatch without an embedding model.

The retrieval evaluation measured a specific weakness. On queries that use the corpus's
own vocabulary, BM25 finds the answer 100% of the time. On paraphrases that deliberately
avoid it ("the machine is shaking a lot more than last month", "we are already late, can
we skip isolating the machine") it finds it 41.7% of the time. That is the classic lexical
retrieval failure: the query and the document mean the same thing and share no terms.

The usual answer is embeddings, which need a key CI does not have. RM3 pseudo-relevance
feedback is the keyless alternative: run the query, assume the top few hits are relevant,
harvest their strongest terms, search again. A paraphrase that lands one roughly-right
document inherits its vocabulary. It cannot rescue a query that retrieves nothing useful.

Expansion terms come from the corpus, never from the query set, and the parameters below
are literature defaults rather than values swept against the labelled queries.
"""
from __future__ import annotations

import math

# Standard RM3 defaults. Deliberately NOT tuned against eval/cases/rag_queries.json:
# sweeping these against the labelled set would turn a held-out test set into a training
# set and make the reported gain meaningless.
FEEDBACK_DOCS = 3          # how many top results to treat as pseudo-relevant
FEEDBACK_TERMS = 12        # how many expansion terms to harvest from them
EXPANSION_WEIGHT = 0.4     # how much the expansion contributes relative to the original


def _term_weights(index, doc_ids: list[int]) -> dict[str, float]:
    """Score candidate expansion terms: tf-idf over the pseudo-relevant set.

    Terms in only one feedback document are damped, since agreement across documents is
    better evidence than one lucky hit."""
    weights: dict[str, float] = {}
    doc_count: dict[str, int] = {}
    for doc_id in doc_ids:
        counts = index.tf[doc_id]
        length = index.doc_len[doc_id] or 1
        for term, freq in counts.items():
            idf = index.idf.get(term, 0.0)
            if idf <= 0:
                continue
            weights[term] = weights.get(term, 0.0) + (freq / length) * idf
            doc_count[term] = doc_count.get(term, 0) + 1
    return {t: w * (1.0 + math.log(doc_count[t])) for t, w in weights.items()}


def expansion_terms(index, query: str, feedback_docs: int = FEEDBACK_DOCS,
                    feedback_terms: int = FEEDBACK_TERMS) -> list[str]:
    """The terms the first-pass results suggest the query is really about."""
    from .index import tokenize

    first_pass = index.search(query, k=feedback_docs)
    if not first_pass:
        return []
    original = set(tokenize(query))
    ranked = sorted(_term_weights(index, [i for i, _ in first_pass]).items(),
                    key=lambda kv: -kv[1])
    return [t for t, _w in ranked if t not in original][:feedback_terms]


def expanded_scores(index, query: str, weight: float = EXPANSION_WEIGHT) -> list[float]:
    """Per-chunk scores for the query plus its expansion.

    The original keeps full weight and the expansion is added at `weight`, so a query that
    already worked cannot be dragged off its answer. That is how naive expansion hurts."""
    base = index.score(query)
    terms = expansion_terms(index, query)
    if not terms:
        return base
    extra = index.score(" ".join(terms))
    return [b + weight * e for b, e in zip(base, extra, strict=True)]


def search(index, query: str, k: int = 4) -> list[tuple[int, float]]:
    scored = sorted(enumerate(expanded_scores(index, query)), key=lambda x: -x[1])
    return [(i, s) for i, s in scored[:k] if s > 0]
