"""DocLang chunker for layout-aware, deterministic XML section extraction.

Parses DocLang (<doclang>) documents into section and clause chunks,
preserving OTSL table structures, section hierarchy, and bounding boxes.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from typing import Any

import defusedxml.ElementTree as safe_ET
from defusedxml.common import DefusedXmlException

from app.logging_config import get_logger

logger = get_logger(__name__)

_HEADING_NUM_PATTERN = re.compile(r"^(\d+(?:\.\d+)*)(?:[.)\s]+(.*))?$")


def parse_otsl_table(table_elem: ET.Element) -> tuple[list[list[str]], str]:
    """Parse an OTSL table element into a 2D matrix and a formatted text representation.

    OTSL (Optimized Table Structure Language) represents table grids using
    <fcel/> (field/cell separator) and <nl/> (newline separator).
    """
    raw_text = "".join(table_elem.itertext()).strip()

    # Split rows by <nl/> or <nl></nl>
    rows: list[list[str]] = []
    current_row: list[str] = []
    current_cell_parts: list[str] = []

    for child in table_elem:
        tag = child.tag.lower().split("}")[-1]  # Strip any XML namespace
        if tag == "fcel":
            if current_cell_parts:
                cell_text = " ".join("".join(current_cell_parts).split())
                if cell_text:
                    current_row.append(cell_text)
                current_cell_parts = []
            inner_text = "".join(child.itertext()).strip()
            if inner_text:
                current_cell_parts.append(inner_text)
            if child.tail and child.tail.strip():
                current_cell_parts.append(child.tail.strip())
        elif tag == "nl":
            if current_cell_parts:
                cell_text = " ".join("".join(current_cell_parts).split())
                if cell_text:
                    current_row.append(cell_text)
                current_cell_parts = []
            if current_row:
                rows.append(current_row)
                current_row = []
        else:
            text = "".join(child.itertext()).strip()
            if text:
                current_cell_parts.append(text)
            if child.tail and child.tail.strip():
                current_cell_parts.append(child.tail.strip())

    if current_cell_parts:
        cell_text = " ".join("".join(current_cell_parts).split())
        if cell_text:
            current_row.append(cell_text)
    if current_row:
        rows.append(current_row)

    # Filter out empty rows
    rows = [r for r in rows if any(c.strip() for c in r)]

    # If rows could not be parsed via tags, fall back to line splits
    if not rows and raw_text:
        lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
        rows = [[line] for line in lines]

    # Format into markdown-like table string for LLM readability
    if rows:
        col_count = max(len(r) for r in rows)
        padded_rows = [r + [""] * (col_count - len(r)) for r in rows]
        formatted_lines = []
        header = padded_rows[0]
        formatted_lines.append("| " + " | ".join(header) + " |")
        formatted_lines.append("| " + " | ".join(["---"] * col_count) + " |")
        for row in padded_rows[1:]:
            formatted_lines.append("| " + " | ".join(row) + " |")
        text_repr = "\n".join(formatted_lines)
    else:
        text_repr = raw_text

    return rows, text_repr


def _render_field_region(field_region: ET.Element) -> str:
    """Render a `<field_region>` element into readable `"key: value"` text.

    Per the spec (Fields section), `field_heading`/`field_item` need not be
    direct children of `field_region`, and a `field_item`'s own `key`
    (0 or 1) / `value` (0 or many) scope excludes descendants belonging to a
    *nested* field_item. We approximate that by only counting a `key`/`value`
    under the nearest enclosing `field_item`.
    """
    parent_map: dict[int, ET.Element] = {id(child): parent for parent in field_region.iter() for child in parent}

    def nearest_field_item(elem: ET.Element) -> ET.Element | None:
        current = parent_map.get(id(elem))
        while current is not None:
            if current.tag.lower().split("}")[-1] == "field_item":
                return current
            current = parent_map.get(id(current))
        return None

    lines: list[str] = []
    for elem in field_region.iter():
        tag = elem.tag.lower().split("}")[-1]
        if tag == "field_heading":
            text = "".join(elem.itertext()).strip()
            if text:
                lines.append(text)
        elif tag == "field_item":
            key_text = ""
            value_texts: list[str] = []
            for descendant in elem.iter():
                if descendant is elem:
                    continue
                if nearest_field_item(descendant) is not elem:
                    continue  # belongs to a nested field_item, not this one
                d_tag = descendant.tag.lower().split("}")[-1]
                if d_tag == "key" and not key_text:
                    key_text = "".join(descendant.itertext()).strip()
                elif d_tag == "value":
                    value_text = "".join(descendant.itertext()).strip()
                    if value_text:
                        value_texts.append(value_text)
            if key_text or value_texts:
                values_joined = "; ".join(value_texts)
                lines.append(f"{key_text}: {values_joined}" if key_text else values_joined)

    return "\n".join(lines)


class DocLangChunker:
    """Extracts structured sections, clauses, and OTSL tables from DocLang XML."""

    def __init__(self) -> None:
        """Initialize DocLangChunker."""
        pass

    def chunk(
        self,
        doclang_xml: str,
        element_bboxes: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        """Parse DocLang XML into structured section chunks.

        Args:
            doclang_xml: Raw XML string in DocLang format.
            element_bboxes: Optional list of element bounding boxes and page provenance.

        Returns:
            List of section chunk dicts with section_number, section_name, text,
            section_path, node_type, and optional bbox/page_number.
        """
        if not doclang_xml or not doclang_xml.strip():
            return []

        try:
            # DocLang XML comes straight from untrusted uploads (.dclg/.dclx) --
            # parse defensively against entity-expansion/external-entity attacks.
            root = safe_ET.fromstring(doclang_xml)
        except ET.ParseError as exc:
            logger.warning("DocLang XML parse error: %s -- falling back to empty chunks", exc)
            return []
        except DefusedXmlException as exc:
            logger.warning("DocLang XML rejected as unsafe: %s -- falling back to empty chunks", exc)
            return []

        chunks: list[dict[str, Any]] = []
        current_section_number: str | None = None
        current_section_name: str | None = None
        current_section_path: list[str] = []
        current_content_blocks: list[str] = []
        current_node_type: str = "paragraph"
        current_bbox: dict[str, Any] | None = None
        current_page_number: int | None = None

        # Level hierarchy tracker: {level_int: section_number}
        level_map: dict[int, str] = {}

        def flush_current_chunk():
            nonlocal current_content_blocks, current_node_type, current_bbox, current_page_number
            if not current_content_blocks:
                return
            combined_text = "\n\n".join(b for b in current_content_blocks if b.strip()).strip()
            if combined_text:
                chunks.append(
                    {
                        "section_number": current_section_number,
                        "section_name": current_section_name,
                        "text": combined_text,
                        "char_count": len(combined_text),
                        "section_path": list(current_section_path),
                        "node_type": current_node_type,
                        "bbox": current_bbox,
                        "page_number": current_page_number,
                    }
                )
            current_content_blocks = []
            current_node_type = "paragraph"
            current_bbox = None
            current_page_number = None

        bbox_idx = 0
        total_bboxes = len(element_bboxes) if element_bboxes else 0

        # `root.iter()` below is a flat, document-order walk over every
        # descendant -- it doesn't let a handler "consume" a subtree the way
        # a recursive walk would. `field_region` is handled as a single
        # self-contained block (like `table`), so its descendants (`text`,
        # `key`, `value`, ... per the spec's examples, some field content is
        # wrapped in `<text>`) must be excluded from the generic dispatch
        # below or they'd also be emitted as their own paragraph chunks.
        skip_ids: set[int] = set()
        for elem in root.iter():
            if elem.tag.lower().split("}")[-1] == "field_region":
                skip_ids.update(id(descendant) for descendant in elem.iter() if descendant is not elem)

        # Needed to tell an inline `<formula>`/`<code>` (nested inside a
        # `text`/`paragraph`/`item` run whose `itertext()` already captured
        # it) apart from a standalone block that needs its own chunk.
        parent_map: dict[int, ET.Element] = {
            id(child): parent for parent in root.iter() for child in parent
        }
        _TEXT_RUN_TAGS = {"text", "paragraph", "p", "item", "li"}

        for elem in root.iter():
            if id(elem) in skip_ids:
                continue
            tag = elem.tag.lower().split("}")[-1]  # Strip namespace

            if tag == "heading":
                # Flush previous content under prior heading
                flush_current_chunk()

                heading_text = "".join(elem.itertext()).strip()
                level_str = elem.attrib.get("level", "1")
                try:
                    level = int(level_str)
                except ValueError:
                    level = 1

                # Detect section number and name
                match = _HEADING_NUM_PATTERN.match(heading_text)
                if match:
                    sec_num = match.group(1)
                    sec_name = (match.group(2) or "").strip() or heading_text
                else:
                    sec_num = None
                    sec_name = heading_text

                # Update hierarchy
                level_map[level] = sec_num or heading_text
                # Purge deeper levels
                for deeper in list(level_map.keys()):
                    if deeper > level:
                        level_map.pop(deeper, None)

                current_section_path = [level_map[lvl] for lvl in sorted(level_map.keys())]
                current_section_number = sec_num
                current_section_name = sec_name
                current_content_blocks = [heading_text]
                current_node_type = "heading"

                # Check for element bbox
                if elem.attrib.get("bbox"):
                    # XML attribute bbox
                    pass
                elif total_bboxes > 0 and bbox_idx < total_bboxes:
                    current_bbox = element_bboxes[bbox_idx].get("bbox")
                    current_page_number = element_bboxes[bbox_idx].get("page_number")
                    bbox_idx += 1

            elif tag == "table":
                # An OTSL table
                _rows, table_text = parse_otsl_table(elem)
                if table_text.strip():
                    if current_content_blocks:
                        flush_current_chunk()
                    current_node_type = "table"
                    current_content_blocks.append(table_text)
                    if total_bboxes > 0 and bbox_idx < total_bboxes:
                        current_bbox = element_bboxes[bbox_idx].get("bbox")
                        current_page_number = element_bboxes[bbox_idx].get("page_number")
                        bbox_idx += 1
                    flush_current_chunk()

            elif tag in ("text", "paragraph", "p"):
                p_text = "".join(elem.itertext()).strip()
                if p_text:
                    current_content_blocks.append(p_text)
                    if current_bbox is None and total_bboxes > 0 and bbox_idx < total_bboxes:
                        current_bbox = element_bboxes[bbox_idx].get("bbox")
                        current_page_number = element_bboxes[bbox_idx].get("page_number")
                    if total_bboxes > 0 and bbox_idx < total_bboxes:
                        bbox_idx += 1

            elif tag in ("item", "li"):
                li_text = "".join(elem.itertext()).strip()
                if li_text:
                    current_content_blocks.append(f"- {li_text}")
                    if total_bboxes > 0 and bbox_idx < total_bboxes:
                        bbox_idx += 1

            elif tag == "field_region":
                field_text = _render_field_region(elem)
                if field_text.strip():
                    if current_content_blocks:
                        flush_current_chunk()
                    current_node_type = "field_region"
                    current_content_blocks.append(field_text)
                    if total_bboxes > 0 and bbox_idx < total_bboxes:
                        current_bbox = element_bboxes[bbox_idx].get("bbox")
                        current_page_number = element_bboxes[bbox_idx].get("page_number")
                        bbox_idx += 1
                    flush_current_chunk()

            elif tag == "formula":
                # Per the spec, <formula> is inline-capable (see doclang-spec-0.7.md
                # "All math is authored as LaTeX inside <formula> ... inlined
                # within a semantic element"). If it sits inside a text-run
                # element, that ancestor's itertext() already captured its
                # LaTeX -- only standalone formulas (parent outside a text
                # run) get their own paragraph-level content here.
                parent = parent_map.get(id(elem))
                parent_tag = parent.tag.lower().split("}")[-1] if parent is not None else ""
                if parent_tag not in _TEXT_RUN_TAGS:
                    latex = "".join(elem.itertext()).strip()
                    if latex:
                        current_content_blocks.append(f"$$ {latex} $$")

            elif tag == "code":
                # Same inline-vs-standalone distinction as <formula> above.
                parent = parent_map.get(id(elem))
                parent_tag = parent.tag.lower().split("}")[-1] if parent is not None else ""
                if parent_tag not in _TEXT_RUN_TAGS:
                    code_text = "".join(elem.itertext())
                    if code_text.strip():
                        if current_content_blocks:
                            flush_current_chunk()
                        current_node_type = "code"
                        current_content_blocks.append(code_text)
                        if total_bboxes > 0 and bbox_idx < total_bboxes:
                            current_bbox = element_bboxes[bbox_idx].get("bbox")
                            current_page_number = element_bboxes[bbox_idx].get("page_number")
                            bbox_idx += 1
                        flush_current_chunk()

        flush_current_chunk()
        logger.info("DocLangChunker extracted %d chunks from DocLang XML", len(chunks))
        return chunks
