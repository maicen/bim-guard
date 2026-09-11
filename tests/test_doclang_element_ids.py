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


LIST_DOCLANG_XML = """<?xml version="1.0" encoding="UTF-8"?>
<doclang>
  <list class="ordered">
    <ldiv><marker>9.8.2.</marker></ldiv>
    <location value="60" /><location value="52" /><location value="146" /><location value="57" />
    <content> Stair Dimensions</content>
  </list>
  <text>First paragraph.</text>
  <list class="ordered">
    <ldiv><marker>(2)</marker></ldiv>
    <location value="68" /><location value="88" /><location value="452" /><location value="94" />
    Required exit stairs shall have a width of not less than 860 mm.
    <ldiv />
    <location value="68" /><location value="115" /><location value="124" /><location value="121" />
    (a) 900 mm, or
  </list>
  <text>Second paragraph.</text>
</doclang>
"""

_LIST_BBOXES = [
    {"kind": "list", "page_number": 1, "bbox": {"l": 0, "t": 0, "r": 1, "b": 1, "coord_origin": "BOTTOMLEFT"}},
    {"kind": "paragraph", "page_number": 1, "bbox": None},
    {"kind": "list", "page_number": 1, "bbox": None},
    {"kind": "list", "page_number": 1, "bbox": None},
    {"kind": "paragraph", "page_number": 1, "bbox": None},
]


def test_assign_element_ids_covers_ldiv_list_items_interleaved_with_paragraphs():
    """Every <ldiv> gets its own id, in true document order.

    Both heading-shaped and plain-clause ldivs get ids, interleaved with the
    surrounding <text> elements -- not dropped, and not all lumped after the
    top-level elements.
    """
    updated_xml, records = assign_element_ids(LIST_DOCLANG_XML, _LIST_BBOXES)

    assert [r["element_id"] for r in records] == ["elem-1", "elem-2", "elem-3", "elem-4", "elem-5"]
    assert [r["kind"] for r in records] == ["list", "paragraph", "list", "list", "paragraph"]
    # elem-1 = the "9.8.2. Stair Dimensions" heading-shaped ldiv, elem-2 = the
    # first <text>, elem-3/elem-4 = the two clause ldivs ("(2)" and "(a)"),
    # elem-5 = the second <text> -- exactly Docling's reading order.
    assert records[0]["bbox"] == {"l": 0, "t": 0, "r": 1, "b": 1, "coord_origin": "BOTTOMLEFT"}


def test_assign_element_ids_places_custom_as_ldiv_sibling_not_child():
    """The injected <custom> must be a sibling of <ldiv>, never its child.

    <ldiv>'s content model is <marker>? only (doclang.xsd), so <custom> has
    to land within the enclosing <list>, positioned after <ldiv>'s trailing
    <location> siblings.
    """
    updated_xml, _records = assign_element_ids(LIST_DOCLANG_XML, _LIST_BBOXES)

    import xml.etree.ElementTree as ET

    root = ET.fromstring(updated_xml)
    first_list = root.find("list")
    ldiv = first_list.find("ldiv")
    assert ldiv.find("custom") is None, "custom must not be injected inside <ldiv>"
    children = list(first_list)
    ldiv_idx = children.index(ldiv)
    # custom sits right after ldiv's 4 <location> siblings, before <content>.
    assert [c.tag for c in children[ldiv_idx : ldiv_idx + 6]] == [
        "ldiv",
        "location",
        "location",
        "location",
        "location",
        "custom",
    ]


def test_assign_element_ids_output_is_schema_valid_doclang():
    """The injected XML must pass the real DocLang XSD + Schematron rules.

    Schematron enforces that element-head members (custom included) precede
    any non-whitespace text -- catches regressions in `_inject_id`'s handling
    of trailing body text stored as a head child's `.tail` rather than
    `elem.text` (the common real-world `<text><location/>x4>words</text>`
    shape), and in `_inject_ldiv_sibling_id`'s placement within `<list>`.
    """
    from app.modules.document_parsing.docling_extractor import DoclingExtractor

    updated_xml, _records = assign_element_ids(LIST_DOCLANG_XML, _LIST_BBOXES)
    assert DoclingExtractor.validate_doclang(updated_xml)


