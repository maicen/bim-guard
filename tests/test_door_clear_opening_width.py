"""DoorClearOpeningWidth (``IFCReader._door_clear_opening_width``).

OverallWidth is the door FRAME width; DoorClearOpeningWidth approximates
the accessible PASSAGE width -- the active leaf's own share of that frame
(PanelWidth if declared, else an even split across NumberOfPanels, else the
whole frame for an apparent single-leaf door) minus a fixed generic
allowance for the leaf thickness/door-stop lost when swung open
(DEFAULT_DOOR_STOP_DEDUCTION_MM). Each case here is built as a real IFC4
door via ifcopenshell so the resolution cascade (direct OverallWidth
attribute -> Pset scan -> geometry fallback) is exercised end to end, not
just the arithmetic in isolation.
"""

from __future__ import annotations

import pytest

ifcopenshell = pytest.importorskip("ifcopenshell")

from app.modules.ifc_reader import DEFAULT_DOOR_STOP_DEDUCTION_MM


def _build_door_model(overall_width_mm: float, *, panel_width: float | None = None, number_of_panels: int | None = None):
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

    door = run("root.create_entity", model, ifc_class="IfcDoor", name="D1")
    door.OverallWidth = overall_width_mm
    door.OverallHeight = 2100.0
    run("spatial.assign_container", model, products=[door], relating_structure=storey)

    if panel_width is not None:
        pset = run("pset.add_pset", model, product=door, name="Pset_DoorPanelProperties")
        run("pset.edit_pset", model, pset=pset, properties={"PanelWidth": panel_width})
    if number_of_panels is not None:
        pset = run("pset.add_pset", model, product=door, name="Pset_DoorCommon")
        run("pset.edit_pset", model, pset=pset, properties={"NumberOfPanels": number_of_panels})

    return model, door


def _resolve(path, overall_width_mm, **kwargs):
    from app.modules.ifc_reader import IFCReader
    from app.modules.comparator import ComplianceComparator

    rule = {
        "rule_id": 1,
        "reference": "TEST-DOOR-CLEAR-1",
        "target_ifc_class": "IfcDoor",
        "property_name": "DoorClearOpeningWidth",
        "operator": "exists",
    }
    extraction = IFCReader(path).extract_for_compliance([rule])
    results = ComplianceComparator().validate_metadata(extraction)
    result = {r["rule_ref"]: r for r in results}["TEST-DOOR-CLEAR-1"]
    return result["all_elements"][0]["actual"]


class TestDoorClearOpeningWidth:
    def test_single_leaf_door_uses_full_width_minus_stop(self, tmp_path_factory):
        model, _door = _build_door_model(900.0)
        path = tmp_path_factory.mktemp("door") / "single.ifc"
        model.write(str(path))

        expected = 900.0 - DEFAULT_DOOR_STOP_DEDUCTION_MM
        value = _resolve(path, 900.0)
        assert value == pytest.approx(expected, abs=0.5)

    def test_declared_panel_width_is_used_when_present(self, tmp_path_factory):
        model, _door = _build_door_model(900.0, panel_width=0.6)
        path = tmp_path_factory.mktemp("door") / "panelwidth.ifc"
        model.write(str(path))

        expected = 900.0 * 0.6 - DEFAULT_DOOR_STOP_DEDUCTION_MM
        value = _resolve(path, 900.0)
        assert value == pytest.approx(expected, abs=0.5)

    def test_two_leaf_door_without_panel_width_assumes_even_split(self, tmp_path_factory):
        model, _door = _build_door_model(900.0, number_of_panels=2)
        path = tmp_path_factory.mktemp("door") / "twopanel.ifc"
        model.write(str(path))

        expected = 900.0 * 0.5 - DEFAULT_DOOR_STOP_DEDUCTION_MM
        value = _resolve(path, 900.0)
        assert value == pytest.approx(expected, abs=0.5)

    def test_clear_width_never_goes_negative_for_a_narrow_leaf(self, tmp_path_factory):
        # A leaf narrower than the stop deduction itself must clip to 0.0,
        # not report a nonsensical negative passage width.
        model, _door = _build_door_model(30.0)
        path = tmp_path_factory.mktemp("door") / "narrow.ifc"
        model.write(str(path))

        value = _resolve(path, 30.0)
        assert value == 0.0
