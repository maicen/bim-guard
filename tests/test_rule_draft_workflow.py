"""Extraction-draft persistence and review workflow (RuleDraftService)."""

from app.modules.contracts import (
    ClauseMetadata,
    RuleCreateRequest,
    RuleDraftReviewRequest,
    RuleDraftStatus,
    RuleExtractionDraft,
)
from app.services.rule_draft_service import RuleDraftService


class FakeTable:
    """Minimal in-memory stand-in for a PersistenceService table adapter."""

    def __init__(self) -> None:
        self._rows: dict[int, dict] = {}
        self._next_id = 1

    @property
    def rows(self):
        return list(self._rows.values())

    def insert(self, payload: dict) -> dict:
        row = {"id": self._next_id, **payload}
        self._rows[self._next_id] = row
        self._next_id += 1
        return dict(row)

    def get(self, pk):
        row = self._rows.get(pk)
        return dict(row) if row is not None else None

    def update(self, *, updates: dict, pk_values):
        row = self._rows.get(pk_values)
        if row is not None:
            row.update(updates)


class FakeRuleService:
    """Records create_rule() calls without touching a real database."""

    def __init__(self) -> None:
        self.created: list[dict] = []

    def create_rule(self, **kwargs) -> dict:
        rule = {"id": len(self.created) + 1, **kwargs}
        self.created.append(rule)
        return rule


def _draft(document_id: int = 1) -> RuleExtractionDraft:
    return RuleExtractionDraft(
        source_document_id=document_id,
        source_node_id="node-1",
        clause=ClauseMetadata(
            clause_id="9.8.2.1", node_type="paragraph", source_document_id=document_id
        ),
        proposed_rule=RuleCreateRequest(
            rule_id="9.8.2.1", description="Stairs shall be >= 900mm wide", operator=">=", check_value="900"
        ),
        confidence=0.9,
        extraction_method="llamaindex_pydantic",
    )


def _service() -> tuple[RuleDraftService, FakeTable, FakeRuleService]:
    table = FakeTable()
    rule_service = FakeRuleService()
    return RuleDraftService(drafts_repo=table, rule_service=rule_service), table, rule_service


def test_save_drafts_persists_pending_review_with_ids():
    service, table, _ = _service()

    saved = service.save_drafts([_draft()])

    assert len(saved) == 1
    assert saved[0].id == 1
    assert saved[0].status == RuleDraftStatus.pending_review
    assert table.rows[0]["status"] == "pending_review"


def test_list_drafts_filters_by_document_and_orders_newest_first():
    service, _, _ = _service()
    service.save_drafts([_draft(document_id=1), _draft(document_id=2), _draft(document_id=1)])

    rows = service.list_drafts(document_id=1)

    assert [row["source_document_id"] for row in rows] == [1, 1]
    assert rows[0]["id"] > rows[1]["id"]  # newest first


def test_review_draft_accept_records_reviewer_and_status():
    service, table, _ = _service()
    saved = service.save_drafts([_draft()])
    draft_id = saved[0].id

    updated = service.review_draft(
        draft_id,
        RuleDraftReviewRequest(status=RuleDraftStatus.accepted, reviewer_email="reviewer@example.com"),
    )

    assert updated["status"] == "accepted"
    assert updated["reviewer_email"] == "reviewer@example.com"
    assert table.rows[0]["reviewed_at"]


def test_review_draft_edited_requires_edited_rule():
    service, _, _ = _service()
    saved = service.save_drafts([_draft()])
    draft_id = saved[0].id

    try:
        service.review_draft(draft_id, RuleDraftReviewRequest(status=RuleDraftStatus.edited))
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_review_draft_edited_preserves_original_proposed_rule():
    service, table, _ = _service()
    saved = service.save_drafts([_draft()])
    draft_id = saved[0].id
    original_rule = table.rows[0]["proposed_rule"]

    edited_rule = RuleCreateRequest(
        rule_id="9.8.2.1", description="Stairs shall be >= 1000mm wide", operator=">=", check_value="1000"
    )
    updated = service.review_draft(
        draft_id, RuleDraftReviewRequest(status=RuleDraftStatus.edited, edited_rule=edited_rule)
    )

    assert updated["proposed_rule"]["check_value"] == "1000"
    assert updated["original_proposed_rule"] == original_rule
    assert updated["original_proposed_rule"]["check_value"] == "900"


def test_review_draft_second_edit_does_not_overwrite_original():
    service, table, _ = _service()
    saved = service.save_drafts([_draft()])
    draft_id = saved[0].id
    original_rule = table.rows[0]["proposed_rule"]

    first_edit = RuleCreateRequest(rule_id="9.8.2.1", description="First edit", check_value="1000")
    service.review_draft(
        draft_id, RuleDraftReviewRequest(status=RuleDraftStatus.edited, edited_rule=first_edit)
    )

    second_edit = RuleCreateRequest(rule_id="9.8.2.1", description="Second edit", check_value="1100")
    updated = service.review_draft(
        draft_id, RuleDraftReviewRequest(status=RuleDraftStatus.edited, edited_rule=second_edit)
    )

    assert updated["proposed_rule"]["check_value"] == "1100"
    # Still the LLM's ORIGINAL guess, not the first human edit.
    assert updated["original_proposed_rule"] == original_rule
    assert updated["original_proposed_rule"]["check_value"] == "900"


def test_review_draft_accept_does_not_set_original_proposed_rule():
    service, table, _ = _service()
    saved = service.save_drafts([_draft()])
    draft_id = saved[0].id

    service.review_draft(draft_id, RuleDraftReviewRequest(status=RuleDraftStatus.accepted))

    assert table.rows[0].get("original_proposed_rule") is None


def test_promote_draft_requires_accepted_or_edited_status():
    service, _, _ = _service()
    saved = service.save_drafts([_draft()])
    draft_id = saved[0].id

    try:
        service.promote_draft(draft_id)
        assert False, "expected ValueError for pending_review draft"
    except ValueError:
        pass


def test_promote_draft_calls_rule_service_create_rule_and_records_promoted_id():
    service, table, rule_service = _service()
    saved = service.save_drafts([_draft()])
    draft_id = saved[0].id
    service.review_draft(draft_id, RuleDraftReviewRequest(status=RuleDraftStatus.accepted))

    created = service.promote_draft(draft_id)

    assert len(rule_service.created) == 1
    assert rule_service.created[0]["rule_id"] == "9.8.2.1"
    assert created["id"] == rule_service.created[0]["id"]
    assert table.rows[0]["promoted_rule_id"] == created["id"]


def test_promote_draft_passes_through_applies_when_and_exceptions():
    service, _, rule_service = _service()
    draft = RuleExtractionDraft(
        source_document_id=1,
        proposed_rule=RuleCreateRequest(
            rule_id="9.8.2.2",
            description="Gypsum partitions shall be fire-rated",
            severity="mandatory",
            applies_when={"material_any_of": ["gypsum"]},
            exceptions=[{"reference": "9.8.2.2-exc", "predicate": {"is_suspended": True}}],
        ),
    )
    saved = service.save_drafts([draft])
    draft_id = saved[0].id
    service.review_draft(draft_id, RuleDraftReviewRequest(status=RuleDraftStatus.accepted))

    service.promote_draft(draft_id)

    assert rule_service.created[0]["applies_when"] == {"material_any_of": ["gypsum"]}
    assert rule_service.created[0]["exceptions"] == [
        {"reference": "9.8.2.2-exc", "predicate": {"is_suspended": True}}
    ]
