"""Room identity, element-to-room links, and room-scoped rules end to end.

A small house is built into ``tmp_path`` as a real IFC4 file so the tests run
against genuine ``IfcRelSpaceBoundary``, ``IfcRelVoidsElement``,
``IfcRelFillsElement`` and containment relationships rather than mocks.

Floor plan (x in mm; every room 0-2700 high, 0-4000 deep)::

    Bedroom 1      Hallway        Kitchen          Nook
    0 ------ 4000  4000 --- 6000  6000 ---- 10000  10000 - 12000

Elements are deliberately given different amounts of evidence, because that is
what real exports do:

    door_bc        boundaries to Bedroom 1 and Hallway            -> boundary
    door_kc        boundaries to Kitchen and Hallway              -> boundary
    door_nc        boundaries to Nook and Hallway (Nook untyped)  -> boundary
    door_host      no boundary; fills an opening in wall_bc       -> host_wall
    door_far       no boundary; fills an opening in wall_far      -> ambiguous host
    door_orphan    no boundary, no host                           -> unlinked
    door_in_kitchen contained directly in the Kitchen space       -> containment
"""

from __future__ import annotations

from pathlib import Path

import pytest

ifcopenshell = pytest.importorskip("ifcopenshell")

from ifcopenshell.api import run  # noqa: E402
from ifcopenshell.guid import new as new_guid  # noqa: E402

from app.modules.comparator import ComplianceComparator  # noqa: E402
from app.modules.ifc_reader import IFCReader  # noqa: E402
from app.modules.ifc_reader.ifc_rooms import (  # noqa: E402
    SOURCE_BOUNDARY,
    SOURCE_CONTAINMENT,
    SOURCE_GEOMETRIC,
    SOURCE_HOST_WALL,
    SOURCE_NONE,
    SOURCE_SELF,
    ElementRoomLinker,
    RoomIndex,
    room_context,
    room_derived_value,
    unique_short_ids,
)
from app.modules.ifc_reader.ifc_spatial import (  # noqa: E402
    BOUNDARY_SOURCE_GEOMETRIC,
    IFCSpatialAdjacency,
)
from app.modules.room_types import UNKNOWN_ROOM_TYPE  # noqa: E402

BOX = {"min_y": 0.0, "max_y": 4000.0, "min_z": 0.0, "max_z": 2700.0}
SPACE_BOXES = {
    "Bedroom 1": {"min_x": 0.0, "max_x": 4000.0, **BOX},
    "Hallway": {"min_x": 4000.0, "max_x": 6000.0, **BOX},
    "Kitchen": {"min_x": 6000.0, "max_x": 10000.0, **BOX},
    "Nook": {"min_x": 10000.0, "max_x": 12000.0, **BOX},
}


def _boundary(model, space, element) -> None:
    model.create_entity(
        "IfcRelSpaceBoundary",
        GlobalId=new_guid(),
        RelatingSpace=space,
        RelatedBuildingElement=element,
        PhysicalOrVirtualBoundary="PHYSICAL",
        InternalOrExternalBoundary="INTERNAL",
    )


