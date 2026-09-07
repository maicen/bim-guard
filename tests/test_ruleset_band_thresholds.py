"""Band boundaries must come from the database, not from a parser's blind spot.

Covers audit F1 (``docs/validation/final-godmode-audit-2026-09-07.md``): the
five band-range parse sites split on U+002D alone, so MC-001's en-dashed Medium
and High lower bounds read as absent and the MIC engine substituted literals for
them; ``check_value`` is stored JSON-encoded, so the GC/CC/MC band rows arrived
as ``'"0.85"'`` and coerced to nothing; and the seeder's existence guard read a
cached snapshot, so a second copy of every GC/CC/MC band row was written on
2026-09-06.

Run: uv run pytest tests/test_ruleset_band_thresholds.py -v
"""

from __future__ import annotations

import json
import logging
from typing import Any

import pytest

from app.services import corrosion_rule_catalog as catalog
from app.services import ruleset_seeder as seeder
from app.services.cache import invalidate_cache
from app.services.corrosion_rule_catalog import (
    RulesetIncompleteError,
    _coerce_float,
    _require_complete_bands,
    band_lower_bound,
    parse_band_range,
)
from app.services.rules_service import RuleService

# ---------------------------------------------------------------------------
# The shared range parser
# ---------------------------------------------------------------------------

#: One band range in each dash the stored rulesets and their sources use.
#: GC-001 and CC-001 write U+002D; the MC-001 payload writes U+2013; U+2014 is
#: the third form a transcribed standard plausibly arrives in.
DASHED_RANGES = [
    ("0.35 - 0.65", 0.35, 0.65),      # U+002D, spaced (GC-001 as stored)
    ("0.25 – 0.50", 0.25, 0.50),  # U+2013, spaced (MC-001 as stored)
    ("0.30 — 0.55", 0.30, 0.55),  # U+2014, spaced
    ("0.65-0.85", 0.65, 0.85),        # U+002D, unspaced
    ("0.50–0.75", 0.50, 0.75),    # U+2013, unspaced
]


@pytest.mark.parametrize("text,lower,upper", DASHED_RANGES)
def test_parse_band_range_reads_every_dash(text: str, lower: float, upper: float):
    """Both bounds come back, whichever of the three dashes separates them."""
    assert parse_band_range(text) == (lower, upper)
    assert band_lower_bound(text) == lower


def test_parse_band_range_reads_the_open_upper_form():
    """``"> 0.75"`` is a lower bound with no upper bound."""
    assert parse_band_range("> 0.75") == (0.75, None)
    assert band_lower_bound("> 0.75") == 0.75


def test_parse_band_range_reads_the_open_lower_form():
    """``"< 0.35"`` is an upper bound, and has no lower bound to report."""
    assert parse_band_range("< 0.35") == (None, 0.35)
    with pytest.raises(ValueError) as excinfo:
        band_lower_bound("< 0.35")
    assert "no lower bound" in str(excinfo.value)


@pytest.mark.parametrize("garbage", ["", "   ", "n/a", "high", "0.25 to 0.50", "- -"])
def test_parse_band_range_raises_on_garbage(garbage: str):
    """A malformed range raises. It must never read as an absent one.

    Returning ``None`` here is exactly how MC-001's Medium and High boundaries
    became invisible: the caller could not tell "this band has no lower bound"
    from "this band's lower bound did not parse".
    """
    with pytest.raises(ValueError):
        parse_band_range(garbage)
    with pytest.raises(ValueError):
        band_lower_bound(garbage)


def test_the_five_parse_sites_all_route_through_the_helper():
    """No band range is read anywhere else in the two modules that read them."""
    for module_path in (
        "app/services/corrosion_rule_catalog.py",
        "app/services/ruleset_seeder.py",
    ):
        with open(module_path, encoding="utf-8") as handle:
            source = handle.read()
        assert 'if "-" in range_text' not in source, module_path


# ---------------------------------------------------------------------------
# check_value coercion
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "stored,expected",
    [
        (0.85, 0.85),        # a float, as MM-001 and XM-001 store it
        ("0.85", 0.85),      # a bare numeric string
        ('"0.85"', 0.85),    # JSON-encoded string, as GC/CC/MC store it
        ('"0.30"', 0.30),
        (' "0.75" ', 0.75),
    ],
)
def test_coerce_float_decodes_a_json_quoted_threshold(stored: Any, expected: float):
    """The seven characters ``"0.85"`` are the number 0.85, not an absent value."""
    assert _coerce_float(stored) == pytest.approx(expected)


