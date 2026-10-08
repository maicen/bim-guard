"""Regression tests for Module 2's single-property resolution cascade.

Covers ``IFCReader._resolve_element_property`` for two of Priority 8's
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
import ifcopenshell.guid
import pytest

from app.modules.ifc_reader import IFCReader


def _empty_reader(f) -> IFCReader:
    """Build a IFCReader bound to *f*, without the geometry/spatial extras."""
    m2 = IFCReader.__new__(IFCReader)
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


class TestOpeningRelationship:
    """A window's opening and host wall are relationships, never Pset keys."""

    def _window_in_wall(self):
        f = _metre_model()
        wall = ifcopenshell.api.run("root.create_entity", f, ifc_class="IfcWall")
        opening = ifcopenshell.api.run("root.create_entity", f, ifc_class="IfcOpeningElement")
        window = ifcopenshell.api.run("root.create_entity", f, ifc_class="IfcWindow")
        ifcopenshell.api.run("feature.add_feature", f, feature=opening, element=wall)
        ifcopenshell.api.run("feature.add_filling", f, opening=opening, element=window)
        return f, wall, opening, window

    @pytest.mark.parametrize("prop_name", ["OpeningElement", "IfcOpeningElement", "OpeningGlobalId", "FillsVoids"])
    def test_window_filling_an_opening_reports_it(self, prop_name):
        f, _wall, opening, window = self._window_in_wall()

        value, found_pset, _ = _empty_reader(f)._resolve_element_property(window, prop_name)

        assert value == opening.GlobalId
        assert found_pset == "relationship:fills_opening"

    def test_host_names_the_voided_wall(self):
        f, wall, _opening, window = self._window_in_wall()
        m2 = _empty_reader(f)

        assert m2._resolve_element_property(window, "HostIfcClass")[0] == "IfcWall"
        assert m2._resolve_element_property(window, "HostGlobalId")[0] == wall.GlobalId

    @pytest.mark.parametrize("prop_name", ["relationships.host_global_id", "Relationships.HostGlobalId"])
    def test_a_namespace_prefix_is_read_as_the_bare_name(self, prop_name):
        """A rule saying "relationships.host_global_id" means host_global_id."""
        f, wall, _opening, window = self._window_in_wall()

        value, found_pset, _ = _empty_reader(f)._resolve_element_property(window, prop_name)

        assert value == wall.GlobalId
        assert found_pset == "relationship:fills_opening"

    def test_window_filling_no_opening_stays_missing(self):
        f = _metre_model()
        window = ifcopenshell.api.run("root.create_entity", f, ifc_class="IfcWindow")

        value, _found_pset, _ = _empty_reader(f)._resolve_element_property(window, "OpeningElement")

        assert value is None


class TestOpeningAsRuleTarget:
    """A rule may target the opening itself, which fills nothing."""

    def test_opening_reads_its_own_class_and_its_host(self):
        f = _metre_model()
        wall = ifcopenshell.api.run("root.create_entity", f, ifc_class="IfcWall")
        opening = ifcopenshell.api.run("root.create_entity", f, ifc_class="IfcOpeningElement")
        ifcopenshell.api.run("feature.add_feature", f, feature=opening, element=wall)
        m2 = _empty_reader(f)

        assert m2._resolve_element_property(opening, "OpeningIfcClass")[0] == "IfcOpeningElement"
        value, found_pset, _ = m2._resolve_element_property(opening, "HostGlobalId")
        assert value == wall.GlobalId
        assert found_pset == "relationship:voids_element"

    def test_opening_voiding_nothing_has_no_host(self):
        f = _metre_model()
        opening = ifcopenshell.api.run("root.create_entity", f, ifc_class="IfcOpeningElement")

        assert _empty_reader(f)._resolve_element_property(opening, "HostGlobalId")[0] is None