def _build_house() -> tuple[ifcopenshell.file, dict]:
    """Build the house; return the model and a name -> entity lookup."""
    model = ifcopenshell.file(schema="IFC4")
    project = run("root.create_entity", model, ifc_class="IfcProject", name="House")
    run("unit.assign_unit", model)
    site = run("root.create_entity", model, ifc_class="IfcSite", name="Site")
    building = run("root.create_entity", model, ifc_class="IfcBuilding", name="Building")
    storey = run("root.create_entity", model, ifc_class="IfcBuildingStorey", name="L01")
    run("aggregate.assign_object", model, products=[site], relating_object=project)
    run("aggregate.assign_object", model, products=[building], relating_object=site)
    run("aggregate.assign_object", model, products=[storey], relating_object=building)

    named: dict = {}

    def make(ifc_class: str, name: str, **attrs):
        entity = run("root.create_entity", model, ifc_class=ifc_class, name=name)
        for key, value in attrs.items():
            setattr(entity, key, value)
        named[name] = entity
        return entity

    spaces = {}
    for long_name in SPACE_BOXES:
        space = make("IfcSpace", long_name, LongName=long_name)
        run("aggregate.assign_object", model, products=[space], relating_object=storey)
        spaces[long_name] = space
    bedroom, hallway, kitchen, nook = (
        spaces["Bedroom 1"], spaces["Hallway"], spaces["Kitchen"], spaces["Nook"],
    )

    # Structure and openings live directly on the storey.
    elements = []

    def element(ifc_class: str, name: str, width: int | None = None):
        entity = make(ifc_class, name)
        elements.append(entity)
        if width is not None:
            pset = run("pset.add_pset", model, product=entity, name="Pset_Test")
            run("pset.edit_pset", model, pset=pset, properties={"WidthMM": width})
        return entity

    wall_bc = element("IfcWall", "wall_bc")
    wall_kc = element("IfcWall", "wall_kc")
    wall_far = element("IfcWall", "wall_far")
    door_bc = element("IfcDoor", "door_bc", 700)
    door_kc = element("IfcDoor", "door_kc", 700)
    door_nc = element("IfcDoor", "door_nc", 700)
    door_host = element("IfcDoor", "door_host", 700)
    door_far = element("IfcDoor", "door_far", 700)
    element("IfcDoor", "door_orphan", 700)  # no evidence at all
    win_bed = element("IfcWindow", "win_bed", 900)
    element("IfcWindow", "win_orphan", 900)  # no evidence at all
    slab_bed = element("IfcSlab", "slab_bed")
    run("spatial.assign_container", model, products=elements, relating_structure=storey)

    # A door contained directly in a space is its own container -- it cannot
    # also be contained in the storey.
    door_in_kitchen = make("IfcDoor", "door_in_kitchen")
    pset = run("pset.add_pset", model, product=door_in_kitchen, name="Pset_Test")
    run("pset.edit_pset", model, pset=pset, properties={"WidthMM": 700})
    run("spatial.assign_container", model, products=[door_in_kitchen], relating_structure=kitchen)

    # Authored space boundaries.
    for space, entity in [
        (bedroom, wall_bc), (hallway, wall_bc),
        (kitchen, wall_kc), (hallway, wall_kc),
        (bedroom, wall_far), (hallway, wall_far), (kitchen, wall_far),
        (bedroom, door_bc), (hallway, door_bc),
        (kitchen, door_kc), (hallway, door_kc),
        (nook, door_nc), (hallway, door_nc),
        (bedroom, win_bed),
        (bedroom, slab_bed),
    ]:
        _boundary(model, space, entity)

    # door_host / door_far sit in openings cut from a wall.
    for door, wall, opening_name in [(door_host, wall_bc, "op_host"), (door_far, wall_far, "op_far")]:
        opening = make("IfcOpeningElement", opening_name)
        run("feature.add_feature", model, feature=opening, element=wall)
        run("feature.add_filling", model, opening=opening, element=door)

    return model, named


@pytest.fixture(scope="module")
def house():
    return _build_house()


@pytest.fixture(scope="module")
def model(house):
    return house[0]


@pytest.fixture(scope="module")
def named(house):
    return house[1]


@pytest.fixture()
def linker(model):
    """Build a linker with no geometry, as for a model whose shapes did not resolve."""
    adjacency = IFCSpatialAdjacency(model, fallback_to_geometric=False).build()
    return ElementRoomLinker(adjacency, model)


class FakeExtractor:
    """Bounding boxes by name, standing in for IFCGeometryExtractor."""

    def __init__(self, boxes: dict[str, dict]):
        self._boxes = boxes

    def get_bounding_box(self, entity):
        return self._boxes.get(entity.Name)


def _names(links) -> list[str]:
    return sorted(r.name for r in links.rooms)


# ── Rooms ─────────────────────────────────────────────────────────────────────


class TestRoomIndex:
    def test_every_space_is_read(self, model):
        assert len(RoomIndex(model)) == 4

    def test_rooms_are_typed_from_their_names(self, model):
        rooms = {r.name: r for r in RoomIndex(model).all()}
        assert rooms["Bedroom 1"].types == ("bedroom",)
        assert rooms["Hallway"].types == ("corridor",)
        assert rooms["Kitchen"].types == ("kitchen",)
        assert rooms["Bedroom 1"].type_source == "LongName"

    def test_an_untypable_room_is_unknown_not_dropped(self, model):
        nook = next(r for r in RoomIndex(model).all() if r.name == "Nook")
        assert nook.types == (UNKNOWN_ROOM_TYPE,)
        assert not nook.is_classified

    def test_storey_is_recorded(self, model):
        assert {r.storey for r in RoomIndex(model).all()} == {"L01"}


# ── Element -> rooms ──────────────────────────────────────────────────────────


class TestAuthoredBoundaries:
    def test_door_links_to_the_rooms_it_bounds(self, linker, named):
        links = linker.links_for(named["door_bc"])
        assert links.source == SOURCE_BOUNDARY
        assert links.usable
        assert _names(links) == ["Bedroom 1", "Hallway"]

    @pytest.mark.parametrize(
        ("element", "expected"),
        [
            ("wall_bc", ["Bedroom 1", "Hallway"]),
            ("win_bed", ["Bedroom 1"]),
            ("slab_bed", ["Bedroom 1"]),
        ],
    )
    def test_every_element_class_links_not_only_doors(self, linker, named, element, expected):
        links = linker.links_for(named[element])
        assert links.source == SOURCE_BOUNDARY
        assert _names(links) == expected

    def test_a_space_is_its_own_room(self, linker, named):
        links = linker.links_for(named["Kitchen"])
        assert links.source == SOURCE_SELF
        assert _names(links) == ["Kitchen"]