def test_coerce_float_returns_the_default_for_a_stored_null():
    """A JSON ``null`` is an absent value, reported by the loader, not here."""
    assert _coerce_float("null") is None
    assert _coerce_float("null", 0.0) == 0.0


@pytest.mark.parametrize("stored", ["abc", '"abc"', "{}", "[]", "true"])
def test_coerce_float_logs_an_undecodable_value_against_its_reference(
    stored: str, caplog: pytest.LogCaptureFixture
):
    """A value that is not a number returns the default and names the row."""
    with caplog.at_level(logging.WARNING):
        assert _coerce_float(stored, reference="MC-001.BAND.MEDIUM") is None
    assert "MC-001.BAND.MEDIUM" in caplog.text
    assert repr(stored) in caplog.text


# ---------------------------------------------------------------------------
# The loader contract
# ---------------------------------------------------------------------------


def test_require_complete_bands_names_the_engine_and_every_missing_key():
    """An incomplete band map is a named failure, not a partial dict."""
    with pytest.raises(RulesetIncompleteError) as excinfo:
        _require_complete_bands("MC-001", {"critical": 0.75})
    message = str(excinfo.value)
    assert "MC-001" in message
    assert "medium" in message
    assert "high" in message


def test_require_complete_bands_passes_a_complete_map_through():
    """A complete map is returned unchanged -- no key is invented or altered."""
    thresholds = {"medium": 0.25, "high": 0.5, "critical": 0.75}
    assert _require_complete_bands("MC-001", thresholds) == thresholds


def test_mc_catalog_raises_rather_than_leaving_a_band_to_the_engine(monkeypatch):
    """The lookup layer refuses to hand the MIC engine a gap to fill.

    ``bimguard_mic_engine.classify_mic_risk`` reads ``thresholds.get("medium",
    0.25)``. That literal is only reachable if a catalog loads without the key,
    which is what this check makes impossible.
    """
    payload = json.loads(json.dumps(catalog._FALLBACK_RULESETS["mic_corrosion_ruleset.json"]))
    payload["risk_bands"].pop("High")

    monkeypatch.setattr(catalog, "_rules_for", lambda ruleset_id: [])
    monkeypatch.setattr(catalog, "_load_json_ruleset", lambda filename: payload)

    with pytest.raises(RulesetIncompleteError) as excinfo:
        catalog.load_mc_catalog()
    assert "MC-001" in str(excinfo.value)
    assert "high" in str(excinfo.value)


def test_mc_catalog_reads_an_en_dashed_payload_without_the_engine_literals(monkeypatch):
    """The stored MC-001 ranges are en-dashed; all three boundaries load."""
    payload = json.loads(json.dumps(catalog._FALLBACK_RULESETS["mic_corrosion_ruleset.json"]))
    payload["risk_bands"]["Medium"]["range"] = "0.25 – 0.50"
    payload["risk_bands"]["High"]["range"] = "0.50 – 0.75"

    monkeypatch.setattr(catalog, "_rules_for", lambda ruleset_id: [])
    monkeypatch.setattr(catalog, "_load_json_ruleset", lambda filename: payload)

    assert catalog.load_mc_catalog()["risk_band_thresholds"] == {
        "medium": 0.25,
        "high": 0.50,
        "critical": 0.75,
    }


def test_one_unreadable_row_does_not_take_its_sibling_bands_down():
    """Rows supply what they can; the payload fills only what they did not.

    Before the fix ``_risk_band_thresholds`` returned as soon as the rows
    produced anything at all, so a single unreadable row silenced the JSON
    fallback for the other two bands as well.
    """
    rows = [
        {
            "rule_type": "risk_band",
            "reference": "MC-001.BAND.CRITICAL",
            "keyword": "Critical",
            "check_value": '"0.75"',
            "parameters": json.dumps({"band": "Critical"}),
        },
        {
            "rule_type": "risk_band",
            "reference": "MC-001.BAND.MEDIUM",
            "keyword": "Medium",
            "check_value": "null",
            "parameters": json.dumps({"band": "Medium"}),
        },
    ]
    json_data = {
        "ruleset_id": "BIMGUARD-MC-001",
        "risk_bands": {
            "Medium": {"range": "0.25 – 0.50"},
            "High": {"range": "0.50 – 0.75"},
            "Critical": {"range": "> 0.75"},
        },
    }
    assert catalog._risk_band_thresholds(rows, json_data) == {
        "medium": 0.25,
        "high": 0.50,
        "critical": 0.75,
    }


