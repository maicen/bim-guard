"""Standardized caching service and backends following SOLID principles.

- Single Responsibility: Clear separation between cache storage backends, key generation, and query decoration.
- Open/Closed: Extensible ICacheBackend interface allows plugging in Redis/Memcached/File backends without altering business logic.
- Liskov Substitution: Any ICacheBackend implementation can replace the default in-memory TTL backend.
- Interface Segregation: Discrete interfaces for read, write, and prefix invalidation.
- Dependency Inversion: Services depend on high-level CacheService and decorator abstractions rather than low-level globals.
"""

from __future__ import annotations

import inspect
import threading
from abc import ABC
from functools import wraps
from typing import Any, Callable, Optional, Protocol, runtime_checkable

from cachetools import TTLCache

DEFAULT_MAXSIZE = 1000
DEFAULT_TTL = 86400  # 24 hours


@runtime_checkable
class ICacheBackend(Protocol):
    """Interface Segregation: Low-level cache storage contract."""

    def get(self, key: str) -> Any:
        """Retrieve a value by key or return None."""
        ...

    def set(self, key: str, value: Any) -> None:
        """Store a value with the configured backend TTL."""
        ...

    def pop(self, key: str) -> Any:
        """Remove and return an entry by key."""
        ...

    def clear(self) -> None:
        """Evict all entries from the cache."""
        ...

    def invalidate_prefix(self, prefix: str) -> int:
        """Evict all keys matching an exact key or prefix string."""
        ...

    def stats(self) -> dict[str, Any]:
        """Return backend-specific metrics and statistics."""
        ...


class InMemoryTTLCacheBackend(ABC):
    """Concrete thread-safe in-memory cache backend built on cachetools.TTLCache (SRP)."""

    def __init__(self, maxsize: int = DEFAULT_MAXSIZE, ttl: int = DEFAULT_TTL) -> None:
        self._maxsize = maxsize
        self._ttl = ttl
        self._lock = threading.RLock()
        self._store = TTLCache(maxsize=maxsize, ttl=ttl)
        self._hits = 0
        self._misses = 0

    @property
    def raw_cache(self) -> TTLCache:
        """Direct access to the underlying TTLCache instance."""
        return self._store

    def get(self, key: str) -> Any:
        with self._lock:
            if key in self._store:
                self._hits += 1
                return self._store[key]
            self._misses += 1
            return None

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            self._store[key] = value

    def pop(self, key: str) -> Any:
        with self._lock:
            return self._store.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._store.clear()
            self._hits = 0
            self._misses = 0

    def invalidate_prefix(self, prefix: str) -> int:
        normalized = str(prefix).strip()
        if not normalized:
            return 0

        with self._lock:
            count = 0
            prefix_with_colon = normalized if normalized.endswith(":") else f"{normalized}:"
            to_remove = set()

            for key in list(self._store.keys()):
                key_str = str(key)
                if key_str == normalized or key_str.startswith(prefix_with_colon):
                    to_remove.add(key)

            for key in to_remove:
                if key in self._store:
                    self._store.pop(key, None)
                    count += 1

            return count

    def stats(self) -> dict[str, Any]:
        with self._lock:
            return {
                "size": len(self._store),
                "maxsize": self._maxsize,
                "ttl": self._ttl,
                "hits": self._hits,
                "misses": self._misses,
            }


class CacheService:
    """High-level caching service coordinating backends and function decoration (SRP & DIP)."""

    def __init__(self, backend: Optional[ICacheBackend] = None) -> None:
        self._backend: InMemoryTTLCacheBackend = backend or InMemoryTTLCacheBackend()

    @property
    def backend(self) -> InMemoryTTLCacheBackend:
        return self._backend

    def get(self, key: str) -> Any:
        return self._backend.get(key)

    def set(self, key: str, value: Any) -> None:
        self._backend.set(key, value)

    def clear(self) -> None:
        self._backend.clear()

    def invalidate(self, key_or_prefix: str) -> int:
        return self._backend.invalidate_prefix(key_or_prefix)

    def get_stats(self) -> dict[str, Any]:
        return self._backend.stats()

    def cached_query(self, key_prefix: str):
        """Decorate sync or async functions with caching."""

        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            is_coroutine = inspect.iscoroutinefunction(func)
            sig = inspect.signature(func)

            def _build_key(args: tuple[Any, ...], kwargs: dict[str, Any]) -> str:
                try:
                    bound = sig.bind(*args, **kwargs)
                    bound.apply_defaults()
                    params = {
                        k: v
                        for k, v in bound.arguments.items()
                        if k not in ("self", "cls")
                    }
                except Exception:
                    params = dict(kwargs)

                query_params = "_".join(f"{k}={v}" for k, v in sorted(params.items()))
                return f"{key_prefix}:{query_params}" if query_params else key_prefix

            if is_coroutine:

                @wraps(func)
                async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                    cache_key = _build_key(args, kwargs)
                    cached = self._backend.get(cache_key)
                    if cached is not None:
                        return cached

                    result = await func(*args, **kwargs)
                    if result is not None:
                        self._backend.set(cache_key, result)
                    return result

                return async_wrapper

            @wraps(func)
            def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                cache_key = _build_key(args, kwargs)
                cached = self._backend.get(cache_key)
                if cached is not None:
                    return cached

                result = func(*args, **kwargs)
                if result is not None:
                    self._backend.set(cache_key, result)
                return result

            return sync_wrapper

        return decorator


# ── Global Singleton & Public Utility Functions ──────────────────────────────
_default_backend = InMemoryTTLCacheBackend(maxsize=DEFAULT_MAXSIZE, ttl=DEFAULT_TTL)
cache_service = CacheService(_default_backend)
local_cache = _default_backend.raw_cache


def get_cache() -> TTLCache:
    """Return the global TTLCache instance for backward compatibility."""
    return _default_backend.raw_cache


def cache_stats() -> dict[str, Any]:
    """Return current cache statistics and metrics."""
    return cache_service.get_stats()


def clear_cache() -> None:
    """Clear all entries from the cache and reset statistics."""
    cache_service.clear()


def invalidate_cache(key_or_prefix: str) -> int:
    """Invalidate an exact key or all keys sharing the given prefix."""
    return cache_service.invalidate(key_or_prefix)


def cache_db_query(key_prefix: str):
    """Decorate synchronous or asynchronous query methods with caching."""
    return cache_service.cached_query(key_prefix)
