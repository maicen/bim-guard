"""Reliability grading: does the grade match a concrete source, not a guessed keyword.

Every branch of app.modules.rule_reliability cites one of four sources -- the live IFC
schema, the bSDD dictionary, BIMGuard's own geometry-computation table, or the project's
reliability reference image. These tests stub each source to a small, known fixture so the
logic is exercised in isolation from the size (and any future drift) of the real data; a
separate suite (test_rule_reliability_real_sources.py) checks the same logic against the
real IFC schema / bSDD dictionary / geometry table.
"""

from __future__ import annotations

import pytest

from app.modules import rule_reliability
from app.modules.contracts import RuleCreateRequest, RuleExtractionDraft, RuleResponse
from app.modules.rule_reliability import assess_property, assess_rule, strip_property_namespace

_SCHEMA_ATTRIBUTES = frozenset({"globalid", "name", "overallwidth", "overallheight", "predefinedtype", "tag"})
#: pset -> the properties it actually contains, mirroring app.services.bsdd_ontology_repository's
#: known_property_set_members() pairing (not two independent name lists).
_PSET_MEMBERS = {
    "pset_doorcommon": frozenset({"firerating", "smokestop", "isexternal"}),
    "pset_wallcommon": frozenset({"loadbearing", "isexternal"}),
    "qto_doorbasequantities": frozenset({"width", "height", "area"}),
}
_BSDD_PROPERTIES = frozenset({"firerating", "smokestop", "globalid", "somestandardthing"})
_GEOMETRY_NAMES = frozenset({"headroomclearance", "requiredheadroom", "clearwidth", "slopeangle"})


@pytest.fixture(autouse=True)
def _fixed_sources(monkeypatch):
    monkeypatch.setattr(rule_reliability, "_ifc_schema_attributes", lambda: _SCHEMA_ATTRIBUTES)
    monkeypatch.setattr(rule_reliability, "_property_set_members", lambda: _PSET_MEMBERS)
    monkeypatch.setattr(rule_reliability, "_bsdd_property_names", lambda: _BSDD_PROPERTIES)
    monkeypatch.setattr(rule_reliability, "_geometry_computed_names", lambda: _GEOMETRY_NAMES)


# -- Source 1: the IFC schema --------------------------------------------------------------------


def test_a_real_schema_attribute_is_high():
    result = assess_property("", "OverallWidth")
    assert result.level == "high"
    assert result.category == "schema_attribute"


def test_the_elements_own_ifc_class_is_high():
    result = assess_property("", "IfcClass")
    assert result.level == "high"
    assert result.category == "ifc_class"


def test_bimguards_relationship_lookups_are_high_and_cite_the_relationship():
    for name, relationship in [
        ("StoreyGlobalId", "IfcRelContainedInSpatialStructure"),
        ("HostGlobalId", "IfcRelVoidsElement"),
        ("OpeningGlobalId", "IfcRelFillsElement"),
        ("TypeGlobalId", "IfcRelDefinesByType"),
        ("TypeAssignmentCount", "IfcRelDefinesByType"),
        ("relationships.host_global_id", "IfcRelVoidsElement"),
        ("PlacementMatrix", "IfcLocalPlacement"),
    ]:
        result = assess_property("", name)
        assert result.level == "high", name
        assert result.category == "relationship"
        assert relationship in result.reason


# -- Source 2: bSDD -------------------------------------------------------------------------------


def test_a_property_in_a_known_standard_pset_is_medium():
    result = assess_property("Pset_DoorCommon", "FireRating")
    assert result.level == "medium"
    assert result.category == "property_set"
    assert result.bsdd_defined is True


def test_a_qto_prefixed_known_set_is_high_not_medium():
    # The project's reference groups quantities with attributes/geometry/relationships, not with
    # Pset_ property-set data.
    result = assess_property("Qto_DoorBaseQuantities", "Width")
    assert result.level == "high"
    assert result.category == "quantity"


def test_a_property_the_set_does_not_actually_contain_is_low_even_though_the_set_is_real():
    # QtoWidth is not a real Qto_DoorBaseQuantities member (the real name is Width) -- catches an
    # invented/mistyped property name that a naive "is the set real" check would have missed.
    result = assess_property("Qto_DoorBaseQuantities", "QtoWidth")
    assert result.level == "low"
    assert result.category == "not_in_set"
    assert "does not list" in result.reason
    result2 = assess_property("Pset_DoorCommon", "NotARealDoorProperty")
    assert result2.level == "low"
    assert result2.category == "not_in_set"


