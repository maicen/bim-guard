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


def test_doclang_chunker_field_region():
    xml = """<doclang>
  <heading level="1">Application Form</heading>
  <field_region>
    <field_heading>Personal Information</field_heading>
    <field_item>
      <key>Name:</key>
      <value>John Smith</value>
    </field_item>
    <field_item>
      <text><key>Email:</key></text>
      <text><value>john@example.com</value></text>
    </field_item>
    <field_item>
      <key>Phone Numbers:</key>
      <value>+1-555-0100</value>
      <value>+1-555-0101</value>
    </field_item>
  </field_region>
</doclang>"""
    chunker = DocLangChunker()
    chunks = chunker.chunk(xml)

    field_chunks = [c for c in chunks if c["node_type"] == "field_region"]
    assert len(field_chunks) == 1
    text = field_chunks[0]["text"]
    assert "Personal Information" in text
    assert "Name:: John Smith" in text
    assert "Email:: john@example.com" in text
    assert "Phone Numbers:: +1-555-0100; +1-555-0101" in text

    # field_region descendants (text/key/value) must not also surface as
    # their own generic paragraph chunks.
    assert not any("John Smith" in c["text"] for c in chunks if c is not field_chunks[0])


def test_doclang_chunker_standalone_formula_and_code():
    xml = """<doclang>
  <heading level="1">Physics</heading>
  <formula>E = mc^2</formula>
  <code><label>python</label><content>print("hi")</content></code>
  <text>Inline math <formula>a^2 + b^2 = c^2</formula> stays inline.</text>
</doclang>"""
    chunker = DocLangChunker()
    chunks = chunker.chunk(xml)

    assert any("$$ E = mc^2 $$" in c["text"] for c in chunks)
    code_chunks = [c for c in chunks if c["node_type"] == "code"]
    assert len(code_chunks) == 1
    assert 'print("hi")' in code_chunks[0]["text"]

    # Inline formula inside a <text> run should appear once, via the
    # paragraph's own text, not duplicated as a second standalone chunk.
    paragraph_chunks = [c for c in chunks if c["node_type"] == "paragraph"]
    assert any("a^2 + b^2 = c^2" in c["text"] for c in paragraph_chunks)
    assert sum(c["text"].count("a^2 + b^2 = c^2") for c in chunks) == 1


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


def test_doclang_asset_manager_extracts_and_offloads_base64():
    """Verify DocLangAssetManager extracts inline data URIs and replaces them with clean relative paths."""
    import base64

    from app.modules.document_parsing.doclang_asset_manager import DocLangAssetManager

    png_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
    b64_str = base64.b64encode(png_bytes).decode("ascii")

    xml_with_image = f"""<doclang>
  <heading level="1">Corrosion Details</heading>
  <p>Diagram below:</p>
  <image src="data:image/png;base64,{b64_str}" />
</doclang>"""

    saved_uploads = []

    class FakeStorage:
        def save_upload(self, filename, content, subdir):
            ref = f"sb://bucket/{subdir}/{filename}"
            saved_uploads.append((filename, content, ref))
            return ref

    sanitized_xml, extracted = DocLangAssetManager.extract_and_offload_assets(
        doclang_xml=xml_with_image,
        doc_key="doc999",
        storage=FakeStorage(),
    )

    assert 'src="assets/asset_1.png"' in sanitized_xml
    assert "data:image/png;base64" not in sanitized_xml
    assert len(extracted) == 1
    assert extracted[0]["filename"] == "asset_1.png"
    assert extracted[0]["asset_bytes"] == png_bytes
    assert len(saved_uploads) == 1
    assert saved_uploads[0][0] == "asset_1.png"
    assert saved_uploads[0][1] == png_bytes


def test_create_document_packages_multimodal_assets_in_dclx():
    """Verify create_document packages extracted assets directly inside the .dclx zip archive."""
    import base64
    import io
    import zipfile

    from app.services.documents_service import DocumentService

    png_bytes = b"fake-png-data"
    b64_str = base64.b64encode(png_bytes).decode("ascii")

    xml_with_img = f'<doclang><figure src="data:image/png;base64,{b64_str}" /></doclang>'

    uploads = {}

    class FakeStorage:
        def save_upload(self, filename, content, subdir):
            ref = f"sb://bucket/{subdir}/{filename}"
            uploads[ref] = content
            return ref

    class FakeRepo:
        def insert(self, payload):
            record = dict(payload)
            record["id"] = 101
            return record

    svc = DocumentService(storage=FakeStorage(), documents_repo=FakeRepo())
    doc = svc.create_document(
        md5_hash="multimodal123456",
        filename="multimodal_spec.pdf",
        file_path="uploads/spec.pdf",
        doclang_xml=xml_with_img,
    )

    archive_ref = doc["doclang_archive_path"]
    assert archive_ref in uploads

    # Inspect zip bundle content
    archive_bytes = uploads[archive_ref]
    zf = zipfile.ZipFile(io.BytesIO(archive_bytes))
    namelist = zf.namelist()
    assert "document.xml" in namelist
    assert "manifest.json" in namelist
    assert "assets/asset_1.png" in namelist
    assert zf.read("assets/asset_1.png") == png_bytes


