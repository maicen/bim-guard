"""Client name on project creation, and the pick-list of names already in use.

The New Project wizard's Details step opens with a required Client Name that
takes free text or a pick from ``GET /api/projects/client-names``. These tests
drive the real routes end to end -- request contract, route, ProjectsService,
and back out through the response and ``GET /api/projects/{id}`` -- over an
in-memory projects table, so they neither need nor touch the live database.
"""

from __future__ import annotations

from typing import Any

import pytest
from starlette.testclient import TestClient

from app.api.dependencies import (
    get_membership_service,
    get_profile_service,
    get_projects_service,
)
from app.main import app
from app.services.projects_service import ProjectsService

OWN_ORG_ID = 1
OTHER_ORG_ID = 2
#: Seeded ids start well clear of anything another test may have left in the
#: process-wide get_project cache.
FIRST_ID = 880_001


class FakeMemberships:
    """The test user belongs to OWN_ORG_ID only, with access to all of it."""

    def org_ids_for_user(self, user_id: str) -> set[int]:
        return {OWN_ORG_ID}

    def get_organization(self, organization_id: int) -> dict[str, Any]:
        return {"id": organization_id, "org_code": "TSTORG"}

    def member_can_access_project(self, organization_id: int, user_id: str, project_id: int) -> bool:
        return organization_id == OWN_ORG_ID

    def accessible_project_ids(self, organization_id: int, user_id: str) -> set[int] | None:
        return None

    def organizations_with_project_access(self, project_id: int, owning_organization_id: int) -> set[int]:
        return {owning_organization_id}

    def list_org_project_grants(self, organization_id: int) -> list[int]:
        return []


class FakeProfiles:
    """Nobody is a superadmin, so visibility is decided by membership alone."""

    def is_superadmin(self, user_id: str) -> bool:
        return False


class FakeTable:
    """Minimal in-memory stand-in for a projects table adapter."""

    def __init__(self, rows: list[dict[str, Any]] | None = None) -> None:
        self._rows = [dict(row) for row in (rows or [])]

    @property
    def columns_dict(self) -> dict[str, Any]:
        return {"id": int}

    @property
    def rows(self) -> list[dict[str, Any]]:
        return [dict(row) for row in self._rows]

    def get(self, pk_value: Any) -> dict[str, Any] | None:
        return next((dict(r) for r in self._rows if r.get("id") == pk_value), None)

    def insert(self, payload: dict[str, Any]) -> dict[str, Any]:
        row = dict(payload)
        row.setdefault("id", max((int(r["id"]) for r in self._rows), default=FIRST_ID - 1) + 1)
        self._rows.append(row)
        return dict(row)

    def rows_where(self, where_sql: str = "", params: list[Any] | None = None, limit: int | None = None):
        return []


def _row(project_id: int, client_name: str, organization_id: int = OWN_ORG_ID) -> dict[str, Any]:
    return {
        "id": project_id,
        "name": f"Seed {project_id}",
        "client_name": client_name,
        "organization_id": organization_id,
        "ifc_file_path": "",
    }


@pytest.fixture
def projects_service() -> ProjectsService:
    """ProjectsService over a table seeded with clients in two organizations."""
    seed = [
        _row(FIRST_ID, "Northwind Health Trust"),
        _row(FIRST_ID + 1, "acme developments "),
        # Same client, typed with different case and spacing on a newer project.
        _row(FIRST_ID + 2, "Acme Developments"),
        # Predates the column: no client at all.
        _row(FIRST_ID + 3, ""),
        # Another tenant's client must never be offered to this one.
        _row(FIRST_ID + 4, "Contoso Rail", organization_id=OTHER_ORG_ID),
    ]
    return ProjectsService(
        projects_repo=FakeTable(seed),
        standards_repo=FakeTable(),
        client_documents_repo=FakeTable(),
    )


@pytest.fixture
def client(projects_service: ProjectsService) -> TestClient:
    """Test client whose project routes run against the fixture service."""
    app.dependency_overrides[get_projects_service] = lambda: projects_service
    app.dependency_overrides[get_membership_service] = lambda: FakeMemberships()
    app.dependency_overrides[get_profile_service] = lambda: FakeProfiles()
    yield TestClient(app)
    # Only undo what this fixture set; conftest's get_current_user override
    # must survive for the tests that run after these.
    del app.dependency_overrides[get_projects_service]
    del app.dependency_overrides[get_membership_service]
    del app.dependency_overrides[get_profile_service]


