"""Tests for Smart Table of Contents (TOC) Generator and PageIndex-style indexing."""

from __future__ import annotations

from app.modules.document_parsing.smart_toc_generator import (
    build_smart_toc,
    extract_citations,
    extract_key_topics,
    extract_target_ifc_classes,
    generate_extractive_summary,
    resolve_page_ranges,
)


def _chunk(number: str, name: str, text: str = "body", page: int | None = None) -> dict:
    return {
        "section_number": number,
        "section_name": name,
        "text": text,
        "char_count": len(text),
        "page_number": page,
    }


def test_extract_citations():
    text = (
        "As outlined in Section 3.4.2 and Table 3.4.2.B, all fire doors must comply with NFPA 80. "
        "Further exceptions are defined in Article 9.10.1."
    )
    citations = extract_citations(text)
    assert "Section 3.4.2" in citations
    assert "Section 9.10.1" in citations
    assert "Table 3.4.2.B" in citations
    assert "NFPA 80" in citations


def test_extract_target_ifc_classes():
    text = "Exit doors serving a corridor must swing in the direction of egress."
    classes = extract_target_ifc_classes(text, name="Corridor Doors")
    assert "IfcDoor" in classes
    assert "IfcSpace" in classes

    stair_text = "Stairs with risers exceeding 200 mm must have continuous handrails on both sides."
    stair_classes = extract_target_ifc_classes(stair_text, name="Stair Flights")
    assert "IfcStair" in stair_classes
    assert "IfcRailing" in stair_classes


def test_extract_key_topics():
    text = "The minimum clear width of means of egress shall provide adequate travel distance to an exit."
    topics = extract_key_topics(text, name="Egress Width")
    assert "Means of Egress" in topics
    assert "Egress Width" in topics
    assert "Travel Distance" in topics


def test_generate_extractive_summary():
    text = (
        "This subsection covers general egress design principles for commercial buildings. "
        "Every exit door shall be readily openable from the inside without the use of a key or special knowledge. "
        "Additional guidance is available in the appendix."
    )
    summary = generate_extractive_summary(text, name="Exit Doors", number="3.4.1")
    # Must prioritize the normative requirement with "shall"
    assert "shall be readily openable" in summary


def test_build_smart_toc_full_flow():
    chunks = [
        _chunk("3", "CHAPTER 3 - FIRE PROTECTION AND MEANS OF EGRESS", "General chapter provisions.", page=10),
        _chunk(
            "3.4",
            "3.4 Doors and Corridors",
            "Exit doors in corridors must have a minimum clear width of 850 mm pursuant to Section 3.2.1.",
            page=12,
        ),
        _chunk(
            "3.4.1",
            "3.4.1 Hardware and Latching",
            "Doors shall be equipped with panic hardware conforming to Table 3.4.1.",
            page=14,
        ),
        _chunk("4", "CHAPTER 4 - ACCESSIBILITY", "Barrier-free paths must accommodate wheelchair turning.", page=20),
    ]

    tree, flat = build_smart_toc(chunks)

    # 2 chapters at root level
    assert len(tree) == 2
    assert tree[0]["section_number"] == "3"
    assert tree[1]["section_number"] == "4"

    # Chapter 3 page span should bound its children (pages 10 to 14)
    assert tree[0]["page_number"] == 10
    assert tree[0]["end_page_number"] >= 14

    # Section 3.4 metadata
    sec_3_4 = flat[1]
    assert "IfcDoor" in sec_3_4["target_ifc_classes"]
    assert "IfcSpace" in sec_3_4["target_ifc_classes"]
    assert "Section 3.2.1" in sec_3_4["citations"]
    assert "Egress Width" in sec_3_4["key_topics"]
    assert sec_3_4["summary"] is not None
    assert sec_3_4["end_page_number"] >= 12

    # Section 3.4.1 metadata
    sec_3_4_1 = flat[2]
    assert "Table 3.4.1" in sec_3_4_1["citations"]
    assert "panic hardware" in sec_3_4_1["summary"]


def test_resolve_page_ranges():
    tree = [
        {
            "id": "c1",
            "section_number": "1",
            "page_number": 5,
            "children": [
                {"id": "s1", "section_number": "1.1", "page_number": 5, "children": []},
                {"id": "s2", "section_number": "1.2", "page_number": 8, "children": []},
            ],
        },
        {
            "id": "c2",
            "section_number": "2",
            "page_number": 15,
            "children": [],
        },
    ]
    flat = [
        {"id": "c1", "section_number": "1", "page_number": 5},
        {"id": "s1", "section_number": "1.1", "page_number": 5},
        {"id": "s2", "section_number": "1.2", "page_number": 8},
        {"id": "c2", "section_number": "2", "page_number": 15},
    ]

    resolve_page_ranges(tree, flat)

    # c1 spans from page 5 to at least page 8 (or 15)
    assert tree[0]["page_number"] == 5
    assert tree[0]["end_page_number"] >= 8
    assert flat[1]["end_page_number"] == 8  # s1 ends where s2 starts


