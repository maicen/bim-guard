"""Tests for Tier 2 (buildingSMART IDS 1.0) exchange verification.

Uses stub `rules_service`/`projects_service` collaborators (constructor
dependency injection, per `IDSValidationService.__init__`) rather than the
live database, so these stay fast and hermetic.
"""

from __future__ import annotations

from pathlib import Path

from app.services.ids_validation_service import IDSValidationService


class _StubRuleService:
    def __init__(self, rows: list[dict]) -> None:
        self._rows = rows

    def list_by_ruleset(self, ruleset_id: str) -> list[dict]:
        return self._rows


class _StubProjectsService:
    def __init__(self, ifc_path: Path | None) -> None:
        self._ifc_path = ifc_path

    def resolve_ifc_file(self, project_id: int) -> Path | None:
        return self._ifc_path


def test_ruleset_with_no_exportable_rows_passes_trivially():
    service = IDSValidationService(
        projects_service=_StubProjectsService(None),
        rules_service=_StubRuleService([]),
    )
    result = service.validate_project(project_id=1, ruleset_id="EMPTY-RULESET")
    assert result.passed is True
    assert result.specifications == []


def test_missing_ifc_model_fails_with_exportable_rows():
    rows = [
        {
            "rule_category": "property_check",
            "target_ifc_class": "IfcWall",
            "property_name": "FireRating",
            "property_set": "Pset_WallCommon",
            "operator": "exists",
            "reference": "TEST-01",
        }
    ]
    service = IDSValidationService(
        projects_service=_StubProjectsService(None),
        rules_service=_StubRuleService(rows),
    )
    result = service.validate_project(project_id=1, ruleset_id="TEST-RULESET")
    assert result.passed is False
    assert result.error is not None


def test_validate_project_against_real_ifc_fixture(tmp_path):
    """End-to-end: build an IDS doc from a rule row and run it against a tiny real IFC file."""
    ifcopenshell = __import__("ifcopenshell")
    model = ifcopenshell.file(schema="IFC4")
    length_unit = model.create_entity("IfcSIUnit", UnitType="LENGTHUNIT", Name="METRE")
    units = model.create_entity("IfcUnitAssignment", Units=[length_unit])
    model.create_entity(
        "IfcProject",
        GlobalId=ifcopenshell.guid.new(),
        Name="Fixture Project",
        UnitsInContext=units,
    )
    wall = model.create_entity("IfcWall", GlobalId=ifcopenshell.guid.new())
    pset = model.create_entity("IfcPropertySet", GlobalId=ifcopenshell.guid.new(), Name="Pset_WallCommon")
    prop = model.create_entity(
        "IfcPropertySingleValue",
        Name="FireRating",
        NominalValue=model.create_entity("IfcLabel", "REI60"),
    )
    pset.HasProperties = [prop]
    model.create_entity("IfcRelDefinesByProperties", RelatedObjects=[wall], RelatingPropertyDefinition=pset)

    ifc_path = tmp_path / "fixture.ifc"
    model.write(str(ifc_path))

    rows = [
        {
            "rule_category": "property_check",
            "target_ifc_class": "IfcWall",
            "property_name": "FireRating",
            "property_set": "Pset_WallCommon",
            "operator": "exists",
            "reference": "TEST-01",
        }
    ]
    service = IDSValidationService(
        projects_service=_StubProjectsService(ifc_path),
        rules_service=_StubRuleService(rows),
    )
    result = service.validate_project(project_id=1, ruleset_id="TEST-RULESET")
    assert result.passed is True
    assert result.error is None
    assert len(result.specifications) == 1
    assert result.specifications[0].applicable_count == 1
    assert result.specifications[0].failed_count == 0
