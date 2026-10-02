"""Door and window clear dimensions are read only where the model states them.

Clear width / clear opening depend on the frame, leaf and stop. Revit exports
the frame and leaf dimensions empty, so the only honest source is a value the
model actually carries (e.g. ``Pset_BIMGuardDoor.ClearWidth`` from the property
mapping file). Without one the result is MISSING with a reason -- never the
overall width, a bounding box, or a fixed-allowance estimate. Each case runs a
real IFC4 model through the extractor and comparator end to end.
"""

from __future__ import annotations

import pytest

ifcopenshell = pytest.importorskip("ifcopenshell")


def _build_model(ifc_class: str, *, authored: dict | None = None):
    from ifcopenshell.api import run

    model = ifcopenshell.file(schema="IFC4")
    run("root.create_entity", model, ifc_class="IfcProject", name="P")
    run("unit.assign_unit", model, length={"is_metric": True, "raw": "MILLIMETERS"})
    storey = run("root.create_entity", model, ifc_class="IfcBuildingStorey", name="L1")
    run("aggregate.assign_object", model, products=[storey], relating_object=model.by_type("IfcProject")[0])

    element = run("root.create_entity", model, ifc_class=ifc_class, name="E1")
    element.OverallWidth = 1045.0
    element.OverallHeight = 2100.0
    run("spatial.assign_container", model, products=[element], relating_structure=storey)
    if authored:
        pset = run("pset.add_pset", model, product=element, name="Pset_BIMGuardOpening")
        run("pset.edit_pset", model, pset=pset, properties=authored)
    return model


def _element_result(tmp_path, model, ifc_class: str, property_name: str) -> dict:
    from app.modules.comparator import ComplianceComparator
    from app.modules.ifc_reader import IFCReader

    path = tmp_path / "model.ifc"
    model.write(str(path))
    rule = {
        "rule_id": 1,
        "reference": "TEST-CLEAR-1",
        "target_ifc_class": ifc_class,
        "property_name": property_name,
        "operator": ">=",
        "check_value": 850,
        "unit": "mm",
    }
    extraction = IFCReader(str(path)).extract_for_compliance([rule])
    results = ComplianceComparator().validate_metadata(extraction)
    return {r["rule_ref"]: r for r in results}["TEST-CLEAR-1"]["all_elements"][0]


@pytest.mark.parametrize("property_name", ["ClearWidth", "DoorClearOpeningWidth"])
def test_door_without_an_authored_clear_width_is_missing_with_the_reason(tmp_path, property_name):
    row = _element_result(tmp_path, _build_model("IfcDoor"), "IfcDoor", property_name)

    assert row["status"] == "MISSING"
    assert row["actual"] is None
    assert "frame width is missing" in row["reason"]


@pytest.mark.parametrize("property_name", ["ClearOpeningWidth", "ClearOpeningHeight", "ClearOpeningArea"])
def test_window_without_an_authored_clear_opening_is_missing(tmp_path, property_name):
    row = _element_result(tmp_path, _build_model("IfcWindow"), "IfcWindow", property_name)

    assert row["status"] == "MISSING"
    assert "window's frame width is missing" in row["reason"]


def test_authored_clear_width_is_used(tmp_path):
    model = _build_model("IfcDoor", authored={"ClearWidth": 900.0})

    row = _element_result(tmp_path, model, "IfcDoor", "ClearWidth")

    assert row["actual"] == 900.0
    assert row["status"] == "PASS"


def test_door_clear_opening_width_accepts_an_authored_clear_width(tmp_path):
    model = _build_model("IfcDoor", authored={"ClearWidth": 800.0})

    row = _element_result(tmp_path, model, "IfcDoor", "DoorClearOpeningWidth")

    assert row["actual"] == 800.0
    assert row["status"] == "FAIL"
