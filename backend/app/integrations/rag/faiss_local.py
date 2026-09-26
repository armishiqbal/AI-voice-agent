"""Small local FAISS index, persisted as validated JSON rather than pickle.

For one backend process. Use a shared managed vector store for multiple replicas.
Embeddings are supplied by the same real provider as Pinecone.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from threading import RLock

from app.integrations.rag.pinecone import EmbeddingProvider, RAGProviderError, RetrievedChunk


class FaissKnowledgeStore:
    def __init__(self, path: str, embedding_provider: EmbeddingProvider) -> None:
        try:
            import faiss
            import numpy as np
        except ImportError as error:
            raise RAGProviderError("Install the local-rag extra to enable FAISS") from error
        self.faiss = faiss
        self.np = np
        self.path = Path(path)
        self.embedding_provider = embedding_provider
        self.lock = RLock()
        self.rows: dict[str, dict] = {}
        if self.path.exists():
            try:
                rows = json.loads(self.path.read_text())
                if not isinstance(rows, dict):
                    raise TypeError("Invalid index")
                for source_id, row in rows.items():
                    if not isinstance(source_id, str) or not isinstance(row.get("text"), str) or not isinstance(row.get("metadata"), dict):
                        raise TypeError("Invalid chunk")
                    self._matrix([row["vector"]])
                self.rows = rows
            except (ValueError, TypeError, KeyError, AttributeError, OSError) as error:
                raise RAGProviderError("Cannot load local vector index") from error

    def _matrix(self, vectors: list[list[float]]):
        matrix = self.np.asarray(vectors, dtype="float32")
        if matrix.ndim != 2 or not matrix.shape[1] or not self.np.isfinite(matrix).all():
            raise RAGProviderError("Invalid embedding vectors")
        if (self.np.linalg.norm(matrix, axis=1) == 0).any():
            raise RAGProviderError("Zero embedding vector")
        self.faiss.normalize_L2(matrix)
        return matrix

    def upsert(self, chunks: list[RetrievedChunk]) -> None:
        if not chunks:
            return
        try:
            vectors = self._matrix(self.embedding_provider.embed([chunk.text for chunk in chunks]))
            if len(vectors) != len(chunks):
                raise ValueError("Embedding count mismatch")
            with self.lock:
                rows = dict(self.rows)
                for chunk, vector in zip(chunks, vectors, strict=True):
                    rows[chunk.source_id] = {"text": chunk.text, "metadata": chunk.metadata, "vector": vector.tolist()}
                self._matrix([row["vector"] for row in rows.values()])
                self.path.parent.mkdir(parents=True, exist_ok=True)
                temporary = self.path.with_suffix(self.path.suffix + ".tmp")
                with temporary.open("w") as stream:
                    json.dump(rows, stream, ensure_ascii=False)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(temporary, self.path)
                self.rows = rows
        except Exception as error:
            raise RAGProviderError("Local vector upsert failed") from error

    @staticmethod
    def _matches(metadata: dict[str, object], filters: dict[str, object]) -> bool:
        for key, expected in filters.items():
            if isinstance(expected, dict):
                if set(expected) != {"$in"} or not isinstance(expected["$in"], list):
                    raise RAGProviderError("Unsupported local metadata filter")
                if metadata.get(key) not in expected["$in"]:
                    return False
            elif metadata.get(key) != expected:
                return False
        return True

    def query(self, text: str, metadata_filter: dict[str, object] | None = None, top_k: int = 5) -> list[RetrievedChunk]:
        if not 1 <= top_k <= 100:
            raise RAGProviderError("top_k must be between 1 and 100")
        try:
            with self.lock:
                selected = [(key, row) for key, row in self.rows.items() if self._matches(row["metadata"], metadata_filter or {})]
            if not selected:
                return []
            vectors = self._matrix([row["vector"] for _, row in selected])
            query = self._matrix(self.embedding_provider.embed([text]))
            if query.shape != (1, vectors.shape[1]):
                raise ValueError("Embedding model dimension changed; rebuild the index")
            index = self.faiss.IndexFlatIP(vectors.shape[1])
            index.add(vectors)
            scores, indices = index.search(query, min(top_k, len(selected)))
            return [RetrievedChunk(selected[int(i)][0], selected[int(i)][1]["text"], float(score), selected[int(i)][1]["metadata"]) for score, i in zip(scores[0], indices[0], strict=True)]
        except Exception as error:
            raise RAGProviderError("Local vector query failed") from error
