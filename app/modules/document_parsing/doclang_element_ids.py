"""Injects stable per-element ids into DocLang XML, paired with their bounding boxes.

Replaces positional (order-based) matching between the frontend's XML parse and
the backend's Docling-provenance bbox list with an explicit id embedded directly
in the DocLang XML at generation time. The id lives in the schema's documented
`<custom>` extension point (see doclang.xsd's `element_head` group) as an
attribute on a leaf child -- never as text content -- so it can never leak into
`itertext()`/`textContent`-based text extraction (`DocLangChunker.chunk()` on the
backend, `parseDoclangDocument()` on the frontend) the way a text node would.

    <text>
      <custom><bg_element_id value="elem-3"/></custom>
      Actual paragraph text stays untouched.
    </text>
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Any
from xml.etree.ElementTree import Element

import defusedxml.ElementTree as safe_ET
from defusedxml.common import DefusedXmlException

from app.logging_config import get_logger

logger = get_logger(__name__)

# Elements that get a stable id -- the same tag set (plus picture/figure, which
# never had bbox coverage before) that DocLangChunker.chunk() already walks for
# section-level bbox, so this reuses an already-proven matching order rather
# than inventing a new one.
_ID_ELIGIBLE_TAGS = {"heading", "table", "text", "paragraph", "p", "picture", "figure"}

# DocLang's documented element-head child order (doclang.xsd `element_head`
# group) -- `custom` must sort last among these when injected.
_HEAD_TAG_ORDER = ["label", "thread", "xref", "href", "layer", "location", "caption", "description", "summary", "custom"]

_KIND_BY_TAG = {
    "heading": "heading",
    "table": "table",
    "text": "paragraph",
    "paragraph": "paragraph",
    "p": "paragraph",
    "picture": "picture",
    "figure": "picture",
    "ldiv": "list",
}

# The coarse "kind" values _KIND_BY_TAG can ever produce -- callers building a
# bbox list to pair against this module's id-eligible XML walk (e.g.
# DoclingExtractor.extract_bytes) must filter to these same kinds first, or
# any bbox entry of a kind that never gets an id here (e.g. Docling's "list",
# from list_item) permanently shifts every bbox after it onto the wrong
# element -- assign_element_ids pairs the two lists by position, not identity.
ID_ELIGIBLE_KINDS = frozenset(_KIND_BY_TAG.values())


def _local_name(el: Element) -> str:
    return el.tag.lower().split("}")[-1]


def _has_selectable_content(elem: Element, tag: str) -> bool:
    if tag in ("table", "picture", "figure"):
        return True
    return bool("".join(elem.itertext()).strip())


def _inject_id(elem: Element, element_id: str) -> None:
    """Add `<custom><bg_element_id value="..."/></custom>` to `elem`, head-ordered.

    Uses an attribute (not text content) so it never contaminates
    `itertext()`-based extraction. Existing head-tag children (label/thread/
    etc.) are kept in their documented order, ahead of any other children.

    `elem`'s body text is *not* always `elem.text` -- for the common real-world
    shape `<text><location/>x4>Actual words</text>`, "Actual words" is stored
    by ElementTree as the last `<location>` child's `.tail`, not as `elem.text`
    (which only covers text before the *first* child). Left where it was, that
    tail would render *before* the re-appended `<custom>`, which the DocLang
    Schematron rules reject: element-head members must precede any
    non-whitespace text. So the trailing text -- from `elem.text` when there
    are no head children, or from the last head child's `.tail` otherwise --
    is moved onto `<custom>`'s own `.tail`, keeping its rendered position
    (right after the head span) while landing after `<custom>` instead of
    before it.
    """
    custom = ET.Element("custom")
    id_el = ET.SubElement(custom, "bg_element_id")
    id_el.set("value", element_id)

    children = list(elem)
    head = [c for c in children if _local_name(c) in _HEAD_TAG_ORDER]
    body = [c for c in children if _local_name(c) not in _HEAD_TAG_ORDER]
    head.sort(key=lambda c: _HEAD_TAG_ORDER.index(_local_name(c)))

    if head:
        last_head = head[-1]
        custom.tail = last_head.tail
        last_head.tail = None
    else:
        custom.tail = elem.text
        elem.text = None

    for c in children:
        elem.remove(c)
    for c in head:
        elem.append(c)
    elem.append(custom)
    for c in body:
        elem.append(c)


def _inject_ldiv_sibling_id(ldiv: Element, parent: Element, element_id: str) -> None:
    """Add a `<custom>` id sibling right after `ldiv`'s element-head span.

    Per doclang.xsd's `list_item` group (`ldiv, element_head?,
    virtual_text_content*`), a list item's own `<ldiv>` never has element-head
    children (its content model is `<marker>?` only) -- the head tags,
    `custom` included, are its SIBLINGS within the enclosing `<list>`,
    positioned between `<ldiv>` and whatever `<content>`/raw text/nested
    elements make up that item's body.
    """
    custom = ET.Element("custom")
    ET.SubElement(custom, "bg_element_id").set("value", element_id)

    children = list(parent)
    try:
        i = children.index(ldiv)
    except ValueError:
        return
    j = i + 1
    while j < len(children) and _local_name(children[j]) in _HEAD_TAG_ORDER and _local_name(children[j]) != "custom":
        j += 1
    parent.insert(j, custom)


def assign_element_ids(
    doclang_xml: str,
    element_bboxes: list[dict[str, Any]] | None = None,
) -> tuple[str, list[dict[str, Any]]]:
    """Inject a stable id into every selectable element and pair it with its bbox.

    Walks `doclang_xml` once, in document order, assigning `elem-{n}` ids to
    heading/paragraph/table/picture elements and zipping them positionally
    against `element_bboxes` (from `DoclingExtractor._bboxes_from_document`,
    itself in Docling's own reading-order via `iterate_items()`) -- both id
    assignment and bbox pairing happen in this single pass, so there is no
    separate order-matching step left for callers to get out of sync.

    Returns `(updated_doclang_xml, element_records)` where each record is
    `{"element_id", "kind", "page_number", "bbox", "order"}`. On any parse
    failure, returns the original XML unchanged and an empty list -- this is a
    best-effort enrichment, never a hard requirement for ingestion to succeed.
    """
    if not doclang_xml or not doclang_xml.strip():
        return doclang_xml, []

    try:
        root = safe_ET.fromstring(doclang_xml)
    except ET.ParseError as exc:
        logger.warning("Skipped DocLang element-id injection, XML parse error: %s", exc)
        return doclang_xml, []
    except DefusedXmlException as exc:
        logger.warning("Skipped DocLang element-id injection, unsafe XML: %s", exc)
        return doclang_xml, []

    bboxes = element_bboxes or []
    records: list[dict[str, Any]] = []

    try:
        # Snapshot the tree before mutating it -- .iter() is a live generator,
        # and inserting <custom> elements mid-walk (for the ldiv case below)
        # would otherwise revisit/skip nodes. The parent map is built from
        # this same pre-mutation snapshot, which is fine: insertions only add
        # new parent/child relationships, never change existing ones.
        elements = list(root.iter())
        parent_map = {child: parent for parent in elements for child in parent}

        for elem in elements:
            tag = _local_name(elem)

            if tag == "ldiv":
                # A list item's own <ldiv> never carries element-head children
                # (its content model is <marker>? only) -- see
                # _inject_ldiv_sibling_id. Every <ldiv>, self-closing or not,
                # corresponds to exactly one Docling list_item bbox entry.
                parent = parent_map.get(elem)
                if parent is None:
                    continue
                idx = len(records)
                element_id = f"elem-{idx + 1}"
                _inject_ldiv_sibling_id(elem, parent, element_id)
            elif tag in _ID_ELIGIBLE_TAGS and _has_selectable_content(elem, tag):
                idx = len(records)
                element_id = f"elem-{idx + 1}"
                _inject_id(elem, element_id)
            else:
                continue

            source = bboxes[idx] if idx < len(bboxes) else {}
            records.append(
                {
                    "element_id": element_id,
                    "kind": source.get("kind") or _KIND_BY_TAG.get(tag, "paragraph"),
                    "page_number": source.get("page_number"),
                    "bbox": source.get("bbox"),
                    "order": idx,
                }
            )
    except Exception:
        logger.warning("Failed injecting DocLang element ids; leaving XML unmodified", exc_info=True)
        return doclang_xml, []

    if not records:
        return doclang_xml, []

    updated_xml = ET.tostring(root, encoding="unicode")
    if doclang_xml.lstrip().startswith("<?xml"):
        updated_xml = '<?xml version="1.0" encoding="UTF-8"?>\n' + updated_xml
    return updated_xml, records
