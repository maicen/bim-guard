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
