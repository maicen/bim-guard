"""Standardized caching service and backends following SOLID principles.

- Single Responsibility: Clear separation between cache storage backends, key generation, and query decoration.
- Open/Closed: Extensible ICacheBackend interface allows plugging in Redis/Memcached/File backends without altering business logic.
- Liskov Substitution: Any ICacheBackend implementation can replace the default in-memory TTL backend.
- Interface Segregation: Discrete interfaces for read, write, and prefix invalidation.
- Dependency Inversion: Services depend on high-level CacheService and decorator abstractions rather than low-level globals.
"""

from __future__ import annotations

import inspect
import os
import tempfile
import threading
import uuid
from abc import ABC
from functools import wraps
from typing import Any, Callable, Optional, Protocol, runtime_checkable

from cachetools import TTLCache

DEFAULT_MAXSIZE = 10000
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


class SharedInvalidationLog:
    """Cross-process invalidation for per-process in-memory caches.

    WHY: production runs uvicorn with several workers (``--workers 4`` in the
    Dockerfile), each holding its own ``TTLCache`` with a 24 h TTL. An
    ``invalidate_cache(...)`` call used to clear only the worker that handled the
    write, so the other workers kept serving the stale value -- e.g. a freshly
    uploaded document stayed missing from ``GET /api/documents`` on 3 of 4
    requests for up to a day.

    Every worker appends the prefixes it invalidates to one append-only file in
    the container's shared temp dir, and before each cache read applies whatever
    other workers appended since it last looked. The read-side cost is one
    ``os.path.getsize`` (the file is only read when it has grown), so cache hits
    stay cheap; only matching keys are dropped. Invariant: entries are whole
    lines written with O_APPEND (atomic for these small writes on POSIX), each
    process tracks its own byte offset (starting at the end of the file), and
    each line carries its writer's id so a process never replays its own entries
    (which would evict values it cached after invalidating).
    """

    CLEAR_ALL = "*"

    def __init__(self, path: str) -> None:
        self._path = path
        self._writer_id = uuid.uuid4().hex[:12]
        self._lock = threading.Lock()
        try:
            self._offset = os.path.getsize(path)
        except OSError:
            self._offset = 0

    def publish(self, prefix: str) -> None:
        try:
            with open(self._path, "ab") as fh:
                line = f"{self._writer_id}\t{prefix.replace(chr(10), ' ')}\n"
                fh.write(line.encode("utf-8"))
        except OSError:
            pass  # caching is an optimisation; never fail the write path over it

    def pending(self) -> list[str]:
        """Prefixes appended (by any process) since this process last checked."""
        try:
            size = os.path.getsize(self._path)
        except OSError:
            return []
        with self._lock:
            if size == self._offset:
                return []
            if size < self._offset:  # file was truncated or replaced
                self._offset = 0
            try:
                with open(self._path, "rb") as fh:
                    fh.seek(self._offset)
                    chunk = fh.read(size - self._offset)
            except OSError:
                return []
            end = chunk.rfind(b"\n")
            if end < 0:
                return []  # a writer is mid-line; pick it up next time
            self._offset += end + 1
            prefixes = []
            for line in chunk[:end].decode("utf-8", "replace").split("\n"):
                writer, sep, prefix = line.partition("\t")
                if sep and prefix and writer != self._writer_id:
                    prefixes.append(prefix)
            return prefixes


def _shared_log(name: str) -> SharedInvalidationLog:
    directory = os.environ.get("BIMGUARD_CACHE_INVALIDATION_DIR") or tempfile.gettempdir()
    return SharedInvalidationLog(os.path.join(directory, f"bimguard-cache-invalidations-{name}.log"))


class InMemoryTTLCacheBackend(ABC):
    """Concrete thread-safe in-memory cache backend built on cachetools.TTLCache (SRP)."""

    def __init__(
        self,
        maxsize: int = DEFAULT_MAXSIZE,
        ttl: int = DEFAULT_TTL,
        shared_log: Optional[SharedInvalidationLog] = None,
    ) -> None:
        self._maxsize = maxsize
        self._ttl = ttl
        self._lock = threading.RLock()
        self._store = TTLCache(maxsize=maxsize, ttl=ttl)
        self._hits = 0
        self._misses = 0
        # Optional cross-worker invalidation (see SharedInvalidationLog); None keeps
        # the backend purely process-local (tests, single-process tools).
        self._shared_log = shared_log

    def _apply_remote_invalidations(self) -> None:
        if self._shared_log is None:
            return
        for prefix in self._shared_log.pending():
            if prefix == SharedInvalidationLog.CLEAR_ALL:
                with self._lock:
                    self._store.clear()
            else:
                self._invalidate_local(prefix)

    @property
    def raw_cache(self) -> TTLCache:
        """Direct access to the underlying TTLCache instance."""
        return self._store

    def get(self, key: str) -> Any:
        self._apply_remote_invalidations()
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
        if self._shared_log is not None:
            self._shared_log.publish(SharedInvalidationLog.CLEAR_ALL)

    def invalidate_prefix(self, prefix: str) -> int:
        count = self._invalidate_local(prefix)
        if self._shared_log is not None and str(prefix).strip():
            self._shared_log.publish(str(prefix).strip())
        return count

    def _invalidate_local(self, prefix: str) -> int:
        normalized = str(prefix).strip()
        if not normalized:
            return 0

        with self._lock:
            count = 0
            prefix_with_colon = normalized if normalized.endswith(":") else f"{normalized}:"
            to_remove = set()

            for key in list(self._store.keys()):
                key_str = str(key)
                if key_str == normalized or key_str.startswith(normalized) or key_str.startswith(prefix_with_colon):
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
_default_backend = InMemoryTTLCacheBackend(
    maxsize=DEFAULT_MAXSIZE, ttl=DEFAULT_TTL, shared_log=_shared_log("default")
)
cache_service = CacheService(_default_backend)
local_cache = _default_backend.raw_cache

# Short-TTL backend for the raw adapter layer (app.services.db_adapters). This
# sits beneath every service-level cache above and covers tables nothing else
# caches (organizations, memberships, grants, profiles, rule_folders/rules
# rows read outside the decorated entry points, etc). A 20s TTL matches the
# staleness the dashboard endpoint already advertises via its own
# Cache-Control header, and bounds cross-worker staleness in a multi-worker
# production deployment to the same window.
DEFAULT_ADAPTER_TTL = 20
_adapter_backend = InMemoryTTLCacheBackend(
    maxsize=DEFAULT_MAXSIZE, ttl=DEFAULT_ADAPTER_TTL, shared_log=_shared_log("adapter")
)
adapter_cache_service = CacheService(_adapter_backend)


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
