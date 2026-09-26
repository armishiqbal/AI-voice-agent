import pytest

from app.integrations.rag.faiss_local import FaissKnowledgeStore
from app.integrations.rag.pinecone import RAGProviderError, RetrievedChunk

pytest.importorskip("faiss")


class TestEmbeddings:
    """Deterministic vectors exclusively for adapter contract testing."""
    def embed(self, texts):
        return [[1.0, 0.0] if "school" in text else [0.0, 1.0] for text in texts]


def test_local_vector_search_persists_and_filters_before_ranking(tmp_path):
    path = str(tmp_path / "vectors.json")
    store = FaissKnowledgeStore(path, TestEmbeddings())
    store.upsert([
        RetrievedChunk("school", "school nearby", 0, {"property_id": "P1"}),
        RetrievedChunk("hospital", "hospital nearby", 0, {"property_id": "P2"}),
    ])
    restored = FaissKnowledgeStore(path, TestEmbeddings())
    assert restored.query("school")[0].source_id == "school"
    assert restored.query("school", {"property_id": {"$in": ["P2"]}})[0].source_id == "hospital"
    assert restored.query("school", {"property_id": {"$in": []}}) == []
    restored.upsert([RetrievedChunk("school", "new school", 0, {"property_id": "P1"})])
    assert len(restored.query("school")) == 2


def test_local_vector_invalid_embedding_does_not_overwrite_index(tmp_path):
    class InvalidEmbeddings:
        def embed(self, texts):
            return [[float("nan"), 0.0]]
    path = tmp_path / "vectors.json"
    store = FaissKnowledgeStore(str(path), InvalidEmbeddings())
    with pytest.raises(RAGProviderError):
        store.upsert([RetrievedChunk("bad", "bad", 0, {})])
    assert not path.exists()


def test_local_vector_rejects_unsupported_filter_and_dimension_change(tmp_path):
    store = FaissKnowledgeStore(str(tmp_path / "vectors.json"), TestEmbeddings())
    store.upsert([RetrievedChunk("school", "school", 0, {"property_id": "P1"})])
    with pytest.raises(RAGProviderError):
        store.query("school", {"property_id": {"$ne": "P1"}})
    class NewEmbeddings:
        def embed(self, texts):
            return [[1.0, 0.0, 0.0]]
    store.embedding_provider = NewEmbeddings()
    with pytest.raises(RAGProviderError):
        store.query("school")