class TestContainment:
    def test_element_contained_in_a_space_is_linked_to_it(self, linker, named):
        links = linker.links_for(named["door_in_kitchen"])
        assert links.source == SOURCE_CONTAINMENT
        assert _names(links) == ["Kitchen"]
        assert links.usable


class TestHostWall:
    def test_door_inherits_the_rooms_of_a_two_room_host(self, linker, named):
        # No geometry: a host bounding only two rooms is unambiguous enough.
        links = linker.links_for(named["door_host"])
        assert links.source == SOURCE_HOST_WALL
        assert _names(links) == ["Bedroom 1", "Hallway"]
        assert links.usable

    def test_a_host_bounding_many_rooms_is_not_guessed_without_geometry(self, linker, named):
        # wall_far bounds three rooms and nothing can say which the door opens
        # onto: no link, rather than crediting it to all three.
        links = linker.links_for(named["door_far"])
        assert links.source == SOURCE_NONE
        assert not links.usable
        assert links.rooms == ()

    def test_geometry_narrows_a_many_room_host_to_the_rooms_the_door_touches(self, model, named):
        adjacency = IFCSpatialAdjacency(model, fallback_to_geometric=False).build()
        # The door sits on the Hallway/Kitchen line (x = 6000), well clear of
        # Bedroom 1 (which ends at 4000).
        door_box = {"min_x": 5900.0, "max_x": 6100.0, **BOX}
        extractor = FakeExtractor({**SPACE_BOXES, "door_far": door_box})
        linker = ElementRoomLinker(adjacency, model, geometry_extractor=extractor)

        links = linker.links_for(named["door_far"])
        assert links.source == SOURCE_HOST_WALL
        assert _names(links) == ["Hallway", "Kitchen"]

    def test_geometry_that_touches_no_candidate_yields_no_link(self, model, named):
        adjacency = IFCSpatialAdjacency(model, fallback_to_geometric=False).build()
        far_away = {"min_x": 90000.0, "max_x": 90100.0, **BOX}
        extractor = FakeExtractor({**SPACE_BOXES, "door_far": far_away})
        linker = ElementRoomLinker(adjacency, model, geometry_extractor=extractor)

        assert linker.links_for(named["door_far"]).source == SOURCE_NONE


class TestUnlinked:
    def test_an_element_with_no_evidence_is_unlinked_and_says_why(self, linker, named):
        links = linker.links_for(named["door_orphan"])
        assert links.source == SOURCE_NONE
        assert not links.usable
        assert "no room could be linked" in links.note


class TestGeometricLinksAreNotUsable:
    """Bounding-box links are recorded but never allowed to scope a rule.

    Contact linked a door to six rooms on a real residential model.
    """

    def test_bbox_only_evidence_is_recorded_but_unusable(self, model, named):
        adjacency = IFCSpatialAdjacency(model, fallback_to_geometric=False).build()
        # Simulate a model with rooms but no authored boundaries, where the
        # fallback found the door "touching" a bedroom.
        bedroom = next(s for s in model.by_type("IfcSpace") if s.LongName == "Bedroom 1")
        adjacency._space_data = {
            bedroom.GlobalId: {
                "space": bedroom,
                "boundaries": [
                    {
                        "element": named["door_orphan"],
                        "element_guid": named["door_orphan"].GlobalId,
                        "element_type": "IfcDoor",
                        "physical": True,
                        "source": BOUNDARY_SOURCE_GEOMETRIC,
                    }
                ],
            }
        }
        adjacency._element_to_spaces = None
        links = ElementRoomLinker(adjacency, model).links_for(named["door_orphan"])

        assert links.source == SOURCE_GEOMETRIC
        assert _names(links) == ["Bedroom 1"]  # recorded...
        assert not links.usable  # ...but not trusted
        assert "bounding-box" in links.note

    def test_context_reports_unusable_links_as_unresolved(self, model, named):
        adjacency = IFCSpatialAdjacency(model, fallback_to_geometric=False).build()
        linker = ElementRoomLinker(adjacency, model)
        context = room_context(named["door_orphan"], linker)
        assert context["rooms"] is None
        assert context["room_types"] is None
        assert context["link_source"] == SOURCE_NONE


class TestRoomContext:
    def test_types_are_the_union_across_connected_rooms(self, linker, named):
        context = room_context(named["door_bc"], linker)
        assert context["rooms"] == ["Bedroom 1", "Hallway"]
        assert sorted(context["room_types"]) == ["bedroom", "corridor"]

    def test_an_untyped_connected_room_shows_up_as_unknown(self, linker, named):
        context = room_context(named["door_nc"], linker)
        assert UNKNOWN_ROOM_TYPE in context["room_types"]
        assert "corridor" in context["room_types"]

    def test_links_are_memoised(self, linker, named):
        assert linker.links_for(named["door_bc"]) is linker.links_for(named["door_bc"])


