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


def test_document_service_auto_offloads_large_doclang_xml(monkeypatch):
    """Verify DocumentService offloads XML exceeding DOCLANG_OFFLOAD_THRESHOLD_BYTES to storage."""
    from app.services.documents_service import DOCLANG_OFFLOAD_THRESHOLD_BYTES, DocumentService

    inserted = []

    class FakeRepo:
        def insert(self, payload):
            record = dict(payload)
            record["id"] = 42
            inserted.append(record)
            return record

    uploads = []

    class FakeStorage:
        def save_upload(self, filename, content, subdir):
            ref = f"sb://bucket/{subdir}/{filename}"
            uploads.append((filename, len(content), ref))
            return ref

    svc = DocumentService(storage=FakeStorage(), documents_repo=FakeRepo())

    # 1. Large XML exceeding threshold -> offloaded to storage, inline xml set to "", archive pre-persisted
    large_xml = "<doclang>" + ("X" * (DOCLANG_OFFLOAD_THRESHOLD_BYTES + 100)) + "</doclang>"
    svc.create_document(
        md5_hash="abc1234567890",
        filename="big_standard.pdf",
        file_path="uploads/big.pdf",
        extracted_text="Text",
        doclang_xml=large_xml,
    )

    assert len(inserted) == 1
    assert inserted[0]["doclang_xml"] == ""  # offloaded, not stored in db row
    assert inserted[0]["doclang_storage_path"].startswith("sb://bucket/doclang/doclang_abc123456789.xml")
    assert inserted[0]["doclang_archive_path"].startswith("sb://bucket/doclang/archive_abc123456789.dclx")
    assert len(uploads) == 2  # xml blob + .dclx zip bundle

    # 2. Small XML under threshold -> kept inline, but .dclx bundle pre-persisted to storage
    small_xml = "<doclang><heading>Small</heading></doclang>"
    svc.create_document(
        md5_hash="small123",
        filename="small_standard.pdf",
        file_path="uploads/small.pdf",
        extracted_text="Text",
        doclang_xml=small_xml,
    )

    assert len(inserted) == 2
    assert inserted[1]["doclang_xml"] == small_xml
    assert inserted[1]["doclang_storage_path"] is None
    assert inserted[1]["doclang_archive_path"].startswith("sb://bucket/doclang/archive_small123.dclx")
    assert len(uploads) == 3  # 2 from previous + 1 .dclx archive


def test_export_doclang_archive_signed_redirect(monkeypatch):
    """Verify GET /api/documents/{id}/export-doclang?redirect=true redirects to signed URL."""
    from fastapi.testclient import TestClient

    from app.api.dependencies import get_documents_service
    from app.main import app

    client = TestClient(app)
    fake_doc = {
        "id": 888,
        "filename": "Spec.pdf",
        "doclang_xml": "<doclang><title>Test</title></doclang>",
        "doclang_archive_path": "sb://bucket/doclang/archive_888.dclx",
    }

    class FakeDocServiceWithRedirect:
        def get_document(self, doc_id):
            if doc_id == 888:
                return fake_doc
            return None

        def get_doclang_archive_signed_url(self, doc, expires_in=3600):
            return "https://pmisdhiigakpjfuyxgfb.supabase.co/storage/v1/object/sign/bim-guard-artifacts/archive_888.dclx?token=signed"

    app.dependency_overrides[get_documents_service] = lambda: FakeDocServiceWithRedirect()
    try:
        res = client.get("/api/documents/888/export-doclang?redirect=true", follow_redirects=False)
        assert res.status_code == 307
        assert "token=signed" in res.headers["location"]
    finally:
        app.dependency_overrides.pop(get_documents_service, None)




