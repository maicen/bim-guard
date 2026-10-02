"""Unit tests for app.api.documents._no_parsing_engine_detail's permission-aware messaging."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api.documents import _no_parsing_engine_detail, confirm_document_upload
from app.modules.document_parsing.document_extractor import NoParsingEngineConfiguredError
from app.modules.permissions import Action
from app.modules.contracts import DocumentConfirmRequest


class _FakePermissions:
    def __init__(self, allowed: bool):
        self._allowed = allowed

    def can(self, organization_id: int, user_id: str, action: Action) -> bool:
        assert action == Action.MANAGE_PARSING_ENGINES
        return self._allowed


def test_self_serve_message_when_caller_can_manage_parsing_engines():
    current_user = SimpleNamespace(id="owner-1")
    detail = _no_parsing_engine_detail(1, current_user, _FakePermissions(allowed=True))
    assert "External Providers" in detail
    assert "ask" not in detail.lower()


def test_ask_admin_message_when_caller_cannot_manage_parsing_engines():
    current_user = SimpleNamespace(id="member-1")
    detail = _no_parsing_engine_detail(1, current_user, _FakePermissions(allowed=False))
    assert "ask an organization owner or admin" in detail.lower()


def test_ask_admin_message_when_no_organization_context():
    current_user = SimpleNamespace(id="anon-1")
    detail = _no_parsing_engine_detail(None, current_user, _FakePermissions(allowed=True))
    assert "ask an organization owner or admin" in detail.lower()


class _FakeInstances:
    def __init__(self, exc: Exception = None):
        self._exc = exc

    def get_default(self, organization_id):
        if self._exc:
            raise self._exc
        return {"name": "docling-local", "kind": "docling-local", "api_url": "http://localhost:5001"}

    def get_instance(self, name, organization_id):
        if self._exc:
            raise self._exc
        return {"name": "docling-local", "kind": "docling-local", "api_url": "http://localhost:5001"}


class _FakeDocumentService:
    def register_pending_document(self, *args, **kwargs):
        return {"id": 123}, True
    
    def process_pending_document_background(self, *args, **kwargs):
        pass


def _upload_with(exc: Exception) -> HTTPException:
    from fastapi import BackgroundTasks
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            confirm_document_upload(
                payload=DocumentConfirmRequest(
                    file_name="spec.pdf",
                    storage_reference="some_ref",
                    doc_type="Specification",
                    project_code="",
                    suitability_code="S0",
                    revision_code="P01.01",
                    parser="auto",
                    generate_doclang=True,
                    organization_id=None,
                ),
                background_tasks=BackgroundTasks(),
                service=_FakeDocumentService(),
                instances_service=_FakeInstances(exc),
                document_access=object(),
                memberships=object(),
                profiles=object(),
                permissions=_FakePermissions(allowed=True),
                current_user=None,
            )
        )
    return exc_info.value


def test_upload_reports_unreachable_engine_as_502_with_the_real_cause():
    cause = ConnectionError("Service transport request failed.")
    failure = NoParsingEngineConfiguredError(
        "spec.pdf", had_instance=True, instance_name="docling-local", cause=cause
    )
    err = _upload_with(failure)
    assert err.status_code == 502
    assert "docling-local" in err.detail
    assert "Service transport request failed" in err.detail
    assert "configure" not in err.detail.lower()


def test_upload_keeps_422_when_no_engine_is_resolved_at_all():
    err = _upload_with(NoParsingEngineConfiguredError("spec.pdf", had_instance=False))
    assert err.status_code == 422
    assert "parsing engine" in err.detail.lower()


# --- which organization's LLM key an AI call on a document uses ---------------


def _org_resolution(requested=None, header=None, *, user_orgs=(1,), grants=None, superadmin=False, doc=None):
    from unittest.mock import MagicMock

    from app.api.documents import _resolve_llm_organization_id

    memberships = MagicMock()
    memberships.org_ids_for_user.return_value = set(user_orgs)
    document_access = MagicMock()
    document_access.list_org_grants.side_effect = lambda oid: (grants or {}).get(oid, [])
    profiles = MagicMock()
    profiles.is_superadmin.return_value = superadmin
    user = SimpleNamespace(id="user-1")
    return _resolve_llm_organization_id(
        500, doc or {}, requested, header, user, memberships, document_access, profiles
    )


def test_llm_org_uses_the_requested_organization_when_the_caller_belongs_to_it():
    assert _org_resolution(requested=2, user_orgs=(1, 2)) == 2
    assert _org_resolution(header="2", user_orgs=(1, 2)) == 2


def test_llm_org_refuses_an_organization_the_caller_does_not_belong_to():
    with pytest.raises(HTTPException) as exc_info:
        _org_resolution(requested=9, user_orgs=(1, 2))
    assert exc_info.value.status_code == 403
    # ... but a superadmin may act for any organization.
    assert _org_resolution(requested=9, user_orgs=(1,), superadmin=True) == 9


def test_llm_org_falls_back_to_the_single_organization_holding_a_grant():
    assert _org_resolution(user_orgs=(1, 2), grants={2: [500]}) == 2
    # Ambiguous (two granted organizations) or none: no guess.
    assert _org_resolution(user_orgs=(1, 2), grants={1: [500], 2: [500]}) is None
    assert _org_resolution(user_orgs=(1, 2), grants={}) is None


def test_extract_drafts_route_reports_a_total_model_failure_as_502():
    import asyncio
    from unittest.mock import MagicMock, patch

    from app.api.documents import extract_rule_drafts
    from app.services.rule_extraction_service import RuleGenerationFailedError

    service = MagicMock()
    service.get_document.return_value = {"id": 500}
    service.get_document_text.return_value = "The door shall be 900 mm wide."
    memberships = MagicMock()
    memberships.org_ids_for_user.return_value = {1}
    profiles = MagicMock()
    profiles.is_superadmin.return_value = False

    async def failing(*args, **kwargs):
        raise RuleGenerationFailedError("The AI model failed on all 2 clauses. Reason: 401")

    with patch("app.api.documents.RuleExtractionService") as extraction:
        extraction.return_value.extract_rule_drafts = failing
        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(
                extract_rule_drafts(
                    500,
                    service=service,
                    access_checker=lambda *a, **k: None,
                    current_user=SimpleNamespace(id="user-1"),
                    memberships=memberships,
                    document_access=MagicMock(),
                    profiles=profiles,
                    ruleset_access=MagicMock(),
                    model="m",
                    organization_id=1,
                    x_org_id=None,
                    body=None,
                )
            )

    assert exc_info.value.status_code == 502
    assert "failed on all 2 clauses" in exc_info.value.detail


def test_extract_drafts_route_grants_the_requesting_org_its_new_batch_ruleset():
    """Reviewing/promoting a draft is grant-checked, so the org that ran the extraction must hold the grant."""
    import asyncio
    from unittest.mock import MagicMock, patch

    from app.api.documents import extract_rule_drafts

    service = MagicMock()
    service.get_document.return_value = {"id": 500}
    service.get_document_text.return_value = "The door shall be 900 mm wide."
    memberships = MagicMock()
    memberships.org_ids_for_user.return_value = {1}
    profiles = MagicMock()
    profiles.is_superadmin.return_value = False
    ruleset_access = MagicMock()

    def _draft(ruleset_id):
        return SimpleNamespace(proposed_rule=SimpleNamespace(ruleset_id=ruleset_id))

    async def extracted(*args, **kwargs):
        return [_draft("EXTRACTED-20260921-000000"), _draft("EXTRACTED-20260921-000000")]

    with (
        patch("app.api.documents.RuleExtractionService") as extraction,
        patch("app.api.documents.RuleExtractionDraftListResponse", side_effect=lambda drafts: drafts),
    ):
        extraction.return_value.extract_rule_drafts = extracted
        asyncio.run(
            extract_rule_drafts(
                500,
                service=service,
                access_checker=lambda *a, **k: None,
                current_user=SimpleNamespace(id="user-1"),
                memberships=memberships,
                document_access=MagicMock(),
                profiles=profiles,
                ruleset_access=ruleset_access,
                model="m",
                organization_id=1,
                x_org_id=None,
                body=None,
            )
        )

    ruleset_access.add_org_grant.assert_called_once_with(1, "EXTRACTED-20260921-000000")




def test_generate_doclang_returns_504_on_timeout(monkeypatch):
    """When generate_document_doclang times out, it raises 504 Gateway Timeout."""
    from app.api.documents import generate_document_doclang
    from app.modules.contracts import GenerateDoclangRequest

    class _DocService:
        def get_document(self, doc_id):
            return {"id": doc_id, "filename": "big.pdf", "file_path": "uploads/big.pdf"}

        def generate_doclang_for_existing(self, *args, **kwargs):
            return {}

    async def fake_wait_for(fut, timeout):
        raise asyncio.TimeoutError()

    monkeypatch.setattr(asyncio, "wait_for", fake_wait_for)

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            generate_document_doclang(
                document_id=456,
                payload=GenerateDoclangRequest(parser="auto"),
                service=_DocService(),
                instances_service=_FakeInstances(),
                access_checker=lambda doc_id, for_mutation=False: None,
            )
        )
    assert exc_info.value.status_code == 504
    assert "timed out" in exc_info.value.detail


def test_upload_document_defaults_to_generate_doclang_false():
    """DocumentConfirmRequest defaults generate_doclang to False, separating upload from conversion."""
    import inspect
    from app.modules.contracts import DocumentConfirmRequest
    
    assert DocumentConfirmRequest.model_fields["generate_doclang"].default is False


def test_generate_doclang_passes_page_range():
    """generate_document_doclang passes start_page and end_page to generate_doclang_for_existing."""
    from app.api.documents import generate_document_doclang
    from app.modules.contracts import GenerateDoclangRequest

    calls = []

    class _DocService:
        def get_document(self, doc_id):
            return {"id": doc_id, "filename": "code.pdf", "file_path": "uploads/code.pdf"}

        def generate_doclang_for_existing(self, doc_id, parser, instance, start_page=None, end_page=None):
            calls.append({"doc_id": doc_id, "parser": parser, "start_page": start_page, "end_page": end_page})
            return {"id": doc_id, "filename": "code.pdf", "doclang_xml": "<doc/>"}

        def get_document_text(self, row):
            return "Sample text"

        def get_doclang_content(self, row):
            return "<doc/>"

    resp = asyncio.run(
        generate_document_doclang(
            document_id=789,
            payload=GenerateDoclangRequest(parser="auto", start_page=5, end_page=15),
            service=_DocService(),
            instances_service=_FakeInstances(),
            access_checker=lambda doc_id, for_mutation=False: None,
        )
    )
    assert resp.id == 789
    assert len(calls) == 1
    assert calls[0]["start_page"] == 5
    assert calls[0]["end_page"] == 15


def test_generate_doclang_rejects_invalid_page_range():
    """generate_document_doclang rejects inverted page ranges or missing end page."""
    from app.api.documents import generate_document_doclang
    from app.modules.contracts import GenerateDoclangRequest

    class _DocService:
        def get_document(self, doc_id):
            return {"id": doc_id, "filename": "code.pdf", "file_path": "uploads/code.pdf"}

    # Inverted range
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            generate_document_doclang(
                document_id=789,
                payload=GenerateDoclangRequest(parser="auto", start_page=15, end_page=5),
                service=_DocService(),
                instances_service=_FakeInstances(),
                access_checker=lambda doc_id, for_mutation=False: None,
            )
        )
    assert exc_info.value.status_code == 400
    assert "start_page" in exc_info.value.detail

    # Missing end page
    with pytest.raises(HTTPException) as exc_info2:
        asyncio.run(
            generate_document_doclang(
                document_id=789,
                payload=GenerateDoclangRequest(parser="auto", start_page=5, end_page=None),
                service=_DocService(),
                instances_service=_FakeInstances(),
                access_checker=lambda doc_id, for_mutation=False: None,
            )
        )
    assert exc_info2.value.status_code == 400
    assert "Both start_page and end_page" in exc_info2.value.detail




def _stream_extraction(extract_rule_drafts_impl):
    """Call the extract-drafts route as an SSE client and collect its events."""
    import asyncio
    import json
    from unittest.mock import MagicMock, patch

    from app.api import documents
    from app.api.documents import extract_rule_drafts

    service = MagicMock()
    service.get_document.return_value = {"id": 500}
    service.get_document_text.return_value = "The door shall be 900 mm wide."
    memberships = MagicMock()
    memberships.org_ids_for_user.return_value = {1}
    profiles = MagicMock()
    profiles.is_superadmin.return_value = False

    async def run():
        response = await extract_rule_drafts(
            500,
            service=service,
            access_checker=lambda *a, **k: None,
            current_user=SimpleNamespace(id="user-1"),
            memberships=memberships,
            document_access=MagicMock(),
            profiles=profiles,
            ruleset_access=MagicMock(),
            model="m",
            organization_id=1,
            x_org_id=None,
            body=None,
            accept="text/event-stream",
        )
        assert response.media_type == "text/event-stream"
        return [chunk async for chunk in response.body_iterator]

    with (
        patch("app.api.documents.RuleExtractionService") as extraction,
        patch.object(documents, "_EXTRACTION_STREAM_INTERVAL_SECONDS", 0.01),
    ):
        extraction.return_value.extract_rule_drafts = extract_rule_drafts_impl
        chunks = asyncio.run(run())

    events = []
    for chunk in chunks:
        event_line, data_line = chunk.strip().split("\n")
        events.append((event_line.removeprefix("event: "), json.loads(data_line.removeprefix("data: "))))
    return events


def test_extract_drafts_stream_sends_progress_then_the_result():
    """A long run keeps the connection alive with progress events instead of hitting the proxy's 524."""
    import asyncio

    async def slow_extraction(*args, **kwargs):
        await asyncio.sleep(0.05)
        return []

    events = _stream_extraction(slow_extraction)

    assert events[0][0] == "progress"
    assert events[0][1]["status"] == "running"
    assert events[-1] == ("result", {"drafts": []})


def test_extract_drafts_stream_reports_a_total_model_failure_as_an_error_event():
    from app.services.rule_extraction_service import RuleGenerationFailedError

    async def failing(*args, **kwargs):
        raise RuleGenerationFailedError("The AI model failed on all 2 clauses. Reason: 401")

    events = _stream_extraction(failing)

    assert events[-1][0] == "error"
    assert events[-1][1]["status"] == "failed"
    assert "failed on all 2 clauses" in events[-1][1]["error"]