def test_validate_document_upload_dclg():
    """Verify validate_document_upload accepts valid .dclg XML and rejects invalid content/MIME."""
    from app.utils import validate_document_upload

    valid_xml = b"<?xml version=\"1.0\"?><doclang><heading>Test</heading></doclang>"

    # 1. Valid .dclg with standard XML MIME types
    assert validate_document_upload("spec.dclg", "text/xml", valid_xml) is None
    assert validate_document_upload("spec.dclg", "application/xml", valid_xml) is None
    assert validate_document_upload("spec.dclg", "text/plain", valid_xml) is None
    assert validate_document_upload("spec.dclg", "application/octet-stream", valid_xml) is None

    # 2. Invalid MIME type
    err = validate_document_upload("spec.dclg", "image/png", valid_xml)
    assert err is not None and "Invalid MIME type" in err

    # 3. Invalid non-XML text
    not_xml = b"This is plain text without starting tag"
    err = validate_document_upload("spec.dclg", "text/xml", not_xml)
    assert err is not None and "does not look like DocLang XML" in err

    # 4. Binary null bytes in XML
    binary_content = b"<doclang>\x00\x01\x02</doclang>"
    err = validate_document_upload("spec.dclg", "text/xml", binary_content)
    assert err is not None and "must be UTF-8 encoded XML text" in err


def test_validate_document_upload_dclx():
    """Verify validate_document_upload accepts valid .dclx zip archives and rejects non-zip content."""
    import io
    import zipfile

    from app.utils import validate_document_upload

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("document.xml", "<doclang>Test</doclang>")
    valid_zip_bytes = buf.getvalue()

    # 1. Valid .dclx archive
    assert validate_document_upload("archive.dclx", "application/zip", valid_zip_bytes) is None
    assert validate_document_upload("archive.dclx", "application/x-zip-compressed", valid_zip_bytes) is None
    assert validate_document_upload("archive.dclx", "application/octet-stream", valid_zip_bytes) is None

    # 2. Invalid MIME type
    err = validate_document_upload("archive.dclx", "text/plain", valid_zip_bytes)
    assert err is not None and "Invalid MIME type" in err

    # 3. Invalid signature (non-zip)
    err = validate_document_upload("archive.dclx", "application/zip", b"not-a-zip-file")
    assert err is not None and "match a valid .dclx (zip) signature" in err


def test_validate_document_upload_unsupported_suffix_mentions_dclg_and_dclx():
    """Verify unsupported file type message lists .dclg and .dclx."""
    from app.utils import validate_document_upload

    err = validate_document_upload("file.xyz", "application/octet-stream", b"dummy")
    assert err is not None
    assert ".dclg" in err
    assert ".dclx" in err


def test_document_service_ingests_dclg_and_dclx(tmp_path):
    """Verify DocumentService ingests raw XML for .dclg and unpacks document.xml for .dclx."""
    import io
    import zipfile

    from app.services.documents_service import DocumentService

    inserted = []

    class FakeRepo:
        def insert(self, payload):
            record = dict(payload)
            record["id"] = len(inserted) + 1
            inserted.append(record)
            return record

        def rows_where(self, *args, **kwargs):
            return []

    class FakeStorage:
        def save_upload(self, filename, content, subdir):
            return f"sb://bucket/{subdir}/{filename}"

    svc = DocumentService(storage=FakeStorage(), documents_repo=FakeRepo())
    # Mock store_document_file
    svc.store_document_file = lambda fname, content: f"uploads/{fname}"

    # 1. Ingest .dclg
    dclg_content = b"<doclang><heading>DocLang Direct</heading></doclang>"
    row_dclg, created = svc.ingest_uploaded_bytes("test_doc.dclg", dclg_content)
    assert created is True
    assert row_dclg["doclang_xml"] == "<doclang><heading>DocLang Direct</heading></doclang>"

    # 2. Ingest .dclx
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("document.xml", "<doclang><title>Archive Unpacked</title></doclang>")
        zf.writestr("manifest.json", '{"entrypoint": "document.xml"}')
    dclx_bytes = buf.getvalue()

    row_dclx, created = svc.ingest_uploaded_bytes("test_archive.dclx", dclx_bytes)
    assert created is True
    assert row_dclx["doclang_xml"] == "<doclang><title>Archive Unpacked</title></doclang>"




