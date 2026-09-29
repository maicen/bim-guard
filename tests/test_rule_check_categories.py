"""Check categories: name resolution, rule persistence and LLM extraction mapping."""

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

CATEGORIES = ["Fire and Smoke Protection", "Emergency Escape", "Energy Performance"]
DESCRIPTIONS = {name: f"Tests about {name.lower()}." for name in CATEGORIES}


class _FakeCategoriesRepo:
    """Minimal stand-in exposing the adapter's ``rows`` property."""

    def __init__(self, names: list[str]):
        # Deliberately stored out of display order to exercise the sort.
        self.rows = [
            {"id": i + 1, "name": name, "sort_order": len(names) - i} for i, name in enumerate(names)
        ]


def _category_service() -> RuleCheckCategoryService:
    return RuleCheckCategoryService(categories_repo=_FakeCategoriesRepo(CATEGORIES))


def _rule_service(tmp_path) -> RuleService:
    db = PersistenceService.get_isolated_sqlite_db(str(tmp_path / "rules.db"))
    return RuleService(check_categories=_category_service(), documents_service=object(), db=db)


def test_names_follow_sort_order():
    assert _category_service().names() == list(reversed(CATEGORIES))


def test_resolve_matches_case_insensitively_and_rejects_unknown():
    service = _category_service()
    assert service.resolve("  fire AND smoke protection ") == "Fire and Smoke Protection"
    assert service.resolve("Plumbing") is None
    assert service.resolve("") is None
    assert service.resolve(None) is None


def test_rule_persists_resolved_check_category(tmp_path):
    service = _rule_service(tmp_path)
    created = service.create_rule(
        rule_id="W-1", description="Window fire rating", ruleset_id="WIN", check_category="emergency escape"
    )
    assert service.get_rule(created["id"])["check_category"] == "Emergency Escape"


def test_uncategorized_rule_row_omits_the_column(tmp_path):
    row = _rule_service(tmp_path)._build_rule_row(rule_id="W-2", description="x")
    assert "check_category" not in row


def test_unknown_check_category_is_rejected_on_create(tmp_path):
    with pytest.raises(ValueError, match="Unknown check category"):
        _rule_service(tmp_path).create_rule(rule_id="W-3", description="x", check_category="Plumbing")


def test_update_sets_and_clears_check_category(tmp_path):
    service = _rule_service(tmp_path)
    rule_id = service.create_rule(rule_id="W-4", description="x", ruleset_id="WIN")["id"]

    service.update_rule(rule_id, check_category="Energy Performance")
    assert service.get_rule(rule_id)["check_category"] == "Energy Performance"

    service.update_rule(rule_id, description="edited")  # omitted -> untouched
    assert service.get_rule(rule_id)["check_category"] == "Energy Performance"

    service.update_rule(rule_id, check_category="")
    assert not service.get_rule(rule_id)["check_category"]


def test_bulk_update_assigns_check_category(tmp_path):
    service = _rule_service(tmp_path)
    ids = [service.create_rule(rule_id=f"W-{n}", description="x", ruleset_id="WIN")["id"] for n in (5, 6)]
    service.bulk_update_rules(ids, {"check_category": "Fire and Smoke Protection"})
    assert {service.get_rule(i)["check_category"] for i in ids} == {"Fire and Smoke Protection"}


def _node() -> DocumentNodeContract:
    return DocumentNodeContract(
        node_id="node-1",
        text="Windows in fire compartment walls shall be rated EI 30.",
        metadata=ClauseMetadata(node_type="paragraph", source_document_id=1),
    )


def test_candidate_category_is_mapped_to_stored_spelling():
    candidate = _LLMRuleCandidate(description="Rated windows", check_category="FIRE AND SMOKE PROTECTION")
    draft = _candidate_to_draft(candidate, _node(), check_categories=DESCRIPTIONS)
    assert draft.proposed_rule.check_category == "Fire and Smoke Protection"


def test_invented_candidate_category_is_dropped():
    candidate = _LLMRuleCandidate(description="Rated windows", check_category="Fire Resistance")
    draft = _candidate_to_draft(candidate, _node(), check_categories=DESCRIPTIONS)
    assert draft.proposed_rule.check_category is None


def test_category_context_lists_names_and_heading():
    block = format_check_category_context(categories=DESCRIPTIONS, section_heading="3. Fire and Smoke")
    assert all(f"  - {name}: {DESCRIPTIONS[name]}" in block for name in CATEGORIES)
    assert '"3. Fire and Smoke"' in block
    assert format_check_category_context(categories={}, section_heading="x") == ""
