"""Compare character chunk sizes using 20 synthetic gold-source retrieval queries."""
import argparse
import json
import sys
from pathlib import Path

if __name__ == "__main__":
    root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(root / "backend"))
    from app.evaluation.chunks import benchmark_chunk_retrieval, fixture_corpus

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--live-embeddings", action="store_true", help="Use configured OpenAI embeddings and a transient evaluation-only FAISS index")
    args = parser.parse_args()
    if args.live_embeddings:
        from app.core.config import Settings
        from app.evaluation.chunks import benchmark_vector_chunks
        from app.integrations.llm import LLMDecisionError, OpenAIEmbeddingProvider

        config = Settings()
        if not config.openai_api_key:
            raise SystemExit("OpenAI embeddings unavailable: OPENAI_API_KEY is not configured")
        try:
            provider = OpenAIEmbeddingProvider(config.openai_api_key, config.embedding_model, timeout_seconds=30)
            report = benchmark_vector_chunks(*fixture_corpus(), provider, config.embedding_model)
        except (LLMDecisionError, ImportError, RuntimeError, ValueError) as error:
            report = {"mode": "synthetic-corpus-live-openai-embeddings-faiss", "status": "unavailable", "error_type": type(error).__name__, "embedding_evidence": False}
    else:
        report = benchmark_chunk_retrieval(*fixture_corpus())
    text = json.dumps(report, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n")
    print(text)
    raise SystemExit(1 if report.get("status") == "unavailable" else 0)
