"""Failure handling for ``POST /analyze/upload`` and the wizard's file encoding.

WHY 200 AND NOT 400

    This endpoint answers htmx, which swaps the returned fragment into the
    page. htmx does not swap a 4xx response by default, so returning an error
    status here would make the explanation *disappear* from the UI rather than
    surface it. Every failure therefore comes back as a rendered Alert with a
    200, which is the same convention the rest of ``analyze_pipeline`` uses.
    The tests below assert the message reaches the caller, which is the part
    that actually matters.

NO LIVE STORAGE, NO LIVE DATABASE

    Both collaborators are monkeypatched, so nothing here uploads an object or
    writes a row.

Run: uv run pytest tests/test_analyze_upload.py -v
"""

from __future__ import annotations

import pytest
from fasthtml.common import to_xml
from starlette.testclient import TestClient

from app.components.project_setup_wizard import ProjectSetupWizard
from app.main import app
from app.modules.phase_6.phase_6a_upload import StoredFileRef, UploadResponse
from app.routes import analyze_pipeline

IFC_BYTES = b"ISO-10303-21;\nHEADER;\nENDSEC;\nDATA;\nENDSEC;\nEND-ISO-10303-21;\n"

STORED = StoredFileRef(
    storage_ref="sb://bucket/uploads/ifc/aaa_tower.ifc",
    file_hash_sha256="a" * 64,
    filename="tower.ifc",
    size_bytes=len(IFC_BYTES),
    kind="ifc",
)


class FailingUploadService:
    """Reports a storage failure the way the real service does — as a value."""

    def __init__(self, error: str):
        self.error = error

    def upload(self, filename, content, *, project_id=None, kind="ifc"):
        return UploadResponse(success=False, error=self.error)


class SucceedingUploadService:
    """Stores successfully, so the attach step is the one under test."""

    def upload(self, filename, content, *, project_id=None, kind="ifc"):
        return UploadResponse(success=True, ref=STORED, recorded=True)


class FailingProjectsService:
    """A projects table that cannot be written."""

    def attach_ifc(self, project_id: int, storage_ref: str) -> None:
        raise RuntimeError("relation \"projects\" does not exist")


@pytest.fixture(scope="module")
def client() -> TestClient:
    """One client for the module — importing app.main is slow."""
    return TestClient(app, raise_server_exceptions=False)


def _post(client: TestClient):
    return client.post(
        "/analyze/upload",
        data={"project_id": "1"},
        files={"ifc_file": ("tower.ifc", IFC_BYTES, "application/octet-stream")},
    )


class TestStorageFailure:
    """A storage backend that cannot be reached must explain itself."""

    def test_reason_reaches_the_caller(self, client, monkeypatch):
        monkeypatch.setattr(
            analyze_pipeline,
            "_upload_service",
            FailingUploadService("The file could not be stored: no credentials"),
        )

        response = _post(client)

        assert response.status_code == 200
        assert "could not be stored" in response.text
        assert "no credentials" in response.text

    def test_does_not_report_success(self, client, monkeypatch):
        monkeypatch.setattr(
            analyze_pipeline, "_upload_service", FailingUploadService("storage is down")
        )

        assert "attached" not in _post(client).text


class TestAttachFailure:
    """The object is stored but the project row cannot be pointed at it."""

    def test_answers_an_explanation_rather_than_a_500(self, client, monkeypatch):
        monkeypatch.setattr(analyze_pipeline, "_upload_service", SucceedingUploadService())
        monkeypatch.setattr(analyze_pipeline, "_projects_service", FailingProjectsService())

        response = _post(client)

        assert response.status_code == 200, "an unwrapped raise would surface as 500 here"
        assert "could not be pointed at it" in response.text

    def test_says_the_file_was_not_lost(self, client, monkeypatch):
        """The bytes are already in storage; the message must not imply otherwise."""
        monkeypatch.setattr(analyze_pipeline, "_upload_service", SucceedingUploadService())
        monkeypatch.setattr(analyze_pipeline, "_projects_service", FailingProjectsService())

        assert "not lost" in _post(client).text


class TestBadRequests:
    """The two guards that run before any storage work."""

    def test_missing_project_id(self, client):
        response = client.post(
            "/analyze/upload",
            files={"ifc_file": ("tower.ifc", IFC_BYTES, "application/octet-stream")},
        )

        assert "No project was supplied." in response.text

    def test_missing_file(self, client):
        assert "Choose an IFC file" in client.post(
            "/analyze/upload", data={"project_id": "1"}
        ).text


class TestWizardFileEncoding:
    """htmx drops file inputs unless hx-encoding says otherwise."""

    @pytest.mark.parametrize("step", [1, 2, 3, 4, 5])
    def test_form_declares_multipart_for_htmx(self, step):
        html = to_xml(ProjectSetupWizard().render(current_step=step, form_data={}))

        assert 'hx-encoding="multipart/form-data"' in html

    def test_native_enctype_is_kept_alongside_it(self):
        """Keep enctype too: it covers a non-htmx submit, so the two are not redundant."""
        html = to_xml(ProjectSetupWizard().render(current_step=4, form_data={}))

        assert 'enctype="multipart/form-data"' in html