def test_smooth_page_numbers_eliminates_backwards_jumps():
    flat = [
        {"id": "s0", "page_number": 232},
        {"id": "s1", "page_number": 67},   # spurious backward jump
        {"id": "s2", "page_number": 235},
        {"id": "s3", "page_number": None},  # missing page
        {"id": "s4", "page_number": 255},
    ]
    from app.modules.document_parsing.smart_toc_generator import smooth_page_numbers

    smooth_page_numbers(flat)

    # s1 should be smoothed forward to 235
    assert flat[1]["page_number"] == 235
    # s3 should be interpolated
    assert flat[3]["page_number"] == 235 or flat[3]["page_number"] == 255


def test_extract_citations_comprehensive_building_codes():
    text = (
        "Pursuant to SBC 201 Section 2.7.2, assemblies tested in accordance with ASTM E 96 "
        "or ASTM C 1047 shall conform to Table 2.7.7(1). Refer also to SBC 801, ICC A117.1, "
        "and ASCE 7 Section 11.15."
    )
    citations = extract_citations(text)
    assert "Section 2.7.2" in citations
    assert "Section 11.15" in citations
    assert "Table 2.7.7(1)" in citations
    assert "ASTM E 96" in citations
    assert "ASTM C 1047" in citations
    assert "SBC 201" in citations
    assert "SBC 801" in citations
    assert "ICC A117.1" in citations
    assert "ASCE 7" in citations


def test_prefix_hierarchy_prevents_table_footnote_hijack():
    from app.modules.document_parsing.section_tree import build_section_tree

    chunks = [
        _chunk("2", "CHAPTER 2 - OCCUPANCY"),
        _chunk("2.3", "SECTION 2.3 - ASSEMBLY GROUP A"),
        {"section_number": None, "section_name": "REQUIRED SEPARATION OF OCCUPANCIES", "text": "Table text", "char_count": 10, "node_type": "table"},
        {"section_number": None, "section_name": "NP = Not permitted.", "text": "Footnote text", "char_count": 10, "node_type": "paragraph"},
        _chunk("2.4", "SECTION 2.4 - BUSINESS GROUP B"),
        _chunk("2.5", "SECTION 2.5 - EDUCATIONAL GROUP E"),
    ]

    tree, flat = build_section_tree(chunks)

    # Chapter 2 is root
    assert len(tree) == 1
    ch2 = tree[0]
    assert ch2["section_number"] == "2"

    # Section 2.4 and 2.5 MUST be direct children of Chapter 2, NOT nested under the table or footnote!
    child_numbers = [c.get("section_number") for c in ch2["children"]]
    assert "2.3" in child_numbers
    assert "2.4" in child_numbers
    assert "2.5" in child_numbers

    # Section 2.3 contains the table and footnote
    sec23 = next(c for c in ch2["children"] if c.get("section_number") == "2.3")
    sec23_child_names = [c.get("section_name") for c in sec23["children"]]
    assert "REQUIRED SEPARATION OF OCCUPANCIES" in sec23_child_names
    assert "NP = Not permitted." in sec23_child_names


def test_extract_dot_leader_entries_clean_numbers():
    from app.modules.document_parsing.smart_toc_generator import extract_dot_leader_entries

    toc_text = """
    CHAPTER 1 DEFINITIONS ................................................. 1
    SECTION 1.1 ........................................................... 1
    SECTION 1.2 DEFINITIONS ............................................... 1
    CHAPTER 2 USE AND OCCUPANCY CLASSIFICATION ............................ 17
    CHAPTER 15 SIGNS ...................................................... 299
    """
    entries = extract_dot_leader_entries(toc_text)
    assert len(entries) == 5

    assert entries[0]["section_number"] == "1"
    assert entries[0]["printed_page_number"] == "1"

    assert entries[1]["section_number"] == "1.1"
    assert entries[1]["printed_page_number"] == "1"

    assert entries[2]["section_number"] == "1.2"
    assert entries[2]["printed_page_number"] == "1"

    assert entries[3]["section_number"] == "2"
    assert entries[3]["printed_page_number"] == "17"

    assert entries[4]["section_number"] == "15"
    assert entries[4]["printed_page_number"] == "299"

