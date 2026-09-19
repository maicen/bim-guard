"""Class-fallback provenance (``IFCReader._class_fallback_warning``).

When a model has no elements of a rule's target class, the reader substitutes
other classes (a generic IfcBuildingElementProxy named "Door", an IfcPlate
standing in for an IfcSlab, ...). Those elements used to be merged into the
normal element list and come out indistinguishable from properly-typed ones.
Each case builds a real IFC4 model so the whole reader -> comparator path is
exercised, and asserts on the per-element ``data_quality_warnings`` the UI and
the BCF export read.
"""

from __future__ import annotations

import pytest

from app.modules.comparator import ComplianceComparator
from app.modules.ifc_reader import IFCReader
from app.modules.reporter import ComplianceReporter

ifcopenshell = pytest.importorskip("ifcopenshell")


def _new_model():
    from ifcopenshell.api import run

    model = ifcopenshell.file(schema="IFC4")
    run("root.create_entity", model, ifc_class="IfcProject", name="P")
    run("unit.assign_unit", model, length={"is_metric": True, "raw": "MILLIMETERS"})
    site = run("root.create_entity", model, ifc_class="IfcSite", name="Site")
    building = run("root.create_entity", model, ifc_class="IfcBuilding", name="B")
    storey = run("root.create_entity", model, ifc_class="IfcBuildingStorey", name="L1")
    run("aggregate.assign_object", model, products=[site], relating_object=model.by_type("IfcProject")[0])
    run("aggregate.assign_object", model, products=[building], relating_object=site)
    run("aggregate.assign_object", model, products=[storey], relating_object=building)
    return model, storey


def _add(model, storey, ifc_class: str, name: str):
    from ifcopenshell.api import run

    element = run("root.create_entity", model, ifc_class=ifc_class, name=name)
    run("spatial.assign_container", model, products=[element], relating_structure=storey)
    return element


def _elements_by_name(tmp_path, model, target: str) -> dict[str, dict]:
    """Run one existence rule against *target* and key its per-element rows by name."""
    path = tmp_path / "model.ifc"
    model.write(str(path))
    rule = {
        "rule_id": 1,
        "reference": "TEST-FALLBACK-1",
        "target_ifc_class": target,
        "property_name": "Name",
        "operator": "exists",
    }
    extraction = IFCReader(path).extract_for_compliance([rule])
    results = ComplianceComparator().validate_metadata(extraction)
    result = {r["rule_ref"]: r for r in results}["TEST-FALLBACK-1"]
    return {el["element_name"]: el for el in result["all_elements"]}


class TestProxyReclassification:
    def test_hinted_proxy_is_flagged_with_the_keyword_that_matched(self, tmp_path):
        model, storey = _new_model()
        _add(model, storey, "IfcBuildingElementProxy", "Door-Single-36in")

        rows = _elements_by_name(tmp_path, model, "IfcDoor")

        warnings = rows["Door-Single-36in"]["data_quality_warnings"]
        assert len(warnings) == 1
        assert "IfcBuildingElementProxy" in warnings[0]
        assert "not IfcDoor" in warnings[0]
        assert '"door"' in warnings[0]

    def test_proxy_that_does_not_look_like_the_target_is_not_pulled_in(self, tmp_path):
        model, storey = _new_model()
        _add(model, storey, "IfcBuildingElementProxy", "Door-Single-36in")
        _add(model, storey, "IfcBuildingElementProxy", "Circulation Pump")

        rows = _elements_by_name(tmp_path, model, "IfcDoor")

        assert set(rows) == {"Door-Single-36in"}

    def test_properly_typed_element_carries_no_warning(self, tmp_path):
        """A real IfcDoor means no fallback ran, so the proxy is never involved."""
        model, storey = _new_model()
        _add(model, storey, "IfcDoor", "D1")
        _add(model, storey, "IfcBuildingElementProxy", "Door-Single-36in")

        rows = _elements_by_name(tmp_path, model, "IfcDoor")

        assert set(rows) == {"D1"}
        assert rows["D1"]["data_quality_warnings"] is None

    def test_proxy_class_without_hints_says_no_name_check_was_applied(self, tmp_path):
        """IfcCovering falls back to *every* proxy — the weakest evidence, said so."""
        model, storey = _new_model()
        _add(model, storey, "IfcBuildingElementProxy", "Widget")

        rows = _elements_by_name(tmp_path, model, "IfcCovering")

        warnings = rows["Widget"]["data_quality_warnings"]
        assert len(warnings) == 1
        assert "every proxy" in warnings[0]
        assert "no name/type check" in warnings[0]


class TestOtherClassFallbacks:
    def test_non_proxy_substitute_names_its_real_class(self, tmp_path):
        model, storey = _new_model()
        _add(model, storey, "IfcPlate", "Deck plate")

        rows = _elements_by_name(tmp_path, model, "IfcSlab")

        warnings = rows["Deck plate"]["data_quality_warnings"]
        assert len(warnings) == 1
        assert "Modelled as IfcPlate, not IfcSlab" in warnings[0]

    def test_warning_names_no_ruleset_or_clause(self, tmp_path):
        """The caveat describes the element, not whichever rule reached it."""
        model, storey = _new_model()
        _add(model, storey, "IfcBuildingElementProxy", "Window-Fixed")

        rows = _elements_by_name(tmp_path, model, "IfcWindow")

        text = " ".join(rows["Window-Fixed"]["data_quality_warnings"])
        assert "TEST-FALLBACK-1" not in text


class TestReporterSurfacesTheWarning:
    FAILURE = {
        "element_name": "Door-Single-36in",
        "guid": "g1",
        "storey": "L1",
        "space": "—",
        "reason": "missing",
        "data_quality_warnings": ["Modelled as IfcBuildingElementProxy, not IfcDoor: included."],
    }
    RULE = {
        "rule_ref": "R1",
        "rule_desc": "Doors must exist",
        "property_name": "Name",
        "severity": "mandatory",
        "target": "IfcDoor",
        "status": "FAIL",
        "failures": [FAILURE],
    }

    def test_bcf_topic_description_carries_the_warning(self):
        topic = ComplianceReporter().create_bcf_topic(self.FAILURE, self.RULE)

        assert "Data quality: Modelled as IfcBuildingElementProxy, not IfcDoor" in topic["description"]

    def test_bcf_issue_description_carries_the_warning(self):
        (issue,) = ComplianceReporter().bcf_issues_for_results([self.RULE])

        assert "Data quality: Modelled as IfcBuildingElementProxy, not IfcDoor" in issue.description

    def test_no_warning_leaves_the_description_unchanged(self):
        clean = {**self.FAILURE, "data_quality_warnings": None}

        topic = ComplianceReporter().create_bcf_topic(clean, self.RULE)

        assert "Data quality" not in topic["description"]
