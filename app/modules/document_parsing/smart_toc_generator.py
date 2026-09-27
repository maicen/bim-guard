"""Smart Table of Contents (TOC) Generator.

Provides PageIndex-style vectorless, layout- and reasoning-aware tree indexing
for architectural specifications, building codes, and technical regulatory documents.

Enriches raw section chunks with:
  1. Hierarchical outline tree topology (parent, children, sibling relationships).
  2. Bounded page ranges (start_page -> end_page).
  3. Extracted in-text cross-references (citations to other sections, tables, standards).
  4. Mapped target IFC classes (e.g. IfcDoor, IfcStair, IfcWall).
  5. Dense semantic summaries and domain topic tags per section.
"""

from __future__ import annotations

import re

from app.logging_config import get_logger
from app.modules.document_parsing.section_tree import build_section_tree

logger = get_logger(__name__)

# Cross-reference citation regex patterns
_SECTION_REF_PATTERN = re.compile(
    r"\b(?:Section|Article|Clause|Part)\s+(\d+(?:\.\d+)*[a-z]?)\b",
    re.IGNORECASE,
)
_TABLE_REF_PATTERN = re.compile(
    r"\b(?:Table)\s+(\d+(?:\.\d+)*(?:\.[A-Z0-9]+)?)\b",
    re.IGNORECASE,
)
_STANDARD_REF_PATTERN = re.compile(
    r"\b(NFPA\s*\d+|IBC\s*\d+|ISO\s*\d+(?:-\d+)?|ASTM\s*[A-Z0-9\-]+|EN\s*\d+|NBC\s*\d+)\b",
    re.IGNORECASE,
)

# Architectural keyword mapping to IFC entity classes
_IFC_CLASS_MAP: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\b(?:door|doors|doorway|doorways|threshold|panic hardware)\b", re.IGNORECASE), "IfcDoor"),
    (re.compile(r"\b(?:stair|stairs|stairway|stairways|stair flight|riser|risers|tread|treads)\b", re.IGNORECASE), "IfcStair"),
    (re.compile(r"\b(?:ramp|ramps|sloped walk)\b", re.IGNORECASE), "IfcRamp"),
    (re.compile(r"\b(?:handrail|handrails|guard|guards|railing|balustrade)\b", re.IGNORECASE), "IfcRailing"),
    (re.compile(r"\b(?:wall|walls|partition|partitions|firewall|fire wall)\b", re.IGNORECASE), "IfcWall"),
    (re.compile(r"\b(?:window|windows|glazing|vision panel)\b", re.IGNORECASE), "IfcWindow"),
    (re.compile(r"\b(?:corridor|corridors|hallway|aisle|exit access|space|room|vestibule)\b", re.IGNORECASE), "IfcSpace"),
    (re.compile(r"\b(?:opening|openings|penetration|duct penetration)\b", re.IGNORECASE), "IfcOpeningElement"),
    (re.compile(r"\b(?:ceiling|ceilings|cladding|finish|covering)\b", re.IGNORECASE), "IfcCovering"),
    (re.compile(r"\b(?:column|columns|pillar)\b", re.IGNORECASE), "IfcColumn"),
    (re.compile(r"\b(?:beam|beams|girder|lintel)\b", re.IGNORECASE), "IfcBeam"),
    (re.compile(r"\b(?:slab|floor|flooring|deck)\b", re.IGNORECASE), "IfcSlab"),
    (re.compile(r"\b(?:roof|roofing|parapet)\b", re.IGNORECASE), "IfcRoof"),
]

# Domain topic keywords for building codes & architectural specifications
_TOPIC_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\b(?:means of egress|egress|exit discharge|exit path|evacuation)\b", re.IGNORECASE), "Means of Egress"),
    (re.compile(r"\b(?:fire separation|fire resistance|fire rating|fire protection|fire-rated)\b", re.IGNORECASE), "Fire Protection"),
    (re.compile(r"\b(?:travel distance|common path of travel)\b", re.IGNORECASE), "Travel Distance"),
    (re.compile(r"\b(?:clear width|minimum width|corridor width|stair width|door width)\b", re.IGNORECASE), "Egress Width"),
    (re.compile(r"\b(?:accessibility|barrier-free|wheelchair|turning space|ada)\b", re.IGNORECASE), "Accessibility"),
    (re.compile(r"\b(?:handrail height|guard height|graspability)\b", re.IGNORECASE), "Guards & Handrails"),
    (re.compile(r"\b(?:illumination|emergency lighting|exit sign)\b", re.IGNORECASE), "Illumination & Signs"),
    (re.compile(r"\b(?:spatial separation|limiting distance|unprotected openings)\b", re.IGNORECASE), "Spatial Separation"),
    (re.compile(r"\b(?:plumbing|fixture counts|water closet|lavatory)\b", re.IGNORECASE), "Plumbing Fixtures"),
    (re.compile(r"\b(?:smoke barrier|smoke compartment|damper)\b", re.IGNORECASE), "Smoke Control"),
]