# ── Counts per room ───────────────────────────────────────────────────────────


class TestSpaceCounts:
    def test_counts_include_inherited_and_authored_links(self, linker, named):
        counts = linker.space_counts(named["Bedroom 1"].GlobalId)["counts"]
        # door_bc (authored) + door_host (inherited via wall_bc)
        assert counts["DoorCount"] == 2
        assert counts["WindowCount"] == 1
        assert counts["SlabCount"] == 1
        assert counts["WallCount"] == 2  # wall_bc, wall_far

    def test_a_room_with_no_windows_counts_zero(self, linker, named):
        counts = linker.space_counts(named["Kitchen"].GlobalId)["counts"]
        assert counts["WindowCount"] == 0

    def test_a_room_nothing_was_ever_linked_to_is_unknown_not_zero(self, model):
        attic = model.create_entity(
            "IfcSpace", GlobalId=new_guid(), Name="Attic", LongName="Attic"
        )
        adjacency = IFCSpatialAdjacency(model, fallback_to_geometric=False).build()
        linker = ElementRoomLinker(adjacency, model)
        try:
            assert linker.space_counts(attic.GlobalId) is None
        finally:
            model.remove(attic)

    def test_a_count_of_zero_is_qualified_by_how_much_of_the_class_is_linked(self, linker, named):
        room = room_context(named["Kitchen"], linker, include_counts=True)
        value, detail = room_derived_value("windowcount", room)
        assert value == 0
        # 1 of the model's 2 windows is linked to any room at all.
        assert any("1 of 2 windows" in w for w in detail["warnings"])

    def test_a_fully_linked_class_carries_no_warning(self, linker, named):
        room = room_context(named["Kitchen"], linker, include_counts=True)
        _, detail = room_derived_value("slabcount", room)
        assert detail["warnings"] == []

    def test_count_of_an_unresolvable_room_is_none(self):
        assert room_derived_value("windowcount", {"space_counts": None}) == (None, {})


# ── Reader + comparator end to end ────────────────────────────────────────────


@pytest.fixture(scope="module")
def house_path(model, tmp_path_factory) -> Path:
    path = tmp_path_factory.mktemp("house") / "house.ifc"
    model.write(str(path))
    return path


def _evaluate(house_path: Path, rule: dict) -> tuple[dict, dict]:
    """Run one rule through Module 2 then Module 4; return (extraction, result)."""
    extraction = IFCReader(house_path).extract_for_compliance([rule])
    return extraction[0], ComplianceComparator().validate_metadata(extraction)[0]


def _by_name(result: dict) -> dict:
    return {e["element_name"]: e for e in result["all_elements"]}


BEDROOM_DOOR_RULE = {
    "reference": "ROOM-E2E.01",
    "description": "Bedroom doors are at least 800 mm wide",
    "target_ifc_class": "IfcDoor",
    "property_set": "Pset_Test",
    "property_name": "WidthMM",
    "operator": ">=",
    "check_value": 800,
    "unit": "mm",
    "applies_when": {"room_type_any_of": ["bedroom"]},
}


@pytest.fixture(scope="module")
def outcome(house_path):
    """Evaluate the bedroom-door rule once for the whole module."""
    return _evaluate(house_path, BEDROOM_DOOR_RULE)


class TestBedroomDoorsEndToEnd:
    """Bedroom doors must be 800 mm wide.

    Every door here is 700 mm, so the verdict for each one is decided entirely
    by whether it is in scope.
    """

    def test_authored_bedroom_door_is_measured_and_fails(self, outcome):
        assert _by_name(outcome[1])["door_bc"]["status"] == "FAIL"

    def test_door_inherited_from_a_bedroom_wall_is_measured_and_fails(self, outcome):
        assert _by_name(outcome[1])["door_host"]["status"] == "FAIL"

    def test_kitchen_door_is_out_of_scope(self, outcome):
        entry = _by_name(outcome[1])["door_kc"]
        assert entry["status"] == "NOT_APPLICABLE"

    def test_door_contained_in_the_kitchen_is_out_of_scope(self, outcome):
        assert _by_name(outcome[1])["door_in_kitchen"]["status"] == "NOT_APPLICABLE"

    def test_door_to_an_untyped_room_stays_in_scope(self, outcome):
        # The Nook could be a bedroom, so the door is checked, not skipped.
        assert _by_name(outcome[1])["door_nc"]["status"] == "FAIL"

    def test_unlinked_doors_stay_in_scope(self, outcome):
        by_name = _by_name(outcome[1])
        assert by_name["door_orphan"]["status"] == "FAIL"
        assert by_name["door_far"]["status"] == "FAIL"

    def test_undetermined_scope_is_reported_not_swallowed(self, outcome):
        notes = outcome[1]["undetermined_predicates"]
        assert any("could not be typed" in n for n in notes)
        assert any("no room could be linked" in n for n in notes)

    def test_findings_name_the_rooms_and_how_they_were_linked(self, outcome):
        failure = next(f for f in outcome[1]["failures"] if f["element_name"] == "door_bc")
        assert sorted(failure["connected_rooms"]) == ["Bedroom 1", "Hallway"]
        assert failure["room_link_source"] == SOURCE_BOUNDARY

    def test_element_record_carries_room_types_for_the_comparator(self, outcome):
        door = next(e for e in outcome[0]["elements"] if e["name"] == "door_bc")
        assert sorted(door["connected_room_types"]) == ["bedroom", "corridor"]