TRAILING_TEXT_DOCLANG_XML = """<?xml version="1.0" encoding="UTF-8"?>
<doclang>
  <text>
    <location value="60" /><location value="71" /><location value="454" /><location value="84" />
    Body text after four locations -- the realistic Docling-export shape.
  </text>
  <text>Body text with no locations at all.</text>
</doclang>
"""

_TRAILING_TEXT_BBOXES = [
    {"kind": "paragraph", "page_number": 1, "bbox": None},
    {"kind": "paragraph", "page_number": 1, "bbox": None},
]


def test_assign_element_ids_keeps_custom_before_trailing_text_after_locations():
    """<custom> must precede body text whether it's elem.text or a tail.

    Regression test for a bug where `_inject_id` re-appended existing
    `<location>` children (preserving their `.tail`, the real home of trailing
    body text in ElementTree) and then appended `<custom>` after them --
    landing `<custom>` *after* the body text, which the DocLang Schematron
    rules reject.
    """
    from app.modules.document_parsing.docling_extractor import DoclingExtractor

    updated_xml, records = assign_element_ids(TRAILING_TEXT_DOCLANG_XML, _TRAILING_TEXT_BBOXES)

    assert len(records) == 2
    assert DoclingExtractor.validate_doclang(updated_xml)

    # <custom> must appear before its own element's body text -- check each
    # <text> element directly rather than raw string offsets.
    import xml.etree.ElementTree as ET

    root = ET.fromstring(updated_xml)
    for text_el in root.findall("text"):
        rendered = ET.tostring(text_el, encoding="unicode")
        assert rendered.index("<custom>") < rendered.index("Body text")


def test_assign_element_ids_does_not_corrupt_chunker_text_extraction_for_lists():
    updated_xml, _records = assign_element_ids(LIST_DOCLANG_XML, _LIST_BBOXES)

    original_chunks = DocLangChunker().chunk(LIST_DOCLANG_XML)
    injected_chunks = DocLangChunker().chunk(updated_xml)

    assert len(original_chunks) == len(injected_chunks)
    for original, injected in zip(original_chunks, injected_chunks, strict=True):
        assert original["text"] == injected["text"]
        assert "elem-" not in injected["text"]


FIELD_FORMULA_CODE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<doclang>
  <heading level="1">Application Form</heading>
  <field_region>
    <field_item>
      <key>Name:</key>
      <value>John Smith</value>
    </field_item>
  </field_region>
  <formula>E = mc^2</formula>
  <code>print("hi")</code>
</doclang>
"""

_FIELD_FORMULA_CODE_BBOXES = [
    {"kind": "heading", "page_number": 1, "bbox": None},
    {"kind": "field", "page_number": 1, "bbox": None},
    {"kind": "formula", "page_number": 1, "bbox": None},
    {"kind": "code", "page_number": 1, "bbox": None},
]


def test_assign_element_ids_covers_field_region_formula_and_code():
    updated_xml, records = assign_element_ids(FIELD_FORMULA_CODE_XML, _FIELD_FORMULA_CODE_BBOXES)

    assert [r["element_id"] for r in records] == ["elem-1", "elem-2", "elem-3", "elem-4"]
    assert [r["kind"] for r in records] == ["heading", "field", "formula", "code"]
    assert 'bg_element_id value="elem-2"' in updated_xml

    # ids must not leak into chunker text extraction.
    chunks = DocLangChunker().chunk(updated_xml)
    assert not any("elem-" in c["text"] for c in chunks)
    assert any(c["node_type"] == "field_region" for c in chunks)
    assert any(c["node_type"] == "code" for c in chunks)


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
