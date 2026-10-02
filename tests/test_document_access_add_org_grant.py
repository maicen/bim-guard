"""DocumentAccessService.add_org_grant and the router's use of the access service.

Regression: POST /api/documents/confirm called document_access.grant_org_access,
which never existed, so every upload 500'd after the document row was created.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from app.services.document_access_service import DocumentAccessService

pytestmark = pytest.mark.documents


class _FakeGrantsRepo:
    def __init__(self, rows=None):
        self.rows = list(rows or [])

    def rows_where(self, _clause, params, **_kwargs):
        return [r for r in self.rows if r["organization_id"] == params[0]]

    def insert(self, row):
        self.rows.append(row)
        return row


def test_add_org_grant_adds_once_and_keeps_existing_grants():
    grants = _FakeGrantsRepo([{"organization_id": 1, "document_id": 7}])
    service = DocumentAccessService(grants, _FakeGrantsRepo())

    service.add_org_grant(1, 42)
    service.add_org_grant(1, 42)

    assert sorted(service.list_org_grants(1)) == [7, 42]


def test_documents_router_only_calls_existing_access_methods():
    router_src = (Path(__file__).resolve().parents[1] / "app" / "api" / "documents.py").read_text(encoding="utf-8")
    called = set(re.findall(r"\bdocument_access\.(\w+)\(", router_src))
    missing = sorted(m for m in called if not hasattr(DocumentAccessService, m))
    assert called, "expected the documents router to use document_access"
    assert missing == []
