"""Reliability grading of rules by the IFC property they read (high / medium / low)."""

from __future__ import annotations

import pytest

from app.modules import rule_reliability
from app.modules.contracts import RuleCreateRequest, RuleExtractionDraft, RuleResponse
from app.modules.rule_reliability import assess_property, assess_rule

#: Stand-in for the bSDD dictionary's property-set names, so these tests don't depend on the bundled data.
_KNOWN_PSETS = frozenset(
    {
        "pset_doorcommon",
        "pset_wallcommon",
        "pset_windowcommon",
        "pset_manufacturertypeinformation",
        "qto_doorbasequantities",
    }
)


@pytest.fixture(autouse=True)
def _fixed_dictionary(monkeypatch):
    monkeypatch.setattr(rule_reliability, "_standard_property_sets", lambda: _KNOWN_PSETS)


@pytest.mark.parametrize(
    ("pset", "name"),
    [
        ("Attributes", "GlobalId"),
        ("", "IfcClass"),
        ("Attributes", "Name"),
        ("", "PredefinedType"),
        ("", "StoreyGlobalId"),
        ("", "StoreyName"),
        ("", "PlacementMatrix"),
        ("", "OpeningGlobalId"),
        ("", "OpeningIfcClass"),
        ("", "HostGlobalId"),
        ("Geometry", "Width"),
        ("", "OverallHeight"),
        ("Qto_DoorBaseQuantities", "Area"),
    ],
)
def test_standard_attributes_geometry_quantities_and_relationships_are_high(pset, name):
    assert assess_property(pset, name).level == "high"


@pytest.mark.parametrize(
    ("pset", "name"),
    [
        ("Pset_DoorCommon", "FireRating"),
        ("Pset_WallCommon", "ThermalTransmittance"),
        ("", "FireRating"),
        ("", "AcousticRating"),
        ("Pset_WindowCommon", "GlazingAreaFraction"),
        ("Pset_DoorCommon", "IsExternal"),
    ],
)
def test_standard_property_set_data_is_medium(pset, name):
    assert assess_property(pset, name).level == "medium"


@pytest.mark.parametrize(
    ("pset", "name", "category"),
    [
        ("Pset_DoorCommon", "UserDefinedPartitioningType", "user_defined"),
        ("", "ClearOpeningWidth", "derived"),
        ("Pset_DoorCommon", "ClearWidth", "derived"),
        ("", "EscapeCompliance", "contextual"),
        ("Pset_DoorCommon", "SmokeProtection", "contextual"),
        ("Pset_ManufacturerTypeInformation", "Manufacturer", "manufacturer"),
        ("", "CalculatedArea", "derived"),
        ("Acme Custom Params", "FireRating", "custom"),
        ("", "SomethingNobodyHeardOf", "unrecognised"),
    ],
)
def test_custom_derived_contextual_and_unknown_data_is_low(pset, name, category):
    result = assess_property(pset, name)
    assert result.level == "low"
    assert result.category == category


def test_the_pset_prefix_is_read_from_the_raw_name_not_the_normalised_one():
    # Normalising strips underscores; a "Pset_" prefix must still be recognised.
    assert assess_property("Pset_DoorCommon", "Reference").level == "medium"
    assert assess_property("PSET_DOORCOMMON", "FireRating").level == "medium"


def test_a_pset_prefix_alone_does_not_make_a_property_set_standard():
    # Projects borrow the "Pset_" prefix for their own data; only dictionary names count.
    result = assess_property("Pset_Compliance", "FireRating")
    assert result.level == "low"
    assert result.category == "custom"
    assert "not in the buildingSMART dictionary" in result.reason


def test_without_the_dictionary_the_prefix_is_the_fallback(monkeypatch):
    monkeypatch.setattr(rule_reliability, "_standard_property_sets", lambda: frozenset())
    assert assess_property("Pset_Compliance", "FireRating").level == "medium"
    assert assess_property("Acme Custom Params", "FireRating").level == "low"


def test_no_property_means_nothing_to_grade():
    assert assess_property("Attributes", "") is None
    assert assess_property(None, None) is None
    assert assess_rule({"description": "no property"}) is None


def test_a_rule_is_as_reliable_as_the_least_reliable_property_it_depends_on():
    # GlobalId is high, but the value is compared against a manufacturer field.
    rule = {"property_set": "", "property_name": "Width", "compare_property": "ManufacturerWidth"}
    result = assess_rule(rule)
    assert result.level == "low"
    assert result.reason.startswith("Compared against ManufacturerWidth:")
    # Same-or-better dependencies do not lower the grade.
    assert assess_rule({"property_name": "Width", "value_max_property": "Height"}).level == "high"


def test_extractor_dicts_with_pset_and_property_keys_are_understood():
    assert assess_rule({"pset": "Pset_DoorCommon", "property": "FireRating"}).level == "medium"


def test_grades_appear_on_drafts_and_saved_rules_and_follow_edits():
    draft = RuleExtractionDraft(
        source_document_id=1,
        proposed_rule=RuleCreateRequest(rule_id="DR-1", property_set="Attributes", property_name="GlobalId"),
    )
    assert draft.model_dump()["reliability"]["level"] == "high"

    edited = draft.model_copy(
        update={
            "proposed_rule": draft.proposed_rule.model_copy(
                update={"property_set": "Pset_DoorCommon", "property_name": "FireRating"}
            )
        }
    )
    assert edited.model_dump()["reliability"]["level"] == "medium"

    saved = RuleResponse(id=7, rule_id="R-7", property_set="Custom", property_name="Whatever")
    assert saved.model_dump()["reliability"]["level"] == "low"
    assert RuleResponse(id=8, rule_id="R-8").model_dump()["reliability"] is None


def test_the_grade_is_never_written_into_the_stored_rule_payload():
    # Drafts persist proposed_rule.model_dump(); the grade must not leak into that JSON.
    stored = RuleCreateRequest(rule_id="DR-1", property_name="GlobalId").model_dump()
    assert "reliability" not in stored


def test_assess_reliability_endpoint_grades_before_a_rule_is_saved():
    from app.api.rules import assess_rule_reliability
    from app.modules.contracts import RuleReliabilityRequest

    graded = assess_rule_reliability(
        RuleReliabilityRequest(property_set="Pset_DoorCommon", property_name="FireRating")
    )
    assert graded.reliability.level == "medium"
    # Nothing to grade until a property is named (e.g. a half-filled form).
    assert assess_rule_reliability(RuleReliabilityRequest(property_set="Attributes")).reliability is None
