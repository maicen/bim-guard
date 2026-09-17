"""GC-001 must not cite a table nobody read, a wrong title or a phantom edition.

The seeded GC-001 payload attributes its environment voltage thresholds to
"NASA-STD-6012 Table 1" -- a locator for numbers that are authored calibration --
titles that standard "Corrosion Control and Treatment for Aerospace Vehicles"
when it is "Corrosion Protection for Space Flight Hardware", and dates Euro Inox
Vol. 10 to 2025, which is the worldstainless.org upload path rather than an
edition (docs/planning/corrosion_provenance_2026-09-13.md §8).

Migration 20260917190000 corrects the stored rows and payload; the seeder carries
the same two strings so a fresh seed cannot reintroduce the old text. This holds
the two together, and pins the replacement chain to JSON that still decodes with
its values untouched.
"""

import json
import re
from pathlib import Path

from app.services import ruleset_seeder

ROOT = Path(__file__).resolve().parents[1]

MIGRATION = ROOT / "supabase" / "migrations" / "20260917190000_correct_gc001_citation_metadata.sql"
SEED_MIGRATION = ROOT / "supabase" / "migrations" / "20260806180500_seed_static_data_assets.sql"

#: Citation text that must not survive anywhere GC-001 emits or stores it.
SUPERSEDED = (
    "NASA-STD-6012 Table 1",
    "Corrosion Control and Treatment for Aerospace Vehicles",
    "Euro Inox (2025)",
)

#: The ``source_text`` the seeder and the migration must both write.
ENV_SOURCE_TEXT = (
    "Source: NASA-STD-6012, governing standard for the mechanism only "
    "(no table of it has been read); threshold is GC-001 authored calibration"
)
SERIES_SOURCE_TEXT = (
    "Source: WorldStainless / Euro Inox Vol. 10 (2009) and AUCSC Basic "
    "Corrosion Course (2024), ordering only; potential is GC-001 authored calibration"
)


def _seeded_payload() -> str:
    """Return the GC-001 ``content_json`` exactly as 20260806180500 seeded it."""
    line = next(
        ln
        for ln in SEED_MIGRATION.read_text(encoding="utf-8").splitlines()
        if ln.startswith("values ('ruleset:BIMGUARD-GC-001'")
    )
    match = re.match(r"values \('[^']*', '[^']*', '[^']*', '(\{.*\})', '\{$", line)
    assert match, "GC-001 seed payload not found in 20260806180500"
    return match.group(1)


def _pairs(block: str) -> list[tuple[str, str]]:
    """Return the (old, new) literal pairs of one nested ``replace()`` chain."""
    literals = [
        lit.replace("''", "'") for lit in re.findall(r"'((?:[^']|'')*)'", block)
    ]
    assert literals and len(literals) % 2 == 0, "expected paired replace() literals"
    return [(literals[i], literals[i + 1]) for i in range(0, len(literals), 2)]


def _replacements() -> list[tuple[str, str]]:
    """Return the migration's (old, new) pairs, read out of the SQL itself.

    Both stored columns are rewritten by identical chains; that they stay
    identical is asserted here rather than left to the eye.
    """
    sql = MIGRATION.read_text(encoding="utf-8")
    json_block, text_block = sql.split("SET content_json = replace(", 1)[1].split(
        "content_text = replace(", 1
    )
    json_pairs = _pairs(json_block)
    text_pairs = _pairs(text_block.split("WHERE asset_key", 1)[0])
    assert json_pairs == text_pairs, "content_json and content_text chains have diverged"
    return json_pairs


