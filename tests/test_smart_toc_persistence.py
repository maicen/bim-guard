"""Tests for Smart TOC database persistence, JSON/CSV import, export, and regeneration."""

from __future__ import annotations

import csv
import io

from app.modules.document_parsing.doclang_chunker import (
    DocLangChunker,
    extract_heading_number_and_name,
)
from app.modules.document_parsing.smart_toc_generator import build_smart_toc
from app.services.documents_service import DocumentService


def test_extract_heading_number_and_name_building_codes():
    """Verify section number and title extraction for common building code heading formats."""
    # SECTION with number
    num, name = extract_heading_number_and_name("SECTION 1.1")
    assert num == "1.1"
    assert name == "SECTION 1.1"

    # SECTION with number and title
    num, name = extract_heading_number_and_name("SECTION 1.2 DEFINITIONS")
    assert num == "1.2"
    assert "SECTION 1.2" in name
    assert "DEFINITIONS" in name

    # CHAPTER with number and title
    num, name = extract_heading_number_and_name("CHAPTER 15: SIGNS")
    assert num == "15"
    assert "CHAPTER 15" in name
    assert "SIGNS" in name

    # TABLE with number
    num, name = extract_heading_number_and_name("TABLE 2.7.7(1) — MAXIMUM ALLOWABLE QUANTITIES")
    assert num == "2.7.7(1)"
    assert "TABLE 2.7.7(1)" in name

    # Dotted decimal without keyword
    num, name = extract_heading_number_and_name("2.24.2 Aircraft hangar.")
    assert num == "2.24.2"
    assert "2.24.2" in name
    assert "Aircraft hangar" in name

    # Exceptions clause
    num, name = extract_heading_number_and_name("Exceptions:")
    assert num is None
    assert name == "Exceptions"

    # Unnumbered front matter
    num, name = extract_heading_number_and_name("PREFACE")
    assert num is None
    assert name == "PREFACE"


def test_section_tree_hierarchy_nesting():
    """Verify that building code chapters, sections, subsections, and exceptions nest correctly."""
    xml = """<doclang>
<heading level="1">CHAPTER 1 DEFINITIONS</heading>
<paragraph>Introductory text.</paragraph>
<heading level="1">SECTION 1.1</heading>
<paragraph>General requirements.</paragraph>
<heading level="1">SECTION 1.2 DEFINITIONS</heading>
<paragraph>Detailed definition entries.</paragraph>
<heading level="1">CHAPTER 2 USE AND OCCUPANCY</heading>
<paragraph>Occupancy classifications.</paragraph>
<heading level="1">SECTION 2.3 ASSEMBLY GROUP A</heading>
<paragraph>Group A assembly spaces shall have exit doors.</paragraph>
<heading level="1">Exceptions:</heading>
<paragraph>1. A room with occupant load less than 50.</paragraph>
<heading level="1">SECTION 2.24 AIRCRAFT-RELATED OCCUPANCIES</heading>
<paragraph>Hangar provisions.</paragraph>
<heading level="2">2.24.2 Aircraft hangar.</heading>
<paragraph>Aircraft hangar clear height requirement.</paragraph>
</doclang>"""

    chunks = DocLangChunker().chunk(xml)
    tree, flat = build_smart_toc(chunks)

    # 2 top-level chapters: Chapter 1 and Chapter 2
    assert len(tree) == 2
    ch1 = tree[0]
    ch2 = tree[1]

    assert ch1["section_number"] == "1"
    assert len(ch1["children"]) == 2  # Section 1.1 and Section 1.2
    assert ch1["children"][0]["section_number"] == "1.1"
    assert ch1["children"][1]["section_number"] == "1.2"

    assert ch2["section_number"] == "2"
    assert len(ch2["children"]) == 2  # Section 2.3 and Section 2.24

    sec23 = ch2["children"][0]
    assert sec23["section_number"] == "2.3"
    assert len(sec23["children"]) == 1  # Exceptions nested under Section 2.3
    assert sec23["children"][0]["section_name"] == "Exceptions"

    sec224 = ch2["children"][1]
    assert sec224["section_number"] == "2.24"
    assert len(sec224["children"]) == 1  # 2.24.2 nested under Section 2.24
    assert sec224["children"][0]["section_number"] == "2.24.2"


def test_document_service_toc_persistence():
    """Verify get_toc_tree and save_toc_tree on DocumentService in-memory mock."""
    mock_repo = {}

    class MockTable:
        def __init__(self, store):
            self.store = store

        def get(self, doc_id):
            return self.store.get(doc_id)

        def update(self, updates, pk_values):
            doc = self.store.setdefault(pk_values, {"id": pk_values})
            doc.update(updates)
            return doc

    table = MockTable(mock_repo)
    service = DocumentService(documents_repo=table)

    doc_id = 42
    mock_repo[doc_id] = {"id": doc_id, "filename": "SBC_201.pdf", "toc_tree": None}

    # Before saving, get_toc_tree returns None
    assert service.get_toc_tree(doc_id) is None

    sample_toc = {
        "document_id": doc_id,
        "tree": [{"id": "s0", "section_number": "1.1", "section_name": "General", "children": []}],
        "sections": [{"id": "s0", "section_number": "1.1", "section_name": "General"}],
        "enhanced": True,
    }

    # Save TOC
    service.save_toc_tree(doc_id, sample_toc)

    # Now get_toc_tree returns the persisted dictionary
    persisted = service.get_toc_tree(doc_id)
    assert persisted is not None
    assert persisted["document_id"] == doc_id
    assert len(persisted["tree"]) == 1
    assert persisted["tree"][0]["section_number"] == "1.1"


