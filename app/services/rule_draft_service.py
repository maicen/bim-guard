"""Persistence and review workflow for LLM-extracted rule extraction drafts.

Fixes the gap where extracted rules previously existed only in the
frontend's in-memory state (RuleExtractionView.svelte) with no server-side
draft persistence, reviewer identity, or audit trail: drafts are written
here as `pending_review`, reviewed (accepted/rejected/edited), and only
`promote_draft` writes into the canonical `rules` table — reusing
`RuleService.create_rule()` rather than duplicating the insert.
"""

from __future__ import annotations

from typing import Any

from app.logging_config import get_logger
from app.modules.contracts import RuleCreateRequest, RuleDraftReviewRequest, RuleExtractionDraft
from app.services.persistence import PersistenceService
from app.services.rule_semantic_alignment_service import (
    AlignmentResult,
    RuleSemanticAlignmentService,
)
from app.services.rules_service import RuleService
from app.utils import now_iso_utc

logger = get_logger(__name__)


def _duplicate_key(payload: RuleCreateRequest) -> tuple:
    """Identity of one rule's check content, independent of its `reference`/`rule_id` text.

    Mirrors app/services/ruleset_seeder.py's own duplicate-prevention
    approach, but keyed on the actual check (target class + property +
    comparison) rather than `reference` -- two rules citing the same
    threshold under different reference strings (e.g. an LLM re-extracting
    the same clause from a re-uploaded document, or one wording it
    "OBC 9.6.4" and another "CODE 9.6.4") are still the same duplicate risk
    that a reference-keyed check would miss (see
    supabase/migrations/20260918155453_dedupe_part9_rules_by_content.sql).
    """
    return (
        str(payload.target_ifc_class or "").strip().lower(),
        str(payload.property_name or "").strip().lower(),
        str(payload.operator or "").strip(),
        str(payload.check_value or "").strip(),
        str(payload.value_min or "").strip(),
        str(payload.value_max or "").strip(),
    )


