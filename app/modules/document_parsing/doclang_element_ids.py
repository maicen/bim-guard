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
}


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
    etc.) are kept in their documented order, ahead of any other children;
    `elem`'s own leading text (`elem.text`, e.g. a paragraph's content) is a
    string attribute on `elem` itself in ElementTree's model, not a child node,
    so reordering children never touches it.
    """
    custom = ET.Element("custom")
    id_el = ET.SubElement(custom, "bg_element_id")
    id_el.set("value", element_id)

    children = list(elem)
    head = [c for c in children if _local_name(c) in _HEAD_TAG_ORDER]
    body = [c for c in children if _local_name(c) not in _HEAD_TAG_ORDER]
    head.sort(key=lambda c: _HEAD_TAG_ORDER.index(_local_name(c)))
    for c in children:
        elem.remove(c)
    for c in head:
        elem.append(c)
    elem.append(custom)
    for c in body:
        elem.append(c)


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
        for elem in root.iter():
            tag = _local_name(elem)
            if tag not in _ID_ELIGIBLE_TAGS or not _has_selectable_content(elem, tag):
                continue

            idx = len(records)
            element_id = f"elem-{idx + 1}"
            _inject_id(elem, element_id)

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
