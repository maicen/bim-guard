"""Tests for DocLang per-element id injection (doclang_element_ids.py)."""

from app.modules.document_parsing.doclang_chunker import DocLangChunker
from app.modules.document_parsing.doclang_element_ids import assign_element_ids

SAMPLE_DOCLANG_XML = """<?xml version="1.0" encoding="UTF-8"?>
<doclang>
  <heading level="1">9.8 Safety Requirements</heading>
  <text>All elements within this section shall conform to ISO standards.</text>
  <heading level="2">9.8.1 Stair Width</heading>
  <text>Every stair flight shall have a clear width of not less than 900 mm.</text>
  <item>Primary egress stairs require 1100 mm minimum.</item>
  <table>
    <fcel/>Category<fcel/>Description<nl/>
    <fcel/>C1<fcel/>Very Low<nl/>
  </table>
</doclang>
"""

_BBOXES = [
    {"kind": "heading", "page_number": 1, "bbox": {"l": 0, "t": 0, "r": 1, "b": 1, "coord_origin": "BOTTOMLEFT"}},
    {"kind": "paragraph", "page_number": 1, "bbox": None},
    {"kind": "heading", "page_number": 1, "bbox": None},
    {"kind": "paragraph", "page_number": 1, "bbox": None},
    {"kind": "table", "page_number": 2, "bbox": None},
]


def test_assign_element_ids_returns_one_record_per_selectable_element():
    updated_xml, records = assign_element_ids(SAMPLE_DOCLANG_XML, _BBOXES)

    assert [r["element_id"] for r in records] == ["elem-1", "elem-2", "elem-3", "elem-4", "elem-5"]
    assert [r["order"] for r in records] == [0, 1, 2, 3, 4]
    assert records[0]["kind"] == "heading"
    assert records[0]["bbox"] == {"l": 0, "t": 0, "r": 1, "b": 1, "coord_origin": "BOTTOMLEFT"}
    assert records[4]["kind"] == "table"
    assert records[4]["page_number"] == 2
    # <item> is deliberately not in _ID_ELIGIBLE_TAGS -- no record/id for it.
    assert 'bg_element_id value="elem-6"' not in updated_xml


def test_assign_element_ids_injects_custom_head_child_with_attribute_not_text():
    updated_xml, _records = assign_element_ids(SAMPLE_DOCLANG_XML, _BBOXES)

    assert '<custom><bg_element_id value="elem-1" /></custom>' in updated_xml
    assert '<custom><bg_element_id value="elem-5" /></custom>' in updated_xml


def test_assign_element_ids_does_not_corrupt_chunker_text_extraction():
    updated_xml, _records = assign_element_ids(SAMPLE_DOCLANG_XML, _BBOXES)

    original_chunks = DocLangChunker().chunk(SAMPLE_DOCLANG_XML)
    injected_chunks = DocLangChunker().chunk(updated_xml)

    assert len(original_chunks) == len(injected_chunks)
    for original, injected in zip(original_chunks, injected_chunks, strict=True):
        assert original["text"] == injected["text"]
        # "elem-N" must never leak into extracted chunk text.
        assert "elem-" not in injected["text"]


def test_assign_element_ids_handles_missing_bboxes_gracefully():
    updated_xml, records = assign_element_ids(SAMPLE_DOCLANG_XML, element_bboxes=None)

    assert len(records) == 5
    assert all(r["bbox"] is None and r["page_number"] is None for r in records)
    assert '<custom><bg_element_id value="elem-1" /></custom>' in updated_xml


def test_assign_element_ids_returns_original_xml_on_empty_input():
    updated_xml, records = assign_element_ids("", _BBOXES)
    assert updated_xml == ""
    assert records == []


def test_assign_element_ids_returns_original_xml_on_parse_error():
    malformed = "<doclang><heading>unterminated"
    updated_xml, records = assign_element_ids(malformed, _BBOXES)
    assert updated_xml == malformed
    assert records == []


def test_get_document_element_bboxes_endpoint():
    """GET /documents/{id}/element-bboxes returns the persisted per-element records."""
    from starlette.testclient import TestClient

    from app.api.documents import get_documents_service
    from app.main import app

    updated_xml, records = assign_element_ids(SAMPLE_DOCLANG_XML, _BBOXES)
    fake_doc = {"id": 42, "element_bboxes": records}

    class FakeDocService:
        def get_document(self, doc_id):
            return fake_doc if doc_id == 42 else None

        def get_element_bboxes(self, doc):
            return [r for r in (doc.get("element_bboxes") or []) if r.get("element_id")]

    client = TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides[get_documents_service] = lambda: FakeDocService()
    try:
        res = client.get("/api/documents/42/element-bboxes")
        assert res.status_code == 200
        body = res.json()
        assert body["document_id"] == 42
        assert [e["element_id"] for e in body["elements"]] == ["elem-1", "elem-2", "elem-3", "elem-4", "elem-5"]
        assert body["elements"][4]["kind"] == "table"

        res_missing = client.get("/api/documents/999/element-bboxes")
        assert res_missing.status_code == 404
    finally:
        app.dependency_overrides.pop(get_documents_service, None)


def test_get_document_asset_endpoint():
    """GET /documents/{id}/assets/{filename} streams an embedded picture from the .dclx archive."""
    from starlette.testclient import TestClient

    from app.api.documents import get_documents_service
    from app.main import app

    png_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
    fake_doc = {"id": 7, "filename": "Spec.pdf"}

    class FakeDocService:
        def get_document(self, doc_id):
            return fake_doc if doc_id == 7 else None

        def get_asset_bytes(self, doc, filename):
            if filename == "asset_1.png":
                return png_bytes
            return None

    client = TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides[get_documents_service] = lambda: FakeDocService()
    try:
        res = client.get("/api/documents/7/assets/asset_1.png")
        assert res.status_code == 200
        assert res.content == png_bytes
        assert res.headers["content-type"] == "image/png"

        res_missing = client.get("/api/documents/7/assets/does_not_exist.png")
        assert res_missing.status_code == 404
    finally:
        app.dependency_overrides.pop(get_documents_service, None)
