"""GET /api/documents/{id}/sections-tree — deterministic tree + optional AI cleanup wiring."""

from __future__ import annotations

import llama_index.core.program as li_program
import pytest
from starlette.testclient import TestClient

from app.document_upload_validation import md5_hex
from app.main import app
from app.modules.document_parsing import llamaindex_program
from app.services.cache import cache_service
from app.services.documents_service import DocumentService

SAMPLE_DOCLANG_XML = """<?xml version="1.0" encoding="UTF-8"?>
<doclang>
  <heading level="1">9.8 Safety Requirements</heading>
  <text>All elements within this section shall conform to ISO standards.</text>
  <heading level="2">9.8.1 Stair Width</heading>
  <text>Every stair flight shall have a clear width of not less than 900 mm.</text>
</doclang>
"""


@pytest.fixture(scope="module")
def client() -> TestClient:
    """One test client for the FastAPI application."""
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def doclang_document():
    doc_service = DocumentService()
    created = doc_service.create_document(
        md5_hash=md5_hex(SAMPLE_DOCLANG_XML.encode()),
        filename="sections-tree-test.dclx",
        file_path="uploads/sections-tree-test.dclx",
        doc_type="Specification",
        doclang_xml=SAMPLE_DOCLANG_XML,
    )
    try:
        yield created
    finally:
        doc_service.delete_document(created["id"])
        cache_service.invalidate(f"section_tree:{created['id']}")


class _FakeOverride:
    def __init__(self, id: str, section_name: str):
        self.id = id
        self.section_name = section_name


class _FakeOverridesResult:
    def __init__(self, overrides):
        self.overrides = overrides


class _FakeProgram:
    def __init__(self, result=None, error: Exception | None = None):
        self._result = result
        self._error = error

    async def acall(self, **_kwargs):
        if self._error:
            raise self._error
        return self._result


def _patch_program(monkeypatch, program: _FakeProgram) -> None:
    def _from_defaults(*, output_cls, prompt_template_str, llm):
        return program

    monkeypatch.setattr(
        li_program.LLMTextCompletionProgram, "from_defaults", staticmethod(_from_defaults)
    )
    monkeypatch.setattr(llamaindex_program, "build_llm", lambda model=None, organization_id=None: None)


def test_sections_tree_applies_ai_relabel_and_syncs_flat_list(
    client: TestClient, doclang_document, monkeypatch
) -> None:
    doc_id = doclang_document["id"]
    _patch_program(
        monkeypatch,
        _FakeProgram(
            result=_FakeOverridesResult(
                overrides=[_FakeOverride(id="s0", section_name="Safety Requirements (Cleaned)")]
            )
        ),
    )

    response = client.get(f"/api/documents/{doc_id}/sections-tree")

    assert response.status_code == 200
    data = response.json()
    assert data["enhanced"] is True

    # Tree node relabeled...
    root = data["tree"][0]
    assert root["section_name"] == "Safety Requirements (Cleaned)"
    # ...and the flat "sections" list mirrors it, not the stale original title.
    flat_root = next(s for s in data["sections"] if s["section_number"] == "9.8")
    assert flat_root["section_name"] == "Safety Requirements (Cleaned)"

    # Untouched sibling keeps its deterministic title in both views.
    child = root["children"][0]
    assert child["section_name"] == "Stair Width"


def test_sections_tree_falls_back_when_ai_pass_fails(
    client: TestClient, doclang_document, monkeypatch
) -> None:
    doc_id = doclang_document["id"]
    _patch_program(monkeypatch, _FakeProgram(error=RuntimeError("LLM unavailable")))

    response = client.get(f"/api/documents/{doc_id}/sections-tree")

    assert response.status_code == 200
    data = response.json()
    assert data["enhanced"] is False
    assert data["tree"][0]["section_name"] == "Safety Requirements"
