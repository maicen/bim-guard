"""SB-001 rule rows must say what the corrected configuration says, and stay that way.

Before 2026-09-13 the seeder wrote SB-001 descriptions citing "EN 1998-1 / DIN 4149"
and an angle range of 35-70 degrees, both carried over from the unverified Hermes
research summary. The insert pass skips references that already exist, so the
correction also has to reach rows already stored -- without overwriting a rule
someone has edited by hand. The Supabase migration that corrects deployed rows
must write the same strings the seeder does.

Run: uv run pytest tests/test_sb001_seeded_provenance.py -v
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from app.services import ruleset_seeder as seeder
from app.services.cache import invalidate_cache
from app.services.rules_service import RuleService
from tests.test_ruleset_band_thresholds import FakeRulesTable

REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads(
    (REPO_ROOT / "data" / "rulesets" / "sb001_seismic_clearance.json").read_text(encoding="utf-8")
)
MIGRATION = (
    REPO_ROOT / "supabase" / "migrations" / "20260913131052_correct_sb001_seeded_rule_provenance.sql"
)

#: The rows as the pre-correction seeder stored them.
LEGACY_ROWS = {
    "SB-001.03": {
        "description": "Maximum transverse seismic brace spacing — 1.0 m per EN 1998-1 / DIN 4149",
    },
    "SB-001.04": {
        "description": "Maximum longitudinal seismic brace spacing — 1.5 m per EN 1998-1 / DIN 4149",
    },
    "SB-001.05": {
        "description": "Seismic brace installation angle — permissible range 35° to 70° from horizontal",
        "value_min": "35.0",
        "value_max": "70.0",
    },
}

#: Which configuration provenance note each seeded rule's source_text restates.
PROVENANCE_KEY = {
    "SB-001.01": "thresholds.pipe_diameter_mm",
    "SB-001.02": "clearance_rules.base_from_structure_mm",
    "SB-001.03": "brace_types.*.spacing_transverse_m",
    "SB-001.04": "brace_types.*.spacing_longitudinal_m",
    "SB-001.05": "angle_constraints.min_degrees",
}


@pytest.fixture
def rules_service() -> RuleService:
    """Yield a RuleService over an in-memory table, with the query cache cleared."""
    invalidate_cache("bimguard:rules")
    service = RuleService(rules_repo=FakeRulesTable(), folders_repo=FakeRulesTable())
    yield service
    invalidate_cache("bimguard:rules")


def _sb001(service: RuleService) -> dict[str, dict[str, Any]]:
    return {row["reference"]: row for row in service.rows_for_ruleset("BIMGUARD-SB-001")}


def _number(stored: Any) -> float:
    return float(json.loads(stored))


def test_fresh_seed_attributes_nothing_to_en_1998_or_din_4149(rules_service: RuleService):
    """A new database gets five rows, none citing the two European standards."""
    assert seeder.seed_seismic_rules(rules_service) == 5
    rows = _sb001(rules_service)
    assert sorted(rows) == sorted(PROVENANCE_KEY)
    for row in rows.values():
        text = f"{row['description']} {row['source_text']}"
        assert "1998" not in text and "4149" not in text


def test_seeded_values_are_the_configuration_values(rules_service: RuleService):
    """Every seeded threshold is the number the SB-001 configuration applies."""
    seeder.seed_seismic_rules(rules_service)
    rows = _sb001(rules_service)
    assert _number(rows["SB-001.01"]["check_value"]) == CONFIG["thresholds"]["pipe_diameter_mm"]
    assert _number(rows["SB-001.02"]["check_value"]) == CONFIG["clearance_rules"]["base_from_structure_mm"]
    spacing = CONFIG["brace_types"]["angle_fire"]
    assert _number(rows["SB-001.03"]["check_value"]) == spacing["spacing_transverse_m"]
    assert _number(rows["SB-001.04"]["check_value"]) == spacing["spacing_longitudinal_m"]
    assert _number(rows["SB-001.05"]["value_min"]) == CONFIG["angle_constraints"]["min_degrees"]
    assert _number(rows["SB-001.05"]["value_max"]) == CONFIG["angle_constraints"]["max_degrees"]


@pytest.mark.parametrize("reference", sorted(PROVENANCE_KEY))
def test_source_text_restates_the_configuration_provenance(reference: str):
    """source_text is the configuration's own note, labelled as authored calibration."""
    note = CONFIG["provenance"][PROVENANCE_KEY[reference]]["note"]
    text = seeder._SB001_SOURCE_TEXT[reference]
    assert text.startswith("BIMGUARD SB-001 authored calibration. ")
    assert text.endswith(note)


