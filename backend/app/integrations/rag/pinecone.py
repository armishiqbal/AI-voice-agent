from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class EmbeddingProvider(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]: ...


class RAGProviderError(RuntimeError):
    """Expected retrieval/indexing failure; callers should fall back or hand off."""


@dataclass(frozen=True)
class RetrievedChunk:
    source_id: str
    text: str
    score: float
    metadata: dict[str, object]


class PineconeKnowledgeStore:
    """Thin, metadata-filtered Pinecone adapter with lazy optional imports."""

    def __init__(
        self,
        api_key: str,
        index_name: str,
        embedding_provider: EmbeddingProvider,
        namespace: str = "default",
    ) -> None:
        try:
            from pinecone import Pinecone
        except ImportError as error:
            raise RAGProviderError("Install the providers extra to enable Pinecone") from error
        self.embedding_provider = embedding_provider
        self.namespace = namespace
        self.index = Pinecone(api_key=api_key).Index(index_name)

    def upsert(self, chunks: list[RetrievedChunk]) -> None:
        if not chunks:
            return
        try:
            vectors = self.embedding_provider.embed([chunk.text for chunk in chunks])
        except Exception as error:
            raise RAGProviderError(f"Embedding upsert failed: {error}") from error
        self.index.upsert(
            vectors=[
                {
                    "id": chunk.source_id,
                    "values": vector,
                    "metadata": {**chunk.metadata, "text": chunk.text},
                }
                for chunk, vector in zip(chunks, vectors, strict=True)
            ],
            namespace=self.namespace,
        )

    def query(
        self,
        text: str,
        metadata_filter: dict[str, object] | None = None,
        top_k: int = 5,
    ) -> list[RetrievedChunk]:
        try:
            vector = self.embedding_provider.embed([text])[0]
        except Exception as error:
            raise RAGProviderError(f"Embedding query failed: {error}") from error
        result = self.index.query(
            vector=vector,
            top_k=top_k,
            include_metadata=True,
            namespace=self.namespace,
            filter=metadata_filter or {},
        )
        matches = (
            result.get("matches", [])
            if isinstance(result, dict)
            else getattr(result, "matches", [])
        )
        chunks: list[RetrievedChunk] = []
        for match in matches:
            metadata = (
                dict(match.get("metadata", {}))
                if isinstance(match, dict)
                else dict(getattr(match, "metadata", {}) or {})
            )
            source_id = match.get("id", "") if isinstance(match, dict) else getattr(match, "id", "")
            score = (
                match.get("score", 0.0) if isinstance(match, dict) else getattr(match, "score", 0.0)
            )
            text_value = str(metadata.pop("text", ""))
            if text_value:
                chunks.append(
                    RetrievedChunk(str(source_id), text_value, float(score or 0.0), metadata)
                )
        return chunks


def build_knowledge_store(config: object) -> PineconeKnowledgeStore | None:
    api_key = getattr(config, "pinecone_api_key", None)
    index_name = getattr(config, "pinecone_index", None)
    openai_key = getattr(config, "openai_api_key", None)
    if not api_key or not index_name or not openai_key:
        return None
    from app.integrations.llm import LLMDecisionError, OpenAIEmbeddingProvider

    try:
        embeddings = OpenAIEmbeddingProvider(
            openai_key,
            model=getattr(config, "embedding_model", "text-embedding-3-small"),
            timeout_seconds=float(getattr(config, "llm_timeout_seconds", 20.0)),
        )
        return PineconeKnowledgeStore(
            api_key,
            index_name,
            embeddings,
            namespace=getattr(config, "pinecone_namespace", "default"),
        )
    except (LLMDecisionError, RAGProviderError, RuntimeError):
        return None
