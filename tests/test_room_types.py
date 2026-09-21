"""Room-type classification of IfcSpace names.

The names below are taken from the sample models in the repo (a residential
house, a two-storey apartment block, an outpatient clinic), so the vocabulary is
exercised on what authors actually type rather than on tidy examples.
"""

from __future__ import annotations

import pytest

from app.modules.room_types import (
    ROOM_SCOPE_KEYS,
    ROOM_TYPES,
    UNKNOWN_ROOM_TYPE,
    classify_room,
    classify_room_text,
    closest_room_types,
    name_mentions,
    suggest_name_correction,
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

    def test_a_misspelling_is_not_silently_read_as_the_room_it_resembles(self):
        # The model's wording is the author's. A near-miss is reported (see
        # TestNameCorrectionSuggestions), not quietly reinterpreted.
        assert classify_room_text("BADROOM 2") == []

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


class TestNameCorrectionSuggestions:
    """Report a name the vocabulary cannot read as a possible typo.

    It is reported with a proposed fix; the name itself is never changed.
    """

    def test_a_misspelt_room_word_gets_a_suggestion(self):
        suggestion = suggest_name_correction("BADROOM 1")
        assert suggestion is not None
        assert suggestion.found == "BADROOM"
        assert suggestion.keyword == "bedroom"
        assert suggestion.room_type == "bedroom"
        assert suggestion.suggested_name == "BEDROOM 1"

    @pytest.mark.parametrize(
        ("name", "expected"),
        [
            ("Badroom 2", "Bedroom 2"),
            ("KITCHN", "KITCHEN"),
            ("Livng Room", "Living Room"),
            ("Bathrom 1", "Bathroom 1"),
            ("Dinning Room", "Dining Room"),
            ("Hallwya", "Hallway"),
            ("Toilt", "Toilet"),
        ],
    )
    def test_only_the_misspelt_word_changes_and_its_case_is_kept(self, name, expected):
        assert suggest_name_correction(name).suggested_name == expected

    def test_a_typed_plural_stays_plural(self):
        assert suggest_name_correction("Badrooms").suggested_name == "Bedrooms"

    def test_the_rest_of_the_name_is_left_exactly_as_written(self):
        suggestion = suggest_name_correction("L2 - Badroom (north) #3")
        assert suggestion.suggested_name == "L2 - Bedroom (north) #3"

    @pytest.mark.parametrize(
        "name",
        [
            "Bedroom 1",  # understood already
            "Nook",  # a real name, nothing resembles it
            "WAITING",
            "RECEPTION",
            "JAN. CL.",
            "OPT. EXAM / OFF.",
            "Studio",
            "LAB",  # too short to judge
            "104",
            "",
            None,
        ],
    )
    def test_names_that_are_merely_unfamiliar_get_no_suggestion(self, name):
        assert suggest_name_correction(name) is None

    def test_the_suggestion_does_not_alter_classification(self):
        assert classify_room_text("BADROOM 1") == []

    def test_a_custom_vocabulary_is_used_for_suggestions_too(self):
        suggestion = suggest_name_correction("Saunna", {"wellness": ["sauna"]})
        assert suggestion.suggested_name == "Sauna"
        assert suggestion.room_type == "wellness"

    def test_did_you_mean_for_a_mistyped_rule_label(self):
        assert closest_room_types("bedrom") == ["bedroom"]
        assert closest_room_types("kichen") == ["kitchen"]
        assert closest_room_types("sauna") == []


class TestOpenToAnyRoomName:
    """The vocabulary is a convenience, not a limit."""

    def test_a_label_outside_the_vocabulary_matches_a_room_by_name(self):
        assert "waiting" not in ROOM_TYPES
        assert name_mentions("CENTRAL WAITING", "waiting")
        assert name_mentions("Waiting / Activity Area", "waiting")

    def test_matching_is_by_whole_word_not_substring(self):
        assert not name_mentions("Table Room", "lab")
        assert name_mentions("Dental Lab", "lab")

    def test_multi_word_labels_and_plurals(self):
        assert name_mentions("PROVIDER CUBICLES", "provider cubicle")
        assert name_mentions("Staff Lounges", "staff lounge")

    def test_case_and_punctuation_are_ignored(self):
        assert name_mentions("OPT. EXAM / OFF.", "exam")

    @pytest.mark.parametrize("phrase", ["", None, "  "])
    def test_an_empty_label_matches_nothing(self, phrase):
        assert not name_mentions("Kitchen", phrase)


def test_scope_keys_are_the_documented_four():
    assert ROOM_SCOPE_KEYS == {
        "room_type_any_of",
        "room_type_all_of",
        "room_type_none_of",
        "room_name_any_of",
    }
