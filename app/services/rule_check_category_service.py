"""Check categories that group rule results under each element type.

The ordered category list (e.g. "Fire and Smoke Protection") lives in the
``rule_check_categories`` table, not in code. Categories belong to element
types (``target_ifc_classes``; empty = every type) and the same name can
exist for several types, so each rule references one by id through
``rules.check_category_id``. ``rule_check_category_properties`` maps an
element class + property name to its category, so a rule checking a known
property is categorised without anyone choosing.
"""

from typing import Any

from app.services.db_adapters import DatabaseAdapter
from app.services.persistence import PersistenceService

_CATEGORY_COLUMNS = {
    "id": int,
    "name": str,
    "description": str,
    "target_ifc_classes": list,
    "sort_order": int,
    "created_at": str,
}

_PROPERTY_MAP_COLUMNS = {
    "id": int,
    "target_ifc_class": str,
    "property_name": str,
    "check_category_id": int,
    "created_at": str,
}


def _classes(row: dict[str, Any]) -> list[str]:
    return [str(c) for c in row.get("target_ifc_classes") or []]


def _applies_to(row: dict[str, Any], target_ifc_class: str | None) -> bool:
    """Return True when the category is offered for ``target_ifc_class`` (or for every type)."""
    classes = _classes(row)
    wanted = (target_ifc_class or "").strip().casefold()
    return not classes or not wanted or wanted in (c.casefold() for c in classes)


class RuleCheckCategoryService:
    """Read access to the ordered check-category list, plus id/name resolution."""

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

    def list_categories(self, target_ifc_class: str | None = None) -> list[dict[str, Any]]:
        """Return categories ordered by ``sort_order``, then ``id``.

        With ``target_ifc_class``, only those offered for that element type.
        """
        rows = [r for r in self._categories.rows if _applies_to(r, target_ifc_class)]
        return sorted(rows, key=lambda r: (int(r.get("sort_order") or 0), int(r.get("id") or 0)))

    def get(self, category_id: int | None) -> dict[str, Any] | None:
        """Return one category by id, or None."""
        if not category_id:
            return None
        return next((r for r in self._categories.rows if int(r.get("id") or 0) == int(category_id)), None)

    def applies_to(self, category_id: int, target_ifc_class: str | None) -> bool:
        """Return True when the category exists and is offered for ``target_ifc_class``."""
        row = self.get(category_id)
        return row is not None and _applies_to(row, target_ifc_class)

    def id_for_name(self, name: str | None, target_ifc_class: str | None) -> int | None:
        """Resolve a user- or LLM-supplied name, within the element type, to its id.

        Matching ignores case and surrounding whitespace; an unknown name, or
        one that only exists for another element type, resolves to None.
        """
        wanted = (name or "").strip().casefold()
        if not wanted:
            return None
        match = next(
            (r for r in self.list_categories(target_ifc_class) if str(r.get("name") or "").casefold() == wanted),
            None,
        )
        return int(match["id"]) if match else None

    def prompt_categories(self) -> list[dict[str, Any]]:
        """Return ``{id, name, description, target_ifc_classes}`` per category, in display order.

        Shape consumed by the extraction prompt and draft mapping.
        """
        return [
            {
                "id": int(r["id"]),
                "name": str(r.get("name") or ""),
                "description": str(r.get("description") or ""),
                "target_ifc_classes": _classes(r),
            }
            for r in self.list_categories()
            if r.get("name")
        ]

    def category_for_property(self, target_ifc_class: str | None, property_name: str | None) -> int | None:
        """Return the mapped category id for a class + property (case-insensitive), or None."""
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
        return int(match["check_category_id"]) if match and self.get(match.get("check_category_id")) else None