class TestStoreyAndPlacement:
    """Storey containment and placement are references, never Pset keys."""

    def _door_on_storey(self):
        f = _metre_model()
        storey = ifcopenshell.api.run("root.create_entity", f, ifc_class="IfcBuildingStorey", name="Level 1")
        door = ifcopenshell.api.run("root.create_entity", f, ifc_class="IfcDoor")
        ifcopenshell.api.run("spatial.assign_container", f, products=[door], relating_structure=storey)
        return f, storey, door

    def test_door_reads_its_storey_by_id_and_name(self):
        f, storey, door = self._door_on_storey()
        m2 = _empty_reader(f)
        spatial = m2.get_spatial_location(door)

        assert m2._resolve_element_property(door, "StoreyGlobalId", spatial=spatial)[0] == storey.GlobalId
        assert m2._resolve_element_property(door, "StoreyName", spatial=spatial)[0] == "Level 1"

    def test_storey_answers_for_itself(self):
        f, storey, _door = self._door_on_storey()
        m2 = _empty_reader(f)

        value, _, _ = m2._resolve_element_property(storey, "StoreyName", spatial=m2.get_spatial_location(storey))

        assert value == "Level 1"

    def test_door_in_a_curtain_wall_reads_the_wall_storey(self):
        f, storey, _door = self._door_on_storey()
        curtain_wall = ifcopenshell.api.run("root.create_entity", f, ifc_class="IfcCurtainWall")
        part = ifcopenshell.api.run("root.create_entity", f, ifc_class="IfcDoor")
        ifcopenshell.api.run("spatial.assign_container", f, products=[curtain_wall], relating_structure=storey)
        ifcopenshell.api.run("aggregate.assign_object", f, products=[part], relating_object=curtain_wall)
        m2 = _empty_reader(f)

        value, _, _ = m2._resolve_element_property(part, "StoreyGlobalId", spatial=m2.get_spatial_location(part))

        assert value == storey.GlobalId

    def test_uncontained_door_has_no_storey(self):
        f = _metre_model()
        door = ifcopenshell.api.run("root.create_entity", f, ifc_class="IfcDoor")
        m2 = _empty_reader(f)

        value, _, _ = m2._resolve_element_property(door, "StoreyGlobalId", spatial=m2.get_spatial_location(door))

        assert value is None

    def test_placement_matrix_is_read_only_when_the_element_is_placed(self):
        f = _metre_model()
        placed = ifcopenshell.api.run("root.create_entity", f, ifc_class="IfcDoor")
        unplaced = ifcopenshell.api.run("root.create_entity", f, ifc_class="IfcDoor")
        ifcopenshell.api.run("geometry.edit_object_placement", f, product=placed)
        m2 = _empty_reader(f)

        value, found_pset, detail = m2._resolve_element_property(placed, "PlacementMatrix")
        assert value is not None
        assert found_pset == "attribute:placement"
        assert len(detail["matrix"]) == 4
        assert m2._resolve_element_property(unplaced, "PlacementMatrix")[0] is None


class TestRevitSillAndHeadHeight:
    """Revit exports these as "Sill Height" / "Head Height", spaces included."""

    @pytest.mark.parametrize(
        ("prop_name", "revit_name", "metres", "mm"),
        [("SillHeight", "Sill Height", 0.9, 900.0), ("HeadHeight", "Head Height", 2.1, 2100.0)],
    )
    def test_revit_parameter_resolves_and_scales_to_mm(self, prop_name, revit_name, metres, mm):
        f = _metre_model()
        window = ifcopenshell.api.run("root.create_entity", f, ifc_class="IfcWindow")
        _add_pset_property(f, window, "Constraints", revit_name, f.createIfcLengthMeasure(metres))

        value, found_pset, _ = _empty_reader(f)._resolve_element_property(
            window, prop_name, unit_scale_mm=1000.0
        )

        assert value == pytest.approx(mm)
        assert found_pset == "alias:Constraints"