# ---------------------------------------------------------------------------
# Seeder idempotency
# ---------------------------------------------------------------------------


class FakeRulesTable:
    """An in-memory ``rules`` table that honours the ruleset_id filter.

    ``rows_where`` has to filter for these tests to mean anything: the whole
    question is whether the seeder can see rows that are already there.
    """

    def __init__(self) -> None:
        self.rows_list: list[dict[str, Any]] = []

    @property
    def columns_dict(self) -> dict[str, Any]:
        return {}

    @property
    def rows(self) -> list[dict[str, Any]]:
        return [dict(row) for row in self.rows_list]

    def get(self, pk_value: Any) -> dict[str, Any] | None:
        for row in self.rows_list:
            if row.get("id") == pk_value:
                return dict(row)
        return None

    def insert(self, payload: dict[str, Any]) -> dict[str, Any]:
        row = dict(payload)
        row.setdefault("id", len(self.rows_list) + 1)
        self.rows_list.append(row)
        return dict(row)

    def insert_many(self, payloads: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [self.insert(payload) for payload in payloads]

    def update(self, *, updates: dict[str, Any], pk_values: Any) -> None:
        for row in self.rows_list:
            if row.get("id") == pk_values:
                row.update(updates)

    def delete(self, pk_value: Any) -> None:
        self.rows_list = [row for row in self.rows_list if row.get("id") != pk_value]

    def rows_where(
        self, where_sql: str = "", params: list[Any] | None = None, limit: int | None = None
    ) -> list[dict[str, Any]]:
        rows = self.rows_list
        if where_sql.strip().startswith("ruleset_id") and params:
            rows = [row for row in rows if row.get("ruleset_id") == params[0]]
        rows = [dict(row) for row in rows]
        return rows[:limit] if limit is not None else rows


#: The band ranges as the stored payloads write them -- GC-001 and CC-001 with
#: an ASCII hyphen, MC-001 with an en dash. Transcribed, not invented: they are
#: the values already in `_FALLBACK_RULESETS` and in the DB payloads.
SEEDED_BANDS = {
    "GC-001": {
        "Low": {"range": "< 0.35", "bcf_action": "Asset register only"},
        "Medium": {"range": "0.35 - 0.65", "bcf_action": "BCF Normal priority"},
        "High": {"range": "0.65 - 0.85", "bcf_action": "BCF Major priority"},
        "Critical": {"range": "> 0.85", "bcf_action": "BCF Critical priority"},
    },
    "CC-001": {
        "Low": {"range": "< 0.30", "bcf_action": "Asset register only"},
        "Medium": {"range": "0.30 - 0.55", "bcf_action": "BCF Normal priority"},
        "High": {"range": "0.55 - 0.80", "bcf_action": "BCF Major priority"},
        "Critical": {"range": "> 0.80", "bcf_action": "BCF Critical priority"},
    },
    "MC-001": {
        "Low": {"range": "< 0.25", "bcf_action": "Asset register only"},
        "Medium": {"range": "0.25 – 0.50", "bcf_action": "BCF Normal priority"},
        "High": {"range": "0.50 – 0.75", "bcf_action": "BCF Major priority"},
        "Critical": {"range": "> 0.75", "bcf_action": "BCF Critical priority"},
    },
}

#: The numeric band packs MM-001 and XM-001 seed, already numbers on disk.
NUMERIC_BANDS = {
    "MM-001": {"medium": 0.35, "high": 0.65, "critical": 0.85},
    "XM-001": {"medium": 0.35, "high": 0.65, "critical": 0.85},
}

#: Three boundaries (Medium, High, Critical) for each of the five engines that
#: band a composite score. Low is never seeded: it is everything below Medium
#: and has no lower bound of its own.
#:
#: The audit's F1 text says "18 expected" while enumerating GC 6 + CC 6 + MC 6 +
#: MM 3 + XM 3, which is the 24 rows it measured, not the expectation. The
#: expectation is 5 x 3.
EXPECTED_BAND_ROWS = 15


def _seed_all_bands(svc: RuleService) -> None:
    """Seed every engine's band rows once, the way the startup seeder does."""
    for prefix, bands in SEEDED_BANDS.items():
        seeder._seed_risk_bands(
            svc,
            ruleset_id=f"BIMGUARD-{prefix}",
            prefix=prefix,
            bands=bands,
        )
    for prefix, thresholds in NUMERIC_BANDS.items():
        seeder._seed_band_thresholds(
            svc,
            ruleset_id=f"BIMGUARD-{prefix}",
            prefix=prefix,
            mechanism=prefix,
            target_ifc_class="IfcPipeSegment",
            thresholds=thresholds,
            existing=svc.references_for_ruleset(f"BIMGUARD-{prefix}"),
        )


def _band_rows(table: FakeRulesTable) -> list[dict[str, Any]]:
    return [row for row in table.rows if ".BAND." in str(row.get("reference") or "")]


@pytest.fixture
def rules_service() -> RuleService:
    """A RuleService over an in-memory table, with the query cache cleared."""
    invalidate_cache("bimguard:rules")
    service = RuleService(rules_repo=FakeRulesTable(), folders_repo=FakeRulesTable())
    yield service
    invalidate_cache("bimguard:rules")


def test_seeding_twice_leaves_one_row_per_band(rules_service: RuleService):
    """A re-seed inserts nothing. 15 band rows after one run and after two."""
    table = rules_service._rules

    _seed_all_bands(rules_service)
    assert len(_band_rows(table)) == EXPECTED_BAND_ROWS

    _seed_all_bands(rules_service)
    assert len(_band_rows(table)) == EXPECTED_BAND_ROWS

    references = [row["reference"] for row in _band_rows(table)]
    assert len(set(references)) == EXPECTED_BAND_ROWS
    assert sorted(set(references)) == sorted(
        f"{prefix}.BAND.{band}"
        for prefix in ("GC-001", "CC-001", "MC-001", "MM-001", "XM-001")
        for band in ("MEDIUM", "HIGH", "CRITICAL")
    )


def test_seeded_thresholds_are_bare_numbers(rules_service: RuleService):
    """check_value is stored as a number, never as a quoted string.

    ``_build_rule_row`` JSON-encodes check_value, so seeding the string
    ``"0.85"`` wrote the seven characters ``'"0.85"'`` into the column and every
    reader of the row then failed to coerce it.
    """
    _seed_all_bands(rules_service)

    stored = {row["reference"]: row["check_value"] for row in _band_rows(rules_service._rules)}
    assert stored["MC-001.BAND.MEDIUM"] == "0.25"
    assert stored["MC-001.BAND.HIGH"] == "0.5"
    assert stored["MC-001.BAND.CRITICAL"] == "0.75"
    assert stored["GC-001.BAND.MEDIUM"] == "0.35"
    for reference, value in stored.items():
        assert '"' not in value, f"{reference} is stored as a quoted string: {value}"
        assert isinstance(json.loads(value), float)


def test_the_guard_sees_rows_this_process_did_not_write(rules_service: RuleService):
    """The idempotency guard reads the table, not a cached snapshot.

    Reproduces 2026-09-06. ``list_by_ruleset`` is wrapped in a 24-hour TTL cache
    that only writes made through this process invalidate, so a second uvicorn
    worker -- and ``run_production_server`` starts several, each running the
    startup seeder -- asked "does this row exist?" and was answered from a
    snapshot taken before the first worker wrote it. Nine duplicate band rows
    were the result, after the guard was already in place.
    """
    table = rules_service._rules

    # Warm the cache while the ruleset is empty, as a worker that booted first
    # would have.
    assert rules_service.list_by_ruleset("BIMGUARD-MC-001") == []

    # Another process writes the rows. Straight into the table, because that is
    # what "another worker" means here: this process's cache never hears of it.
    for prefix in list(SEEDED_BANDS) + list(NUMERIC_BANDS):
        for band in ("MEDIUM", "HIGH", "CRITICAL"):
            table.insert(
                {
                    "reference": f"{prefix}.BAND.{band}",
                    "rule_type": "risk_band",
                    "ruleset_id": f"BIMGUARD-{prefix}",
                    "check_value": "0.5",
                    "keyword": band.capitalize(),
                }
            )
    assert len(_band_rows(table)) == EXPECTED_BAND_ROWS
    assert rules_service.list_by_ruleset("BIMGUARD-MC-001") == [], (
        "the cached snapshot should still be stale -- otherwise this test is "
        "not exercising the hazard it was written for"
    )

    _seed_all_bands(rules_service)
    assert len(_band_rows(table)) == EXPECTED_BAND_ROWS
