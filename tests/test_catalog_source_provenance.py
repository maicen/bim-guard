"""A degraded corrosion run must be distinguishable from a good one afterwards.

The GC-001, CC-001 and MC-001 catalogs load from seeded rule rows, else the
stored ``static_data_assets`` payload, else the hardcoded fallback tables -- and
the fallback tables band some elements differently. Every finding therefore
records which of the three built its engine's thresholds, in ``catalog_source``,
and the switches between them are logged. None of this may move a score.

See ``docs/defects/corrosion-catalog-fallback-divergence.md``.

Run: uv run pytest tests/test_catalog_source_provenance.py -v
"""

from __future__ import annotations

import copy
import csv
import io
import logging
from typing import Any

import pytest
from postgrest.exceptions import APIError

from app.engines import bimguard_corrosion_engine, bimguard_crevice_engine, bimguard_mic_engine
from app.modules.phase_6 import phase_6c_corrosion_ui as ui
from app.modules.phase_6.phase_6e_export import CSV_COLUMNS, _description, to_csv, to_json
from app.services import corrosion_rule_catalog as catalog
from app.services import db_adapters
from tests.test_compute_pool import _sample_element

LOADERS = {
    "GC-001": ("galvanic_corrosion_ruleset.json", catalog.load_gc_catalog),
    "CC-001": ("crevice_corrosion_ruleset.json", catalog.load_cc_catalog),
    "MC-001": ("mic_corrosion_ruleset.json", catalog.load_mc_catalog),
}
ENGINES = {
    "GC-001": bimguard_corrosion_engine,
    "CC-001": bimguard_crevice_engine,
    "MC-001": bimguard_mic_engine,
}


def _stored_payload(filename: str) -> dict[str, Any]:
    """Return a payload equal to the fallback in content but not the fallback object."""
    return copy.deepcopy(catalog._FALLBACK_RULESETS[filename])


def _seeded_rows(monkeypatch, code: str) -> list[dict[str, Any]]:
    """Rows as a stored-payload load synthesises them, for use as table rows."""
    filename, loader = LOADERS[code]
    monkeypatch.setattr(catalog, "_rules_for", lambda ruleset_id: [])
    monkeypatch.setattr(catalog, "_load_json_ruleset", lambda f: _stored_payload(filename))
    return list(loader()["rules"])


# ---------------------------------------------------------------------------
# The three source states
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("code", sorted(LOADERS))
def test_rows_present_records_database_rows(monkeypatch, code):
    filename, loader = LOADERS[code]
    rows = _seeded_rows(monkeypatch, code)
    monkeypatch.setattr(catalog, "_rules_for", lambda ruleset_id: rows)
    monkeypatch.setattr(catalog, "_load_json_ruleset", lambda f: _stored_payload(filename))

    loaded = loader()
    assert loaded["catalog_source"] == catalog.CATALOG_SOURCE_ROWS
    assert loaded["catalog_payload_source"] == catalog.CATALOG_SOURCE_PAYLOAD


@pytest.mark.parametrize("code", sorted(LOADERS))
def test_no_rows_with_a_stored_payload_records_stored_payload(monkeypatch, code, caplog):
    filename, loader = LOADERS[code]
    monkeypatch.setattr(catalog, "_rules_for", lambda ruleset_id: [])
    monkeypatch.setattr(catalog, "_load_json_ruleset", lambda f: _stored_payload(filename))

    with caplog.at_level(logging.WARNING):
        loaded = loader()
    assert loaded["catalog_source"] == catalog.CATALOG_SOURCE_PAYLOAD
    assert f"engine={code}" in caplog.text
    assert "catalog_source=stored_payload" in caplog.text
    assert "Using hardcoded fallback ruleset" not in caplog.text


@pytest.mark.parametrize("code", sorted(LOADERS))
def test_no_rows_and_no_payload_records_in_memory_fallback(monkeypatch, code, caplog):
    filename, loader = LOADERS[code]
    monkeypatch.setattr(catalog, "_rules_for", lambda ruleset_id: [])
    monkeypatch.setattr(
        catalog, "_load_json_ruleset", lambda f: catalog._FALLBACK_RULESETS[filename]
    )

    with caplog.at_level(logging.WARNING):
        loaded = loader()
    assert loaded["catalog_source"] == catalog.CATALOG_SOURCE_FALLBACK
    assert loaded["catalog_payload_source"] == catalog.CATALOG_SOURCE_FALLBACK
    assert "Using hardcoded fallback ruleset" in caplog.text
    assert "catalog_source=in_memory_fallback" in caplog.text


def test_rows_with_a_fallback_payload_are_not_reported_as_fallback(monkeypatch, caplog):
    """The case the old WARNING got wrong: rows were live, only the payload was not."""
    filename, loader = LOADERS["CC-001"]
    rows = _seeded_rows(monkeypatch, "CC-001")
    monkeypatch.setattr(catalog, "_rules_for", lambda ruleset_id: rows)
    monkeypatch.setattr(
        catalog, "_load_json_ruleset", lambda f: catalog._FALLBACK_RULESETS[filename]
    )

    with caplog.at_level(logging.WARNING):
        loaded = loader()
    assert loaded["catalog_source"] == catalog.CATALOG_SOURCE_ROWS
    assert loaded["catalog_payload_source"] == catalog.CATALOG_SOURCE_FALLBACK
    assert "Using hardcoded fallback ruleset" not in caplog.text
    assert "Catalog built from database rows" in caplog.text


