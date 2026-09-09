"""Tests for DocLangChunker and OTSL table parsing."""

import xml.etree.ElementTree as ET

from app.modules.contracts import DocumentNodeContract
from app.modules.document_parsing.doclang_chunker import DocLangChunker, parse_otsl_table
from app.modules.document_parsing.llamaindex_ingestor import LlamaIndexIngestor

SAMPLE_DOCLANG_XML = """<?xml version="1.0" encoding="UTF-8"?>
<doclang>
  <heading level="1">9.8 Safety Requirements</heading>
  <text>All elements within this section shall conform to ISO standards.</text>
  <heading level="2">9.8.1 Stair Width</heading>
  <text>Every stair flight shall have a clear width of not less than 900 mm.</text>
  <item>Primary egress stairs require 1100 mm minimum.</item>
  <item>Secondary egress stairs require 900 mm minimum.</item>
  <heading level="2">9.8.2 Environmental Classifications</heading>
  <table>
    <fcel/>Category<fcel/>Description<fcel/>Corrosivity<nl/>
    <fcel/>C1<fcel/>Very Low<fcel/>Indoor heated<nl/>
    <fcel/>C3<fcel/>Medium<fcel/>Urban and industrial<nl/>
  </table>
</doclang>
"""


def test_parse_otsl_table_with_separators():
    xml_snippet = """<table>
      <fcel/>Col1<fcel/>Col2<nl/>
      <fcel/>ValA<fcel/>ValB<nl/>
    </table>"""
    elem = ET.fromstring(xml_snippet)
    rows, text_repr = parse_otsl_table(elem)

    assert len(rows) == 2
    assert rows[0] == ["Col1", "Col2"]
    assert rows[1] == ["ValA", "ValB"]
    assert "| Col1 | Col2 |" in text_repr
    assert "| ValA | ValB |" in text_repr


def test_parse_otsl_table_fallback():
    xml_snippet = "<table>Single row table text fallback</table>"
    elem = ET.fromstring(xml_snippet)
    rows, text_repr = parse_otsl_table(elem)

    assert len(rows) == 1
    assert "Single row table text fallback" in text_repr


def test_doclang_chunker_basic_chunking():
    chunker = DocLangChunker()
    chunks = chunker.chunk(SAMPLE_DOCLANG_XML)

    assert len(chunks) >= 3
    # Check section numbers and paths
    sec_nums = [c["section_number"] for c in chunks if c["section_number"]]
    assert "9.8" in sec_nums
    assert "9.8.1" in sec_nums
    assert "9.8.2" in sec_nums

    # Verify table chunk
    table_chunks = [c for c in chunks if c["node_type"] == "table"]
    assert len(table_chunks) == 1
    assert "| Category | Description | Corrosivity |" in table_chunks[0]["text"]
    assert "| C1 | Very Low | Indoor heated |" in table_chunks[0]["text"]


def test_doclang_chunker_empty_and_invalid():
    chunker = DocLangChunker()
    assert chunker.chunk("") == []
    assert chunker.chunk("   ") == []
    assert chunker.chunk("<not-closed-xml") == []


def test_doclang_chunker_with_bboxes():
    chunker = DocLangChunker()
    bboxes = [
        {"bbox": {"x": 10.0, "y": 20.0, "width": 100.0, "height": 30.0}, "page_number": 1},
        {"bbox": {"x": 10.0, "y": 60.0, "width": 200.0, "height": 40.0}, "page_number": 1},
        {"bbox": {"x": 10.0, "y": 110.0, "width": 150.0, "height": 25.0}, "page_number": 2},
    ]
    chunks = chunker.chunk(SAMPLE_DOCLANG_XML, element_bboxes=bboxes)
    assert len(chunks) > 0
    # First chunk has bbox
    assert chunks[0]["bbox"] is not None
    assert chunks[0]["page_number"] == 1


