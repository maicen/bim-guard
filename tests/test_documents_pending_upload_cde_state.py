"""Pending uploads must only ever write ISO 19650 CDE states to documents.cde_state.

Regression: register_pending_document used cde_state="Processing" (and the
background task "Failed"), which violates documents_cde_state_check, so every
upload through POST /api/documents/confirm failed with a 500.
"""

from __future__ import annotations

import pytest

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