def test_a_pset_prefix_alone_does_not_make_a_property_set_standard():
    # A project can borrow the "Pset_" prefix for its own data; only a dictionary-known name counts.
    result = assess_property("Pset_Compliance", "FireRating")
    assert result.level == "low"
    assert result.category == "custom"
    assert "not in the buildingSMART dictionary" in result.reason


def test_without_the_dictionary_the_prefix_is_the_fallback(monkeypatch):
    monkeypatch.setattr(rule_reliability, "_property_set_members", lambda: {})
    assert assess_property("Pset_Compliance", "FireRating").level == "medium"
    assert assess_property("Acme Custom Params", "FireRating").level == "low"


def test_bsdd_lifts_a_property_with_no_pset_stated_that_would_otherwise_be_unrecognised():
    lifted = assess_property("", "SomeStandardThing")
    assert lifted.level == "medium"
    assert lifted.category == "bsdd_defined"
    assert lifted.bsdd_defined is True


def test_the_bsdd_flag_is_unknown_when_the_dictionary_is_unavailable(monkeypatch):
    monkeypatch.setattr(rule_reliability, "_bsdd_property_names", lambda: frozenset())
    assert assess_property("Pset_DoorCommon", "FireRating").bsdd_defined is None


# -- Source 3: BIMGuard's own geometry engine ------------------------------------------------------


def test_a_geometry_computed_name_is_low_and_says_so_concretely():
    # The user's own example: clearance above stairs is calculated, not filled in by anyone.
    result = assess_property("", "HeadroomClearance")
    assert result.level == "low"
    assert result.category == "calculated"
    assert "geometry engine computes this" in result.reason


def test_stored_sources_are_checked_before_the_geometry_fallback():
    # OverallWidth is in both the schema-attribute fixture and would be a geometry-map name too
    # in the real table; the schema attribute must win, matching the resolver's own pass order.
    result = assess_property("", "OverallWidth")
    assert result.category == "schema_attribute"


# -- Source 4: the project's own reference image -----------------------------------------------


def test_the_images_named_low_examples_are_low():
    # Given with no property set (so nothing can resolve them via bSDD first) -- isolates the
    # fallback pattern match itself from whatever a real dictionary happens to contain.
    assert assess_property("", "ClearOpeningWidth").category == "derived"
    assert assess_property("", "SmokeProtection").category == "contextual"
    assert assess_property("", "Manufacturer").category == "manufacturer"
    assert assess_property("", "UserDefinedPartitioningType").category == "user_defined"


def test_a_property_genuinely_defined_by_bsdd_is_medium_even_if_its_name_sounds_like_the_low_examples():
    # SmokeStop is a real Pset_DoorCommon property (per the fixture above): if a model has it, a
    # person filled it in -- provenance, the thing this whole module grades, beats a keyword guess.
    result = assess_property("Pset_DoorCommon", "SmokeStop")
    assert result.level == "medium"
    assert result.category == "property_set"


def test_a_name_matching_no_source_at_all_is_low_and_says_unrecognised():
    result = assess_property("", "SomethingNobodyHeardOf")
    assert result.level == "low"
    assert result.category == "unrecognised"


# -- No property / rule-level grading ------------------------------------------------------------


def test_no_property_means_nothing_to_grade():
    assert assess_property("Attributes", "") is None
    assert assess_property(None, None) is None
    assert assess_rule({"description": "no property"}) is None


def test_a_rule_is_as_reliable_as_the_least_reliable_property_it_depends_on():
    rule = {"property_name": "OverallWidth", "compare_property": "SomethingNobodyHeardOf"}
    result = assess_rule(rule)
    assert result.level == "low"
    assert result.reason.startswith("Compared against SomethingNobodyHeardOf:")
    assert assess_rule({"property_name": "OverallWidth", "compare_property": "OverallHeight"}).level == "high"


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
    assert graded.reliability.bsdd_defined is True
    assert assess_rule_reliability(RuleReliabilityRequest(property_set="Attributes")).reliability is None


def test_only_category_namespaces_are_stripped_from_a_property_name():
    assert strip_property_namespace("relationships.host_global_id") == "host_global_id"
    assert strip_property_namespace("Attributes.OverallWidth") == "OverallWidth"
    # A Pset-qualified name is not a category namespace and is left alone.
    assert strip_property_namespace("Pset_DoorCommon.FireRating") == "Pset_DoorCommon.FireRating"
    assert strip_property_namespace("FireRating") == "FireRating"
