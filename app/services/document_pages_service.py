"""Persistence for page-tagged document text (document viewer / rule-source annotation)."""

import re
from typing import Optional

from app.logging_config import get_logger
from app.services.persistence import PersistenceService

logger = get_logger(__name__)


def _normalize_for_match(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip().lower()


class DocumentPagesService:
    """CRUD for `document_pages` — independent of clause/section chunking."""

    def __init__(self, *, pages_repo=None):
        """Initialize the document_pages table adapter with dependency injection."""
        self._pages = (
            pages_repo
            if pages_repo is not None
            else PersistenceService.get_table(
                "document_pages",
                {
                    "id": int,
                    "document_id": int,
                    "page_number": int,
                    "text": str,
                    "char_count": int,
                },
            )
        )

    def save_pages(self, document_id: int, pages: list[dict]) -> None:
        """Persist a document's page-tagged text, replacing any existing rows."""
        if not pages:
            return
        rows = [
            {
                "document_id": document_id,
                "page_number": int(page["page_number"]),
                "text": page.get("text") or "",
                "char_count": len(page.get("text") or ""),
            }
            for page in pages
        ]
        if hasattr(self._pages, "insert_many"):
            self._pages.insert_many(rows)
        else:
            for row in rows:
                self._pages.insert(row)
        logger.info("Document pages stored document_id=%d pages=%d", document_id, len(rows))

    def get_pages(self, document_id: int) -> list[dict]:
        """Return all page rows for a document, ordered by page number."""
        rows = [row for row in self._pages.rows if int(row.get("document_id") or 0) == document_id]
        return sorted(rows, key=lambda row: int(row.get("page_number") or 0))

    @staticmethod
    def find_best_matching_page(pages: list[dict], snippet: str) -> Optional[int]:
        """Resolve which page's text a source snippet lives on.

        Whitespace-normalized substring match first (the common case — the
        snippet is a contiguous quote from one page); falls back to the page
        with the highest word-overlap ratio when no page contains it verbatim
        (e.g. the snippet spans a page break, or minor OCR/whitespace drift).

        Shared by both a promoted rule's `/rules/{id}/source` lookup
        (`source_text`) and a pre-promotion draft's `/rules/drafts/{id}/source`
        lookup (`source_snippet`) — same matching problem either way.
        """
        norm_snippet = _normalize_for_match(snippet)
        if not norm_snippet or not pages:
            return None

        for page in pages:
            if norm_snippet in _normalize_for_match(page.get("text", "")):
                return page.get("page_number")

        snippet_words = set(norm_snippet.split())
        if not snippet_words:
            return None

        best_page, best_score = None, 0.0
        for page in pages:
            page_words = set(_normalize_for_match(page.get("text", "")).split())
            if not page_words:
                continue
            overlap = len(snippet_words & page_words) / len(snippet_words)
            if overlap > best_score:
                best_score, best_page = overlap, page.get("page_number")

        return best_page if best_score > 0.3 else None
