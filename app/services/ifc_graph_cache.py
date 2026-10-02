"""Per-process cache of IFC graph artifacts for the read-only graph endpoints.

WHY THIS EXISTS

    ``/api/graph/{project_id}/status``, ``/spatial-tree``,
    ``/element/{guid}/relationships``, ``/code-to-ifc-trace`` and
    ``/model-health`` each used to ``ifcopenshell.open`` the primary model,
    rebuild the NetworkX relationship graph (a ``get_psets`` call per
    product), and -- for some -- rebuild spatial adjacency and centrality, on
    *every* request. Those are seconds of CPU per call on a large model, all
    to derive data that only changes when the file does. The viewer calls the
    relationships endpoint once per clicked element, so the same model was
    re-parsed over and over.

HOW IT STAYS CORRECT

    Entries are keyed on ``(resolved path, size, mtime_ns)``: replacing or
    re-uploading a model changes the key, so a stale artifact can never be
    served -- it simply misses and is rebuilt. Each artifact is computed
    lazily, once per model, under that model's lock (so concurrent first
    requests do the work once and ifcopenshell is never driven from two
    threads at once).

    Cached artifacts are shared between requests: callers must treat them as
    read-only. The NetworkX graph and the rdflib BOT graph hold only plain
    data (GUID strings, dicts), not ifcopenshell entities.

    The cache is per process and small (``_MAX_MODELS``) because each entry
    keeps the opened model in memory; with several uvicorn workers each holds
    its own copy, which is acceptable for a handful of recently viewed models.
"""

from __future__ import annotations

import threading
from collections import OrderedDict
from collections.abc import Callable
from pathlib import Path
from typing import Any

from app.logging_config import get_logger

logger = get_logger(__name__)

#: Models kept per process. Each entry holds an opened ifcopenshell model
#: (large models are hundreds of MB), so this stays deliberately small.
_MAX_MODELS = 2

_CacheKey = tuple[str, int, int]


class _ModelEntry:
    """Lazily computed artifacts for one version of one model file."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.lock = threading.Lock()
        self.artifacts: dict[str, Any] = {}

    def get(self, name: str, compute: Callable[["_ModelEntry"], Any]) -> Any:
        with self.lock:
            if name not in self.artifacts:
                self.artifacts[name] = compute(self)
            return self.artifacts[name]


_entries: OrderedDict[_CacheKey, _ModelEntry] = OrderedDict()
_entries_lock = threading.Lock()


def _entry_for(path: Path) -> _ModelEntry:
    stat = path.stat()
    key: _CacheKey = (str(path.resolve()), stat.st_size, stat.st_mtime_ns)
    with _entries_lock:
        entry = _entries.get(key)
        if entry is None:
            entry = _ModelEntry(path)
            _entries[key] = entry
            while len(_entries) > _MAX_MODELS:
                _entries.popitem(last=False)
        else:
            _entries.move_to_end(key)
        return entry


def clear() -> None:
    """Drop every cached model (tests, or to free memory)."""
    with _entries_lock:
        _entries.clear()


# -- artifact builders (run under the entry's lock) --------------------------


def _model(entry: _ModelEntry) -> Any:
    import ifcopenshell

    return ifcopenshell.open(str(entry.path))


def _ifc_graph(entry: _ModelEntry) -> Any:
    from app.modules.ifc_reader.ifc_graph import build_ifc_graph

    return build_ifc_graph(_get_locked(entry, "model", _model))


def _get_locked(entry: _ModelEntry, name: str, compute: Callable[[_ModelEntry], Any]) -> Any:
    """Like ``entry.get`` for use inside a builder that already holds the lock."""
    if name not in entry.artifacts:
        entry.artifacts[name] = compute(entry)
    return entry.artifacts[name]


def _adjacency(entry: _ModelEntry) -> Any:
    from app.modules.ifc_reader.ifc_spatial import IFCSpatialAdjacency

    model = _get_locked(entry, "model", _model)
    return IFCSpatialAdjacency(model, fallback_to_geometric=True).build()


def _summary(entry: _ModelEntry) -> dict:
    from app.modules.ifc_reader.ifc_graph import build_ifc_graph_summary

    return build_ifc_graph_summary(_get_locked(entry, "ifc_graph", _ifc_graph))


# -- public API ---------------------------------------------------------------


def graph_summary(path: Path) -> dict:
    """``build_ifc_graph_summary`` (with centrality) for ``path``. Read-only."""
    return _entry_for(path).get("summary", _summary)


def adjacency_flags(path: Path) -> tuple[bool, bool]:
    """``(has_boundaries, is_geometric_fallback)`` of the model's spatial adjacency."""

    def compute(entry: _ModelEntry) -> tuple[bool, bool]:
        adj = _get_locked(entry, "adjacency", _adjacency)
        return bool(adj.has_boundaries), bool(adj.is_geometric_fallback)

    return _entry_for(path).get("adjacency_flags", compute)


def spatial_tree(path: Path) -> dict | None:
    """``build_spatial_tree`` for ``path``. Read-only."""
    from app.modules.ifc_reader.ifc_graph import build_spatial_tree

    return _entry_for(path).get(
        "spatial_tree", lambda e: build_spatial_tree(_get_locked(e, "ifc_graph", _ifc_graph))
    )


def bot_graph(path: Path) -> Any:
    """The BOT/SAREF4BLDG rdflib graph for ``path``. Read-only."""
    from app.modules.ifc_reader.bot_graph import build_bot_graph

    def compute(entry: _ModelEntry) -> Any:
        return build_bot_graph(
            _get_locked(entry, "ifc_graph", _ifc_graph),
            _get_locked(entry, "adjacency", _adjacency),
        )

    return _entry_for(path).get("bot_graph", compute)


def product_count(path: Path) -> int:
    """Number of ``IfcProduct`` entities in ``path``."""
    return _entry_for(path).get(
        "product_count", lambda e: len(_get_locked(e, "model", _model).by_type("IfcProduct"))
    )
