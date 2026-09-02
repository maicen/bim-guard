"""Regression tests for Module 2's single-property resolution cascade.

Covers ``Module2_IFCRead._resolve_element_property`` for two of Priority 8's
IFC ingestion correctness bugs:

* A Pset value authored as a numeric string (e.g. ``IfcLabel('1.2')``
  instead of a proper ``IfcPositiveLengthMeasure``) used to skip unit
  conversion entirely because it failed the ``isinstance(value, (int,
  float))`` guard, so a 1.2 m value was compared as 1.2 mm.
* ``RequiredHeadroom`` was misspelled ``requireheadroom`` in
  ``_LENGTH_DIRECT_ATTRS``, so ``Pset_StairCommon.RequiredHeadroom`` only
  converted to mm when it carried an explicit IFC measure type.
"""

from __future__ import annotations

import ifcopenshell
import ifcopenshell.api
import pytest

from app.modules.module2_ifc_read import Module2_IFCRead


def _empty_reader(f) -> Module2_IFCRead:
    """Build a Module2_IFCRead bound to *f*, without the geometry/spatial extras."""
    m2 = Module2_IFCRead.__new__(Module2_IFCRead)
    m2.ifc_file = f
    m2.geometry_extractor = None
    m2.spatial_adjacency = None
    m2.egress_graph = None
    return m2


def _metre_model():
    f = ifcopenshell.api.run("project.create_file", version="IFC4")
    ifcopenshell.api.run("root.create_entity", f, ifc_class="IfcProject", name="Test")
    ifcopenshell.api.run("unit.assign_unit", f, length={"is_metric": True, "raw": "METERS"})
    return f


def _add_pset_property(f, product, pset_name: str, prop_name: str, ifc_value):
    pset = ifcopenshell.api.run("pset.add_pset", f, product=product, name=pset_name)
    prop = f.createIfcPropertySingleValue(prop_name, None, ifc_value, None)
    pset.HasProperties = [prop]
    return pset


class TestNumericStringUnitConversion:
    """A quantity authored as a numeric string must still be scaled to mm."""

    def test_ifclabel_numeric_string_is_scaled_to_mm(self):
        f = _metre_model()
        window = ifcopenshell.api.run("root.create_entity", f, ifc_class="IfcWindow")
        _add_pset_property(
            f, window, "Pset_WindowCommon", "ClearWidth", f.createIfcLabel("1.2")
        )

        m2 = _empty_reader(f)
        value, found_pset, _ = m2._resolve_element_property(
            window, "ClearWidth", unit_scale_mm=1000.0
        )

        assert value == pytest.approx(1200.0)
        assert isinstance(value, float)
        assert found_pset == "Pset_WindowCommon"

    def test_ifcreal_numeric_value_is_unaffected(self):
        """Sanity check: a properly-typed value keeps converting as before."""
        f = _metre_model()
        window = ifcopenshell.api.run("root.create_entity", f, ifc_class="IfcWindow")
        _add_pset_property(
            f, window, "Pset_WindowCommon", "ClearWidth", f.createIfcReal(1.2)
        )

        m2 = _empty_reader(f)
        value, _, _ = m2._resolve_element_property(
            window, "ClearWidth", unit_scale_mm=1000.0
        )

        assert value == pytest.approx(1200.0)

    def test_non_numeric_string_is_left_alone(self):
        """A genuinely textual property (e.g. FireRating) must not be coerced."""
        f = _metre_model()
        door = ifcopenshell.api.run("root.create_entity", f, ifc_class="IfcDoor")
        _add_pset_property(
            f, door, "Pset_DoorCommon", "FireRating", f.createIfcLabel("60min")
        )

        m2 = _empty_reader(f)
        value, _, _ = m2._resolve_element_property(
            door, "FireRating", unit_scale_mm=1000.0
        )

        assert value == "60min"

    def test_millimetre_model_needs_no_scaling(self):
        f = ifcopenshell.api.run("project.create_file", version="IFC4")
        ifcopenshell.api.run("root.create_entity", f, ifc_class="IfcProject", name="Test")
        ifcopenshell.api.run(
            "unit.assign_unit", f, length={"is_metric": True, "raw": "MILLIMETERS"}
        )
        window = ifcopenshell.api.run("root.create_entity", f, ifc_class="IfcWindow")
        _add_pset_property(
            f, window, "Pset_WindowCommon", "ClearWidth", f.createIfcLabel("1200")
        )

        m2 = _empty_reader(f)
        value, _, _ = m2._resolve_element_property(
            window, "ClearWidth", unit_scale_mm=1.0
        )

        # unit_scale_mm == 1.0 short-circuits Pass 8 entirely, so the raw
        # string is returned as-is -- Module 4 compares it against the
        # rule's numeric bound, which coerces on its own side.
        assert value == "1200"


class TestRequiredHeadroomTypo:
    """Covers the ``requireheadroom`` / ``requiredheadroom`` typo.

    The direct-attribute length set had the misspelling, so a plain
    ``IfcReal``-typed RequiredHeadroom value (no explicit measure type)
    silently skipped unit conversion.
    """

    def test_requiredheadroom_without_measure_type_is_scaled_to_mm(self):
        f = _metre_model()
        flight = ifcopenshell.api.run("root.create_entity", f, ifc_class="IfcStairFlight")
        _add_pset_property(
            f, flight, "Pset_StairCommon", "RequiredHeadroom", f.createIfcReal(1.95)
        )

        m2 = _empty_reader(f)
        value, _, rich = m2._resolve_element_property(
            flight, "RequiredHeadroom", unit_scale_mm=1000.0
        )

        assert rich["measure_type"] == "IfcReal"  # not a length-measure type
        assert value == pytest.approx(1950.0)
