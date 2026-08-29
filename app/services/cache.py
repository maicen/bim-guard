"""In-memory caching utilities built on cachetools.TTLCache."""

from __future__ import annotations

import inspect
import threading
from functools import wraps
from typing import Any, Callable

from cachetools import TTLCache

# Global in-memory cache holding up to 1000 items with a 24-hour default TTL
DEFAULT_MAXSIZE = 1000
DEFAULT_TTL = 86400  # 24 hours

_CACHE_LOCK = threading.RLock()
local_cache = TTLCache(maxsize=DEFAULT_MAXSIZE, ttl=DEFAULT_TTL)
_stats = {"hits": 0, "misses": 0}


def get_cache() -> TTLCache:
    """Return the global TTLCache instance."""
    return local_cache


def cache_stats() -> dict[str, Any]:
    """Return current cache statistics and metrics."""
    with _CACHE_LOCK:
        return {
            "size": len(local_cache),
            "maxsize": getattr(local_cache, "maxsize", DEFAULT_MAXSIZE),
            "ttl": getattr(local_cache, "ttl", DEFAULT_TTL),
            "hits": _stats["hits"],
            "misses": _stats["misses"],
        }


def clear_cache() -> None:
    """Clear all entries from the local RAM cache and reset statistics."""
    with _CACHE_LOCK:
        local_cache.clear()
        _stats["hits"] = 0
        _stats["misses"] = 0


def invalidate_cache(key_or_prefix: str) -> int:
    """Invalidate an exact key or all keys sharing the given prefix.

    Args:
        key_or_prefix: Exact cache key or prefix (e.g. 'bimguard:projects:item' or 'bimguard:rules').

    Returns:
        The number of evicted entries.
    """
    normalized = str(key_or_prefix).strip()
    if not normalized:
        return 0

    with _CACHE_LOCK:
        count = 0
        prefix_with_colon = normalized if normalized.endswith(":") else f"{normalized}:"

        to_remove = set()
        for key in list(local_cache.keys()):
            key_str = str(key)
            if key_str == normalized or key_str.startswith(prefix_with_colon):
                to_remove.add(key)

        for key in to_remove:
            if key in local_cache:
                local_cache.pop(key, None)
                count += 1

        return count


def cache_db_query(key_prefix: str):
    """Decorate synchronous or asynchronous query methods with in-memory caching.

    Args:
        key_prefix: Prefix identifier for the cached query (e.g. 'bimguard:projects:item').

    Returns:
        Decorator wrapping the target callable with RAM caching.
    """

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
                with _CACHE_LOCK:
                    if cache_key in local_cache:
                        _stats["hits"] += 1
                        return local_cache[cache_key]
                    _stats["misses"] += 1

                result = await func(*args, **kwargs)

                if result is not None:
                    with _CACHE_LOCK:
                        local_cache[cache_key] = result

                return result

            return async_wrapper

        @wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            cache_key = _build_key(args, kwargs)
            with _CACHE_LOCK:
                if cache_key in local_cache:
                    _stats["hits"] += 1
                    return local_cache[cache_key]
                _stats["misses"] += 1

            result = func(*args, **kwargs)

            if result is not None:
                with _CACHE_LOCK:
                    local_cache[cache_key] = result

            return result

        return sync_wrapper

    return decorator
