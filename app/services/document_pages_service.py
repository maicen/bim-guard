"""Persistence for page-tagged document text (document viewer / rule-source annotation)."""

from app.logging_config import get_logger
from app.services.persistence import PersistenceService

logger = get_logger(__name__)


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
