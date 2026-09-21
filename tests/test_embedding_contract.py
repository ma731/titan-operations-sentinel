"""Provider-independent tests for dense query/document semantics and fallback."""
import pytest

from rag import embeddings as emb
from rag import retrieve


@pytest.fixture
def cache(monkeypatch, tmp_path):
    emb._cache.cache_clear()
    monkeypatch.setattr(emb, "CACHE_PATH", tmp_path / "vectors.json")
    monkeypatch.setenv("TOS_EMBEDDINGS", "test:model")
    yield
    emb._cache.cache_clear()


def test_query_and_document_vectors_are_distinct_and_cached(monkeypatch, cache):
    class Client:
        def embed_documents(self, texts):
            assert texts == ["same text"]
            return [[1.0, 0.0]]

        def embed_query(self, text):
            assert text == "same text"
            return [0.0, 1.0]

    monkeypatch.setattr(emb, "_client", lambda spec: Client())
    assert emb.embed(["same text"]) == [[1.0, 0.0]]
    assert emb.embed(["same text"], query=True) == [[0.0, 1.0]]
    monkeypatch.setattr(emb, "_client", lambda spec: pytest.fail("cache hit must not need a client"))
    assert emb.embed(["same text"]) == [[1.0, 0.0]]
    assert emb.embed(["same text"], query=True) == [[0.0, 1.0]]


@pytest.mark.parametrize("vectors", [[], [[float("nan")]], [[]]])
def test_malformed_provider_response_degrades(monkeypatch, cache, vectors):
    class Client:
        def embed_documents(self, texts):
            return vectors
    monkeypatch.setattr(emb, "_client", lambda spec: Client())
    assert emb.embed(["bearing"]) is None


def test_dimension_mismatch_falls_back_honestly(monkeypatch):
    monkeypatch.setattr(emb, "embed", lambda texts, query=False:
                        [[1.0]] if query else [[1.0, 0.0] for _ in texts])
    result = retrieve.search("bearing temperature", mode="dense")
    assert result["retrieval_mode"] == "lexical"
    assert result["passages"]


def test_dense_ranking_uses_query_embedding_and_returns_real_citations(monkeypatch):
    chunks = retrieve.get_index().chunks
    target = chunks[2].citation
    def embed(texts, query=False):
        return [[1.0, 0.0]] if query else [
            [1.0, 0.0] if i == 2 else [0.0, 1.0] for i in range(len(texts))]
    monkeypatch.setattr(emb, "embed", embed)
    result = retrieve.search("semantic query", k=1, mode="dense")
    assert result["retrieval_mode"] == "dense"
    assert result["passages"][0]["citation"] == target


def test_empty_query_never_calls_embedding_provider(monkeypatch):
    monkeypatch.setattr(emb, "embed", lambda *a, **k: pytest.fail("unnecessary provider call"))
    assert retrieve.search(" ", mode="dense")["passages"] == []
