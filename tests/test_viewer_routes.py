"""Route-level tests for the multi-model IFC viewer.

NO LIVE DATABASE, NO LIVE STORAGE

    ``app.routes.viewer_routes`` holds its collaborators as module globals, so
    every test here swaps them for fakes and the handlers never reach Supabase
    or the object bucket. That follows the same rule as
    ``tests/test_phase_6a_upload.py``: this suite runs against the live
    project, and a test that inserted an ``uploaded_files`` row or stored an
    object would leave it behind.

    The consequence worth naming: these tests prove the *routes* -- lookup,
    scoping, status codes, and the bytes that come back -- but not that the
    ``uploaded_files`` schema matches what the fakes return. The fakes mirror
    the column set declared in ``FileUploadService._default_table``.

Run: uv run pytest tests/test_viewer_routes.py -v
"""

from __future__ import annotations

from pathlib import Path

import pytest
from starlette.testclient import TestClient

from app.main import app
from app.routes import viewer_routes

PROJECT_ID = 4242
OTHER_PROJECT_ID = 8888
NONEXISTENT_ID = 999_999_999

#: A minimal but structurally valid IFC part 21 file. Small enough to inline,
#: complete enough that the header/data sections a parser looks for are real.
IFC_BYTES = b"""ISO-10303-21;
HEADER;
FILE_DESCRIPTION((''),'2;1');
FILE_NAME('tower.ifc','2026-08-29T00:00:00',(''),(''),'','','');
FILE_SCHEMA(('IFC4'));
ENDSEC;
DATA;
#1=IFCPROJECT('0YvctVUKr0kugbFTf53O9L',$,'Tower',$,$,$,$,$,$);
ENDSEC;
END-ISO-10303-21;
"""


class FakeUploadService:
    """Stands in for ``FileUploadService`` with an in-memory row set."""

    def __init__(self, rows: list[dict]):
        self.rows = rows

    def list_for_project(self, project_id: int, kind: str | None = None) -> list[dict]:
        rows = [r for r in self.rows if r.get("project_id") == project_id]
        if kind is not None:
            rows = [r for r in rows if r.get("kind") == kind]
        return sorted(rows, key=lambda r: str(r.get("created_at") or ""), reverse=True)

    def get_recorded(self, file_id: int) -> dict | None:
        return next((r for r in self.rows if r.get("id") == file_id), None)


class FakeProjectsService:
    """Returns one known project and nothing else."""

    def __init__(self, projects: dict[int, dict]):
        self.projects = projects

    def get_project(self, project_id: int) -> dict | None:
        return self.projects.get(project_id)


class FakeStorage:
    """Maps a storage ref to a real file on disk, or to nothing."""

    def __init__(self, refs: dict[str, Path]):
        self.refs = refs

    def materialize_local_path(self, reference: str) -> Path | None:
        return self.refs.get(reference)


@pytest.fixture(scope="module")
def client() -> TestClient:
    """One client for the module — importing app.main is slow.

    raise_server_exceptions is False so a raising handler surfaces as a 500 to
    assert against rather than aborting the run.
    """
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def ifc_on_disk(tmp_path: Path) -> Path:
    """Write the sample IFC where a fake storage backend can hand it back."""
    path = tmp_path / "tower.ifc"
    path.write_bytes(IFC_BYTES)
    return path


@pytest.fixture
def rows(ifc_on_disk: Path) -> list[dict]:
    """Four rows covering every branch the routes distinguish."""
    return [
        {
            "id": 1,
            "project_id": PROJECT_ID,
            "kind": "ifc",
            "filename": "tower.ifc",
            "storage_ref": "sb://bucket/uploads/ifc/aaa_tower.ifc",
            "file_hash_sha256": "a" * 64,
            "size_bytes": len(IFC_BYTES),
            "created_at": "2026-08-02T00:00:00Z",
        },
        {
            "id": 2,
            "project_id": PROJECT_ID,
            "kind": "ifc",
            "filename": "podium.ifc",
            "storage_ref": "sb://bucket/uploads/ifc/bbb_podium.ifc",
            "file_hash_sha256": "b" * 64,
            "size_bytes": len(IFC_BYTES),
            "created_at": "2026-08-01T00:00:00Z",
        },
        {
            # Same project, different kind — must not reach the viewer.
            "id": 3,
            "project_id": PROJECT_ID,
            "kind": "document",
            "filename": "spec.pdf",
            "storage_ref": "sb://bucket/uploads/documents/ccc_spec.pdf",
            "file_hash_sha256": "c" * 64,
            "size_bytes": 10,
            "created_at": "2026-08-03T00:00:00Z",
        },
        {
            # Another project's model — the scoping check's target.
            "id": 4,
            "project_id": OTHER_PROJECT_ID,
            "kind": "ifc",
            "filename": "secret.ifc",
            "storage_ref": "sb://bucket/uploads/ifc/ddd_secret.ifc",
            "file_hash_sha256": "d" * 64,
            "size_bytes": len(IFC_BYTES),
            "created_at": "2026-08-04T00:00:00Z",
        },
    ]


