"""MC-001 must not emit a citation claiming a named standard supplies its thresholds.

The seeded MC-001 ruleset declares ASTM G-187 a soil-resistivity practice and
then cites it for MIC; "NACCE TPC 11" misspells NACE and names an unverified
document (docs/planning/corrosion_provenance_2026-09-13.md §5). Findings, BCF
issues and seeded ``source_text`` defaults once repeated both. They now name the
body of practice for the mechanism only and say the thresholds are authored.
"""

import ast
import json
import re
from pathlib import Path

import pytest

from app.engines import bimguard_mic_engine as mic
from app.modules.phase_6 import phase_6c_corrosion_ui as ui
from app.services import ruleset_seeder

ROOT = Path(__file__).resolve().parents[1]

#: Spellings of the two suspect citations.
SUSPECT = ("G-187", "G187", "NACCE", "TPC 11", "TPC-11")

#: The modules that emit MC-001 citation text.
EMITTERS = (
    "app/engines/bimguard_mic_engine.py",
    "app/modules/phase_6/phase_6c_corrosion_ui.py",
    "app/services/ruleset_seeder.py",
)


def _result() -> mic.MICResult:
    return mic.assess_mic_risk(
        mic.MICElement(
            global_id="MIC-CITE-001",
            element_type="IfcPipeSegment",
            system_type="DOMESTICCOLDWATER",
            material="carbon_steel",
            nominal_diameter_m=0.05,
            flow_velocity_ms=0.0,
            operating_temp_c=28.0,
            dead_leg_length_m=2.5,
        )
    )


def _docstring_nodes(tree: ast.AST) -> set[int]:
    ids = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = getattr(node, "body", [])
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
                ids.add(id(body[0].value))
    return ids


def test_finding_citation_does_not_attribute_the_threshold_to_a_standard():
    result = _result()
    first = ui._mic_citations(result)[0]
    text = f"{first['standard']} {first['clause']}"
    assert not any(s in text for s in SUSPECT), text
    assert "authored calibration" in first["clause"]
    assert first["reason"] == f"flow class {result.flow_velocity_class}"


def test_bcf_issue_does_not_attribute_the_thresholds_to_a_standard():
    description = mic._mic_bcf_issue(_result()).description
    assert not any(s in description for s in SUSPECT), description
    assert "authored calibration" in description


def test_seeded_material_default_does_not_cite_nacce(monkeypatch):
    payload = {
        "scoring_model": {"formula": "f", "weights": {}},
        "risk_bands": {},
        "flow_velocity_classes": {},
        "temperature_classes": {},
        "dead_leg_classes": {},
        "material_susceptibility": {"pvc": {"score": 0.05, "label": "PVC"}},
        "system_type_modifiers": {},
        "under_insulation_risk": {},
        "mitigation_catalogue": {},
    }
    rows: list[dict] = []

    class Svc:
        def has_ruleset(self, _rid):
            return False

        def references_for_ruleset(self, _rid):
            return set()

        def create_rule(self, **kw):
            rows.append(kw)

    monkeypatch.setattr(ruleset_seeder, "_load", lambda _name: payload)
    ruleset_seeder._seed_mc001(Svc())
    (row,) = [r for r in rows if r.get("rule_type") == "material_susceptibility"]
    assert not any(s in row["source_text"] for s in SUSPECT), row["source_text"]
    assert "authored calibration" in row["source_text"]


def _match_key_nodes(tree: ast.AST) -> set[int]:
    """Keys of the seeder's superseded-reference map: matched, never emitted.

    test_seeded_material_citations_match_the_migration holds that none of them
    reaches a seeded row.
    """
    ids = set()
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Assign)
            and any(
                isinstance(t, ast.Name) and t.id == "_MC001_SUPERSEDED_MATERIAL_REFERENCES"
                for t in node.targets
            )
            and isinstance(node.value, ast.Dict)
        ):
            ids.update(id(k) for k in node.value.keys if isinstance(k, ast.Constant))
    return ids


@pytest.mark.parametrize("relpath", EMITTERS)
def test_no_executable_string_carries_a_suspect_citation(relpath):
    """Docstrings may record the defect; no emitted string may repeat it."""
    tree = ast.parse((ROOT / relpath).read_text(encoding="utf-8"))
    exempt = _docstring_nodes(tree) | _match_key_nodes(tree)
    offending = [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and id(node) not in exempt
        and any(s in node.value for s in SUSPECT)
    ]
    assert not offending, offending


#: docs/planning/corrosion_provenance_2026-09-13.md §12.2; the value migration
#: 20260914195107 writes.
MIGRATION = ROOT / "supabase" / "migrations" / "20260914195107_correct_mc001_material_citations.sql"
SEED_MIGRATION = ROOT / "supabase" / "migrations" / "20260806180500_seed_static_data_assets.sql"
CORRECTED_SOURCE_TEXT = (
    "Source: AMPP (formerly NACE) industry practice, MIC mechanism only; "
    "score is MC-001 authored calibration"
)
CORRECTED_MATERIALS = (
    "CARBON_STEEL",
    "CAST_IRON",
    "GALV_STEEL",
    "SS304",
    "SS316",
    "DUPLEX2205",
    "TITANIUM",
)


def test_seeded_material_citations_match_the_migration(monkeypatch):
    """A fresh seed of the shipped MC-001 payload writes what the migration writes."""
    sql = SEED_MIGRATION.read_text(encoding="utf-8")
    match = re.search(
        r"values \('ruleset:BIMGUARD-MC-001', '[^']*', 'json', '((?:[^']|'')*)'", sql
    )
    assert match, "MC-001 static asset insert not found in 20260806180500"
    payload = json.loads(match.group(1).replace("''", "'"))
    rows: list[dict] = []

    class Svc:
        def has_ruleset(self, _rid):
            return False

        def references_for_ruleset(self, _rid):
            return set()

        def create_rule(self, **kw):
            rows.append(kw)

    monkeypatch.setattr(ruleset_seeder, "_load", lambda _name: payload)
    ruleset_seeder._seed_mc001(Svc())

    assert len(rows) == 57
    assert f"SET source_text = '{CORRECTED_SOURCE_TEXT}'" in MIGRATION.read_text(encoding="utf-8")
    by_ref = {r["reference"]: r for r in rows}
    for key in CORRECTED_MATERIALS:
        assert by_ref[f"MC-001.MAT.{key}"]["source_text"] == CORRECTED_SOURCE_TEXT, key
    carrying = [
        (r["reference"], r["source_text"])
        for r in rows
        if "ASTM G-187" in str(r.get("source_text") or "")
        or "NACCE" in str(r.get("source_text") or "")
    ]
    assert not carrying, carrying
