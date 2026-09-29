"""Check categories that group rule results under each element type.

The ordered category list (e.g. "Fire and Smoke Protection") lives in the
``rule_check_categories`` table, not in code; each rule references one entry
by name through ``rules.check_category``. ``rule_check_category_properties``
maps an element class + property name to its category, so a rule checking a
known property is categorised without anyone choosing.
"""

from typing import Any

from app.services.db_adapters import DatabaseAdapter
from app.services.persistence import PersistenceService

_CATEGORY_COLUMNS = {
    "id": int,
    "name": str,
    "description": str,
    "target_ifc_class": str,
    "sort_order": int,
    "created_at": str,
}

_PROPERTY_MAP_COLUMNS = {
    "id": int,
    "target_ifc_class": str,
    "property_name": str,
    "check_category": str,
    "created_at": str,
}


class RuleCheckCategoryService:
    """Read access to the ordered check-category list, plus name resolution."""

    def __init__(
        self,
        *,
        categories_repo: DatabaseAdapter | None = None,
        property_map_repo: DatabaseAdapter | None = None,
    ):
        """Bind the category and property-map tables (both injectable for tests)."""
        self._categories = (
            categories_repo
            if categories_repo is not None
            else PersistenceService.get_table("rule_check_categories", _CATEGORY_COLUMNS)
        )
        self._property_map = (
            property_map_repo
            if property_map_repo is not None
            else PersistenceService.get_table("rule_check_category_properties", _PROPERTY_MAP_COLUMNS)
        )

    def list_categories(self) -> list[dict[str, Any]]:
        """Return every category ordered by ``sort_order``, then ``id``."""
        rows = list(self._categories.rows)
        return sorted(rows, key=lambda r: (int(r.get("sort_order") or 0), int(r.get("id") or 0)))

    def names(self) -> list[str]:
        """Return the category names in display order."""
        return [str(r["name"]) for r in self.list_categories() if r.get("name")]

    def prompt_categories(self) -> list[dict[str, str]]:
        """Return ``{name, description, target_ifc_class}`` per category, in display order.

        Shape consumed by the extraction prompt; ``target_ifc_class`` is ""
        for a category offered to every element type.
        """
        return [
            {
                "name": str(r["name"]),
                "description": str(r.get("description") or ""),
                "target_ifc_class": str(r.get("target_ifc_class") or ""),
            }
            for r in self.list_categories()
            if r.get("name")
        ]

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

    def category_for_property(self, target_ifc_class: str | None, property_name: str | None) -> str | None:
        """Return the mapped category for a class + property (case-insensitive), or None."""
        cls = (target_ifc_class or "").strip().casefold()
        prop = (property_name or "").strip().casefold()
        if not cls or not prop:
            return None
        match = next(
            (
                r
                for r in self._property_map.rows
                if str(r.get("target_ifc_class") or "").casefold() == cls
                and str(r.get("property_name") or "").casefold() == prop
            ),
            None,
        )
        return self.resolve(match.get("check_category")) if match else None