@pytest.fixture
def wired(monkeypatch, rows: list[dict], ifc_on_disk: Path):
    """Point the route module at the fakes for the duration of one test."""
    monkeypatch.setattr(viewer_routes, "_upload_service", FakeUploadService(rows))
    monkeypatch.setattr(
        viewer_routes,
        "_projects_service",
        FakeProjectsService(
            {
                PROJECT_ID: {"id": PROJECT_ID, "name": "Riverside Tower"},
                OTHER_PROJECT_ID: {"id": OTHER_PROJECT_ID, "name": "Other"},
            }
        ),
    )
    monkeypatch.setattr(
        viewer_routes,
        "_object_storage",
        FakeStorage(
            {
                "sb://bucket/uploads/ifc/aaa_tower.ifc": ifc_on_disk,
                "sb://bucket/uploads/ifc/bbb_podium.ifc": ifc_on_disk,
                # id=4 is deliberately absent: exercises the unavailable-object
                # branch as well as the scoping one.
            }
        ),
    )


# ---------------------------------------------------------------------------
# GET /analyze/viewer
# ---------------------------------------------------------------------------


def test_viewer_page_lists_every_ifc_for_the_project(client, wired):
    """Both IFC models render, each with its own download URL."""
    response = client.get("/analyze/viewer", params={"project_id": PROJECT_ID})

    assert response.status_code == 200
    body = response.text
    assert "tower.ifc" in body
    assert "podium.ifc" in body
    assert f"/uploads/1/ifc?project_id={PROJECT_ID}" in body
    assert f"/uploads/2/ifc?project_id={PROJECT_ID}" in body
    assert "Riverside Tower" in body
    assert "Models (2)" in body


def test_viewer_page_excludes_non_ifc_uploads(client, wired):
    """A document in the same project is not offered as a model."""
    response = client.get("/analyze/viewer", params={"project_id": PROJECT_ID})

    assert response.status_code == 200
    assert "spec.pdf" not in response.text


def test_viewer_page_excludes_other_projects_models(client, wired):
    """The viewer is scoped to the project it was asked for."""
    response = client.get("/analyze/viewer", params={"project_id": PROJECT_ID})

    assert response.status_code == 200
    assert "secret.ifc" not in response.text


def test_viewer_page_mounts_the_viewer_container(client, wired):
    """The page carries the mount point and the loader module."""
    response = client.get("/analyze/viewer", params={"project_id": PROJECT_ID})

    body = response.text
    assert 'id="multi-viewer-container"' in body
    assert "/static/js/viewer/ifc-viewer.js" in body
    assert "data-model-toggle" in body


def test_viewer_page_renders_empty_state_without_models(client, monkeypatch):
    """A project with no uploads gets the empty state, not a dead viewport."""
    monkeypatch.setattr(viewer_routes, "_upload_service", FakeUploadService([]))
    monkeypatch.setattr(
        viewer_routes,
        "_projects_service",
        FakeProjectsService({PROJECT_ID: {"id": PROJECT_ID, "name": "Empty"}}),
    )

    response = client.get("/analyze/viewer", params={"project_id": PROJECT_ID})

    assert response.status_code == 200
    assert "No IFC models have been uploaded" in response.text
    assert 'id="multi-viewer-container"' not in response.text


def test_viewer_page_reports_unknown_project(client, wired):
    """An id with no project row renders the not-found block."""
    response = client.get("/analyze/viewer", params={"project_id": NONEXISTENT_ID})

    assert response.status_code == 200
    assert "not found" in response.text.lower()


def test_viewer_page_without_project_id(client, wired):
    """No project_id is a missing project, not a crash."""
    response = client.get("/analyze/viewer")

    assert response.status_code == 200
    assert "not found" in response.text.lower()


# ---------------------------------------------------------------------------
# GET /uploads/{file_id}/ifc
# ---------------------------------------------------------------------------


def test_upload_download_returns_valid_ifc(client, wired):
    """The route answers 200 with the exact stored IFC bytes."""
    response = client.get("/uploads/1/ifc", params={"project_id": PROJECT_ID})

    assert response.status_code == 200
    assert response.content == IFC_BYTES
    assert response.content.startswith(b"ISO-10303-21;")
    assert response.content.rstrip().endswith(b"END-ISO-10303-21;")
    assert b"FILE_SCHEMA(('IFC4'));" in response.content


def test_upload_download_sets_filename(client, wired):
    """The original upload name rides along, not the storage key."""
    response = client.get("/uploads/1/ifc", params={"project_id": PROJECT_ID})

    assert "tower.ifc" in response.headers.get("content-disposition", "")


def test_upload_download_requires_project_id(client, wired):
    """Without a project_id there is nothing to scope the file against."""
    response = client.get("/uploads/1/ifc")

    assert response.status_code == 400


def test_upload_download_refuses_another_projects_file(client, wired):
    """A file belonging to a different project is refused, not served."""
    response = client.get("/uploads/4/ifc", params={"project_id": PROJECT_ID})

    assert response.status_code == 403
    assert IFC_BYTES not in response.content


def test_upload_download_missing_row(client, wired):
    """An id with no row is a 404."""
    response = client.get(f"/uploads/{NONEXISTENT_ID}/ifc", params={"project_id": PROJECT_ID})

    assert response.status_code == 404


def test_upload_download_refuses_non_ifc_kind(client, wired):
    """The IFC route does not serve documents."""
    response = client.get("/uploads/3/ifc", params={"project_id": PROJECT_ID})

    assert response.status_code == 404


def test_upload_download_when_object_is_unavailable(client, wired):
    """A row whose object cannot be materialised answers 404, not 500."""
    response = client.get("/uploads/4/ifc", params={"project_id": OTHER_PROJECT_ID})

    assert response.status_code == 404
