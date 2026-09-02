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
from app.services.rules_service import RuleService
from app.utils import now_iso_utc

logger = get_logger(__name__)


class RuleDraftService:
    """CRUD + review workflow for `rule_extraction_drafts`."""

    def __init__(self, *, drafts_repo=None, rule_service: RuleService | None = None) -> None:
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
                },
            )
        )
        self._rule_service = rule_service if rule_service is not None else RuleService()

    def save_drafts(self, drafts: list[RuleExtractionDraft]) -> list[RuleExtractionDraft]:
        """Persist a batch of extraction drafts as `pending_review`, returning them with DB ids."""
        saved: list[RuleExtractionDraft] = []
        for draft in drafts:
            row = self._drafts.insert(
                {
                    "source_document_id": draft.source_document_id,
                    "source_node_id": draft.source_node_id or "",
                    "clause": draft.clause.model_dump() if draft.clause else None,
                    "proposed_rule": draft.proposed_rule.model_dump(),
                    "confidence": draft.confidence,
                    "extraction_method": draft.extraction_method,
                    "status": draft.status.value,
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
            updates["proposed_rule"] = payload.edited_rule.model_dump()

        self._drafts.update(updates=updates, pk_values=draft_id)
        logger.info("Reviewed rule extraction draft draft_id=%d status=%s", draft_id, payload.status.value)
        return self.get_draft(draft_id) or {**existing, **updates}

    def promote_draft(self, draft_id: int) -> dict[str, Any]:
        """Insert an accepted/edited draft's proposed rule into `public.rules`.

        Delegates the actual insert to `RuleService.create_rule()` so the
        canonical rule table has exactly one write path, whether a rule came
        from the manual UI, `POST /api/rules/bulk`, or draft promotion.
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
        created = self._rule_service.create_rule(
            rule_id=payload.rule_id,
            description=payload.description or "",
            source_text="",
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
        )

        self._drafts.update(updates={"promoted_rule_id": created.get("id")}, pk_values=draft_id)
        logger.info("Promoted rule extraction draft draft_id=%d rule_id=%s", draft_id, created.get("id"))
        return created