def extract_citations(text: str) -> list[str]:
    """Extract referenced sections, tables, and standards from text."""
    if not text:
        return []

    citations: set[str] = set()

    for m in _SECTION_REF_PATTERN.finditer(text):
        citations.add(f"Section {m.group(1)}")

    for m in _TABLE_REF_PATTERN.finditer(text):
        citations.add(f"Table {m.group(1)}")

    for m in _STANDARD_REF_PATTERN.finditer(text):
        citations.add(m.group(1).strip())

    return sorted(citations)


def extract_target_ifc_classes(text: str, name: str | None = None) -> list[str]:
    """Map architectural element mentions to standardized IFC entity classes."""
    combined = f"{name or ''} {text or ''}"
    classes: set[str] = set()
    for pattern, ifc_class in _IFC_CLASS_MAP:
        if pattern.search(combined):
            classes.add(ifc_class)
    return sorted(classes)


def extract_key_topics(text: str, name: str | None = None) -> list[str]:
    """Detect key building code and architectural compliance topic tags."""
    combined = f"{name or ''} {text or ''}"
    topics: set[str] = set()
    for pattern, topic in _TOPIC_PATTERNS:
        if pattern.search(combined):
            topics.add(topic)
    return sorted(topics)


def generate_extractive_summary(
    text: str,
    name: str | None = None,
    number: str | None = None,
    max_length: int = 180,
) -> str:
    """Generate a dense, PageIndex-style summary for a document section node.

    Extracts the core normative requirement or purpose sentence, prioritizing
    clauses with modal verbs ('shall', 'must', 'required').
    """
    cleaned = " ".join((text or "").split()).strip()
    if not cleaned:
        label = name or (f"Section {number}" if number else "Section")
        return f"Specification clause: {label}."

    # Look for the primary normative sentence
    sentences = re.split(r"(?<=[.!?])\s+", cleaned)
    normative_sentence = None
    for sentence in sentences:
        if re.search(r"\b(?:shall|must|required|prohibited|permitted|except)\b", sentence, re.IGNORECASE):
            normative_sentence = sentence.strip()
            break

    summary_text = normative_sentence or sentences[0].strip()
    if len(summary_text) > max_length:
        summary_text = summary_text[: max_length - 1].rstrip() + "…"

    return summary_text


def resolve_page_ranges(tree: list[dict], flat: list[dict]) -> None:
    """Compute continuous start and end page spans across the section tree.

    For leaf nodes without children, end_page equals start_page (or subsequent node's start).
    For parent nodes, the span is [min(children start_page), max(children end_page)].
    """
    # Create id-to-flat map
    flat_by_id = {node["id"]: node for node in flat}

    # Pass 1: Set end_page on flat entries based on next node's page_number
    total = len(flat)
    for i, node in enumerate(flat):
        start_p = node.get("page_number")
        if start_p is None:
            node["end_page_number"] = None
            continue

        # Look ahead for next valid page number
        next_p = None
        for j in range(i + 1, total):
            np = flat[j].get("page_number")
            if np is not None:
                next_p = np
                break

        if next_p is not None and next_p >= start_p:
            node["end_page_number"] = next_p
        else:
            node["end_page_number"] = start_p

    # Pass 2: Propagate to tree hierarchy and update parent spans
    def _postorder_tree(nodes: list[dict]) -> tuple[int | None, int | None]:
        for node in nodes:
            flat_item = flat_by_id.get(node["id"])
            children = node.get("children") or []

            if children:
                # Recurse children
                child_starts: list[int] = []
                child_ends: list[int] = []
                for child in children:
                    c_start, c_end = _postorder_tree([child])
                    if c_start is not None:
                        child_starts.append(c_start)
                    if c_end is not None:
                        child_ends.append(c_end)

                node_start = node.get("page_number")
                if node_start is not None:
                    child_starts.append(node_start)

                final_start = min(child_starts) if child_starts else node_start
                final_end = max(child_ends) if child_ends else (flat_item.get("end_page_number") if flat_item else None)

                node["page_number"] = final_start
                node["end_page_number"] = final_end
                if flat_item:
                    flat_item["page_number"] = final_start
                    flat_item["end_page_number"] = final_end
            else:
                if flat_item:
                    node["page_number"] = flat_item.get("page_number")
                    node["end_page_number"] = flat_item.get("end_page_number")

        # Return start and end for current batch if single node
        if len(nodes) == 1:
            return nodes[0].get("page_number"), nodes[0].get("end_page_number")
        return None, None

    _postorder_tree(tree)


