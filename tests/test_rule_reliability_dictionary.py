"""Reliability grading against the real bundled bSDD dictionary (not a stand-in)."""

from __future__ import annotations

import pytest

from app.modules import rule_reliability
from app.modules.rule_reliability import assess_property


@pytest.fixture(scope="module")
def dictionary():
    rule_reliability._standard_property_sets.cache_clear()
    known = rule_reliability._standard_property_sets()
    if not known:
        pytest.skip("local bSDD reference data is not available")
    return known


def test_the_bundled_dictionary_knows_the_standard_sets_and_not_a_project_one(dictionary):
    assert {"pset_doorcommon", "qto_doorbasequantities"} <= dictionary
    assert "pset_compliance" not in dictionary


def test_grades_use_the_bundled_dictionary(dictionary):
    assert assess_property("Pset_DoorCommon", "FireRating").level == "medium"
    assert assess_property("Qto_DoorBaseQuantities", "Width").level == "high"
    assert assess_property("Pset_Compliance", "FireRating").level == "low"
