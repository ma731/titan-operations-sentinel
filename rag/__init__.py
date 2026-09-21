"""Retrieval-augmented grounding over the technical reference corpus.

This is document retrieval with citations, which is what "RAG" means: the corpus in
rag/corpus is chunked by section, indexed lexically (BM25) and optionally densely
(embeddings), and the Reliability and Compliance agents query it through the
`search_technical_docs` tool.

It is a separate thing from case memory (tools/recall_cases.py), which matches past
incidents in a structured JSON library. Both are retrieval, but only one of them is
retrieval over documents, and the README keeps the two labelled apart on purpose.
"""
from .index import corpus_stats, get_index, load_chunks
from .retrieve import default_mode, rank, search

__all__ = ["corpus_stats", "default_mode", "get_index", "load_chunks", "rank", "search"]