class TestOtherClassesAndTheInverseRule:
    def test_window_scoped_by_room(self, house_path):
        rule = {
            **BEDROOM_DOOR_RULE,
            "reference": "ROOM-E2E.02",
            "target_ifc_class": "IfcWindow",
            "check_value": 1000,
        }
        _, result = _evaluate(house_path, rule)
        by_name = _by_name(result)
        assert by_name["win_bed"]["status"] == "FAIL"  # in a bedroom, 900 < 1000
        # win_orphan has no room evidence, so it is checked and flagged.
        assert by_name["win_orphan"]["status"] == "FAIL"

    def test_kitchen_must_have_a_window(self, house_path):
        rule = {
            "reference": "ROOM-E2E.03",
            "description": "Every kitchen has at least one window",
            "target_ifc_class": "IfcSpace",
            "property_name": "WindowCount",
            "operator": ">=",
            "check_value": 1,
            "applies_when": {"room_type_any_of": ["kitchen"]},
        }
        _, result = _evaluate(house_path, rule)
        by_name = _by_name(result)

        assert by_name["Kitchen"]["status"] == "FAIL"
        assert by_name["Kitchen"]["actual"] == 0
        # A bedroom is not a kitchen: out of scope, whatever its window count.
        assert by_name["Bedroom 1"]["status"] == "NOT_APPLICABLE"
        assert by_name["Hallway"]["status"] == "NOT_APPLICABLE"

    def test_a_room_count_carries_its_own_link_provenance(self, house_path):
        rule = {
            "reference": "ROOM-E2E.04",
            "description": "Bedrooms have a window",
            "target_ifc_class": "IfcSpace",
            "property_name": "WindowCount",
            "operator": ">=",
            "check_value": 1,
            "applies_when": {"room_type_any_of": ["bedroom"]},
        }
        extraction, result = _evaluate(house_path, rule)
        assert _by_name(result)["Bedroom 1"]["status"] == "PASS"
        assert _by_name(result)["Bedroom 1"]["room_link_source"] == SOURCE_SELF

    def test_connected_spaces_property_now_resolves_for_a_wall(self, house_path):
        rule = {
            "reference": "ROOM-E2E.05",
            "description": "Walls report the rooms they bound",
            "target_ifc_class": "IfcWall",
            "property_name": "ConnectedSpaces",
            "operator": "exists",
        }
        _, result = _evaluate(house_path, rule)
        by_name = _by_name(result)
        assert by_name["wall_bc"]["status"] == "PASS"
        assert "Bedroom 1" in by_name["wall_bc"]["actual"]

    def test_room_type_property_resolves_for_a_door(self, house_path):
        rule = {
            "reference": "ROOM-E2E.06",
            "description": "Doors report their room types",
            "target_ifc_class": "IfcDoor",
            "property_name": "ConnectedRoomTypes",
            "operator": "exists",
        }
        _, result = _evaluate(house_path, rule)
        by_name = _by_name(result)
        assert "bedroom" in by_name["door_bc"]["actual"]
        # No evidence, no value: missing data, never an empty pass.
        assert by_name["door_orphan"]["status"] == "FAIL"


class TestNoRegression:
    def test_rules_that_ask_about_no_room_resolve_no_room_data(self, house_path):
        rule = {
            "reference": "ROOM-E2E.07",
            "description": "Plain door width",
            "target_ifc_class": "IfcDoor",
            "property_set": "Pset_Test",
            "property_name": "WidthMM",
            "operator": ">=",
            "check_value": 800,
        }
        extraction, result = _evaluate(house_path, rule)
        for element in extraction["elements"]:
            assert element["connected_rooms"] is None
            assert element["connected_room_types"] is None
        # Every door is 700 mm and nothing scoped any of them out.
        assert result["fail_count"] == len(extraction["elements"])
        assert result["not_applicable_count"] == 0


# ── Room names: kept as written, typos reported, any name accepted ────────────