def test_llamaindex_nodes_from_doclang():
    ingestor = LlamaIndexIngestor()
    bboxes = [
        {"bbox": {"x": 50.0, "y": 100.0, "width": 200.0, "height": 25.0}, "page_number": 3}
    ]
    nodes = ingestor.nodes_from_doclang(
        SAMPLE_DOCLANG_XML,
        source_document_id=99,
        element_bboxes=bboxes,
    )

    assert len(nodes) >= 3
    assert all(isinstance(n, DocumentNodeContract) for n in nodes)
    assert all(n.metadata.source_document_id == 99 for n in nodes)
    assert any(n.metadata.clause_id == "9.8.1" for n in nodes)
    assert any(n.metadata.node_type == "table" for n in nodes)


def test_export_doclang_archive_endpoint(monkeypatch):
    import io
    import json
    import zipfile

    from starlette.testclient import TestClient

    from app.api.documents import get_documents_service
    from app.main import app

    client = TestClient(app, raise_server_exceptions=False)

    fake_doc = {
        "id": 123,
        "filename": "Sample_Standard.pdf",
        "doclang_xml": SAMPLE_DOCLANG_XML,
        "extracted_text": "Sample text",
        "project_code": "PRJ-01",
        "originator": "ENG",
        "cde_state": "SHARED",
        "suitability_code": "S1",
        "revision_code": "P01.01",
    }

    class FakeDocService:
        def get_document(self, doc_id):
            if doc_id == 123:
                return fake_doc
            return None

        def get_doclang_content(self, doc):
            return doc.get("doclang_xml") or ""

    app.dependency_overrides[get_documents_service] = lambda: FakeDocService()

    try:
        # 1. GET /api/documents/{id}/doclang
        res_xml = client.get("/api/documents/123/doclang")
        assert res_xml.status_code == 200
        assert "application/xml" in res_xml.headers["content-type"]
        assert '<heading level="1">9.8 Safety Requirements</heading>' in res_xml.text

        # 2. GET /api/documents/{id}/export-doclang
        res_dclx = client.get("/api/documents/123/export-doclang")
        assert res_dclx.status_code == 200
        assert res_dclx.headers["content-type"] == "application/zip"
        assert "Sample_Standard.dclx" in res_dclx.headers["content-disposition"]

        # Verify zip content
        zf = zipfile.ZipFile(io.BytesIO(res_dclx.content))
        namelist = zf.namelist()
        assert "document.xml" in namelist
        assert "manifest.json" in namelist
        manifest = json.loads(zf.read("manifest.json").decode("utf-8"))
        assert manifest["format"] == "doclang-archive"
        assert manifest["document_name"] == "Sample_Standard.pdf"
        assert manifest["metadata"]["cde_state"] == "SHARED"
    finally:
        app.dependency_overrides.pop(get_documents_service, None)


def test_document_service_get_doclang_content_storage_fallback(tmp_path):
    """Verify DocumentService.get_doclang_content resolves from storage when inline xml is empty."""
    from app.services.documents_service import DocumentService

    # Create dummy storage file
    xml_file = tmp_path / "doclang_999.xml"
    xml_file.write_text("<doclang>from storage</doclang>", encoding="utf-8")

    class FakeStorage:
        def materialize_local_path(self, ref):
            if ref == "sb://test-bucket/doclang/doclang_999.xml":
                return xml_file
            return None

    svc = DocumentService(storage=FakeStorage(), documents_repo=None)

    # 1. Inline xml takes precedence
    doc_inline = {"doclang_xml": "<doclang>inline</doclang>", "doclang_storage_path": None}
    assert svc.get_doclang_content(doc_inline) == "<doclang>inline</doclang>"

    # 2. Offloaded storage fallback when inline is empty
    doc_offloaded = {
        "doclang_xml": "",
        "doclang_storage_path": "sb://test-bucket/doclang/doclang_999.xml",
    }
    assert svc.get_doclang_content(doc_offloaded) == "<doclang>from storage</doclang>"

    # 3. None/missing returns empty string
    assert svc.get_doclang_content({}) == ""


