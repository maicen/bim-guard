"""Tests for LlamaIndexIngestor (clause metadata + deontic statement extraction)."""

import asyncio

from app.modules.contracts import ClauseMetadata, DeonticStatement, DocumentNodeContract
from app.modules.module1_doc_parser.llamaindex_ingestor import LlamaIndexIngestor

SAMPLE_TEXT = """9.8.2.1 Stair Width
Every stair shall have a minimum width of 900 mm.

9.8.2.2 Handrails
A handrail must be provided on at least one side.

9.8.3 Definitions
A stair is a series of steps connecting two levels.
"""


def test_nodes_from_text_attaches_clause_metadata():
    nodes = LlamaIndexIngestor().nodes_from_text(SAMPLE_TEXT, source_document_id=42)

    assert len(nodes) == 3
    assert all(isinstance(node, DocumentNodeContract) for node in nodes)
    assert nodes[0].metadata.clause_id == "9.8.2.1"
    assert nodes[0].metadata.source_document_id == 42
    assert nodes[0].metadata.parent_section == "9.8.2.1 Stair Width"
    assert "Every stair shall" in nodes[0].text


def test_nodes_from_text_empty_input_yields_no_nodes():
    assert LlamaIndexIngestor().nodes_from_text("", source_document_id=1) == []
    assert LlamaIndexIngestor().nodes_from_text("   ", source_document_id=1) == []


def test_nodes_from_text_detects_table_like_chunks():
    table_text = """9.9.1 Fixture Counts
Male   2   1
Female   2   1
Unisex   1   0
"""
    nodes = LlamaIndexIngestor().nodes_from_text(table_text, source_document_id=1)
    assert len(nodes) == 1
    assert nodes[0].metadata.node_type == "table"


def test_extract_deontic_statements_skips_non_deontic_nodes(monkeypatch):
    """Only nodes containing a deontic keyword should reach the LLM."""
    calls = []

    async def fake_extract(clause_text, *, clause):
        calls.append(clause_text)
        return DeonticStatement(
            text=clause_text.strip(),
            modality="shall",
            subject="IfcStairFlight",
            clause=clause,
        )

    monkeypatch.setattr(
        "app.modules.module1_doc_parser.llamaindex_program.extract_deontic_statement",
        fake_extract,
    )

    ingestor = LlamaIndexIngestor()
    nodes = ingestor.nodes_from_text(SAMPLE_TEXT, source_document_id=1)
    statements = asyncio.run(ingestor.extract_deontic_statements(nodes))

    # Only the two nodes containing "shall"/"must" should have been sent to the LLM;
    # the "Definitions" node contains neither keyword.
    assert len(calls) == 2
    assert len(statements) == 2
    assert all(isinstance(s, DeonticStatement) for s in statements)


def test_extract_deontic_statements_empty_nodes_short_circuits(monkeypatch):
    called = False

    async def fake_extract(*args, **kwargs):
        nonlocal called
        called = True

    monkeypatch.setattr(
        "app.modules.module1_doc_parser.llamaindex_program.extract_deontic_statement",
        fake_extract,
    )

    statements = asyncio.run(LlamaIndexIngestor().extract_deontic_statements([]))
    assert statements == []
    assert called is False


def test_clause_metadata_and_document_node_contract_roundtrip():
    clause = ClauseMetadata(
        clause_id="9.8.2.1",
        page_number=12,
        parent_section="Stair Width",
        section_path=["9", "9.8", "9.8.2.1"],
        node_type="paragraph",
        source_document_id=7,
    )
    node = DocumentNodeContract(node_id="abc-123", text="Every stair shall...", metadata=clause)
    assert node.model_dump()["metadata"]["clause_id"] == "9.8.2.1"
