"""Unit tests for app.api.documents._no_parsing_engine_detail's permission-aware messaging."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api.documents import _no_parsing_engine_detail, upload_document
from app.modules.document_parsing.document_extractor import NoParsingEngineConfiguredError
from app.modules.permissions import Action


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


class _FakeUpload:
    filename = "spec.pdf"
    content_type = "application/pdf"

    async def read(self) -> bytes:
        return b"%PDF-1.4 minimal"


class _FakeInstances:
    def get_default(self, organization_id):
        return {"name": "docling-local", "kind": "docling-local", "api_url": "http://localhost:5001"}


class _RaisingDocumentService:
    def __init__(self, exc: Exception):
        self._exc = exc

    def ingest_uploaded_bytes(self, *args, **kwargs):
        raise self._exc


def _upload_with(exc: Exception) -> HTTPException:
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            upload_document(
                file=_FakeUpload(),
                # Called directly, not through FastAPI, so the Form()/Header()
                # defaults aren't resolved -- pass every one explicitly.
                doc_type="Specification",
                project_code="",
                originator="",
                suitability_code="S0",
                revision_code="P01.01",
                parser="auto",
                engine_instance="",
                generate_doclang=True,
                start_page=None,
                end_page=None,
                organization_id=None,
                x_org_id=None,
                service=_RaisingDocumentService(exc),
                instances_service=_FakeInstances(),
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
                    model="m",
                    organization_id=1,
                    x_org_id=None,
                    body=None,
                )
            )

    assert exc_info.value.status_code == 502
    assert "failed on all 2 clauses" in exc_info.value.detail