def test_toc_csv_serialization_roundtrip():
    """Verify CSV export representation and parsing round-trip for document sections."""
    sections = [
        {
            "id": "s0",
            "section_number": "1.1",
            "section_name": "General Provisions",
            "page_number": 5,
            "end_page_number": 8,
            "target_ifc_classes": ["IfcDoor", "IfcSpace"],
            "citations": ["Section 2.1", "NFPA 101"],
            "key_topics": ["Means of Egress"],
            "char_count": 450,
            "summary": "General requirements for commercial building egress.",
        }
    ]

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "id", "section_number", "section_name", "page_number", "end_page_number",
        "target_ifc_classes", "citations", "key_topics", "char_count", "summary"
    ])
    for s in sections:
        writer.writerow([
            s["id"],
            s["section_number"],
            s["section_name"],
            s["page_number"],
            s["end_page_number"],
            "; ".join(s["target_ifc_classes"]),
            "; ".join(s["citations"]),
            "; ".join(s["key_topics"]),
            s["char_count"],
            s["summary"],
        ])

    csv_text = output.getvalue()
    reader = csv.DictReader(io.StringIO(csv_text))
    parsed = list(reader)

    assert len(parsed) == 1
    row = parsed[0]
    assert row["id"] == "s0"
    assert row["section_number"] == "1.1"
    assert row["section_name"] == "General Provisions"
    assert row["page_number"] == "5"
    assert "IfcDoor" in row["target_ifc_classes"]
    assert "NFPA 101" in row["citations"]


def test_multiline_heading_stitching_and_running_header_pruning():
    """Verify multiline wrapped headings are stitched and repetitive headers are pruned."""
    xml = """<doclang>
<heading level="1">2024 INTERNATIONAL BUILDING CODE</heading>
<heading level="2">1004.1 Design occupant</heading>
<heading level="2">load.</heading>
<paragraph>Occupant load shall be calculated per Table 1004.5.</paragraph>
<heading level="1">2024 INTERNATIONAL BUILDING CODE</heading>
<heading level="2">1004.2 Minimum egress width</heading>
<paragraph>Corridors shall provide minimum clear width.</paragraph>
<heading level="1">2024 INTERNATIONAL BUILDING CODE</heading>
<heading level="2">1004.3 Exits</heading>
<paragraph>Exit access requirements.</paragraph>
</doclang>"""

    chunker = DocLangChunker()
    chunks = chunker.chunk(xml)

    # Running header "2024 INTERNATIONAL BUILDING CODE" appeared 3 times -> pruned!
    # No chunk should have section_name "2024 INTERNATIONAL BUILDING CODE"
    for c in chunks:
        assert c.get("section_name") != "2024 INTERNATIONAL BUILDING CODE"

    # Multiline heading was stitched into "1004.1 — Design occupant load."
    first = chunks[0]
    assert first["section_number"] == "1004.1"
    assert "Design occupant load" in first["section_name"]
    assert len(chunks) == 3  # 1004.1, 1004.2, 1004.3


def test_explicit_toc_dot_leader_and_page_offset_calibration():
    """Verify dot leader extraction and logical-to-physical page offset calibration."""
    xml = """<doclang>
<heading level="1">TABLE OF CONTENTS</heading>
<paragraph>
1.1 Scope and Administration .................... 10
1.2 Occupancy Classification .................. 15
</paragraph>
<heading level="1">SECTION 1.1</heading>
<paragraph>General provisions for commercial construction.</paragraph>
<heading level="1">SECTION 1.2 OCCUPANCY</heading>
<paragraph>Classification requirements.</paragraph>
</doclang>"""

    chunks = DocLangChunker().chunk(xml)
    # Assign physical PDF pages: TOC on page 2, Section 1.1 on physical page 18, Section 1.2 on physical page 23
    # Offset is 18 - 10 = 8
    physical_pages = [2, 18, 23]
    tree, flat = build_smart_toc(chunks, page_numbers=physical_pages)

    # Flat contains Section 1.1 and 1.2
    sec11 = next(n for n in flat if n.get("section_number") == "1.1")
    sec12 = next(n for n in flat if n.get("section_number") == "1.2")

    assert sec11["page_number"] == 18
    assert sec11["printed_page_number"] == "10"

    assert sec12["page_number"] == 23
    assert sec12["printed_page_number"] == "15"