class TestGlobalIdAttribute:
    """GlobalId is a direct schema attribute and must resolve like one.

    It used to be on get_direct_attributes' skip list, so an ``exists``
    rule on GlobalId reported every element as missing it.
    """

    def test_globalid_resolves_from_the_entity(self):
        f = _metre_model()
        window = ifcopenshell.api.run("root.create_entity", f, ifc_class="IfcWindow")

        value, found_pset, _ = _empty_reader(f)._resolve_element_property(window, "GlobalId")

        assert value == window.GlobalId
        assert found_pset == "direct_attribute"


def _typed_window(schema: str, type_class: str, type_name: str = "Sliding 2500x2980"):
    """Return ``(file, window)`` with the window assigned a ``type_class`` type."""
    f = ifcopenshell.api.run("project.create_file", version=schema)
    ifcopenshell.api.run("root.create_entity", f, ifc_class="IfcProject", name="Test")
    window = ifcopenshell.api.run("root.create_entity", f, ifc_class="IfcWindow")
    window_type = ifcopenshell.api.run("root.create_entity", f, ifc_class=type_class, name=type_name)
    ifcopenshell.api.run("type.assign_type", f, related_objects=[window], relating_type=window_type)
    return f, window


class TestTypeAssignment:
    """"Every window must have an assigned IfcWindowType" reads IfcRelDefinesByType.

    No exporter writes a Pset property literally named ``WindowType``, so the
    Pset passes alone failed every window -- typed or not.
    """

    @pytest.mark.parametrize("prop_name", ["WindowType", "IfcWindowType", "Window Type"])
    def test_ifc4_window_type_answers_from_the_type_object(self, prop_name):
        f, window = _typed_window("IFC4", "IfcWindowType")

        value, found_pset, detail = _empty_reader(f)._resolve_element_property(window, prop_name)

        assert value == "Sliding 2500x2980"
        assert found_pset == "relationship:type"
        assert detail["type_ifc_class"] == "IfcWindowType"

    def test_ifc2x3_window_style_counts_as_the_window_type(self):
        """IfcWindowType does not exist in IFC2x3; Revit types windows with IfcWindowStyle."""
        # Built directly: ifcopenshell.api refuses IFC2x3 roots without an
        # owner history, which is irrelevant to the type link under test.
        f = ifcopenshell.file(schema="IFC2X3")
        window = f.create_entity("IfcWindow", GlobalId=ifcopenshell.guid.new())
        style = f.create_entity(
            "IfcWindowStyle",
            GlobalId=ifcopenshell.guid.new(),
            Name="Sliding 2500x2980",
            ConstructionType="NOTDEFINED",
            OperationType="NOTDEFINED",
            ParameterTakesPrecedence=False,
            Sizeable=False,
        )
        f.create_entity(
            "IfcRelDefinesByType",
            GlobalId=ifcopenshell.guid.new(),
            RelatedObjects=[window],
            RelatingType=style,
        )

        value, found_pset, detail = _empty_reader(f)._resolve_element_property(window, "IfcWindowType")

        assert value == "Sliding 2500x2980"
        assert found_pset == "relationship:type"
        assert detail["type_ifc_class"] == "IfcWindowStyle"

    def test_untyped_window_still_has_no_window_type(self):
        f = _metre_model()
        window = ifcopenshell.api.run("root.create_entity", f, ifc_class="IfcWindow")

        value, found_pset, _ = _empty_reader(f)._resolve_element_property(window, "WindowType")

        assert value is None
        assert found_pset is None

    def test_an_authored_window_type_property_wins_over_the_type_link(self):
        """A model storing "WindowType" itself keeps that value for comparisons."""
        f, window = _typed_window("IFC4", "IfcWindowType")
        _add_pset_property(f, window, "Custom", "WindowType", f.createIfcLabel("Sliding"))

        value, found_pset, _ = _empty_reader(f)._resolve_element_property(window, "WindowType")

        assert value == "Sliding"
        assert found_pset == "Custom"

    @pytest.mark.parametrize("prop_name", ["IsTypedBy", "RelatingType"])
    def test_is_typed_by_answers_from_the_type_link(self, prop_name):
        """"Door must be typed via IfcRelDefinesByType" names the relationship itself."""
        f = _metre_model()
        door = ifcopenshell.api.run("root.create_entity", f, ifc_class="IfcDoor")
        door_type = ifcopenshell.api.run("root.create_entity", f, ifc_class="IfcDoorType", name="Door_Opening 1045x2300")
        ifcopenshell.api.run("type.assign_type", f, related_objects=[door], relating_type=door_type)

        value, found_pset, _ = _empty_reader(f)._resolve_element_property(door, prop_name)

        assert value == "Door_Opening 1045x2300"
        assert found_pset == "relationship:type"

    def test_untyped_element_has_no_is_typed_by(self):
        f = _metre_model()
        door = ifcopenshell.api.run("root.create_entity", f, ifc_class="IfcDoor")

        value, _, _ = _empty_reader(f)._resolve_element_property(door, "IsTypedBy")

        assert value is None

    def test_type_global_id_reads_the_type_objects_guid(self):
        f, window = _typed_window("IFC4", "IfcWindowType")
        expected = f.by_type("IfcWindowType")[0].GlobalId

        value, _, _ = _empty_reader(f)._resolve_element_property(window, "TypeGlobalId")

        assert value == expected

    def test_a_numeric_type_name_is_not_rescaled_as_a_length(self):
        f, window = _typed_window("IFC4", "IfcWindowType", type_name="1200")

        value, _, _ = _empty_reader(f)._resolve_element_property(
            window, "WindowType", unit_scale_mm=1000.0
        )

        assert value == "1200"

    def test_another_class_type_name_does_not_match(self):
        """A window is never answered for "DoorType"."""
        f, window = _typed_window("IFC4", "IfcWindowType")

        value, _, _ = _empty_reader(f)._resolve_element_property(window, "DoorType")

        assert value is None


