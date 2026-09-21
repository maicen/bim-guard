"""Room-scope predicates in ComplianceComparator.

``applies_when`` can scope a rule by the rooms an element connects to
(``room_type_any_of`` and friends). An element can bound several rooms and a room
can be of a type nobody could identify, so every predicate is three-valued:

* MATCH / NO_MATCH when the known rooms settle the question;
* UNDETERMINED when an untyped room (or a missing link) leaves it open.

UNDETERMINED keeps the element IN scope (a scope gate must never silently
suppress a check) and is reported on the result rather than discarded.
"""

from __future__ import annotations

import pytest

from app.modules.comparator import (
    MATCH,
    NO_MATCH,
    UNDETERMINED,
    ComplianceComparator,
)
from app.modules.room_types import UNKNOWN_ROOM_TYPE


def _door(name: str, width, types, rooms=None, **extra) -> dict:
    """Build a Module 2 element record for a door with resolved room links."""
    element = {
        "guid": f"guid-{name}",
        "name": name,
        "actual_value": width,
        "found": width is not None,
        "storey": "L01",
        "space": None,
        "materials": [],
        "scope_values": {},
        "connected_room_types": types,
        "connected_rooms": rooms,
    }
    element.update(extra)
    return element


def _rule(elements, applies_when, **extra) -> dict:
    item = {
        "rule_ref": "ROOM-001",
        "rule_desc": "Bedroom doors at least 800 mm",
        "target_ifc_class": "IfcDoor",
        "property_name": "Width",
        "operator": ">=",
        "check_value": 800.0,
        "unit": "mm",
        "applies_when": applies_when,
        "elements": elements,
    }
    item.update(extra)
    return item


def _predicate(key, expected, element) -> str:
    outcome, _ = ComplianceComparator._predicate_key(key, expected, element)
    return outcome


class TestRoomTypeAnyOf:
    def test_matches_when_one_connected_room_is_of_the_type(self):
        door = _door("d", 700, ["bedroom", "corridor"])
        assert _predicate("room_type_any_of", ["bedroom"], door) == MATCH

    def test_no_match_when_every_room_is_typed_and_none_qualifies(self):
        door = _door("d", 700, ["kitchen", "corridor"])
        assert _predicate("room_type_any_of", ["bedroom"], door) == NO_MATCH

    def test_untyped_room_leaves_it_undetermined(self):
        # The corridor is known, but the other room might be a bedroom.
        door = _door("d", 700, ["corridor", UNKNOWN_ROOM_TYPE])
        assert _predicate("room_type_any_of", ["bedroom"], door) == UNDETERMINED

    def test_a_known_match_wins_over_an_untyped_room(self):
        door = _door("d", 700, ["bedroom", UNKNOWN_ROOM_TYPE])
        assert _predicate("room_type_any_of", ["bedroom"], door) == MATCH

    def test_any_of_several_listed_types(self):
        door = _door("d", 700, ["kitchen"])
        assert _predicate("room_type_any_of", ["bedroom", "kitchen"], door) == MATCH

    def test_accepts_a_bare_string_and_ignores_case(self):
        door = _door("d", 700, ["bedroom"])
        assert _predicate("room_type_any_of", "  Bedroom ", door) == MATCH


class TestRoomTypeAllOf:
    def test_matches_when_every_listed_type_is_present(self):
        door = _door("d", 700, ["bedroom", "bathroom"])
        assert _predicate("room_type_all_of", ["bedroom", "bathroom"], door) == MATCH

    def test_no_match_when_a_type_is_missing_and_all_rooms_are_typed(self):
        door = _door("d", 700, ["bedroom", "corridor"])
        assert _predicate("room_type_all_of", ["bedroom", "bathroom"], door) == NO_MATCH

    def test_untyped_room_could_be_the_missing_type(self):
        door = _door("d", 700, ["bedroom", UNKNOWN_ROOM_TYPE])
        assert _predicate("room_type_all_of", ["bedroom", "bathroom"], door) == UNDETERMINED


class TestRoomTypeNoneOf:
    def test_matches_when_no_connected_room_is_excluded(self):
        door = _door("d", 700, ["corridor", "kitchen"])
        assert _predicate("room_type_none_of", ["bedroom"], door) == MATCH

    def test_no_match_when_an_excluded_type_is_present(self):
        door = _door("d", 700, ["corridor", "bedroom"])
        assert _predicate("room_type_none_of", ["bedroom"], door) == NO_MATCH

    def test_untyped_room_cannot_be_ruled_out(self):
        door = _door("d", 700, ["corridor", UNKNOWN_ROOM_TYPE])
        assert _predicate("room_type_none_of", ["bedroom"], door) == UNDETERMINED

    def test_a_known_excluded_type_beats_an_untyped_room(self):
        door = _door("d", 700, ["bedroom", UNKNOWN_ROOM_TYPE])
        assert _predicate("room_type_none_of", ["bedroom"], door) == NO_MATCH