def _build_typo_house() -> ifcopenshell.file:
    """Build a house whose rooms carry misspelt and custom names, as authored.

    Two rooms are both called "BADROOM 1" (a repeated flat), one "BADROOM 2",
    one is the perfectly ordinary but unlisted "WAITING", one a plain "Kitchen".
    """
    model = ifcopenshell.file(schema="IFC4")
    project = run("root.create_entity", model, ifc_class="IfcProject", name="Typos")
    run("unit.assign_unit", model)
    site = run("root.create_entity", model, ifc_class="IfcSite", name="Site")
    building = run("root.create_entity", model, ifc_class="IfcBuilding", name="Building")
    storey = run("root.create_entity", model, ifc_class="IfcBuildingStorey", name="L01")
    run("aggregate.assign_object", model, products=[site], relating_object=project)
    run("aggregate.assign_object", model, products=[building], relating_object=site)
    run("aggregate.assign_object", model, products=[storey], relating_object=building)

    def space(long_name: str):
        entity = run("root.create_entity", model, ifc_class="IfcSpace", name=long_name)
        entity.LongName = long_name
        run("aggregate.assign_object", model, products=[entity], relating_object=storey)
        return entity

    bad1_a, bad1_b, bad2 = space("BADROOM 1"), space("BADROOM 1"), space("BADROOM 2")
    waiting, kitchen = space("WAITING"), space("Kitchen")

    doors = []
    for door_name, room in [
        ("door_a", bad1_a),
        ("door_b", bad1_b),
        ("door_c", bad2),
        ("door_w", waiting),
    ]:
        door = run("root.create_entity", model, ifc_class="IfcDoor", name=door_name)
        pset = run("pset.add_pset", model, product=door, name="Pset_Test")
        run("pset.edit_pset", model, pset=pset, properties={"WidthMM": 700})
        doors.append(door)
        _boundary(model, room, door)
        _boundary(model, kitchen, door)
    run("spatial.assign_container", model, products=doors, relating_structure=storey)
    return model


@pytest.fixture(scope="module")
def typo_path(tmp_path_factory) -> Path:
    path = tmp_path_factory.mktemp("typos") / "typos.ifc"
    _build_typo_house().write(str(path))
    return path


@pytest.fixture(scope="module")
def typo_index(typo_path):
    return RoomIndex(ifcopenshell.open(str(typo_path)))


class TestRoomNamesAreKeptAsWritten:
    def test_names_come_through_verbatim(self, typo_index):
        assert sorted(r.name for r in typo_index.all()) == [
            "BADROOM 1",
            "BADROOM 1",
            "BADROOM 2",
            "Kitchen",
            "WAITING",
        ]

    def test_a_misspelling_is_not_read_as_the_type_it_resembles(self, typo_index):
        typos = [r for r in typo_index.all() if r.name.startswith("BADROOM")]
        assert all(r.types == (UNKNOWN_ROOM_TYPE,) for r in typos)

    def test_any_name_is_accepted_without_complaint(self, typo_index):
        waiting = next(r for r in typo_index.all() if r.name == "WAITING")
        assert waiting.suggestion is None  # a real name, nothing to correct
        assert waiting.name == "WAITING"


class TestTypoWarnings:
    def test_identical_names_are_reported_once_with_their_count(self, typo_index):
        groups = {g["room_name"]: g for g in typo_index.typo_groups()}
        assert set(groups) == {"BADROOM 1", "BADROOM 2"}
        assert groups["BADROOM 1"]["count"] == 2
        assert groups["BADROOM 1"]["suggested_name"] == "BEDROOM 1"
        assert groups["BADROOM 2"]["suggested_name"] == "BEDROOM 2"

    def test_the_message_names_the_typo_the_fix_and_that_nothing_was_changed(self, typo_index):
        messages = typo_index.warning_messages()
        assert len(messages) == 2
        first = messages[0]  # most rooms first
        assert "'BADROOM 1' (2 rooms: #" in first  # small groups list each room's id
        assert "misspelling of 'bedroom'" in first
        assert "Suggested name: 'BEDROOM 1'" in first
        assert "left as written" in first

    def test_a_single_room_is_not_pluralised(self, typo_index):
        message = typo_index.warning_messages()[1]
        assert "'BADROOM 2' [#" in message  # a lone room is identified by its id
        assert "rooms" not in message.split("looks like")[0]

    def test_a_model_with_no_typos_has_no_warnings(self, model):
        assert RoomIndex(model).warning_messages() == []


