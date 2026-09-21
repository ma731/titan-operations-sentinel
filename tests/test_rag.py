"""
Tests for the retrieval layer and the agent-facing tool that wraps it.

Offline: BM25 needs no key and no network, and the dense path is skipped when embeddings
are not configured rather than being faked.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from rag import embeddings as emb
from rag.index import corpus_stats, get_index, load_chunks, tokenize
from rag.retrieve import search
from tools.doc_search import search_technical_docs


# --- chunking and indexing ------------------------------------------------- #
def test_corpus_loads_and_every_chunk_is_citable():
    chunks = load_chunks()
    assert len(chunks) > 40, "corpus looks empty or unchunked"
    for c in chunks:
        assert "#S" in c.citation
        assert c.text.strip()
        assert c.provenance in {"internal-synthetic", "public-standard-paraphrase"}


def test_citations_are_unique():
    citations = [c.citation for c in load_chunks()]
    assert len(citations) == len(set(citations))


def test_readme_is_not_indexed():
    assert not any(c.doc_id.lower() == "readme" for c in load_chunks())


def test_tokenizer_stems_domain_plurals_together():
    assert tokenize("bearings")[0] == tokenize("bearing")[0]
    assert tokenize("lubrication")[0] == tokenize("lubricate")[0][:len(tokenize("lubrication")[0])]


def test_tokenizer_keeps_regulation_numbers():
    assert "1910.147" in tokenize("OSHA 1910.147 lockout")


def test_corpus_stats_are_reported():
    stats = corpus_stats()
    assert stats["documents"] >= 10
    assert stats["chunks"] == len(get_index().chunks)


# --- retrieval quality ----------------------------------------------------- #
@pytest.mark.parametrize("query,expected", [
    ("may an automated system authorise removing a lockout tagout lock",
     "osha-1910-147-loto#S4"),
    ("at what vibration level does a spindle enter the critical band",
     "tms-101-spindle-bearing-maintenance#S3"),
    ("what are the four collaborative operation modes for an industrial robot",
     "iso-10218-ts15066-collaborative-robots#S2"),
    ("can a purchase be split into smaller orders to stay under the approval ceiling",
     "tms-520-parts-sourcing-expedite-policy#S4"),
])
def test_known_questions_retrieve_their_answer(query, expected):
    citations = [p["citation"] for p in search(query, k=4)["passages"]]
    assert expected in citations, f"{expected} not in {citations}"


def test_search_returns_provenance_so_a_paraphrase_is_identifiable():
    hit = search("lockout tagout energy control procedure", k=1)["passages"][0]
    assert hit["provenance"] == "public-standard-paraphrase"


def test_search_respects_k():
    assert len(search("bearing", k=2)["passages"]) <= 2


def test_empty_query_does_not_raise():
    assert search("", k=3)["passages"] == []


# --- the agent-facing tool ------------------------------------------------- #
def test_tool_clamps_k_into_range():
    assert len(search_technical_docs("bearing temperature limit", k=99)["passages"]) <= 8
    assert len(search_technical_docs("bearing temperature limit", k=0)["passages"]) >= 1


def test_tool_handles_a_non_numeric_k():
    out = search_technical_docs("bearing temperature limit", k="four")
    assert out["passages"]


def test_tool_output_tells_the_agent_to_cite():
    out = search_technical_docs("maximum permissible bearing temperature")
    assert "citation" in out["note"]
    assert all("citation" in p for p in out["passages"])


# --- dense retrieval (skipped unless configured) --------------------------- #
@pytest.mark.skipif(not emb.available(), reason="TOS_EMBEDDINGS not configured")
def test_dense_retrieval_returns_passages_when_configured():
    out = search("what has to be true before we open an emergency window", k=3, mode="dense")
    assert out["retrieval_mode"] == "dense"
    assert out["passages"]


def test_dense_degrades_to_lexical_rather_than_failing_when_unconfigured():
    """The mode field reports what actually ran, so a scorecard cannot silently claim
    a dense result it did not compute."""
    out = search("bearing temperature limit", k=3, mode="dense")
    assert out["retrieval_mode"] in {"dense", "lexical"}
    assert out["passages"]