def _create_payload(**overrides: Any) -> dict[str, Any]:
    payload = {
        "client_name": "Northwind Health Trust",
        "name": "Clinic extension",
        "short_name": "Clinic Ext",
        "project_code": "CLX1",
        "country": "Canada",
        "analysis_type": "Arch",
        "project_type": "MEDICAL",
    }
    payload.update(overrides)
    return payload


# ── creation persists client_name ────────────────────────────────────────────


def test_create_persists_new_free_text_client_end_to_end(client: TestClient, projects_service):
    """A client typed fresh (not in the pick-list) is stored, returned and re-read."""
    response = client.post("/api/projects", json=_create_payload(client_name="  Fabrikam Estates  "))
    assert response.status_code == 201, response.text
    created = response.json()
    assert created["client_name"] == "Fabrikam Estates"

    # Persisted on the row itself, not only echoed back.
    assert projects_service.get_project(created["id"])["client_name"] == "Fabrikam Estates"

    fetched = client.get(f"/api/projects/{created['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["client_name"] == "Fabrikam Estates"

    # And it is offered back to the next project.
    names = client.get("/api/projects/client-names").json()["client_names"]
    assert "Fabrikam Estates" in names


def test_create_with_client_picked_from_list_does_not_duplicate_it(client: TestClient):
    """Reusing a listed client stores that exact name and the list stays distinct."""
    picked = client.get("/api/projects/client-names").json()["client_names"][0]
    response = client.post("/api/projects", json=_create_payload(client_name=picked))
    assert response.status_code == 201, response.text
    assert response.json()["client_name"] == picked

    names = client.get("/api/projects/client-names").json()["client_names"]
    assert names.count(picked) == 1


@pytest.mark.parametrize(
    "client_name",
    [None, "", "   "],
    ids=["missing", "empty", "whitespace"],
)
def test_create_requires_a_client_name(client: TestClient, client_name):
    """Client Name is required: absent, empty and blank are all refused."""
    payload = _create_payload()
    if client_name is None:
        payload.pop("client_name")
    else:
        payload["client_name"] = client_name
    response = client.post("/api/projects", json=payload)
    assert response.status_code == 422


# ── lifecycle status is no longer asked for ──────────────────────────────────


def test_new_projects_start_active_without_a_status_field(client: TestClient):
    """The wizard sends no status; the project is created Active server-side."""
    response = client.post("/api/projects", json=_create_payload())
    assert response.status_code == 201, response.text
    assert response.json()["status"] == "Active"


def test_a_stray_status_in_the_payload_is_ignored(client: TestClient):
    """Status is not part of the create contract, so an old client cannot set Draft."""
    response = client.post("/api/projects", json=_create_payload(status="Draft"))
    assert response.status_code == 201, response.text
    assert response.json()["status"] == "Active"


def test_create_contract_has_client_name_and_no_status():
    """The OpenAPI schema the frontend mirrors says the same thing."""
    schema = app.openapi()["components"]["schemas"]["ProjectCreateRequest"]
    assert "client_name" in schema["required"]
    assert "status" not in schema["properties"]


# ── the pick-list ────────────────────────────────────────────────────────────


def test_client_names_are_distinct_sorted_and_scoped_to_the_callers_org(client: TestClient):
    """One entry per client, newest spelling kept, blanks and other tenants left out.

    A 200 here also proves the route is declared above ``/{project_id}``,
    which would otherwise reject "client-names" as a project id with a 422.
    """
    response = client.get("/api/projects/client-names")
    assert response.status_code == 200
    assert response.json() == {"client_names": ["Acme Developments", "Northwind Health Trust"]}


def test_client_names_for_an_org_the_caller_is_not_in_are_empty(client: TestClient):
    """Asking for another organization's clients reveals nothing."""
    response = client.get("/api/projects/client-names", params={"organization_id": OTHER_ORG_ID})
    assert response.status_code == 200
    assert response.json() == {"client_names": []}


def test_distinct_client_names_unit():
    """Case/space-insensitive dedupe keeps the newest row's spelling."""
    rows = [
        {"id": 1, "client_name": "acme"},
        {"id": 3, "client_name": " ACME "},
        {"id": 2, "client_name": "Beta"},
        {"id": 4, "client_name": None},
        {"id": 5},
    ]
    assert ProjectsService.distinct_client_names(rows) == ["ACME", "Beta"]
