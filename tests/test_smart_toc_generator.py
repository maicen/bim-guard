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


def _chunk(number: str, name: str, text: str, page: int | None = None) -> dict:
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