class TestIfcClass:
    """"Runtime IFC class must resolve to IfcDoor" reads the entity class itself.

    ``ifc_class`` is neither a Pset key nor a get_info() attribute, so it used
    to resolve to nothing and every element was reported missing.
    """

    @pytest.mark.parametrize("prop_name", ["ifc_class", "IfcClass", "IFC Class", "ifc_entity"])
    def test_ifc_class_is_the_elements_entity_class(self, prop_name):
        f = _metre_model()
        door = ifcopenshell.api.run("root.create_entity", f, ifc_class="IfcDoor")

        value, found_pset, _ = _empty_reader(f)._resolve_element_property(door, prop_name)

        assert value == "IfcDoor"
        assert found_pset == "attribute:ifc_class"

    def test_a_door_exported_as_a_proxy_reports_the_proxy_class(self):
        """So a "must resolve to IfcDoor" rule fails it rather than passing it."""
        f = _metre_model()
        proxy = ifcopenshell.api.run("root.create_entity", f, ifc_class="IfcBuildingElementProxy", name="Door")

        value, _, _ = _empty_reader(f)._resolve_element_property(proxy, "ifc_class")

        assert value == "IfcBuildingElementProxy"

    def test_an_authored_property_cannot_override_the_runtime_class(self):
        f = _metre_model()
        proxy = ifcopenshell.api.run("root.create_entity", f, ifc_class="IfcBuildingElementProxy")
        _add_pset_property(f, proxy, "Custom", "ifc_class", f.createIfcLabel("IfcDoor"))

        value, _, _ = _empty_reader(f)._resolve_element_property(proxy, "ifc_class")

        assert value == "IfcBuildingElementProxy"


