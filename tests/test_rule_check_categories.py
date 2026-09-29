"""Check categories: id resolution, rule persistence and LLM extraction mapping."""

import pytest

from app.modules.contracts import ClauseMetadata, DocumentNodeContract
from app.modules.rule_builder._extraction_prompts import format_check_category_context
from app.modules.rule_builder.llamaindex_rule_generator import (
    _candidate_to_draft,
    _LLMRuleCandidate,
)
from app.services.persistence import PersistenceService
from app.services.rule_check_category_service import RuleCheckCategoryService
from app.services.rules_service import RuleService

pytestmark = pytest.mark.rules

WINDOW_FIRE, WINDOW_ESCAPE, DOOR_SOURCE, STAIR_SOURCE, ANY_TYPE = 1, 2, 3, 4, 5

CATEGORY_ROWS = [
    # Stored out of display order to exercise the sort.
    {"id": WINDOW_ESCAPE, "name": "Emergency Escape", "description": "Escape.",
     "target_ifc_classes": ["IfcWindow"], "sort_order": 2},
    {"id": WINDOW_FIRE, "name": "Fire and Smoke Protection", "description": "Fire.",
     "target_ifc_classes": ["IfcWindow"], "sort_order": 1},
    # Same name for two element types, as in the door and stair tables.
    {"id": DOOR_SOURCE, "name": "IFC Source, Units and Coordinate Context", "description": "Source.",
     "target_ifc_classes": ["IfcDoor"], "sort_order": 1},
    {"id": STAIR_SOURCE, "name": "IFC Source, Units and Coordinate Context", "description": "Source.",
     "target_ifc_classes": ["IfcStair", "IfcStairFlight", "IfcRailing"], "sort_order": 1},
    {"id": ANY_TYPE, "name": "General", "description": "", "target_ifc_classes": [], "sort_order": 9},
]


class _Repo:
    """Minimal stand-in exposing the adapter's ``rows`` property."""

    def __init__(self, rows):
        self.rows = rows


def _category_service() -> RuleCheckCategoryService:
    return RuleCheckCategoryService(
        categories_repo=_Repo(CATEGORY_ROWS),
        property_map_repo=_Repo([
            {"id": 1, "target_ifc_class": "IfcWindow", "property_name": "FireRating", "check_category_id": WINDOW_FIRE},
            {"id": 2, "target_ifc_class": "IfcDoor", "property_name": "IfcSchema", "check_category_id": DOOR_SOURCE},
            {"id": 3, "target_ifc_class": "IfcRailing", "property_name": "IfcSchema", "check_category_id": STAIR_SOURCE},
        ]),
    )


def _rule_service(tmp_path) -> RuleService:
    db = PersistenceService.get_isolated_sqlite_db(str(tmp_path / "rules.db"))
    return RuleService(check_categories=_category_service(), documents_service=object(), db=db)


def test_list_is_ordered_and_filtered_by_element_type():
    service = _category_service()
    assert [c["id"] for c in service.list_categories("IfcWindow")] == [WINDOW_FIRE, WINDOW_ESCAPE, ANY_TYPE]
    assert [c["id"] for c in service.list_categories("ifcrailing")] == [STAIR_SOURCE, ANY_TYPE]


def test_same_name_resolves_per_element_type():
    service = _category_service()
    name = "ifc source, units and coordinate context"
    assert service.id_for_name(name, "IfcDoor") == DOOR_SOURCE
    assert service.id_for_name(name, "IfcStairFlight") == STAIR_SOURCE
    assert service.id_for_name(name, "IfcWindow") is None
    assert service.id_for_name("Plumbing", "IfcWindow") is None


def test_property_map_lookup_is_case_insensitive_and_class_scoped():
    service = _category_service()
    assert service.category_for_property("ifcwindow", "firerating") == WINDOW_FIRE
    assert service.category_for_property("IfcRailing", "IfcSchema") == STAIR_SOURCE
    assert service.category_for_property("IfcDoor", "FireRating") is None
    assert service.category_for_property("IfcWindow", "") is None


def test_rule_persists_explicit_category(tmp_path):
    service = _rule_service(tmp_path)
    created = service.create_rule(
        rule_id="W-1", description="x", target_ifc_class="IfcWindow", check_category_id=WINDOW_ESCAPE
    )
    assert service.get_rule(created["id"])["check_category_id"] == WINDOW_ESCAPE