def test_rows_seeded_before_the_correction_are_corrected_in_place(rules_service: RuleService):
    """Legacy rows are rewritten, not skipped, and no second copy is inserted."""
    seeder.seed_seismic_rules(rules_service)
    for reference, legacy in LEGACY_ROWS.items():
        row = _sb001(rules_service)[reference]
        rules_service._rules.update(updates={**legacy, "source_text": ""}, pk_values=row["id"])

    assert seeder.seed_seismic_rules(rules_service) == 0
    rows = _sb001(rules_service)
    assert len(rows) == 5
    for reference in LEGACY_ROWS:
        assert rows[reference]["description"] == seeder._SB001_SUPERSEDED[reference]["description"][1]
        assert rows[reference]["source_text"] == seeder._SB001_SOURCE_TEXT[reference]
    assert _number(rows["SB-001.05"]["value_min"]) == 40.0
    assert _number(rows["SB-001.05"]["value_max"]) == 65.0


def test_a_second_run_changes_nothing(rules_service: RuleService):
    """Correction is idempotent: a corrected row is not touched again."""
    seeder.seed_seismic_rules(rules_service)
    before = _sb001(rules_service)
    assert seeder._correct_superseded_seismic_rows(rules_service) == 0
    assert _sb001(rules_service) == before


def test_a_hand_edited_rule_is_left_as_edited(rules_service: RuleService):
    """Only fields still holding the exact superseded value are corrected."""
    seeder.seed_seismic_rules(rules_service)
    row = _sb001(rules_service)["SB-001.05"]
    edited = {"description": "Project-specific brace angle", "value_min": "30.0", "value_max": "70.0"}
    rules_service._rules.update(updates=edited, pk_values=row["id"])

    seeder.seed_seismic_rules(rules_service)
    after = _sb001(rules_service)["SB-001.05"]
    assert after["description"] == "Project-specific brace angle"
    assert after["value_min"] == "30.0"
    # 70.0 is the superseded upper bound, so it alone is corrected.
    assert _number(after["value_max"]) == 65.0


def test_other_rulesets_are_out_of_scope(rules_service: RuleService):
    """A row outside BIMGUARD-SB-001 is never rewritten, whatever it says."""
    legacy = LEGACY_ROWS["SB-001.03"]["description"]
    rules_service._rules.insert(
        {"reference": "SB-001.03", "ruleset_id": "PROJECT-COPY", "description": legacy, "source_text": ""}
    )
    seeder._correct_superseded_seismic_rows(rules_service)
    copy = rules_service.rows_for_ruleset("PROJECT-COPY")[0]
    assert copy["description"] == legacy
    assert copy["source_text"] == ""


def test_migration_writes_the_seeder_strings():
    """The SQL that corrects deployed rows uses the seeder's old and new text verbatim."""
    sql = MIGRATION.read_text(encoding="utf-8")
    for reference, fields in seeder._SB001_SUPERSEDED.items():
        old, new = fields["description"]
        assert f"description = '{old}'" in sql, reference
        assert f"SET description = '{new}'" in sql, reference
    for reference, text in seeder._SB001_SOURCE_TEXT.items():
        assert f"SET source_text = '{text.replace(chr(39), chr(39) * 2)}'" in sql, reference
    assert "requirements per EN 1998-1 / DIN 4149';" in sql
