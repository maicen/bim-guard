"""Tests for GlobalId deduplication in ``parse_ifc_model``.

THE BUG

    IFC classes are a hierarchy: an IfcPipeSegment is also an IfcFlowSegment
    and an IfcDistributionElement. ``parse_ifc_model`` calls ``model.by_type()``
    once per entry in ``IFC_SERVICE_LABELS``, so the same entity came back once
    per matching class. A three-entity model produced eight ServiceElements
    sharing three GlobalIds.

    Downstream that meant inflated ``ifc_element_count``, the corrosion engines
    running repeatedly over one element, and duplicate issues raised against a
    single GlobalId — which breaks the rule that guid is the join key
    (data contracts §1).

Models are synthesised in memory, so the entity count under test is the entity
count asserted, and the suite needs neither the network nor ``data/cache``.

Run: uv run pytest tests/test_ifc_parser_dedup.py -v
"""

from __future__ import annotations

import pytest

from app.modules.module2_ifc_read.ifc_parser import (
    IFC_SERVICE_LABELS,
    parse_ifc_model,
)

ifcopenshell = pytest.importorskip("ifcopenshell", reason="IFC parsing needs ifcopenshell")


def model_with(specs: list[tuple[str, str]], schema: str = "IFC4"):
    """Build an in-memory model from ``(ifc_type, name)`` pairs."""
    model = ifcopenshell.file(schema=schema)
    for ifc_type, name in specs:
        model.create_entity(ifc_type, GlobalId=ifcopenshell.guid.new(), Name=name)
    return model


class TestOneEntityOneElement:
    """The core guarantee."""

    def test_single_pipe_yields_one_element(self):
        """IfcPipeSegment also matches IfcFlowSegment and IfcDistributionElement."""
        elements = parse_ifc_model(model_with([("IfcPipeSegment", "P-01")]))
        assert len(elements) == 1

    def test_three_entities_yield_three_elements(self):
        """Was eight before the fix."""
        elements = parse_ifc_model(
            model_with(
                [
                    ("IfcPipeSegment", "CHW-Supply"),
                    ("IfcPipeSegment", "CHW-Return"),
                    ("IfcValve", "Isolation"),
                ]
            )
        )
        assert len(elements) == 3

    def test_guids_are_unique(self):
        """guid is the join key for every downstream Issue."""
        elements = parse_ifc_model(
            model_with([("IfcPipeSegment", f"P-{i:02d}") for i in range(6)])
        )
        guids = [e.guid for e in elements]
        assert len(guids) == len(set(guids))

    def test_element_count_equals_entity_count(self):
        specs = [("IfcValve", f"V-{i}") for i in range(5)]
        assert len(parse_ifc_model(model_with(specs))) == len(specs)


class TestMostSpecificClassWins:
    """IFC_SERVICE_LABELS is ordered specific to general and iterated in order."""

    def test_pipe_segment_keeps_its_own_class(self):
        elements = parse_ifc_model(model_with([("IfcPipeSegment", "P-01")]))
        assert elements[0].ifc_type == "IfcPipeSegment"

    def test_valve_keeps_its_own_class(self):
        elements = parse_ifc_model(model_with([("IfcValve", "V-01")]))
        assert elements[0].ifc_type == "IfcValve"

    def test_specific_classes_precede_general_ones(self):
        """The ordering the first-wins rule depends on."""
        keys = list(IFC_SERVICE_LABELS)
        assert keys.index("IfcPipeSegment") < keys.index("IfcDistributionElement")
        assert keys.index("IfcValve") < keys.index("IfcDistributionElement")


class TestMixedAndEdgeCases:
    def test_distinct_entities_are_not_collapsed(self):
        """Dedup keys on GlobalId, so different entities all survive."""
        specs = [("IfcPipeSegment", "P-01"), ("IfcValve", "V-01"), ("IfcPump", "PU-01")]
        elements = parse_ifc_model(model_with(specs))
        assert len(elements) == len(specs)
        assert len({e.guid for e in elements}) == len(specs)

    def test_empty_model_yields_nothing(self):
        assert parse_ifc_model(model_with([])) == []

    def test_ifc2x3_model_also_deduplicates(self):
        """The hierarchy exists in IFC2X3 too."""
        elements = parse_ifc_model(model_with([("IfcFlowSegment", "P-01")], schema="IFC2X3"))
        assert len(elements) == 1

    def test_type_counts_do_not_double_count(self):
        from collections import Counter

        elements = parse_ifc_model(
            model_with([("IfcPipeSegment", f"P-{i}") for i in range(4)])
        )
        counts = Counter(e.ifc_type for e in elements)
        assert counts == {"IfcPipeSegment": 4}
        assert sum(counts.values()) == len(elements)
