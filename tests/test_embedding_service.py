"""Unit tests for EmbeddingService."""

import asyncio

from app.services.embedding_service import EmbeddingService


def test_embedding_service_fallback():
    """Verify EmbeddingService generates deterministic normalized fallback vectors when offline."""
    service = EmbeddingService(dimension=64)

    # Empty text returns zero vector
    vec_empty = asyncio.run(service.get_embedding(""))
    assert len(vec_empty) == 64
    assert all(v == 0.0 for v in vec_empty)

    # Text generates normalized non-zero vector
    vec_text = asyncio.run(service.get_embedding("Fire door clear width requirements"))
    assert len(vec_text) == 64
    assert any(v != 0.0 for v in vec_text)

    # Test caching: repeated calls return same vector from cache
    vec_text_2 = asyncio.run(service.get_embedding("Fire door clear width requirements"))
    assert vec_text == vec_text_2


def test_embedding_service_batch():
    """Verify batch embedding generation with caching."""
    service = EmbeddingService(dimension=32)
    texts = [
        "Means of egress sizing",
        "Corridor fire rating",
        "Means of egress sizing",  # Duplicate to test cache hit
    ]
    batch = asyncio.run(service.get_embeddings_batch(texts))
    assert len(batch) == 3
    assert batch[0] == batch[2]
    assert len(batch[0]) == 32
