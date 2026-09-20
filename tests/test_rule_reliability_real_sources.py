"""Reliability grading against the real IFC schema, bSDD dictionary and geometry table.

test_rule_reliability.py checks the grading *logic* against small stubbed fixtures. This file
checks the *sources themselves* -- that ifcopenshell's real schema, the bundled bSDD data, and
BIMGuard's own geometry-computation table actually contain what the grading logic assumes they
do, and that a few properties the team has already reasoned about by hand come out right.
"""

from __future__ import annotations

import pytest

from app.modules import rule_reliability
from app.modules.rule_reliability import assess_property


@pytest.fixture(scope="module", autouse=True)
def _real_sources():
    for name in ("_ifc_schema_attributes", "_property_set_members", "_bsdd_property_names", "_geometry_computed_names"):
        getattr(rule_reliability, name).cache_clear()


def test_the_live_ifc_schema_confirms_the_direct_attributes():
    names = rule_reliability._ifc_schema_attributes()
    if not names:
        pytest.skip("ifcopenshell schema data is not available")
    assert {"globalid", "name", "overallwidth", "overallheight", "tag"} <= names


def test_headroomclearance_is_not_a_real_ifc_attribute_or_bsdd_property():
    # Grounds the user's own example: clearance above stairs has no stored source at all.
    schema = rule_reliability._ifc_schema_attributes()
    bsdd = rule_reliability._bsdd_property_names()
    if not schema or not bsdd:
        pytest.skip("reference data is not available")
    assert "headroomclearance" not in schema
    assert "headroomclearance" not in bsdd


def test_the_geometry_table_is_read_from_ifc_geometry_not_duplicated():
    from app.modules.ifc_reader.ifc_geometry import _GEOMETRY_PROPERTY_MAP

    names = rule_reliability._geometry_computed_names()
    if not names:
        pytest.skip("ifc_geometry module is not available")
    assert names == frozenset(_GEOMETRY_PROPERTY_MAP)
    assert "headroomclearance" in names
    assert "clearwidth" in names


def test_the_bundled_bsdd_dictionary_knows_the_standard_sets_and_not_a_project_one():
    members = rule_reliability._property_set_members()
    if not members:
        pytest.skip("local bSDD reference data is not available")
    assert {"pset_doorcommon", "qto_doorbasequantities"} <= members.keys()
    assert "pset_compliance" not in members


def test_qto_doorbasequantities_really_contains_width_and_not_qtowidth():
    # Grounds the pair-aware lookup itself: the set exists, but only the real property name is
    # one of its members -- an invented name isn't rescued just because the set is real.
    members = rule_reliability._property_set_members()
    if not members:
        pytest.skip("local bSDD reference data is not available")
    assert "width" in members["qto_doorbasequantities"]
    assert "qtowidth" not in members["qto_doorbasequantities"]


def test_grading_the_teams_own_door_rules_against_the_real_sources():
    if not rule_reliability._ifc_schema_attributes() or not rule_reliability._bsdd_property_names():
        pytest.skip("reference data is not available")

    # Stored, single-source data: high.
    assert assess_property("Attributes", "GlobalId").level == "high"
    assert assess_property("", "OverallWidth").level == "high"
    assert assess_property("", "StoreyGlobalId").level == "high"
    assert assess_property("Qto_DoorBaseQuantities", "Area").level == "high"

    # Standard property-set data: medium, true if found.
    assert assess_property("Pset_DoorCommon", "FireRating").level == "medium"

    # Genuinely calculated, or with no source at all: low.
    assert assess_property("", "HeadroomClearance").level == "low"
    assert assess_property("", "ClearOpeningWidth").level == "low"
    # A property name the extractor invented, which does not exist in any quantity set.
    assert assess_property("Qto_DoorBaseQuantities", "QtoWidth").level == "low"
