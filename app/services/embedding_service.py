"""Embedding service for Graph-RAG and Neo4j vector search.

Provides asynchronous embedding generation with in-memory caching, batching,
and graceful offline fallback.
"""

from __future__ import annotations

import asyncio
import hashlib
import os
from typing import Optional

from app.logging_config import get_logger

logger = get_logger(__name__)

DEFAULT_EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
DEFAULT_EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM", "1536"))


class EmbeddingService:
    """Service generating dense vector embeddings for documents and graph entities."""

    def __init__(
        self,
        model: str = DEFAULT_EMBEDDING_MODEL,
        dimension: int = DEFAULT_EMBEDDING_DIM,
        *,
        max_batch_size: int = 64,
    ) -> None:
        self.model = model
        self.dimension = dimension
        self.max_batch_size = max_batch_size
        self._cache: dict[str, list[float]] = {}
        self._lock = asyncio.Lock()

    @staticmethod
    def _hash_text(text: str) -> str:
        """Compute MD5 hash of text for caching."""
        return hashlib.md5(text.strip().encode("utf-8")).hexdigest()

    async def get_embedding(self, text: str) -> list[float]:
        """Generate embedding vector for a single text string."""
        if not text or not text.strip():
            return [0.0] * self.dimension

        cache_key = self._hash_text(text)
        if cache_key in self._cache:
            return self._cache[cache_key]

        embeddings = await self.get_embeddings_batch([text])
        return embeddings[0] if embeddings else [0.0] * self.dimension

    async def get_embeddings_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embedding vectors for a batch of text strings."""
        if not texts:
            return []

        results: list[Optional[list[float]]] = [None] * len(texts)
        missing_indices: list[int] = []
        missing_texts: list[str] = []

        # Check cache
        for idx, text in enumerate(texts):
            clean = text.strip() if text else ""
            if not clean:
                results[idx] = [0.0] * self.dimension
                continue
            key = self._hash_text(clean)
            if key in self._cache:
                results[idx] = self._cache[key]
            else:
                missing_indices.append(idx)
                missing_texts.append(clean)

        if not missing_texts:
            return [r or [0.0] * self.dimension for r in results]

        # Call litellm.aembedding for missing texts in chunks
        for i in range(0, len(missing_texts), self.max_batch_size):
            chunk_texts = missing_texts[i : i + self.max_batch_size]
            chunk_indices = missing_indices[i : i + self.max_batch_size]

            try:
                chunk_embeddings = await self._call_embedding_provider(chunk_texts)
                for c_idx, emb in zip(chunk_indices, chunk_embeddings):
                    results[c_idx] = emb
                    # Store in cache
                    text_key = self._hash_text(texts[c_idx])
                    self._cache[text_key] = emb
            except Exception as exc:
                logger.warning(
                    "Embedding generation failed for %d texts (falling back to deterministic pseudo-vectors): %s",
                    len(chunk_texts),
                    exc,
                )
                for c_idx in chunk_indices:
                    fallback_emb = self._generate_fallback_vector(texts[c_idx])
                    results[c_idx] = fallback_emb
                    text_key = self._hash_text(texts[c_idx])
                    self._cache[text_key] = fallback_emb

        return [r or [0.0] * self.dimension for r in results]

    async def _call_embedding_provider(self, texts: list[str]) -> list[list[float]]:
        """Call litellm.aembedding."""
        try:
            import litellm
            response = await litellm.aembedding(
                model=self.model,
                input=texts,
            )
            data = getattr(response, "data", [])
            embeddings: list[list[float]] = []
            for item in data:
                emb = item.get("embedding") if isinstance(item, dict) else getattr(item, "embedding", None)
                if emb:
                    embeddings.append(list(emb))
                else:
                    embeddings.append([0.0] * self.dimension)
            return embeddings
        except ImportError:
            logger.error("LiteLLM is not installed.")
            raise

    def _generate_fallback_vector(self, text: str) -> list[float]:
        """Generate a deterministic normalized pseudo-embedding based on hash when offline."""
        import math
        vec = [0.0] * self.dimension
        if not text:
            return vec

        h = hashlib.sha256(text.encode("utf-8")).digest()
        for i in range(self.dimension):
            byte_val = h[i % len(h)]
            # Spread across floats between -1.0 and 1.0
            vec[i] = (byte_val - 128.0) / 128.0

        # Normalize to unit length
        norm = math.sqrt(sum(v * v for v in vec))
        if norm > 0:
            vec = [v / norm for v in vec]
        return vec
