"""
Pseudo-relevance feedback: fixing vocabulary mismatch without an embedding model.

The retrieval evaluation measured a specific weakness. On queries that use the corpus's
own vocabulary, BM25 finds the answer 100% of the time. On paraphrases that deliberately
avoid it ("the machine is shaking a lot more than last month", "we are already late, can
we skip isolating the machine") it finds it 41.7% of the time. That is the classic lexical
retrieval failure: the query and the document mean the same thing and share no terms.

The usual answer is embeddings. They need an API key, which CI does not have, so the
scorecard would report a number nobody could reproduce for free. RM3-style pseudo-relevance
feedback is the keyless alternative and it is a well-established technique, not a trick:

  1. Run the original query. Assume the top few results are relevant (hence "pseudo").
  2. Pull the highest-weight terms out of those results.
  3. Add them to the query and search again.

A paraphrase that lands even one roughly-right document in the top few then inherits that
document's vocabulary and can reach its neighbours. It cannot rescue a query that retrieves
nothing useful at all, which is a real limitation and shows up in the numbers.

The expansion terms come from the corpus, never from the query set. Nothing here is fitted
to the evaluation queries, and the parameters below are the literature defaults rather than
values swept against the test set. That distinction is the difference between a retrieval
improvement and a number that only works on the queries it was tuned on.
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
    """Score candidate expansion terms from the pseudo-relevant set.

    A term is a good expansion if it is frequent in the feedback documents and rare in the
    corpus overall, which is tf-idf. Terms appearing in only one feedback document are
    damped: a term all three documents agree on is far better evidence of what the query is
    actually about than one that got in on a single lucky hit."""
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

    The original query keeps full weight. The expansion is added at `weight` so a query
    that was already working cannot be dragged away from its answer by feedback terms,
    which is the main way naive query expansion makes retrieval worse."""
    base = index.score(query)
    terms = expansion_terms(index, query)
    if not terms:
        return base
    extra = index.score(" ".join(terms))
    return [b + weight * e for b, e in zip(base, extra, strict=True)]


def search(index, query: str, k: int = 4) -> list[tuple[int, float]]:
    scored = sorted(enumerate(expanded_scores(index, query)), key=lambda x: -x[1])
    return [(i, s) for i, s in scored[:k] if s > 0]
