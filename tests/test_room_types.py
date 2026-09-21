"""Room-type classification of IfcSpace names.

The names below are taken from the sample models in the repo (a residential
house, a two-storey apartment block, an outpatient clinic), so the vocabulary is
exercised on what authors actually type rather than on tidy examples.
"""

from __future__ import annotations

import pytest

from app.modules.room_types import (
    ROOM_SCOPE_KEYS,
    UNKNOWN_ROOM_TYPE,
    classify_room,
    classify_room_text,
)


class TestSingleNames:
    @pytest.mark.parametrize(
        ("name", "expected"),
        [
            ("Bedroom 1", ["bedroom"]),
            ("Primary Bedroom", ["bedroom"]),
            ("Kitchen", ["kitchen"]),
            ("Hallway", ["corridor"]),
            ("LIVING ROOM", ["living"]),
            ("Great Room", ["living"]),
            ("Bathroom 1", ["bathroom"]),
            ("Primary Walk-in Closet", ["closet"]),
            ("Dining", ["dining"]),
            ("STAIR", ["stair"]),
            ("TRICARE OFFICE", ["office"]),
        ],
    )
    def test_real_names(self, name, expected):
        assert classify_room_text(name) == expected

    def test_dotted_abbreviation(self):
        assert classify_room_text("W.C.") == ["toilet"]

    def test_misspelling_seen_in_the_reference_model(self):
        assert classify_room_text("BADROOM 2") == ["bedroom"]

    def test_plural(self):
        assert classify_room_text("Bedrooms") == ["bedroom"]
        assert classify_room_text("Stairs") == ["stair"]

    def test_digit_glued_to_the_word(self):
        assert classify_room_text("Bedroom1") == ["bedroom"]

    def test_case_and_punctuation_are_ignored(self):
        assert classify_room_text("KITCHEN!!") == ["kitchen"]
        assert classify_room_text("  (bed room)  ") == ["bedroom"]


class TestHeadNoun:
    """English puts the head noun last, so it decides the type."""

    def test_bedroom_closet_is_a_closet(self):
        assert classify_room_text("Bedroom Closet") == ["closet"]

    def test_master_bedroom_bathroom_is_a_bathroom(self):
        assert classify_room_text("Master Bedroom Bathroom") == ["bathroom"]

    def test_entry_hall_is_a_corridor_not_a_lobby(self):
        assert classify_room_text("Entry Hall") == ["corridor"]

    def test_longer_phrase_beats_shorter_one_ending_in_the_same_place(self):
        # "closet" alone is a closet; "water closet" is a toilet.
        assert classify_room_text("Water Closet") == ["toilet"]
        assert classify_room_text("Closet") == ["closet"]


class TestSeveralRoomsInOneName:
    @pytest.mark.parametrize(
        "name", ["Kitchen/Dining", "Kitchen & Dining", "Kitchen and Dining", "Kitchen, Dining"]
    )
    def test_each_segment_is_typed(self, name):
        assert classify_room_text(name) == ["kitchen", "dining"]

    def test_repeated_type_is_listed_once(self):
        assert classify_room_text("Bedroom / Guest Room") == ["bedroom"]

    def test_unknown_segment_does_not_hide_the_known_one(self):
        # "Laundry / Mud Room": the laundry is typed, the mud room is not.
        assert classify_room_text("Laundry / Mud Room") == ["laundry"]


class TestWholeWordMatching:
    def test_keyword_is_not_matched_inside_another_word(self):
        assert classify_room_text("Garden") == []  # "den"
        assert classify_room_text("Hidden Store") == ["storage"]  # not "den"

    def test_short_keyword_is_not_matched_inside_a_word(self):
        assert classify_room_text("Swcap") == []  # "wc"


class TestUnknown:
    @pytest.mark.parametrize("name", ["Nook", "WAITING", "104", "", None, "   "])
    def test_unmatched_text_yields_no_type(self, name):
        assert classify_room_text(name) == []

    def test_classify_room_reports_unknown_as_a_value_not_an_absence(self):
        types, source = classify_room([("Name", "Nook")])
        assert types == [UNKNOWN_ROOM_TYPE]
        assert source is None


class TestSourcePriority:
    def test_explicit_category_beats_the_name(self):
        types, source = classify_room(
            [
                ("Pset_SpaceCommon.Category", "Bedroom"),
                ("Name", "Kitchen"),
            ]
        )
        assert types == ["bedroom"]
        assert source == "Pset_SpaceCommon.Category"

    def test_falls_through_an_unhelpful_source(self):
        # A Revit room: the Name is the room number, the LongName is the label.
        types, source = classify_room(
            [("Pset_SpaceCommon.Category", None), ("LongName", "Kitchen"), ("Name", "104")]
        )
        assert types == ["kitchen"]
        assert source == "LongName"

    def test_a_category_that_matches_nothing_does_not_block_the_name(self):
        # Some exporters write the Revit category "Rooms" into Category.
        types, source = classify_room(
            [("Pset_SpaceCommon.Category", "Rooms"), ("Name", "Bedroom 2")]
        )
        assert types == ["bedroom"]
        assert source == "Name"


class TestCustomVocabulary:
    def test_keywords_can_be_overridden(self):
        assert classify_room_text("Sauna", {"wellness": ["sauna", "steam room"]}) == ["wellness"]
        # ...and the default vocabulary is not consulted when one is supplied.
        assert classify_room_text("Bedroom", {"wellness": ["sauna"]}) == []


def test_scope_keys_are_the_documented_four():
    assert ROOM_SCOPE_KEYS == {
        "room_type_any_of",
        "room_type_all_of",
        "room_type_none_of",
        "room_name_any_of",
    }