class TestRuleScopeMissWarnings:
    def test_a_type_the_model_only_has_misspelt_points_at_the_misspellings(self, typo_index):
        (message,) = typo_index.scope_miss_warnings({"room_type_any_of": ["bedroom"]})
        assert "no room in this model matches" in message
        assert "look like misspellings of 'bedroom'" in message
        assert "'BADROOM 1' (2 rooms) -> 'BEDROOM 1'" in message
        assert "'BADROOM 2' (1 room) -> 'BEDROOM 2'" in message

    def test_a_mistyped_rule_label_offers_did_you_mean(self, typo_index):
        (message,) = typo_index.scope_miss_warnings({"room_type_any_of": ["bedrom"]})
        assert "Did you mean: 'bedroom'" in message
        assert "Room types found in this model: kitchen." in message
        assert "'WAITING'" in message  # what the model does have

    def test_a_mistyped_room_name_offers_the_models_own_spelling(self, typo_index):
        (message,) = typo_index.scope_miss_warnings({"room_name_any_of": ["waitng"]})
        assert "'WAITING'" in message

    def test_a_label_the_model_has_produces_no_warning(self, typo_index):
        assert typo_index.scope_miss_warnings({"room_type_any_of": ["kitchen"]}) == []
        # ...including a custom one, matched by name.
        assert typo_index.scope_miss_warnings({"room_type_any_of": ["waiting"]}) == []
        assert typo_index.scope_miss_warnings({"room_name_any_of": ["BADROOM"]}) == []

    def test_none_of_is_satisfied_by_an_absent_room_so_it_never_warns(self, typo_index):
        assert typo_index.scope_miss_warnings({"room_type_none_of": ["sauna"]}) == []

    def test_each_missing_label_is_reported_separately(self, typo_index):
        messages = typo_index.scope_miss_warnings({"room_type_any_of": ["bedroom", "sauna"]})
        assert len(messages) == 2

    def test_no_scope_no_warnings(self, typo_index):
        assert typo_index.scope_miss_warnings({}) == []
        assert typo_index.scope_miss_warnings(None) == []


class TestWarningsReachTheUser:
    """Through the reader: model level, per rule, and per element."""

    def test_the_model_level_warnings_join_the_ifc_quality_warnings(self, typo_path):
        reader = IFCReader(typo_path)
        joined = " ".join(reader.quality_warnings)
        assert "'BADROOM 1' (2 rooms: #" in joined
        assert "Suggested name: 'BEDROOM 1'" in joined

    def test_a_rule_naming_a_room_the_model_lacks_carries_the_explanation(self, typo_path):
        rule = {**BEDROOM_DOOR_RULE, "reference": "ROOM-T.01"}
        extraction = IFCReader(typo_path).extract_for_compliance([rule])
        result = ComplianceComparator().validate_metadata(extraction)[0]
        assert len(result["scope_warnings"]) == 1
        assert "misspellings of 'bedroom'" in result["scope_warnings"][0]

    def test_each_element_flags_the_typo_in_its_own_rooms(self, typo_path):
        rule = {**BEDROOM_DOOR_RULE, "reference": "ROOM-T.02"}
        extraction = IFCReader(typo_path).extract_for_compliance([rule])
        door = next(e for e in extraction[0]["elements"] if e["name"] == "door_c")
        assert any("'BADROOM 2'" in w and "BEDROOM 2" in w for w in door["data_quality_warnings"])
        # The room is shown exactly as the model spells it.
        assert "BADROOM 2" in door["connected_rooms"]

    def test_a_typo_room_stays_in_scope_rather_than_being_dropped(self, typo_path):
        rule = {**BEDROOM_DOOR_RULE, "reference": "ROOM-T.03"}
        extraction = IFCReader(typo_path).extract_for_compliance([rule])
        result = ComplianceComparator().validate_metadata(extraction)[0]
        by_name = _by_name(result)
        for door in ("door_a", "door_b", "door_c"):
            assert by_name[door]["status"] == "FAIL"
            assert by_name[door]["scope_undetermined"]

    def test_a_rule_can_name_any_room_the_model_carries(self, typo_path):
        rule = {
            **BEDROOM_DOOR_RULE,
            "reference": "ROOM-T.04",
            "description": "Doors to the waiting room are at least 800 mm wide",
            "applies_when": {"room_type_any_of": ["waiting"]},
        }
        extraction = IFCReader(typo_path).extract_for_compliance([rule])
        result = ComplianceComparator().validate_metadata(extraction)[0]
        by_name = _by_name(result)

        assert by_name["door_w"]["status"] == "FAIL"  # measured: it IS the waiting room's door
        for other in ("door_a", "door_b", "door_c"):
            assert by_name[other]["status"] == "NOT_APPLICABLE"  # decided by name, no guessing
        assert result["scope_warnings"] == []  # the model has a WAITING room


# ── Unique room ids: telling identically-named rooms apart ────────────────────


