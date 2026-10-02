"""ifc_graph_cache: parse once per model version, rebuild when the file changes."""

from __future__ import annotations

import os

from app.services import ifc_graph_cache


def test_artifacts_are_computed_once_per_model_version(tmp_path, monkeypatch):
    path = tmp_path / "m.ifc"
    path.write_text("v1")
    ifc_graph_cache.clear()
    opens = []

    class FakeModel:
        def by_type(self, cls):
            return [1, 2, 3]

    def fake_model(entry):
        opens.append(entry.path)
        return FakeModel()

    monkeypatch.setattr(ifc_graph_cache, "_model", fake_model)
    assert ifc_graph_cache.product_count(path) == 3
    assert ifc_graph_cache.product_count(path) == 3
    assert len(opens) == 1

    # A replaced model (new size/mtime) is a new key: rebuilt, never stale.
    path.write_text("version two")
    os.utime(path, ns=(1, 1))
    ifc_graph_cache.product_count(path)
    assert len(opens) == 2
    ifc_graph_cache.clear()


def test_cache_is_bounded(tmp_path, monkeypatch):
    ifc_graph_cache.clear()
    monkeypatch.setattr(ifc_graph_cache, "_model", lambda e: type("M", (), {"by_type": lambda s, c: []})())
    for i in range(ifc_graph_cache._MAX_MODELS + 3):
        p = tmp_path / f"m{i}.ifc"
        p.write_text(str(i))
        ifc_graph_cache.product_count(p)
    assert len(ifc_graph_cache._entries) == ifc_graph_cache._MAX_MODELS
    ifc_graph_cache.clear()