_DOT_LEADER_LINE = re.compile(
    r"^([A-Za-z0-9]+(?:\.[A-Za-z0-9]+)*)?\s*(.*?)\s*(?:\.{2,}|…{2,}|\_{2,}|\-{2,}|\s{3,})\s*([ivxlcdm]+|\d+)\s*$",
    re.IGNORECASE,
)


def extract_dot_leader_entries(text: str) -> list[dict]:
    """Extract explicit TOC entries from text blocks with dot leaders.

    Matches lines like:
      '1.1 Scope and Administration .................... 12'
      'SECTION 1004 OCCUPANT LOAD .................. 240'
      'Table 1004.5 Floor Area Allowances .......... 242'
    """
    entries: list[dict] = []
    if not text:
        return entries
    for line in text.splitlines():
        line = line.strip()
        m = _DOT_LEADER_LINE.match(line)
        if m:
            num = (m.group(1) or "").strip()
            title = (m.group(2) or "").strip()
            page_str = m.group(3).strip()
            entries.append(
                {
                    "section_number": num or None,
                    "title": title or None,
                    "printed_page_number": page_str,
                }
            )
    return entries


def calibrate_page_offsets(tree: list[dict], flat: list[dict]) -> int | None:
    """Calibrate logical-to-physical page offsets between printed and physical PDF pages.

    Physical PDF Index = Printed TOC Page + Offset

    If a consistent offset vector is discovered (e.g. Roman numeral front matter causes
    body Chapter 1 printed on page 1 to appear on physical page 11), calibrates
    `printed_page_number` for all nodes where only physical `page_number` is known.
    """
    offsets: list[int] = []
    for node in flat:
        text = node.get("text", "")
        entries = extract_dot_leader_entries(text)
        if entries:
            for entry in entries:
                ref_num = entry.get("section_number")
                printed_p = entry.get("printed_page_number")
                if ref_num and printed_p and printed_p.isdigit():
                    p_int = int(printed_p)
                    for target in flat:
                        if target.get("section_number") == ref_num:
                            phys_p = target.get("page_number")
                            if phys_p is not None and phys_p >= p_int:
                                offsets.append(phys_p - p_int)
                                target["printed_page_number"] = str(p_int)

    if offsets:
        offsets.sort()
        median_offset = offsets[len(offsets) // 2]
        id_to_printed = {}
        for node in flat:
            if not node.get("printed_page_number") and node.get("page_number") is not None:
                calc_printed = node["page_number"] - median_offset
                if calc_printed >= 1:
                    node["printed_page_number"] = str(calc_printed)
            id_to_printed[node["id"]] = node.get("printed_page_number")

        def _sync_printed(nodes: list[dict]) -> None:
            for n in nodes:
                n["printed_page_number"] = id_to_printed.get(n["id"])
                _sync_printed(n.get("children") or [])

        _sync_printed(tree)
        return median_offset

    return None


def build_smart_toc(
    chunks: list[dict],
    *,
    page_numbers: list[int | None] | None = None,
) -> tuple[list[dict], list[dict]]:
    """Build a PageIndex-style Smart Table of Contents from document chunks.

    Transforms flat chunks into a rich hierarchical tree and flat registry,
    enriched with citations, IFC entities, topics, page spans, and summaries.

    Args:
        chunks: List of raw section dictionaries (from DocLangChunker or SectionChunker).
        page_numbers: Optional list of resolved page numbers matching chunks order.

    Returns:
        (tree, flat) with all enhanced PageIndex-style attributes populated.
    """
    tree, flat = build_section_tree(chunks)

    # Attach starting page numbers if provided
    if page_numbers and len(page_numbers) == len(flat):
        for node, page in zip(flat, page_numbers):
            node["page_number"] = page

    # Enrich each node with semantic and relational metadata
    for node in flat:
        text = node.get("text", "")
        name = node.get("section_name")
        number = node.get("section_number")

        node["citations"] = extract_citations(text)
        node["target_ifc_classes"] = extract_target_ifc_classes(text, name)
        node["key_topics"] = extract_key_topics(text, name)
        node["summary"] = generate_extractive_summary(text, name, number)
        node["printed_page_number"] = node.get("printed_page_number")

    # Propagate enriched attributes to tree nodes
    id_to_flat = {n["id"]: n for n in flat}

    def _sync_tree(nodes: list[dict]) -> None:
        for node in nodes:
            flat_item = id_to_flat.get(node["id"])
            if flat_item:
                node["summary"] = flat_item["summary"]
                node["citations"] = flat_item["citations"]
                node["target_ifc_classes"] = flat_item["target_ifc_classes"]
                node["key_topics"] = flat_item["key_topics"]
                node["printed_page_number"] = flat_item.get("printed_page_number")
            _sync_tree(node.get("children") or [])

    _sync_tree(tree)

    # Resolve bounding page ranges
    resolve_page_ranges(tree, flat)

    # Calibrate logical-to-physical page offsets
    calibrate_page_offsets(tree, flat)

    return tree, flat

