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


def _draft(document_id: int = 1, source_element_id: str | None = "elem-3") -> RuleExtractionDraft:
    return RuleExtractionDraft(
        source_document_id=document_id,
        source_node_id="node-1",
        source_element_id=source_element_id,
        clause=ClauseMetadata(
            clause_id="9.8.2.1", node_type="paragraph", source_document_id=document_id
        ),
        proposed_rule=RuleCreateRequest(
            rule_id="9.8.2.1",
            description="Stairs shall be >= 900mm wide",
            target_ifc_class="IfcStairFlight",
            operator=">=",
            check_value="900",
        ),
        confidence=0.9,
        extraction_method="llamaindex_pydantic",
    )


def _service() -> tuple[RuleDraftService, FakeTable, FakeRuleService]:
    table = FakeTable()
    rule_service = FakeRuleService()
    return RuleDraftService(drafts_repo=table, rule_service=rule_service), table, rule_service


class FakeDocumentService:
    """Stand-in for DocumentService, exposing only what relink_source_element uses."""

    _ELEMENTS = [
        {"element_id": "elem-3", "kind": "paragraph", "page_number": 1, "bbox": {"l": 0, "t": 0, "r": 1, "b": 1}},
        {"element_id": "elem-5", "kind": "paragraph", "page_number": 2, "bbox": {"l": 2, "t": 2, "r": 3, "b": 3}},
        {"element_id": "elem-7", "kind": "table", "page_number": 3, "bbox": {"l": 4, "t": 4, "r": 5, "b": 5}},
    ]

    def get_document(self, document_id: int) -> dict:
        return {"id": document_id, "element_bboxes": self._ELEMENTS}

    def get_element_bboxes(self, doc: dict) -> list[dict]:
        return self._ELEMENTS


def test_save_drafts_persists_pending_review_with_ids():
    service, table, _ = _service()

    saved = service.save_drafts([_draft()])

    assert len(saved) == 1
    assert saved[0].id == 1
    assert saved[0].status == RuleDraftStatus.pending_review
    assert table.rows[0]["status"] == "pending_review"


def test_save_drafts_keeps_the_grounding_note_so_the_bsdd_label_survives_a_reload():
    service, table, _ = _service()
    note = "bSDD grounding: corrected property to Pset_DoorCommon.FireRating (was fire rating)."

    service.save_drafts([_draft().model_copy(update={"review_notes": note})])

    assert table.rows[0]["review_notes"] == note
    assert service.list_drafts(1)[0]["review_notes"] == note


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


def test_promote_draft_passes_through_source_element_id():
    """A draft's exact source_element_id survives promotion into public.rules.

    Matches DocumentElementBbox.element_id, for the rule-source map view.
    """
    service, _table, rule_service = _service()
    saved = service.save_drafts([_draft(source_element_id="elem-3")])
    draft_id = saved[0].id
    service.review_draft(draft_id, RuleDraftReviewRequest(status=RuleDraftStatus.accepted))

    service.promote_draft(draft_id)

    assert rule_service.created[0]["source_element_id"] == "elem-3"


def test_relink_source_element_snapshots_original_only_once(monkeypatch):
    """The first relink snapshots the LLM's original pick; later relinks don't overwrite it."""
    monkeypatch.setattr("app.services.documents_service.DocumentService", FakeDocumentService)

    service, _table, _rule_service = _service()
    saved = service.save_drafts([_draft(source_element_id="elem-3")])
    draft_id = saved[0].id

    first = service.relink_source_element(draft_id, "elem-5")
    assert first["source_element_id"] == "elem-5"
    assert first["original_source_element_id"] == "elem-3"
    assert first["clause"]["page_number"] == 2

    second = service.relink_source_element(draft_id, "elem-7")
    assert second["source_element_id"] == "elem-7"
    assert second["original_source_element_id"] == "elem-3"
    assert second["clause"]["page_number"] == 3


def test_relink_source_element_from_never_linked_snapshots_empty_not_falsy(monkeypatch):
    """A never-linked draft's genuine "" original must survive a second relink.

    A second relink must not re-snapshot the now-current link over it, since
    "" is a legitimate "no original link" value, not a "haven't snapshotted
    yet" sentinel.
    """
    monkeypatch.setattr("app.services.documents_service.DocumentService", FakeDocumentService)

    service, _table, _rule_service = _service()
    saved = service.save_drafts([_draft(source_element_id=None)])
    draft_id = saved[0].id

    first = service.relink_source_element(draft_id, "elem-5")
    assert first["source_element_id"] == "elem-5"
    assert first["original_source_element_id"] == ""

    second = service.relink_source_element(draft_id, "elem-7")
    assert second["source_element_id"] == "elem-7"
    assert second["original_source_element_id"] == ""