class TestRoomNameAnyOf:
    def test_matches_on_a_substring_of_a_room_name(self):
        door = _door("d", 700, ["bedroom"], rooms=["Primary Bedroom", "Hallway"])
        assert _predicate("room_name_any_of", ["primary"], door) == MATCH

    def test_no_match_when_no_name_contains_the_text(self):
        door = _door("d", 700, ["bedroom"], rooms=["Bedroom 2", "Hallway"])
        assert _predicate("room_name_any_of", ["primary"], door) == NO_MATCH


class TestUnresolvedLinks:
    """No links is not the same claim as "touches no room"."""

    @pytest.mark.parametrize(
        "key",
        ["room_type_any_of", "room_type_all_of", "room_type_none_of", "room_name_any_of"],
    )
    def test_every_room_predicate_is_undetermined_without_links(self, key):
        door = _door("d", 700, None, rooms=None)
        assert _predicate(key, ["bedroom"], door) == UNDETERMINED

    def test_the_reason_recorded_at_extraction_is_reported(self):
        door = _door(
            "d", 700, None, room_link_note="room links were only inferred from bounding-box contact"
        )
        _, detail = ComplianceComparator._predicate_key("room_type_any_of", ["bedroom"], door)
        assert "bounding-box contact" in detail

    def test_an_empty_list_of_rooms_never_narrows_scope(self):
        door = _door("d", 700, ["bedroom"])
        assert _predicate("room_type_any_of", [], door) == UNDETERMINED


class TestRuleLevelScoping:
    """The predicates through the whole rule evaluation."""

    def test_only_bedroom_doors_are_measured(self):
        bedroom = _door("bedroom-door", 700, ["bedroom", "corridor"])
        kitchen = _door("kitchen-door", 700, ["kitchen", "corridor"])

        result = ComplianceComparator().validate_metadata(
            [_rule([bedroom, kitchen], {"room_type_any_of": ["bedroom"]})]
        )[0]

        assert result["status"] == "FAIL"
        assert result["fail_count"] == 1
        assert result["not_applicable_count"] == 1
        assert [f["element_name"] for f in result["failures"]] == ["bedroom-door"]

    def test_out_of_scope_door_passes_no_check_it_was_never_subject_to(self):
        kitchen = _door("kitchen-door", 700, ["kitchen", "corridor"])
        result = ComplianceComparator().validate_metadata(
            [_rule([kitchen], {"room_type_any_of": ["bedroom"]})]
        )[0]
        assert result["status"] == "NOT_APPLICABLE"

    def test_undetermined_door_stays_in_scope_and_is_flagged(self):
        # A door whose rooms could not be resolved must still be checked.
        unlinked = _door("orphan-door", 700, None)
        result = ComplianceComparator().validate_metadata(
            [_rule([unlinked], {"room_type_any_of": ["bedroom"]})]
        )[0]

        assert result["status"] == "FAIL"
        assert result["fail_count"] == 1
        assert any(
            "room_type_any_of" in note for note in result["undetermined_predicates"]
        )

    def test_each_finding_says_whether_its_scope_was_actually_decided(self):
        # Two doors fail the same 800 mm check. One is known to be in a
        # bedroom; the other only MIGHT be, because a room is untyped. Both are
        # checked, but a reviewer must be able to tell them apart.
        known = _door("known-bedroom", 700, ["bedroom"])
        uncertain = _door("maybe-bedroom", 700, ["corridor", UNKNOWN_ROOM_TYPE])

        result = ComplianceComparator().validate_metadata(
            [_rule([known, uncertain], {"room_type_any_of": ["bedroom"]})]
        )[0]

        entries = {e["element_name"]: e for e in result["all_elements"]}
        assert entries["known-bedroom"]["scope_undetermined"] is None
        assert entries["maybe-bedroom"]["scope_undetermined"] == [
            "room_type_any_of: a connected room could not be typed"
        ]
        failures = {f["element_name"]: f for f in result["failures"]}
        assert failures["known-bedroom"]["scope_undetermined"] is None
        assert failures["maybe-bedroom"]["scope_undetermined"]

    def test_a_rule_with_no_scope_marks_nothing_undetermined(self):
        result = ComplianceComparator().validate_metadata(
            [_rule([_door("d", 700, ["bedroom"])], {})]
        )[0]
        assert result["all_elements"][0]["scope_undetermined"] is None

    def test_scope_combines_with_other_predicates(self):
        # AND across keys: in a bedroom AND on storey L02 (the door is on L01).
        door = _door("d", 700, ["bedroom"])
        result = ComplianceComparator().validate_metadata(
            [_rule([door], {"room_type_any_of": ["bedroom"], "storey_any_of": ["L02"]})]
        )[0]
        assert result["status"] == "NOT_APPLICABLE"

    def test_a_room_predicate_can_waive_a_failure(self):
        # An exemption stated in room terms: closets are exempt.
        closet = _door("closet-door", 600, ["closet"])
        rule = _rule(
            [closet],
            {},
            exceptions=[
                {
                    "reference": "EXEMPT-CLOSET",
                    "label": "Closet doors are exempt",
                    "predicate": {"room_type_any_of": ["closet"]},
                }
            ],
        )
        result = ComplianceComparator().validate_metadata([rule])[0]
        assert result["status"] == "WAIVED"
        assert result["waived_count"] == 1