class RuleDraftService:
    """CRUD + review workflow for `rule_extraction_drafts`."""

    def __init__(
        self,
        *,
        drafts_repo=None,
        rule_service: RuleService | None = None,
        alignment_service: RuleSemanticAlignmentService | None = None,
    ) -> None:
        """Initialize the drafts table adapter and rule service with dependency injection."""
        self._drafts = (
            drafts_repo
            if drafts_repo is not None
            else PersistenceService.get_table(
                "rule_extraction_drafts",
                {
                    "id": int,
                    "source_document_id": int,
                    "source_node_id": str,
                    "source_element_id": str,
                    "original_source_element_id": str,
                    "source_snippet": str,
                    "clause": dict,
                    "proposed_rule": dict,
                    "confidence": float,
                    "extraction_method": str,
                    "status": str,
                    "reviewer_email": str,
                    "reviewed_at": str,
                    "review_notes": str,
                    "promoted_rule_id": int,
                    "created_at": str,
                    "original_proposed_rule": dict,
                    "bbox": dict,
                },
            )
        )
        self._rule_service = rule_service if rule_service is not None else RuleService()
        self._alignment_service = (
            alignment_service
            if alignment_service is not None
            else RuleSemanticAlignmentService(rule_service=self._rule_service)
        )

    def save_drafts(self, drafts: list[RuleExtractionDraft]) -> list[RuleExtractionDraft]:
        """Persist a batch of extraction drafts as `pending_review`, returning them with DB ids."""
        saved: list[RuleExtractionDraft] = []
        for draft in drafts:
            row = self._drafts.insert(
                {
                    "source_document_id": draft.source_document_id,
                    "source_node_id": draft.source_node_id or "",
                    "source_element_id": draft.source_element_id or "",
                    "source_snippet": draft.source_snippet or "",
                    "clause": draft.clause.model_dump() if draft.clause else None,
                    "bbox": draft.bbox or (draft.clause.bbox if draft.clause else None),
                    "proposed_rule": draft.proposed_rule.model_dump(),
                    "confidence": draft.confidence,
                    "extraction_method": draft.extraction_method,
                    "status": draft.status.value,
                    # Carries e.g. the bSDD grounding note, so the label survives a reload.
                    "review_notes": draft.review_notes,
                    "created_at": now_iso_utc(),
                }
            )
            saved.append(draft.model_copy(update={"id": row.get("id"), "created_at": row.get("created_at")}))
        logger.info("Saved %d rule extraction drafts", len(saved))
        return saved

    def list_drafts(self, document_id: int) -> list[dict[str, Any]]:
        """Return all drafts for one source document, newest first."""
        rows = [
            row
            for row in self._drafts.rows
            if int(row.get("source_document_id") or 0) == document_id
        ]
        return sorted(rows, key=lambda row: row.get("id") or 0, reverse=True)

    def list_all_drafts(
        self, status: str | None = None, ruleset_id: str | None = None
    ) -> list[dict[str, Any]]:
        """Return drafts across every source document, newest first.

        Used by extraction-accuracy consumers (e.g. the bim-guard-evaluation
        companion repo) that need approve/reject/edit outcomes system-wide,
        not one document at a time like :meth:`list_drafts`.
        """
        rows = list(self._drafts.rows)
        if status:
            rows = [row for row in rows if row.get("status") == status]
        if ruleset_id:
            rows = [
                row
                for row in rows
                if (row.get("proposed_rule") or {}).get("ruleset_id") == ruleset_id
            ]
        return sorted(rows, key=lambda row: row.get("id") or 0, reverse=True)

    def get_draft(self, draft_id: int) -> dict[str, Any] | None:
        """Return one draft row by primary key."""
        return self._drafts.get(draft_id)

    def review_draft(self, draft_id: int, payload: RuleDraftReviewRequest) -> dict[str, Any]:
        """Record an accept/reject/edit review decision on one draft."""
        existing = self.get_draft(draft_id)
        if existing is None:
            raise ValueError(f"Rule extraction draft {draft_id} not found")

        updates: dict[str, Any] = {
            "status": payload.status.value,
            "reviewer_email": payload.reviewer_email or "",
            "reviewed_at": now_iso_utc(),
            "review_notes": payload.review_notes or "",
        }
        if payload.status.value == "edited":
            if payload.edited_rule is None:
                raise ValueError("edited_rule is required when status is 'edited'")
            # Preserve the LLM's pre-edit proposed_rule the first time this
            # draft is edited, so the evaluation feedback loop can diff
            # "what the model produced" against "what the reviewer corrected
            # it to" -- a second edit does not overwrite the original again.
            if not existing.get("original_proposed_rule"):
                updates["original_proposed_rule"] = existing.get("proposed_rule")
            updates["proposed_rule"] = payload.edited_rule.model_dump()

        self._drafts.update(updates=updates, pk_values=draft_id)
        logger.info("Reviewed rule extraction draft draft_id=%d status=%s", draft_id, payload.status.value)
        return self.get_draft(draft_id) or {**existing, **updates}

    def relink_source_element(self, draft_id: int, element_id: str) -> dict[str, Any]:
        """Correct which element a draft is linked to, snapshotting the original link once.

        Mirrors `review_draft`'s `original_proposed_rule` snapshot: the first
        correction preserves what the LLM originally linked to in
        `original_source_element_id`, so the evaluation companion repo can
        score localization accuracy the same way it scores rule-content
        accuracy -- a second relink does not overwrite the original again.
        Recomputes `page_number`/`bbox` from the newly-picked element so the
        stored location stays consistent with `source_element_id`.
        """
        existing = self.get_draft(draft_id)
        if existing is None:
            raise ValueError(f"Rule extraction draft {draft_id} not found")

        from app.services.documents_service import DocumentService

        document_id = existing.get("source_document_id")
        doc = DocumentService().get_document(int(document_id)) if document_id else None
        if not doc:
            raise ValueError(f"Source document {document_id} for draft {draft_id} no longer exists")

        matched = next(
            (el for el in DocumentService().get_element_bboxes(doc) if el.get("element_id") == element_id),
            None,
        )
        if matched is None:
            raise ValueError(f"Element {element_id!r} not found in document {document_id}")

        updates: dict[str, Any] = {"source_element_id": element_id}
        # `is None` (not falsy) on purpose: once a draft has never been linked to
        # anything, the first relink snapshots that as "" -- a legitimate
        # snapshot, not "no snapshot yet". Treating "" as falsy here would make
        # every subsequent relink re-snapshot the *previous* link instead of
        # preserving the LLM's true original one.
        if existing.get("original_source_element_id") is None:
            updates["original_source_element_id"] = existing.get("source_element_id") or ""

        clause = dict(existing.get("clause") or {})
        clause["page_number"] = matched.get("page_number")
        clause["bbox"] = matched.get("bbox")
        updates["clause"] = clause
        updates["bbox"] = matched.get("bbox")

        self._drafts.update(updates=updates, pk_values=draft_id)
        logger.info("Relinked rule extraction draft draft_id=%d to element_id=%s", draft_id, element_id)
        return self.get_draft(draft_id) or {**existing, **updates}

    def promote_draft(self, draft_id: int) -> dict[str, Any]:
        """Insert an accepted/edited draft's proposed rule into `public.rules`.

        Delegates the actual insert to `RuleService.create_rule()` so the
        canonical rule table has exactly one write path, whether a rule came
        from the manual UI, `POST /api/rules/bulk`, or draft promotion.

        Refuses to promote a draft whose `target_ifc_class` is empty: such a
        rule can never match an IFC element, so writing it would silently
        reproduce the bug this same field's own promotion wiring had (fixed
        alongside this guard). Also refuses a draft whose `target_ifc_class`
        doesn't match any known bSDD/IFC entity (see
        RuleSemanticAlignmentService); non-blocking ontology-vocabulary
        warnings and cross-rule conflicts are attached to the returned dict
        as `alignment_issues`/`conflicts` and force `needs_review=1` on the
        created rule instead of blocking.
        """
        row = self.get_draft(draft_id)
        if row is None:
            raise ValueError(f"Rule extraction draft {draft_id} not found")
        if row.get("status") not in ("accepted", "edited"):
            raise ValueError(
                f"Draft {draft_id} must be 'accepted' or 'edited' before promotion "
                f"(status={row.get('status')!r})"
            )

        payload = RuleCreateRequest.model_validate(row.get("proposed_rule") or {})

        if not (payload.target_ifc_class or "").strip():
            raise ValueError(
                f"Draft {draft_id} has no target_ifc_class -- promoting it would write a rule "
                "that can never match any IFC element (see supabase/migrations/"
                "20260922164528_backfill_missing_target_ifc_class.sql for what that looked like "
                "in practice). Edit the draft to set an IFC entity type before accepting."
            )

        alignment: AlignmentResult = self._alignment_service.check(payload)
        if alignment.blocks_promotion:
            messages = "; ".join(issue.message for issue in alignment.issues if issue.severity == "blocking")
            raise ValueError(f"Draft {draft_id} failed ontology validation: {messages}")

        existing_duplicate = self._find_existing_duplicate(payload)
        if existing_duplicate is not None:
            self._drafts.update(updates={"promoted_rule_id": existing_duplicate.get("id")}, pk_values=draft_id)
            logger.info(
                "Skipped promoting rule extraction draft draft_id=%d: an equivalent rule "
                "already exists in ruleset_id=%s (existing_rule_id=%s) -- linked instead of duplicating",
                draft_id,
                payload.ruleset_id,
                existing_duplicate.get("id"),
            )
            return {**existing_duplicate, "alignment_issues": [], "conflicts": []}

        # A non-blocking alignment issue or a detected conflict doesn't stop
        # promotion (the reviewer already accepted/edited this draft), but it
        # does mean the resulting rule shouldn't look identical to a clean
        # one -- force needs_review so it surfaces the same way any other
        # uncertain extraction does.
        if alignment.issues or alignment.conflicts:
            payload.needs_review = 1

        clause_meta = row.get("clause") or {}
        created = self._rule_service.create_rule(
            rule_id=payload.rule_id,
            description=payload.description or "",
            source_text=row.get("source_snippet") or "",
            source_document_id=row.get("source_document_id"),
            source_node_id=row.get("source_node_id") or None,
            source_element_id=row.get("source_element_id") or clause_meta.get("element_id") or None,
            source_page_number=clause_meta.get("page_number"),
            source_bbox=row.get("bbox") or clause_meta.get("bbox"),
            target_ifc_class=payload.target_ifc_class or "",
            property_set=payload.property_set or "",
            property_name=payload.property_name or "",
            operator=payload.operator or "==",
            check_value=payload.check_value,
            value_min=payload.value_min,
            value_max=payload.value_max,
            value_min_property=payload.value_min_property or "",
            value_max_property=payload.value_max_property or "",
            value_min_offset=payload.value_min_offset or 0,
            value_max_offset=payload.value_max_offset or 0,
            compare_property=payload.compare_property or "",
            name_pattern=payload.name_pattern or "",
            uniqueness_scope=payload.uniqueness_scope or "",
            unit=payload.unit or "",
            severity=payload.severity,
            mechanism=payload.mechanism or "CODE",
            ruleset_id=payload.ruleset_id or "",
            rule_category=payload.rule_category or "property_check",
            category=payload.category or "",
            confidence=float(payload.confidence) if payload.confidence else 1.0,
            extraction_method=payload.extraction_method or "ai_extracted",
            needs_review=payload.needs_review,
            applies_when=payload.applies_when,
            exceptions=payload.exceptions,
            rase_requirement=payload.rase_requirement,
            rase_applicability=payload.rase_applicability,
            rase_selection=payload.rase_selection,
            rase_exception=payload.rase_exception,
        )

        self._drafts.update(updates={"promoted_rule_id": created.get("id")}, pk_values=draft_id)
        logger.info("Promoted rule extraction draft draft_id=%d rule_id=%s", draft_id, created.get("id"))
        return {
            **created,
            "alignment_issues": [issue.model_dump() for issue in alignment.issues],
            "conflicts": [conflict.model_dump() for conflict in alignment.conflicts],
        }

    def _find_existing_duplicate(self, payload: RuleCreateRequest) -> dict[str, Any] | None:
        """Find an existing rule in the same ruleset with the same check content, if any.

        Skipped entirely when the draft has no `ruleset_id` (nothing to
        dedupe against) or no `target_ifc_class`/`property_name` (too
        unspecific a key to safely treat as a duplicate match -- e.g. a
        count/relationship rule with no single property). Reads
        `rows_for_ruleset` uncached, the same idempotency-check pattern
        `app/services/ruleset_seeder.py` already established, since a
        cached read could miss a row another process just wrote.
        """
        ruleset_id = str(payload.ruleset_id or "").strip()
        if not ruleset_id or not payload.target_ifc_class or not payload.property_name:
            return None

        key = _duplicate_key(payload)
        for existing_row in self._rule_service.rows_for_ruleset(ruleset_id):
            existing_payload = RuleCreateRequest.model_construct(
                target_ifc_class=existing_row.get("target_ifc_class"),
                property_name=existing_row.get("property_name"),
                operator=existing_row.get("operator"),
                check_value=existing_row.get("check_value"),
                value_min=existing_row.get("value_min"),
                value_max=existing_row.get("value_max"),
            )
            if _duplicate_key(existing_payload) == key:
                return existing_row
        return None