def test_relink_source_element_rejects_unknown_element_id(monkeypatch):
    monkeypatch.setattr("app.services.documents_service.DocumentService", FakeDocumentService)

    service, _table, _rule_service = _service()
    saved = service.save_drafts([_draft(source_element_id="elem-3")])
    draft_id = saved[0].id

    try:
        service.relink_source_element(draft_id, "elem-does-not-exist")
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert "elem-does-not-exist" in str(exc)


def test_promote_draft_refuses_to_write_an_empty_target_ifc_class():
    """A draft that still has no target_ifc_class must never reach the rules table.

    The hard backstop behind the inference work in RuleExtractionService:
    even if every grounding/inference path upstream fails to determine a
    class, a rule that can never match an element must not be silently
    promoted with target_ifc_class = '' (the exact bug this guard closes off
    for good, regardless of what breaks upstream in the future).
    """
    service, _, rule_service = _service()
    draft = RuleExtractionDraft(
        source_document_id=1,
        proposed_rule=RuleCreateRequest(
            rule_id="REQ-NO-CLASS", description="Something shall be true", check_value="1"
        ),
    )
    saved = service.save_drafts([draft])
    draft_id = saved[0].id
    service.review_draft(draft_id, RuleDraftReviewRequest(status=RuleDraftStatus.accepted))

    try:
        service.promote_draft(draft_id)
        assert False, "expected ValueError for empty target_ifc_class"
    except ValueError as exc:
        assert "target_ifc_class" in str(exc)

    assert rule_service.created == []


def test_promote_draft_passes_through_target_ifc_class():
    service, _, rule_service = _service()
    draft = RuleExtractionDraft(
        source_document_id=1,
        proposed_rule=RuleCreateRequest(
            rule_id="DR-012",
            description="Doors shall have an overall width >= 800mm",
            target_ifc_class="IfcDoor",
            property_name="OverallWidth",
            operator=">=",
            check_value="800",
        ),
    )
    saved = service.save_drafts([draft])
    draft_id = saved[0].id
    service.review_draft(draft_id, RuleDraftReviewRequest(status=RuleDraftStatus.accepted))

    service.promote_draft(draft_id)

    assert rule_service.created[0]["target_ifc_class"] == "IfcDoor"


def test_promote_draft_passes_through_applies_when_and_exceptions():
    service, _, rule_service = _service()
    draft = RuleExtractionDraft(
        source_document_id=1,
        proposed_rule=RuleCreateRequest(
            rule_id="9.8.2.2",
            description="Gypsum partitions shall be fire-rated",
            target_ifc_class="IfcWall",
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


def test_promote_draft_passes_through_value_scale_and_offset():
    """A rule bound as 'a same-element property, scaled and offset' survives promotion."""
    service, _, rule_service = _service()
    draft = RuleExtractionDraft(
        source_document_id=1,
        proposed_rule=RuleCreateRequest(
            rule_id="9.8.4.5",
            description="Riser height shall not exceed one-half of the tread going",
            target_ifc_class="IfcStairFlight",
            property_name="RiserHeight",
            operator="<=",
            value_max_property="TreadGoing",
            value_max_scale="0.5",
            value_max_offset="0",
        ),
    )
    saved = service.save_drafts([draft])
    draft_id = saved[0].id
    service.review_draft(draft_id, RuleDraftReviewRequest(status=RuleDraftStatus.accepted))

    service.promote_draft(draft_id)

    assert rule_service.created[0]["value_max_property"] == "TreadGoing"
    assert rule_service.created[0]["value_max_scale"] == "0.5"


def test_promote_draft_defaults_value_scale_to_one_when_unset():
    service, _, rule_service = _service()
    saved = service.save_drafts([_draft()])
    draft_id = saved[0].id
    service.review_draft(draft_id, RuleDraftReviewRequest(status=RuleDraftStatus.accepted))

    service.promote_draft(draft_id)

    assert rule_service.created[0]["value_min_scale"] == 1
    assert rule_service.created[0]["value_max_scale"] == 1
