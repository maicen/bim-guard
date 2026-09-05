"""Short-lived cache for computed ``AnalysisResult`` values.

An analysis over a large model takes seconds. Downloading its CSV, then its
JSON, then its BCF re-ran it three times. This keeps the result between those
requests.

DESIGN CONSTRAINTS, AND WHY

    **Keyed on the model's SHA-256, not just the project id.** A cache keyed on
    ``project_id`` alone goes stale the moment someone re-uploads: the next
    download would serve findings for the previous model while the page shows
    the new one. Including the digest means a changed model cannot hit a stale
    entry — it simply misses and recomputes. The digest is already computed by
    Session A on upload and Session B on parse, so this reuses an existing
    value rather than inventing a second key.

    **Keyed on the engines that ran, too.** The engine selection is part of
    what produced the result, so it is part of the key. A run of GC-001 alone
    and a run of all three engines over the same model are different results,
    and one must never be served for the other.

    **A miss is never an error.** Callers run the analysis on a miss. The cache
    is an optimisation; nothing depends on it for correctness. That matters
    because this store is per-process: under multiple uvicorn workers a request
    can land on a worker that has never seen the entry, and the only visible
    consequence must be that it takes longer.

    **Bounded and expiring.** ``analyze.py`` keeps results in module-level
    globals (``_last_simple_compliance``) that grow without limit and never
    expire. This holds at most :data:`MAX_ENTRIES`, evicting least-recently-used,
    and treats anything older than :data:`TTL_SECONDS` as absent.

    **Not a database.** Results are derived data, reproducible from the model at
    any time. Persisting them would add a schema, a migration and an
    invalidation problem in exchange for saving a recomputation.
"""

from __future__ import annotations

import threading
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any

from app.logging_config import get_logger

logger = get_logger(__name__)

#: Most results held at once. Each is a list of Issues plus statistics — tens of
#: KB for a large model — so this bounds the store to a few MB.
MAX_ENTRIES: int = 32

#: How long an entry stays usable. Long enough to cover a user reading a results
#: page and downloading all three formats; short enough that a stale process
#: does not hold results indefinitely.
TTL_SECONDS: float = 1800.0


@dataclass(frozen=True)
class CacheKey:
    """What makes one cached result distinct from another.

    Attributes:
        project_id: Owning project.
        slug: Analysis slug, e.g. ``"corrosion"`` or ``"seismic"``. Two
            analyses of one model are different results.
        source_sha256: Digest of the model the result was computed from. This
            is what makes staleness impossible rather than merely unlikely.
        engines: Ruleset codes the result was computed from, canonicalised and
            in a stable order. A partial run is a different result from a full
            one, so without this a GC-001-only run would be served back to a
            request that asked for every engine — the same staleness the digest
            rules out, arriving through the selection instead of the model.
            Empty means the caller made no selection.
        include_low: Whether the result carries Low-band verdicts. A run that
            suppressed them is a different result from one that kept them --
            on Clinic Plumbing the difference is GC-001's 6,587 findings -- so
            without this the first of the two to be computed would be served
            back to a caller who asked for the other.
    """

    project_id: int
    slug: str
    source_sha256: str
    engines: tuple[str, ...] = ()
    include_low: bool = True


class AnalysisCache:
    """A bounded, expiring, thread-safe store of analysis results.

    Thread-safe because uvicorn serves requests from a thread pool: two
    downloads of the same result can be in flight at once, and ``OrderedDict``
    reordering under ``move_to_end`` is not atomic.
    """

    def __init__(self, max_entries: int = MAX_ENTRIES, ttl_seconds: float = TTL_SECONDS):
        self._entries: OrderedDict[CacheKey, tuple[float, dict]] = OrderedDict()
        self._max_entries = max_entries
        self._ttl = ttl_seconds
        self._lock = threading.Lock()
        self._hits = 0
        self._misses = 0

    def get(self, key: CacheKey) -> dict | None:
        """Return the cached result for ``key``, or ``None``.

        ``None`` means "compute it" — never "something went wrong".
        """
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                self._misses += 1
                return None

            stored_at, result = entry
            if (time.monotonic() - stored_at) > self._ttl:
                # Expired entries are dropped on read rather than by a sweeper:
                # there is no background task to run one, and an entry nobody
                # reads costs only its slot.
                del self._entries[key]
                self._misses += 1
                logger.debug("Analysis cache expired project_id=%d slug=%s", key.project_id, key.slug)
                return None

            self._entries.move_to_end(key)
            self._hits += 1
            logger.debug("Analysis cache hit project_id=%d slug=%s", key.project_id, key.slug)
            return result

    def put(self, key: CacheKey, result: dict) -> None:
        """Store ``result`` under ``key``, evicting the least recently used."""
        with self._lock:
            self._entries[key] = (time.monotonic(), result)
            self._entries.move_to_end(key)
            while len(self._entries) > self._max_entries:
                evicted, _ = self._entries.popitem(last=False)
                logger.debug(
                    "Analysis cache evicted project_id=%d slug=%s",
                    evicted.project_id,
                    evicted.slug,
                )

    def invalidate_project(self, project_id: int) -> int:
        """Drop every entry for one project. Returns how many were removed.

        Called when a project gets a new model. Strictly speaking the digest in
        the key already prevents a stale hit, so this frees memory rather than
        protecting correctness — but leaving superseded results to age out would
        hold the store at its ceiling for no benefit.
        """
        with self._lock:
            doomed = [k for k in self._entries if k.project_id == project_id]
            for key in doomed:
                del self._entries[key]
        if doomed:
            logger.info(
                "Analysis cache invalidated project_id=%d entries=%d", project_id, len(doomed)
            )
        return len(doomed)

    def clear(self) -> None:
        """Empty the store. For tests and for a deliberate operational reset."""
        with self._lock:
            self._entries.clear()
            self._hits = 0
            self._misses = 0

    def stats(self) -> dict[str, Any]:
        """Return counters, for logging and for asserting behaviour in tests."""
        with self._lock:
            return {
                "entries": len(self._entries),
                "max_entries": self._max_entries,
                "ttl_seconds": self._ttl,
                "hits": self._hits,
                "misses": self._misses,
            }


#: Process-wide instance. Per-process by design — see the module docstring on
#: why a miss under multiple workers is a latency question, not a correctness one.
ANALYSIS_CACHE = AnalysisCache()
