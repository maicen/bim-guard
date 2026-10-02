"""Pending uploads: valid CDE states, and text extraction that recovers on re-upload.

Regression: register_pending_document used cde_state="Processing" (and the
background task "Failed"), which violates documents_cde_state_check, so every
upload through POST /api/documents/confirm failed with a 500.
"""

from __future__ import annotations

import asyncio

import pytest
from fastapi import BackgroundTasks

import app.api.documents as documents_api
from app.modules.contracts import DocumentConfirmRequest
from app.modules.contracts.base import CDEState
from app.services.documents_service import DocumentService

pytestmark = pytest.mark.documents

_VALID_STATES = {s.value for s in CDEState}


class _FakeDocumentsRepo:
    def __init__(self):
        self.inserted: list[dict] = []

    def rows_where(self, *_args, **_kwargs):
        return []

    def insert(self, payload):
        self.inserted.append(payload)
        return {**payload, "id": 1}


class _MissingFileStorage:
    def materialize_local_path(self, _ref):
        return None


def test_register_pending_document_uses_a_valid_cde_state():
    repo = _FakeDocumentsRepo()
    service = DocumentService(documents_repo=repo, storage=_MissingFileStorage())

    row, created = service.register_pending_document(
        filename="OBC_clauses.txt", storage_reference="docs/ref.txt", md5_hash="abc123"
    )

    assert created is True
    assert repo.inserted[0]["cde_state"] in _VALID_STATES
    assert row["cde_state"] == "WIP"


def test_background_failure_does_not_write_an_invalid_cde_state(monkeypatch):
    service = DocumentService(documents_repo=_FakeDocumentsRepo(), storage=_MissingFileStorage())
    updates: list[dict] = []
    monkeypatch.setattr(service, "update_document", lambda *a, **kw: updates.append(kw))

    service.process_pending_document_background(1, "OBC_clauses.txt", "docs/missing.txt")

    assert all(u.get("cde_state", "WIP") in _VALID_STATES for u in updates)


# -- confirm_document_upload re-queues text extraction for an empty existing row --

class _ExistingRowService:
    def __init__(self, row):
        self._row = row

    def register_pending_document(self, **_kwargs):
        return self._row, False

    def process_pending_document_background(self, **_kwargs):
        pass


class _Grants:
    def add_org_grant(self, *_args):
        pass


def _confirm(row, monkeypatch) -> BackgroundTasks:
    monkeypatch.setattr(documents_api, "_row_to_detail_response", lambda r, _s: r)
    tasks = BackgroundTasks()
    asyncio.run(
        documents_api.confirm_document_upload(
            payload=DocumentConfirmRequest(
                file_name="OBC_clauses.txt", storage_reference="docs/new-key.txt", doc_type="Specification",
                organization_id=1,
            ),
            background_tasks=tasks,
            service=_ExistingRowService(row),
            instances_service=object(),
            document_access=_Grants(),
            memberships=object(),
            profiles=object(),
            permissions=object(),
            current_user=None,
        )
    )
    return tasks


def test_reupload_requeues_extraction_for_existing_row_without_text(monkeypatch):
    row = {"id": 5, "file_path": "docs/original-key.txt", "doclang_xml": "", "doclang_storage_path": None}
    tasks = _confirm(row, monkeypatch)
    assert len(tasks.tasks) == 1
    assert tasks.tasks[0].kwargs["storage_reference"] == "docs/original-key.txt"


def test_reupload_does_not_reprocess_a_document_that_has_text(monkeypatch):
    row = {"id": 6, "file_path": "docs/k.txt", "doclang_xml": "<doclang/>", "doclang_storage_path": None}
    assert _confirm(row, monkeypatch).tasks == []