def test_rule_without_category_is_categorised_from_property_map(tmp_path):
    service = _rule_service(tmp_path)
    mapped = service.create_rule(rule_id="W-2", description="x", target_ifc_class="IfcWindow", property_name="FireRating")
    explicit = service.create_rule(
        rule_id="W-3", description="x", target_ifc_class="IfcWindow", property_name="FireRating",
        check_category_id=WINDOW_ESCAPE,
    )
    assert service.get_rule(mapped["id"])["check_category_id"] == WINDOW_FIRE
    assert service.get_rule(explicit["id"])["check_category_id"] == WINDOW_ESCAPE


def test_uncategorized_rule_row_omits_the_column(tmp_path):
    row = _rule_service(tmp_path)._build_rule_row(rule_id="W-4", description="x", target_ifc_class="IfcWindow")
    assert "check_category_id" not in row


@pytest.mark.parametrize("category_id", [999, DOOR_SOURCE])
def test_unknown_or_other_type_category_is_rejected_on_create(tmp_path, category_id):
    with pytest.raises(ValueError, match="does not exist or does not apply"):
        _rule_service(tmp_path).create_rule(
            rule_id="W-5", description="x", target_ifc_class="IfcWindow", check_category_id=category_id
        )


def test_update_sets_and_clears_check_category(tmp_path):
    service = _rule_service(tmp_path)
    rule_id = service.create_rule(rule_id="W-6", description="x", ruleset_id="WIN", target_ifc_class="IfcWindow")["id"]

    service.update_rule(rule_id, check_category_id=WINDOW_ESCAPE)
    assert service.get_rule(rule_id)["check_category_id"] == WINDOW_ESCAPE

    service.update_rule(rule_id, description="edited")  # omitted -> untouched
    assert service.get_rule(rule_id)["check_category_id"] == WINDOW_ESCAPE

    service.update_rule(rule_id, check_category_id=0)
    assert not service.get_rule(rule_id)["check_category_id"]


def test_bulk_update_rejects_a_category_that_fits_only_some_rules(tmp_path):
    service = _rule_service(tmp_path)
    window = service.create_rule(rule_id="W-7", description="x", ruleset_id="WIN", target_ifc_class="IfcWindow")["id"]
    door = service.create_rule(rule_id="D-1", description="x", ruleset_id="WIN", target_ifc_class="IfcDoor")["id"]

    with pytest.raises(ValueError):
        service.bulk_update_rules([window, door], {"check_category_id": WINDOW_FIRE})
    assert not service.get_rule(window)["check_category_id"]

    service.bulk_update_rules([window, door], {"check_category_id": ANY_TYPE})
    assert {service.get_rule(i)["check_category_id"] for i in (window, door)} == {ANY_TYPE}


def _node() -> DocumentNodeContract:
    return DocumentNodeContract(
        node_id="node-1",
        text="Windows in fire compartment walls shall be rated EI 30.",
        metadata=ClauseMetadata(node_type="paragraph", source_document_id=1),
    )


PROMPT_CATEGORIES = _category_service().prompt_categories()


def test_candidate_category_name_maps_to_id_within_its_element_type():
    stair = _LLMRuleCandidate(
        description="Schema", target_ifc_class="IfcStairFlight",
        check_category="IFC SOURCE, UNITS AND COORDINATE CONTEXT",
    )
    draft = _candidate_to_draft(stair, _node(), check_categories=PROMPT_CATEGORIES)
    assert draft.proposed_rule.check_category_id == STAIR_SOURCE


@pytest.mark.parametrize(
    ("target", "name"),
    [("IfcWindow", "Fire Resistance"), ("IfcDoor", "Fire and Smoke Protection")],
)
def test_invented_or_other_type_candidate_category_is_dropped(target, name):
    candidate = _LLMRuleCandidate(description="Rated", target_ifc_class=target, check_category=name)
    draft = _candidate_to_draft(candidate, _node(), check_categories=PROMPT_CATEGORIES)
    assert draft.proposed_rule.check_category_id is None


def test_category_context_groups_categories_by_element_type():
    block = format_check_category_context(categories=PROMPT_CATEGORIES, section_heading="3. Fire and Smoke")
    assert "  IfcWindow:" in block
    assert "  IfcStair, IfcStairFlight, IfcRailing:" in block
    assert "  Any element type:" in block
    assert "    - Fire and Smoke Protection: Fire." in block
    assert '"3. Fire and Smoke"' in block
    assert format_check_category_context(categories=[], section_heading="x") == ""
