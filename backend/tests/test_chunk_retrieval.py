from app.evaluation.chunks import benchmark_chunk_retrieval, fixture_corpus


def test_chunk_experiment_measures_gold_source_retrieval_for_six_configurations():
    report = benchmark_chunk_retrieval(*fixture_corpus())
    assert report["query_count"] == 20
    assert report["document_count"] == 10
    assert report["embedding_evidence"] is False
    assert report["company_data_evidence"] is False
    assert len(report["configurations"]) == 6
    for configuration in report["configurations"]:
        assert len(configuration["results"]) == 20
        assert 0 <= configuration["source_accuracy_at_1"] <= configuration["source_recall_at_3"] <= 1
        assert all(result["gold_source"] for result in configuration["results"])


def test_chunk_experiment_detects_wrong_gold_source():
    report = benchmark_chunk_retrieval({"actual": "parking parking parking"}, [{"id": "wrong-gold", "query": "parking", "gold_source": "missing"}])
    assert all(configuration["source_accuracy_at_1"] == 0 for configuration in report["configurations"])


def test_vector_benchmark_batches_queries_once_and_chunks_per_configuration():
    import pytest
    pytest.importorskip("faiss")
    from app.evaluation.chunks import benchmark_vector_chunks

    class TestOnlyEmbeddings:
        def __init__(self):
            self.calls = []

        def embed(self, texts):
            self.calls.append(len(texts))
            return [[1.0, float(len(text))] for text in texts]

    provider = TestOnlyEmbeddings()
    report = benchmark_vector_chunks(*fixture_corpus(), provider, "test-only-vectors")
    assert provider.calls[0] == 20
    assert len(provider.calls) == 7
    assert len(report["configurations"]) == 6
    assert report["embedding_model"] == "test-only-vectors"