class TestTypeAssignmentCount:
    """"Each window must resolve exactly one type association" counts IfcRelDefinesByType.

    No exporter writes a ``TypeAssignmentCount`` Pset value, so every window
    reported missing whether or not it was typed.
    """

    @pytest.mark.parametrize("prop_name", ["TypeAssignmentCount", "type_assignment_count", "TypeCount"])
    def test_ifc4_typed_window_counts_one(self, prop_name):
        f, window = _typed_window("IFC4", "IfcWindowType")

        value, found_pset, detail = _empty_reader(f)._resolve_element_property(window, prop_name)

        assert value == 1
        assert found_pset == "relationship:type_count"
        assert detail["type_names"] == ["Sliding 2500x2980"]

    def test_untyped_window_counts_zero_not_missing(self):
        """0 is a real answer the rule must fail, not a missing value."""
        f = _metre_model()
        window = ifcopenshell.api.run("root.create_entity", f, ifc_class="IfcWindow")

        value, found_pset, _ = _empty_reader(f)._resolve_element_property(window, "TypeAssignmentCount")

        assert value == 0
        assert found_pset == "relationship:type_count"

    def test_ifc2x3_window_style_counts_via_is_defined_by(self):
        """IFC2x3 has no IsTypedBy inverse; the type link sits in IsDefinedBy."""
        f = ifcopenshell.file(schema="IFC2X3")
        window = f.create_entity("IfcWindow", GlobalId=ifcopenshell.guid.new())
        style = f.create_entity(
            "IfcWindowStyle",
            GlobalId=ifcopenshell.guid.new(),
            Name="Sliding",
            ConstructionType="NOTDEFINED",
            OperationType="NOTDEFINED",
            ParameterTakesPrecedence=False,
            Sizeable=False,
        )
        f.create_entity(
            "IfcRelDefinesByType", GlobalId=ifcopenshell.guid.new(), RelatedObjects=[window], RelatingType=style
        )

        value, _, _ = _empty_reader(f)._resolve_element_property(window, "TypeAssignmentCount")

        assert value == 1

    def test_window_assigned_two_types_counts_two(self):
        f, window = _typed_window("IFC4", "IfcWindowType")
        second = ifcopenshell.api.run("root.create_entity", f, ifc_class="IfcWindowType", name="Casement")
        # Built directly: type.assign_type replaces an existing assignment,
        # but a malformed export can carry two.
        f.create_entity(
            "IfcRelDefinesByType", GlobalId=ifcopenshell.guid.new(), RelatedObjects=[window], RelatingType=second
        )

        value, _, detail = _empty_reader(f)._resolve_element_property(window, "TypeAssignmentCount")

        assert value == 2
        assert sorted(detail["type_names"]) == ["Casement", "Sliding 2500x2980"]


class TestConnectedSpaceCountFallback:
    """A door's room count must agree with the room names it reports."""

    _ROOM = {"rooms": ["CORRIDOR", "WIC"], "link_source": "host_lining"}

    def _door(self):
        f = _metre_model()
        return f, ifcopenshell.api.run("root.create_entity", f, ifc_class="IfcDoor")

    def test_door_without_boundary_data_counts_its_room_links(self):
        f, door = self._door()
        no_data = {"has_data": False, "connected_space_count": 0}

        value, found_pset, _ = _empty_reader(f)._resolve_element_property(
            door, "ConnectedSpaceCount", door_space_connection=no_data, room=self._ROOM
        )

        assert value == 2
        assert found_pset == "spatial:room_link"

    def test_boundary_data_wins_over_room_links(self):
        f, door = self._door()
        with_data = {"has_data": True, "connected_space_count": 1}

        value, found_pset, _ = _empty_reader(f)._resolve_element_property(
            door, "ConnectedSpaceCount", door_space_connection=with_data, room=self._ROOM
        )

        assert value == 1
        assert found_pset == "spatial:door_space_connection"

    def test_door_with_no_evidence_still_counts_zero(self):
        f, door = self._door()

        value, _, _ = _empty_reader(f)._resolve_element_property(
            door, "ConnectedSpaceCount", door_space_connection={"has_data": False, "connected_space_count": 0}
        )

        assert value == 0
