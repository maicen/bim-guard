"""Check categories that group rule results under each element type.

The ordered category list (e.g. "Fire and Smoke Protection") lives in the
``rule_check_categories`` table, not in code; each rule references one entry
by name through ``rules.check_category``.
"""

from typing import Any

from app.services.db_adapters import DatabaseAdapter
from app.services.persistence import PersistenceService

_CATEGORY_COLUMNS = {
    "id": int,
    "name": str,
    "sort_order": int,
    "created_at": str,
}


class RuleCheckCategoryService:
    """Read access to the ordered check-category list, plus name resolution."""

    def __init__(self, *, categories_repo: DatabaseAdapter | None = None):
        """Bind the ``rule_check_categories`` table (injectable for tests)."""
        self._categories = (
            categories_repo
            if categories_repo is not None
            else PersistenceService.get_table("rule_check_categories", _CATEGORY_COLUMNS)
        )

    def list_categories(self) -> list[dict[str, Any]]:
        """Return every category ordered by ``sort_order``, then ``id``."""
        rows = list(self._categories.rows)
        return sorted(rows, key=lambda r: (int(r.get("sort_order") or 0), int(r.get("id") or 0)))

    def names(self) -> list[str]:
        """Return the category names in display order."""
        return [str(r["name"]) for r in self.list_categories() if r.get("name")]

    def resolve(self, value: str | None) -> str | None:
        """Map a user- or LLM-supplied name to its stored spelling, or None.

        Matching ignores case and surrounding whitespace. Anything that is not
        a known category resolves to None (uncategorized) rather than being
        written through: ``rules.check_category`` is a foreign key, and an
        unknown name would fail the insert.
        """
        wanted = (value or "").strip().casefold()
        if not wanted:
            return None
        return next((name for name in self.names() if name.casefold() == wanted), None)