def test_seeder_writes_the_corrected_citations():
    """Both payload shapes seed the corrected text, old and renamed keys alike."""
    legacy_env = {"E1_CONTROLLED": {}, "source": "NASA-STD-6012 Table 1"}
    renamed_env = {
        "E1_CONTROLLED": {},
        "governing_reference": "NASA-STD-6012",
        "provenance": "authored",
    }
    for block in (legacy_env, renamed_env):
        assert (
            ruleset_seeder._gc001_source_text(
                block,
                corrected=ruleset_seeder._GC001_ENV_SOURCE_TEXT,
                default="NASA-STD-6012",
            )
            == ENV_SOURCE_TEXT
        )

    legacy_series = {
        "materials": {},
        "source": "WorldStainless / Euro Inox (2025) and AUCSC Basic Corrosion Course (2024)",
    }
    renamed_series = {"materials": {}, "governing_reference": "x", "provenance": "authored"}
    for block in (legacy_series, renamed_series):
        assert (
            ruleset_seeder._gc001_source_text(
                block,
                corrected=ruleset_seeder._GC001_SERIES_SOURCE_TEXT,
                default="WorldStainless / Euro Inox Vol. 10 (2009)",
            )
            == SERIES_SOURCE_TEXT
        )


def test_an_unrelated_citation_is_left_alone():
    """Only the two superseded strings are rewritten."""
    block = {"source": "IMOA Design Manual 4th Ed."}
    assert (
        ruleset_seeder._gc001_source_text(block, corrected="unused", default="fallback")
        == "Source: IMOA Design Manual 4th Ed."
    )


def test_migration_writes_the_same_text_as_the_seeder():
    sql = MIGRATION.read_text(encoding="utf-8")
    assert f"SET source_text = '{ENV_SOURCE_TEXT}'" in sql
    assert f"SET source_text = '{SERIES_SOURCE_TEXT}'" in sql


def test_seeder_and_migration_agree_on_the_constants():
    assert ruleset_seeder._GC001_ENV_SOURCE_TEXT == ENV_SOURCE_TEXT
    assert ruleset_seeder._GC001_SERIES_SOURCE_TEXT == SERIES_SOURCE_TEXT


def test_replacements_leave_decodable_json_with_the_values_untouched():
    """The payload still parses, and only citation text moves."""
    original = _seeded_payload()
    corrected = original
    for old, new in _replacements():
        assert old in corrected, f"migration replaces text the payload does not hold: {old[:60]}"
        corrected = corrected.replace(old, new)

    before, after = json.loads(original), json.loads(corrected)
    assert before["galvanic_series"]["materials"] == after["galvanic_series"]["materials"]
    assert before["scoring_model"] == after["scoring_model"]
    assert before["area_ratio_bands"] == after["area_ratio_bands"]
    assert {k: v for k, v in before["environment_classes"].items() if k.startswith("E")} == {
        k: v for k, v in after["environment_classes"].items() if k.startswith("E")
    }

    assert after["environment_classes"]["governing_reference"] == "NASA-STD-6012"
    assert after["environment_classes"]["provenance"] == "authored"
    assert after["galvanic_series"]["provenance"] == "authored"
    assert "Space Flight Hardware" in after["standards_referenced"][0]

    for bad in SUPERSEDED:
        assert bad not in corrected, bad
    # The electrode claim the values contradict is gone, and what replaced it
    # says what the numbers are.
    assert "reference_electrode" not in corrected
    assert "reference_electrolyte" not in corrected
    assert "ranking index" in after["galvanic_series"]["scale"]


def test_no_superseded_citation_is_emitted_by_the_engine_or_seeder():
    for relative in (
        "app/engines/bimguard_corrosion_engine.py",
        "app/services/ruleset_seeder.py",
        "app/constants.py",
    ):
        text = (ROOT / relative).read_text(encoding="utf-8")
        for bad in SUPERSEDED:
            # The seeder names the superseded payload strings it maps away from,
            # which is the one legitimate place they appear.
            if relative.endswith("ruleset_seeder.py") and bad in (
                "NASA-STD-6012 Table 1",
                "Euro Inox (2025)",
            ):
                continue
            assert bad not in text, f"{relative} still emits {bad!r}"
