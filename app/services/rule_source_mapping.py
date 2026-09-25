"""Shared grouping logic for the rule-source map (and draft-source map, ruleset rollup).

Groups rows (rule or rule-extraction-draft dicts) that carry a
`source_element_id` against a document's *current* `DocumentElementBbox` list,
distinguishing three states so a stale link never silently disappears:

- exact: `source_element_id` matches one of `elements`.
- unmapped: no `source_element_id` at all (extracted before that linkage
  existed).
- orphaned: `source_element_id` is set but matches none of `elements` --
  almost always because the source document was re-parsed/re-uploaded and
  element ids shifted.
"""

from __future__ import annotations

from typing import Any

from app.modules.contracts import DocumentElementBbox


def group_rows_by_element(
    elements: list[DocumentElementBbox], rows: list[dict[str, Any]]
) -> tuple[dict[str, list[dict[str, Any]]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Split *rows* into (by_element, unmapped, orphaned) against *elements*.

    `by_element` is keyed by `source_element_id`, containing only rows whose
    id matches a current element. Every row in `rows` ends up in exactly one
    of the three outputs -- none are dropped.
    """
    known_ids = {el.element_id for el in elements}
    by_element: dict[str, list[dict[str, Any]]] = {}
    unmapped: list[dict[str, Any]] = []
    orphaned: list[dict[str, Any]] = []

    for row in rows:
        element_id = row.get("source_element_id")
        if not element_id:
            unmapped.append(row)
        elif element_id in known_ids:
            by_element.setdefault(element_id, []).append(row)
        else:
            orphaned.append(row)

    return by_element, unmapped, orphaned
