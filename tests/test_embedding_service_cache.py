"""Shared EmbeddingService and its bounded LRU cache."""

from __future__ import annotations

from app.services.embedding_service import _BoundedCache, get_shared_embedding_service


def test_shared_service_is_one_instance_per_process():
    assert get_shared_embedding_service() is get_shared_embedding_service()


def test_bounded_cache_evicts_least_recently_used():
    cache = _BoundedCache(2)
    cache["a"] = [1.0]
    cache["b"] = [2.0]
    _ = cache["a"]  # touch: "b" is now the oldest
    cache["c"] = [3.0]
    assert "a" in cache and "c" in cache
    assert "b" not in cache
    assert len(cache) == 2