class TestUniqueShortIds:
    """Two flats each have a "BADROOM 1"; a finding must say WHICH one."""

    def test_ids_are_the_tail_of_the_guid_and_at_least_four_characters(self):
        ids = unique_short_ids(["0OirwS9nPC0Q_Xf_oVuY8A", "2DPVKuGSTB8ghY4kRhSoJ5"])
        assert ids == {"0OirwS9nPC0Q_Xf_oVuY8A": "uY8A", "2DPVKuGSTB8ghY4kRhSoJ5": "SoJ5"}

    def test_ids_are_unique_even_when_the_tails_collide(self):
        # Same last four characters: the id grows until they differ.
        ids = unique_short_ids(["aaaaAAAA1234", "bbbbBBBB1234", "cccccccc9999"])
        assert len(set(ids.values())) == 3
        assert len({len(v) for v in ids.values()}) == 1  # one uniform length

    def test_a_single_room_still_gets_the_minimum_length(self):
        assert unique_short_ids(["0OirwS9nPC0Q_Xf_oVuY8A"]) == {"0OirwS9nPC0Q_Xf_oVuY8A": "uY8A"}

    def test_no_rooms_no_ids(self):
        assert unique_short_ids([]) == {}

    def test_every_room_in_a_model_gets_a_distinct_id(self, typo_index):
        ids = [r.short_id for r in typo_index.all()]
        assert all(ids)
        assert len(set(ids)) == len(ids)

    def test_two_rooms_with_the_same_name_are_told_apart(self, typo_index):
        twins = [r for r in typo_index.all() if r.name == "BADROOM 1"]
        assert len(twins) == 2
        assert twins[0].label != twins[1].label
        assert twins[0].short_id != twins[1].short_id

    def test_the_label_keeps_the_name_exactly_as_written(self, typo_index):
        for room in typo_index.all():
            assert room.label == f"{room.name} [#{room.short_id}]"
            assert room.label.startswith(room.name)

    def test_the_short_id_is_the_end_of_the_real_guid(self, typo_index):
        for room in typo_index.all():
            assert room.guid.endswith(room.short_id)


class TestRoomIdsReachTheFindings:
    def test_a_finding_lists_each_connected_room_with_its_id(self, typo_path):
        rule = {**BEDROOM_DOOR_RULE, "reference": "ROOM-ID.01"}
        extraction = IFCReader(typo_path).extract_for_compliance([rule])
        result = ComplianceComparator().validate_metadata(extraction)[0]
        by_name = _by_name(result)

        labels_a = by_name["door_a"]["connected_room_labels"]
        labels_b = by_name["door_b"]["connected_room_labels"]
        # door_a and door_b each open onto a room called "BADROOM 1" -- the
        # labels differ, so the two findings do not read as the same room.
        assert any(lbl.startswith("BADROOM 1 [#") for lbl in labels_a)
        assert any(lbl.startswith("BADROOM 1 [#") for lbl in labels_b)
        assert labels_a != labels_b

    def test_the_full_ids_are_the_ifc_guids_of_those_rooms(self, typo_path):
        rule = {**BEDROOM_DOOR_RULE, "reference": "ROOM-ID.02"}
        extraction = IFCReader(typo_path).extract_for_compliance([rule])
        result = ComplianceComparator().validate_metadata(extraction)[0]
        entry = _by_name(result)["door_a"]

        model = ifcopenshell.open(str(typo_path))
        real_guids = {s.GlobalId for s in model.by_type("IfcSpace")}
        assert entry["connected_room_ids"]
        assert set(entry["connected_room_ids"]) <= real_guids
        # names and ids line up one to one
        assert len(entry["connected_room_ids"]) == len(entry["connected_rooms"])

    def test_names_used_for_matching_stay_plain(self, typo_path):
        # The label is for display. Matching still runs on the bare name, so an
        # id can never make a rule match (or miss) a room.
        rule = {**BEDROOM_DOOR_RULE, "reference": "ROOM-ID.03", "applies_when": {"room_name_any_of": ["#"]}}
        extraction = IFCReader(typo_path).extract_for_compliance([rule])
        result = ComplianceComparator().validate_metadata(extraction)[0]
        assert all(e["status"] == "NOT_APPLICABLE" for e in result["all_elements"])
        assert not any("[#" in name for e in extraction[0]["elements"] for name in e["connected_rooms"])

    def test_the_typo_warning_on_an_element_names_the_room_by_id(self, typo_path):
        rule = {**BEDROOM_DOOR_RULE, "reference": "ROOM-ID.04"}
        extraction = IFCReader(typo_path).extract_for_compliance([rule])
        door = next(e for e in extraction[0]["elements"] if e["name"] == "door_c")
        (warning,) = [w for w in door["data_quality_warnings"] if "BADROOM 2" in w]
        guid = door["connected_room_ids"][door["connected_rooms"].index("BADROOM 2")]
        assert f"[#{guid[-4:]}" in warning

    def test_a_room_target_carries_its_own_label(self, typo_path):
        rule = {
            "reference": "ROOM-ID.05",
            "description": "Every room has a door",
            "target_ifc_class": "IfcSpace",
            "property_name": "DoorCount",
            "operator": ">=",
            "check_value": 1,
        }
        extraction = IFCReader(typo_path).extract_for_compliance([rule])
        result = ComplianceComparator().validate_metadata(extraction)[0]
        labels = [e["connected_room_labels"][0] for e in result["all_elements"]]
        assert len(labels) == len(set(labels)) == 5  # five rooms, five distinct labels