def test_a_failed_rows_read_is_logged(monkeypatch, caplog):
    class Broken:
        def list_by_ruleset(self, ruleset_id):
            raise RuntimeError("connection refused")

    monkeypatch.setattr(catalog, "RuleService", Broken)
    with caplog.at_level(logging.WARNING):
        assert catalog._rules_for("BIMGUARD-CC-001") == []
    assert "Rule rows could not be read ruleset_id=BIMGUARD-CC-001" in caplog.text


# ---------------------------------------------------------------------------
# Onto the finding, per engine
# ---------------------------------------------------------------------------


@pytest.fixture
def mixed_sources(monkeypatch):
    """Give each engine a different recorded source without touching its tables."""
    sources = {
        "GC-001": catalog.CATALOG_SOURCE_ROWS,
        "CC-001": catalog.CATALOG_SOURCE_PAYLOAD,
        "MC-001": catalog.CATALOG_SOURCE_FALLBACK,
    }
    for code, module in ENGINES.items():
        value = {"catalog_source": sources[code], "catalog_payload_source": "x"}
        monkeypatch.setattr(module, "catalog_source", lambda value=value: dict(value))
    monkeypatch.setattr(catalog, "reload_all_catalogs", lambda: None)
    monkeypatch.setenv("BIMGUARD_DISABLE_MULTIPROCESSING", "1")
    return sources


def _run(elements):
    return ui.run_corrosion_analysis(
        {"quality": {"valid": True}, "elements": elements},
        include_low=True,
        engines=["GC-001", "CC-001", "MC-001"],
    )["audit_issues"]


def test_each_finding_carries_its_own_engines_source(mixed_sources):
    issues = _run([_sample_element(i) for i in range(6)])
    per_engine = [i for i in issues if i.metadata.get("mechanism_code") in mixed_sources]
    assert per_engine
    for issue in per_engine:
        assert issue.metadata["catalog_source"] == mixed_sources[issue.metadata["mechanism_code"]]


def test_the_source_is_read_in_the_scoring_process():
    items, _ = ui._assess_elements_chunk(
        [_sample_element(0)], specs_codes=("GC-001", "CC-001", "MC-001"), include_low=True
    )
    for item in items:
        assert item[-1] == ENGINES[item[2]].catalog_source()


def test_adding_the_field_changes_no_score_band_or_mitigation(mixed_sources, monkeypatch):
    """The same run with the provenance switched off differs only in the added keys."""
    elements = [_sample_element(i) for i in range(12)]
    with_field = _run(elements)
    monkeypatch.setattr(ui, "_catalog_provenance", lambda spec: {})
    without_field = _run(elements)

    def core(issue):
        return (
            issue.id, issue.element_id, issue.rule_id, issue.band, issue.score,
            issue.mitigation, issue.description, issue.title,
        )

    assert [core(i) for i in with_field] == [core(i) for i in without_field]
    for a, b in zip(with_field, without_field):
        stripped = {
            k: v for k, v in a.metadata.items()
            if k not in ("catalog_source", "catalog_payload_source")
        }
        assert stripped == b.metadata


# ---------------------------------------------------------------------------
# Into the exports
# ---------------------------------------------------------------------------


def test_the_source_reaches_csv_json_and_bcf(mixed_sources):
    issues = [i for i in _run([_sample_element(i) for i in range(3)]) if i.metadata.get("catalog_source")]
    result = {"audit_issues": issues}

    assert CSV_COLUMNS[-1] == "catalog_source"
    rows = list(csv.DictReader(io.StringIO(to_csv(result))))
    assert {r["catalog_source"] for r in rows} <= set(catalog.CATALOG_SOURCES)
    assert any(r["catalog_source"] for r in rows)

    assert '"catalog_source": "in_memory_fallback"' in to_json(result)

    assert any("  Catalog source: " in _description(i) for i in issues)


# ---------------------------------------------------------------------------
# The adapter's per-table degrade
# ---------------------------------------------------------------------------


class _MissingTableClient:
    def table(self, name):
        raise APIError({"code": "PGRST205", "message": "relation not in schema cache"})


def test_a_table_degrade_is_logged_once(caplog):
    name = "test_catalog_source_degrade_table"
    adapter = db_adapters.SupabaseTableAdapter(_MissingTableClient(), name, {}, pk="id")
    try:
        with caplog.at_level(logging.WARNING):
            assert adapter.rows_where("ruleset_id = ?", ["X"]) == []
            adapter.rows_where("ruleset_id = ?", ["X"])
        messages = [r.getMessage() for r in caplog.records if "Table degraded" in r.getMessage()]
        assert len(messages) == 1
        assert f"table={name}" in messages[0]
        assert "operation=rows_where" in messages[0]
        assert "error_code=PGRST205" in messages[0]
        assert "no longer authoritative" in messages[0]
    finally:
        db_adapters._USE_MEMORY_FALLBACK_TABLES.discard(name)
        db_adapters._SHARED_MEMORY_TABLES.pop(name, None)
