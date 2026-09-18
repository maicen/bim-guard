"""ISO 19650 container naming on model upload is advisory, not a gate.

The seven fields a compliant name carries are stored as metadata only --
nothing selects an engine, discipline or analysis path from them -- so
``POST /api/projects/{id}/models`` attaches a model whatever it is called and
reports a non-compliant name as a warning. The one check kept is the project
code: a name that parses cleanly and names a *different* project is refused
unless the caller opts in with ``allow_project_code_mismatch``.

NO LIVE DATABASE: the project lookup, storage and models service are fakes.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import HTTPException
from starlette.testclient import TestClient

from app.api.dependencies import (
    get_models_service,
    get_naming_config_service,
    get_phase6_service,
)
from app.api.models import _iso_fields_for
from app.api.projects import get_authorized_project
from app.main import app

PROJECT_CODE = "PRJ1"


class FakeUploads:
    """Stands in for FileUploadService: every upload succeeds."""

    def upload(self, name: str, content: bytes, *, project_id: int, kind: str) -> Any:
        ref = SimpleNamespace(storage_ref=f"projects/{project_id}/{name}", filename=name)
        return SimpleNamespace(success=True, ref=ref, error=None)


class FakeModelsService:
    """Records every attach_model call instead of writing rows."""

    def __init__(self) -> None:
        self.attached: list[dict[str, Any]] = []

    def attach_model(self, project_id: int, **kwargs: Any) -> dict:
        row = {"project_id": project_id, **kwargs}
        self.attached.append(row)
        return row

    def get_primary(self, project_id: int) -> dict | None:
        return next((r for r in self.attached if r.get("is_primary")), None)


class FakeNamingConfig:
    """A project with no saved naming configuration."""

    def get_for_project(self, project_id: int) -> dict:
        return {"project_id": project_id, "is_configured": False}


@pytest.fixture
def models() -> FakeModelsService:
    return FakeModelsService()


@pytest.fixture
def client(models: FakeModelsService):
    overrides = {
        get_authorized_project: lambda project_id: {
            "id": project_id,
            "project_code": PROJECT_CODE,
            "organization_id": None,
        },
        get_models_service: lambda: models,
        get_phase6_service: lambda: SimpleNamespace(upload_service=FakeUploads()),
        get_naming_config_service: lambda: FakeNamingConfig(),
    }
    app.dependency_overrides.update(overrides)
    yield TestClient(app, raise_server_exceptions=False)
    # Only undo what this fixture set; conftest's auth overrides must survive.
    for dependency in overrides:
        del app.dependency_overrides[dependency]


def post_models(client: TestClient, *names: str, **form: Any):
    files = [("files", (name, b"ISO-10303-21;", "application/octet-stream")) for name in names]
    return client.post("/api/projects/7/models", files=files, data={"primary_index": "0", **form})


# ── upload endpoint ──────────────────────────────────────────────────────────


def test_non_conforming_filename_attaches_with_a_warning(
    client: TestClient, models: FakeModelsService
) -> None:
    response = post_models(client, "west_riverside_hospital_arc_ifc4.ifc")

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["success"] is True
    assert len(body["warnings"]) == 1
    assert "does not follow ISO 19650" in body["warnings"][0]

    assert [row["file_name"] for row in models.attached] == ["west_riverside_hospital_arc_ifc4.ifc"]
    # No parsed metadata: project_code/originator are left to default from the project.
    assert models.attached[0]["project_code"] is None
    assert models.attached[0]["type_code"] is None


def test_wrong_field_lengths_no_longer_reject(client: TestClient, models: FakeModelsService) -> None:
    """The 3-character Type code that used to 422 now attaches with a warning."""
    response = post_models(client, "PRJ1-BIMG-01-00-ARC-A-0001.ifc")

    assert response.status_code == 201, response.text
    assert "Type code 'ARC'" in response.json()["warnings"][0]
    assert len(models.attached) == 1


def test_compliant_filename_attaches_with_its_fields_and_no_warning(
    client: TestClient, models: FakeModelsService
) -> None:
    response = post_models(client, "PRJ1-BIMG-01-00-M3-A-0001.ifc")

    assert response.status_code == 201, response.text
    assert response.json()["warnings"] == []
    row = models.attached[0]
    assert row["project_code"] == "PRJ1"
    assert row["originator"] == "BIMG"
    assert row["type_code"] == "M3"


def test_mismatched_project_code_is_refused(client: TestClient, models: FakeModelsService) -> None:
    response = post_models(client, "OTHR-BIMG-01-00-M3-A-0001.ifc")

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert "OTHR" in detail and PROJECT_CODE in detail
    assert "allow_project_code_mismatch" in detail
    assert models.attached == []


def test_mismatch_refuses_the_whole_batch(client: TestClient, models: FakeModelsService) -> None:
    """A fine file uploaded alongside a mismatched one is not attached either."""
    response = post_models(
        client, "west_riverside_hospital_arc_ifc4.ifc", "OTHR-BIMG-01-00-M3-A-0001.ifc"
    )

    assert response.status_code == 422
    assert models.attached == []


def test_mismatched_project_code_attaches_when_explicitly_allowed(
    client: TestClient, models: FakeModelsService
) -> None:
    response = post_models(
        client, "OTHR-BIMG-01-00-M3-A-0001.ifc", allow_project_code_mismatch="true"
    )

    assert response.status_code == 201, response.text
    assert "OTHR" in response.json()["warnings"][0]
    assert models.attached[0]["project_code"] == "OTHR"


# ── _iso_fields_for ──────────────────────────────────────────────────────────


def _parse(name: str, **kwargs: Any):
    options = {
        "separator": "-",
        "guess_separator": True,
        "expected_project_code": PROJECT_CODE,
        "allow_project_code_mismatch": False,
    }
    options.update(kwargs)
    return _iso_fields_for(name, **options)


def test_project_code_comparison_ignores_case() -> None:
    fields, warning = _parse("prj1-BIMG-01-00-M3-A-0001.ifc")
    assert fields["project_code"] == "prj1"
    assert warning is None


def test_project_with_no_code_skips_the_comparison() -> None:
    fields, warning = _parse("OTHR-BIMG-01-00-M3-A-0001.ifc", expected_project_code="")
    assert fields["project_code"] == "OTHR"
    assert warning is None


def test_underscore_separated_name_is_still_recognised() -> None:
    fields, warning = _parse("PRJ1_BIMG_01_00_M3_A_0001.ifc")
    assert fields["originator"] == "BIMG"
    assert warning is None


def test_unparseable_name_never_triggers_the_mismatch_check() -> None:
    """A name that does not parse cleanly names no project, so it cannot mismatch."""
    fields, warning = _parse("OTHR-BIMG-01-00-ARC-A-0001.ifc")
    assert fields == {}
    assert warning is not None


def test_mismatch_raises_422() -> None:
    with pytest.raises(HTTPException) as caught:
        _parse("OTHR-BIMG-01-00-M3-A-0001.ifc")
    assert caught.value.status_code == 422
