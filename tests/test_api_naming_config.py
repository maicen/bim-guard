"""Tests for /api/naming-config and the ISO 19650 naming service.

The catalog and preview endpoints are exercised over HTTP because they touch no
database. The per-project read/write paths are exercised against the service
with a fake adapter, so a test run neither needs a live project row nor leaves
one behind.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from starlette.testclient import TestClient

from app.main import app
from app.services.naming_config_service import (
    DEFAULT_CONVENTION,
    DEFAULTS,
    ISO_MASTER_CODES,
    NAMING_TOKENS,
    NamingConfigService,
    render_date,
)

client = TestClient(app)
NONEXISTENT_ID = 999_999_999
FIXED_NOW = datetime(2026, 8, 31, tzinfo=timezone.utc)


class _FakeAdapter:
    """In-memory stand-in for the project_naming_config table adapter."""

    def __init__(self, *, broken: bool = False) -> None:
        self.rows: list[dict[str, Any]] = []
        self._broken = broken
        self._next_id = 1

    def rows_where(self, _clause: str, params: list[Any]):
        if self._broken:
            raise RuntimeError('relation "project_naming_config" does not exist')
        return [row for row in self.rows if row["project_id"] == params[0]]

    def insert(self, payload: dict[str, Any]) -> dict[str, Any]:
        row = {"id": self._next_id, **payload}
        self._next_id += 1
        self.rows.append(row)
        return row

    def update(self, *, updates: dict[str, Any], pk_values: Any) -> None:
        for row in self.rows:
            if row["id"] == pk_values:
                row.update(updates)

    def delete(self, pk_value: Any) -> None:
        self.rows = [row for row in self.rows if row["id"] != pk_value]


def _service(**kwargs: Any) -> NamingConfigService:
    """Build a service over a fake adapter."""
    return NamingConfigService(naming_repo=_FakeAdapter(**kwargs))


# ── catalog ──────────────────────────────────────────────────────────────────


def test_catalog_serves_the_documented_vocabulary():
    """Verify the catalog carries the five conventions and the full code library."""
    response = client.get("/api/naming-config/catalog")
    assert response.status_code == 200
    data = response.json()

    assert [c["id"] for c in data["conventions"]] == [
        "iso19650",
        "iso19650_date",
        "simple",
        "descriptive",
        "uniclass",
    ]
    assert len(data["tokens"]) == len(NAMING_TOKENS) == 19
    assert len(data["codes"]["levels"]) == len(ISO_MASTER_CODES["levels"]) == 18
    assert len(data["codes"]["disciplines"]) == 12
    assert len(data["codes"]["volumes"]) == 9
    assert data["default_convention"] == DEFAULT_CONVENTION


def test_catalog_marks_the_two_non_iso_conventions():
    """Verify simple and descriptive are flagged rather than quietly offered."""
    data = client.get("/api/naming-config/catalog").json()
    non_compliant = {c["id"] for c in data["conventions"] if not c["iso_compliant"]}
    assert non_compliant == {"simple", "descriptive"}


def test_cde_status_table_matches_iso_19650_2_table_1():
    """Verify all seven statuses are served and only five are selectable."""
    data = client.get("/api/naming-config/catalog").json()
    assert [s["code"] for s in data["cde_statuses"]] == ["S0", "S1", "S2", "S3", "A", "B", "S7"]
    selectable = [s["code"] for s in data["cde_statuses"] if s["selectable"]]
    assert selectable == ["S0", "S1", "S2", "S3", "A"]


def test_presets_is_an_alias_of_catalog():
    """Verify /presets and /catalog serve the same document."""
    assert client.get("/api/naming-config/presets").json() == (
        client.get("/api/naming-config/catalog").json()
    )


# ── preview ──────────────────────────────────────────────────────────────────


def test_preview_renders_every_field_of_the_default_convention():
    """Verify the default convention resolves all nine of its tokens."""
    response = client.post(
        "/api/naming-config/preview",
        json={"config": {"project_code": "A7000", "originator_code": "BIM01"}},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["convention_id"] == "iso19650_date"
    assert data["unresolved_tokens"] == []
    assert data["name"].startswith("A7000_BIM01_")


def test_preview_uniclass_resolves_the_classification_tokens():
    """Verify Uniclass names carry the classification codes rather than blanks.

    The source platform hardcodes classA and classB to empty strings, so its
    Uniclass names ship with two empty segments. Storing them fixes that, and
    this is the test that says so.
    """
    response = client.post(
        "/api/naming-config/preview",
        json={
            "config": {
                "project_code": "A7000",
                "originator_code": "BIM01",
                "active_convention": "uniclass",
                "class_a": "Ss_25",
                "class_b": "Pr_20",
            }
        },
    )
    data = response.json()
    assert "Ss_25" in data["name"]
    assert "Pr_20" in data["name"]
    assert "__" not in data["name"]


def test_preview_applies_the_projects_separator_to_the_format_it_reports():
    """Verify the reported format is the one that produced the name."""
    response = client.post(
        "/api/naming-config/preview",
        json={
            "config": {
                "project_code": "A7000",
                "originator_code": "BIM01",
                "separator": "-",
            }
        },
    )
    data = response.json()
    assert data["name"] == data["name"].replace("_", "-")
    assert "_" not in data["applied_format"]
    assert data["applied_format"].startswith("{project}-{originator}-")


def test_preview_falls_back_when_the_convention_does_not_resolve():
    """Verify a configuration naming a deleted convention still renders."""
    response = client.post(
        "/api/naming-config/preview",
        json={"config": {"active_convention": "since-deleted"}},
    )
    assert response.status_code == 200
    assert response.json()["convention_id"] == DEFAULT_CONVENTION


def test_preview_reports_tokens_nothing_resolved():
    """Verify an unresolvable token is left literal and reported, not blanked."""
    response = client.post(
        "/api/naming-config/preview",
        json={
            "config": {
                "active_convention": "custom",
                "custom_conventions": [
                    {
                        "id": "custom",
                        "name": "Custom",
                        "format": "{project}_{nosuchtoken}",
                        "separator": "_",
                        "description": "",
                        "preset": False,
                        "iso_compliant": True,
                    }
                ],
                "project_code": "A7000",
            }
        },
    )
    data = response.json()
    assert data["convention_id"] == "custom"
    assert data["unresolved_tokens"] == ["nosuchtoken"]
    assert data["name"] == "A7000_{nosuchtoken}"


# ── project-scoped endpoints ─────────────────────────────────────────────────


def test_get_config_for_unknown_project_is_404():
    """Verify addressing a project that does not exist reports 404."""
    response = client.get(f"/api/naming-config/projects/{NONEXISTENT_ID}")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_save_config_for_unknown_project_is_404():
    """Verify writing against a project that does not exist reports 404."""
    response = client.put(
        f"/api/naming-config/projects/{NONEXISTENT_ID}", json={"project_code": "A7000"}
    )
    assert response.status_code == 404


# ── service ──────────────────────────────────────────────────────────────────


def test_unconfigured_project_reports_defaults_not_an_error():
    """Verify a project with no saved row reads as the defaults, unconfigured."""
    config = _service().get_for_project(1)
    assert config["is_configured"] is False
    assert config["active_convention"] == DEFAULT_CONVENTION
    assert config["level_codes"] == []


def test_a_missing_table_degrades_to_defaults():
    """Verify a read before the migration has run does not take the caller down."""
    config = _service(broken=True).get_for_project(1)
    assert config["is_configured"] is False
    assert config["project_code"] == ""


def test_save_then_read_round_trips():
    """Verify a saved configuration reads back as saved and marked configured."""
    service = _service()
    service.save_for_project(7, {"project_code": "A7000", "originator_code": "BIM01"})
    config = service.get_for_project(7)
    assert config["is_configured"] is True
    assert config["project_code"] == "A7000"
    assert config["originator_code"] == "BIM01"


def test_a_partial_save_does_not_blank_the_other_fields():
    """Verify saving one tab of the form leaves the rest of the row alone."""
    service = _service()
    service.save_for_project(
        7,
        {
            "project_code": "A7000",
            "level_codes": [{"code": "G00", "label": "Ground"}],
        },
    )
    service.save_for_project(7, {"suitability": "S2"})

    config = service.get_for_project(7)
    assert config["suitability"] == "S2"
    assert config["project_code"] == "A7000"
    assert config["level_codes"] == [{"code": "G00", "label": "Ground"}]


def test_saving_twice_edits_one_row():
    """Verify the second save updates rather than accumulating a second row."""
    service = _service()
    service.save_for_project(7, {"project_code": "A7000"})
    service.save_for_project(7, {"project_code": "B8000"})
    assert len(service._repo.rows) == 1  # noqa: SLF001 - asserting the upsert, not the API
    assert service.get_for_project(7)["project_code"] == "B8000"


def test_delete_returns_the_project_to_defaults_and_is_idempotent():
    """Verify a reset clears the row, and resetting an unconfigured project is not an error."""
    service = _service()
    service.save_for_project(7, {"project_code": "A7000"})

    assert service.delete_for_project(7) is True
    assert service.get_for_project(7)["is_configured"] is False
    assert service.delete_for_project(7) is False


def test_json_columns_survive_being_stored_as_text():
    """Verify a JSON column read back as a string still reads as a list.

    Supabase returns JSONB already parsed and SQLite returns the text it stored;
    both have to reach the caller as a list.
    """
    service = _service()
    service.save_for_project(7, {"project_code": "A7000"})
    service._repo.rows[0]["level_codes"] = '[{"code": "RF", "label": "Roof"}]'  # noqa: SLF001

    assert service.get_for_project(7)["level_codes"] == [{"code": "RF", "label": "Roof"}]


def test_render_date_covers_the_five_offered_formats():
    """Verify each offered date format renders, and an unknown one falls back."""
    assert render_date("YYMMDD", now=FIXED_NOW) == "260831"
    assert render_date("DDMMYY", now=FIXED_NOW) == "310826"
    assert render_date("YYYYMMDD", now=FIXED_NOW) == "20260831"
    assert render_date("DD-MM-YY", now=FIXED_NOW) == "31-08-26"
    assert render_date("ISO", now=FIXED_NOW) == "2026-08-31"
    assert render_date("not-a-format", now=FIXED_NOW) == "260831"


def test_render_name_is_stable_for_a_fixed_moment():
    """Verify the whole default name, so a change to any token is visible here."""
    config = {**DEFAULTS, "project_code": "A7000", "originator_code": "BIM01"}
    rendered = _service().render_name(config, now=FIXED_NOW)
    assert rendered == "A7000_BIM01_ZZ_G00_CO_A_0001_S1_01_260831"
