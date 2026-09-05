"""Tests for attaching several IFC models to one project, and reading them back.

Three properties, and the third is the reason the first two exist:

1. **The upload records every model.** ``POST /api/projects/{id}/upload`` stores
   each file, writes a ``project_ifc_files`` row for it, and points
   ``projects.ifc_file_path`` at the one marked primary so every reader that
   predates the child table still resolves a model.
2. **A corrosion run reads the primary and nothing else.** Galvanic and crevice
   assessment is a question about a pipe run; a second discipline's copy of that
   run would double every finding rather than add one.
3. **A seismic run reads all of them.** A clearance envelope is a question about
   a building. The brace is in the mechanical model and the beam it must clear
   is in the structural one, so a single-model run reports silence about exactly
   the clashes a coordinator federates models to find.

NO LIVE DATABASE. Repositories are in-memory and storage is a dict, so what is
asserted is the code's behaviour rather than a fixture's contents.

Run: uv run pytest tests/test_multi_file_ifc_upload.py -v
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from starlette.testclient import TestClient

import app.services.analysis_runner as runner
from app.api.dependencies import get_membership_service, get_phase6_service, get_projects_service
from app.main import app
from app.modules.phase_6.phase_6a_upload import FileUploadService
from app.services.projects_service import ProjectsService

#: The fake project below needs an organization_id for app.api.projects'
#: get_authorized_project check to pass; FakeMemberships below says the test
#: user belongs to exactly this one, so nothing here touches the live DB.
FAKE_ORG_ID = 1


class FakeMemberships:
    """A membership service fixed to one organization, no live DB involved."""

    def org_ids_for_user(self, user_id: str) -> set[int]:
        return {FAKE_ORG_ID}

    def member_can_access_project(self, organization_id: int, user_id: str, project_id: int) -> bool:
        return True

    def accessible_project_ids(self, organization_id: int, user_id: str) -> set[int] | None:
        return None

ifcopenshell = pytest.importorskip("ifcopenshell", reason="the seismic kernel needs ifcopenshell")


# ── doubles ──────────────────────────────────────────────────────────────────


class FakeTable:
    """In-memory table honouring the ``project_id = ?`` predicate."""

    def __init__(self, rows: list[dict[str, Any]] | None = None) -> None:
        self._rows = [dict(row) for row in (rows or [])]

    @property
    def columns_dict(self) -> dict[str, Any]:
        return {"id": int, "project_id": int}

    @property
    def rows(self) -> list[dict[str, Any]]:
        return [dict(row) for row in self._rows]

    def get(self, pk_value: Any) -> dict[str, Any] | None:
        return next((dict(r) for r in self._rows if r.get("id") == pk_value), None)

    def insert(self, payload: dict[str, Any]) -> dict[str, Any]:
        row = dict(payload)
        row.setdefault("id", max((int(r.get("id", 0)) for r in self._rows), default=0) + 1)
        self._rows.append(row)
        return dict(row)

    def update(self, *, updates: dict[str, Any], pk_values: Any) -> None:
        for row in self._rows:
            if row.get("id") == pk_values:
                row.update(updates)

    def delete(self, pk_value: Any) -> None:
        self._rows = [r for r in self._rows if r.get("id") != pk_value]

    def rows_where(
        self,
        where_sql: str = "",
        params: list[Any] | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        rows = self.rows
        if "project_id" in where_sql and params:
            rows = [r for r in rows if r.get("project_id") == params[0]]
        return rows[:limit] if limit else rows


class DictStorage:
    """Object storage as a dict, materialising into a tmp directory."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.objects: dict[str, bytes] = {}

    def save_upload(self, filename: str, content: bytes, subdir: str) -> str:
        ref = f"mem://{subdir}/{len(self.objects)}_{filename}"
        self.objects[ref] = content
        return ref

    def materialize_local_path(self, reference: str) -> Path | None:
        if reference not in self.objects:
            return None
        path = self.root / reference.rsplit("/", 1)[-1]
        path.write_bytes(self.objects[reference])
        return path

    def delete(self, reference: str) -> None:
        self.objects.pop(reference, None)


# ── models ───────────────────────────────────────────────────────────────────


def model_with(entities: list[tuple[str, str]]) -> bytes:
    """Build an IFC holding one entity per ``(ifc_class, name)``.

    No geometry representations: enough for element enumeration, which is what
    these tests count. The geometry paths are covered by
    tests/test_phase_6d_seismic.py.
    """
    model = ifcopenshell.file(schema="IFC4")
    for ifc_class, name in entities:
        model.create_entity(ifc_class, GlobalId=ifcopenshell.guid.new(), Name=name)
    return model.to_string().encode("utf-8")


PIPING_MODEL = model_with([("IfcPipeSegment", "CHW-01"), ("IfcPipeSegment", "CHW-02")])
STRUCTURAL_MODEL = model_with([("IfcBeam", "B-01"), ("IfcColumn", "C-01")])
ARCHITECTURAL_MODEL = model_with([("IfcWall", "W-01")])
#: Braced services in a second discipline model. The seismic kernel reports one
#: data_quality Issue per braced element it cannot read geometry for, so these
#: three are what a federated run finds and a primary-only run does not.
MECHANICAL_MODEL = model_with(
    [("IfcDuctSegment", "SA-01"), ("IfcDuctSegment", "SA-02"), ("IfcDuctSegment", "RA-01")]
)

#: IFC SPF writes entity types in upper case, so a byte-level assertion about a
#: model's contents has to look for IFCPIPESEGMENT, not IfcPipeSegment. Spelling
#: it once here keeps an absence assertion from passing because it searched for
#: a string the format never emits.
SPF = {
    "pipe": b"IFCPIPESEGMENT",
    "duct": b"IFCDUCTSEGMENT",
    "beam": b"IFCBEAM",
    "wall": b"IFCWALL",
}


# ── wiring ───────────────────────────────────────────────────────────────────


@pytest.fixture
def service(tmp_path: Path) -> ProjectsService:
    """Build a ProjectsService over in-memory repositories and dict storage."""
    return ProjectsService(
        projects_repo=FakeTable(
            [
                {
                    "id": 7,
                    "name": "Federated tower",
                    "ifc_file_path": "",
                    "created_at": "2026-08-30",
                    "organization_id": FAKE_ORG_ID,
                }
            ]
        ),
        standards_repo=FakeTable(),
        client_documents_repo=FakeTable(),
        ifc_files_repo=FakeTable(),
        storage=DictStorage(tmp_path),
    )


@pytest.fixture
def client(service: ProjectsService, monkeypatch) -> TestClient:
    """Return a test client whose routes and analysis runner share one service."""
    uploads = FileUploadService(storage=service._storage, table=FakeTable())

    class Phase6Double:
        upload_service = uploads

    app.dependency_overrides[get_projects_service] = lambda: service
    app.dependency_overrides[get_phase6_service] = lambda: Phase6Double()
    app.dependency_overrides[get_membership_service] = lambda: FakeMemberships()
    # The runner holds a module-level service of its own; point it at the same
    # one so an upload made through the API is the model the analysis reads.
    monkeypatch.setattr(runner, "_projects_service", service)
    yield TestClient(app, raise_server_exceptions=False)
    # Only undo what this fixture set — a bare .clear() would also remove
    # conftest.py's session-wide get_current_user override, breaking every
    # test that runs after this one in the same session.
    del app.dependency_overrides[get_projects_service]
    del app.dependency_overrides[get_phase6_service]
    del app.dependency_overrides[get_membership_service]


def upload(client: TestClient, project_id: int = 7, **form: Any):
    """POST the three discipline models, primary first unless told otherwise."""
    files = [
        ("files", ("plumbing.ifc", PIPING_MODEL, "application/octet-stream")),
        ("files", ("structural.ifc", STRUCTURAL_MODEL, "application/octet-stream")),
        ("files", ("architectural.ifc", ARCHITECTURAL_MODEL, "application/octet-stream")),
    ]
    data: dict[str, Any] = {"primary_index": "0", "roles": ["primary", "structural", "architectural"]}
    data.update(form)
    return client.post(f"/api/projects/{project_id}/upload", files=files, data=data)


# ── 1. the upload records every model ────────────────────────────────────────


def test_three_files_produce_three_rows(client: TestClient, service: ProjectsService) -> None:
    """Uploading three models attaches three, not just the last or the first."""
    response = upload(client)
    assert response.status_code == 201, response.text

    body = response.json()
    assert body["success"] is True
    assert len(body["files"]) == 3
    assert [f["file_name"] for f in body["files"]] == [
        "plumbing.ifc",
        "structural.ifc",
        "architectural.ifc",
    ]
    assert len(service.get_ifc_files_by_project(7)) == 3


def test_roles_are_recorded_per_file(client: TestClient, service: ProjectsService) -> None:
    """The roles list is parallel to the files list, not applied to all of them."""
    upload(client)
    by_name = {row["file_name"]: row for row in service.get_ifc_files_by_project(7)}
    assert by_name["structural.ifc"]["role"] == "structural"
    assert by_name["architectural.ifc"]["role"] == "architectural"


def test_exactly_one_model_is_primary(client: TestClient, service: ProjectsService) -> None:
    """primary_index marks one model, and marks only it."""
    upload(client, primary_index="1")
    files = service.get_ifc_files_by_project(7)
    assert [f["file_name"] for f in files if f["is_primary"]] == ["structural.ifc"]


def test_primary_is_mirrored_onto_the_project(client: TestClient, service: ProjectsService) -> None:
    """projects.ifc_file_path follows the primary, so old readers still work."""
    upload(client, primary_index="2")
    primary = service.get_primary_ifc_file(7)
    assert primary["file_name"] == "architectural.ifc"
    assert service.get_project(7)["ifc_file_path"] == primary["file_path"]


def test_response_names_the_primary_row(client: TestClient, service: ProjectsService) -> None:
    """primary_id identifies the row a caller would promote or analyse."""
    body = upload(client, primary_index="1").json()
    assert body["primary_id"] == service.get_primary_ifc_file(7)["id"]


def test_listing_returns_the_primary_first(client: TestClient) -> None:
    """GET /files puts the analysis model at the head of the list."""
    upload(client, primary_index="1")
    listed = client.get("/api/projects/7/files").json()
    assert listed[0]["file_name"] == "structural.ifc"
    assert len(listed) == 3


def test_promoting_a_model_moves_the_project_pointer(
    client: TestClient, service: ProjectsService
) -> None:
    """set_primary_ifc_file re-points both the row and the projects column."""
    upload(client, primary_index="0")
    target = next(f for f in service.get_ifc_files_by_project(7) if f["file_name"] == "structural.ifc")

    promoted = service.set_primary_ifc_file(7, target["id"])

    assert promoted["is_primary"] is True
    assert service.get_primary_ifc_file(7)["file_name"] == "structural.ifc"
    assert service.get_project(7)["ifc_file_path"] == target["file_path"]


def test_promoting_leaves_one_primary(client: TestClient, service: ProjectsService) -> None:
    """The previous primary is demoted, not left as a second claimant."""
    upload(client, primary_index="0")
    target = next(f for f in service.get_ifc_files_by_project(7) if f["file_name"] == "structural.ifc")
    service.set_primary_ifc_file(7, target["id"])
    assert sum(1 for f in service.get_ifc_files_by_project(7) if f["is_primary"]) == 1


def test_a_model_attached_before_the_table_is_kept(
    client: TestClient, service: ProjectsService
) -> None:
    """A pre-migration model gets a row of its own rather than dropping out.

    get_ifc_files_by_project reports projects.ifc_file_path only while the child
    table holds nothing, so the first row written ends that fallback. Without
    adopting the existing model first, attaching a second one would detach the
    first.
    """
    service._projects.update(
        updates={"ifc_file_path": "mem://legacy/original.ifc"}, pk_values=7
    )
    service._storage.objects["mem://legacy/original.ifc"] = PIPING_MODEL

    upload(client)

    names = [row["file_name"] for row in service.get_ifc_files_by_project(7)]
    assert "original.ifc" in names
    assert len(names) == 4


# ── validation ───────────────────────────────────────────────────────────────


def test_a_non_ifc_file_rejects_the_whole_batch(
    client: TestClient, service: ProjectsService
) -> None:
    """All four discipline models attach or none do; three plus a message is worse."""
    response = client.post(
        "/api/projects/7/upload",
        files=[
            ("files", ("plumbing.ifc", PIPING_MODEL, "application/octet-stream")),
            ("files", ("notes.pdf", b"%PDF-1.4", "application/pdf")),
        ],
    )
    assert response.status_code == 400
    assert "notes.pdf" in response.json()["detail"]
    assert service.get_ifc_files_by_project(7) == []


def test_primary_index_outside_the_batch_is_rejected(
    client: TestClient, service: ProjectsService
) -> None:
    """A primary nobody uploaded would leave the project without one."""
    response = upload(client, primary_index="9")
    assert response.status_code == 400
    assert service.get_ifc_files_by_project(7) == []


def test_partial_roles_are_rejected(client: TestClient) -> None:
    """Two roles for three files names no file in particular."""
    response = client.post(
        "/api/projects/7/upload",
        files=[
            ("files", ("a.ifc", PIPING_MODEL, "application/octet-stream")),
            ("files", ("b.ifc", STRUCTURAL_MODEL, "application/octet-stream")),
            ("files", ("c.ifc", ARCHITECTURAL_MODEL, "application/octet-stream")),
        ],
        data={"roles": ["primary", "structural"]},
    )
    assert response.status_code == 400


def test_roles_may_be_omitted_entirely(client: TestClient, service: ProjectsService) -> None:
    """Not having classified the models yet is a state, not an error."""
    response = client.post(
        "/api/projects/7/upload",
        files=[
            ("files", ("a.ifc", PIPING_MODEL, "application/octet-stream")),
            ("files", ("b.ifc", STRUCTURAL_MODEL, "application/octet-stream")),
        ],
    )
    assert response.status_code == 201
    roles = {row["file_name"]: row["role"] for row in service.get_ifc_files_by_project(7)}
    assert roles == {"a.ifc": "primary", "b.ifc": "context"}


def test_upload_to_a_missing_project_is_404(client: TestClient) -> None:
    response = upload(client, project_id=404)
    assert response.status_code == 404


def test_listing_a_missing_project_is_404(client: TestClient) -> None:
    assert client.get("/api/projects/404/files").status_code == 404


def test_a_project_with_no_models_lists_nothing(client: TestClient) -> None:
    """No model yet is an empty list, not a missing resource."""
    response = client.get("/api/projects/7/files")
    assert response.status_code == 200
    assert response.json() == []


# ── serving one attached model to the viewer ─────────────────────────────────
#
# GET /{id}/ifc resolves through projects.ifc_file_path and so always serves the
# primary. A viewer offering the project's models as a list has to be able to
# fetch the one the user picked, which is what these cover.


def test_each_attached_model_downloads_its_own_bytes(client: TestClient) -> None:
    """Every row serves the model it names, not the project's primary."""
    attached = upload(client).json()["files"]
    by_name = {f["file_name"]: f["id"] for f in attached}

    piping = client.get(f"/api/projects/7/files/{by_name['plumbing.ifc']}/ifc")
    structural = client.get(f"/api/projects/7/files/{by_name['structural.ifc']}/ifc")

    assert piping.status_code == 200
    assert structural.status_code == 200
    # The non-primary request must not be quietly answered with the primary,
    # which is the failure that would make a file picker look like it works.
    assert SPF["pipe"] in piping.content
    assert SPF["beam"] in structural.content
    assert SPF["beam"] not in piping.content


def test_downloaded_model_is_named_after_its_row(client: TestClient) -> None:
    """The response is attached under the uploaded filename."""
    attached = upload(client).json()["files"]
    file_id = next(f["id"] for f in attached if f["file_name"] == "architectural.ifc")

    response = client.get(f"/api/projects/7/files/{file_id}/ifc")

    assert response.status_code == 200
    assert "architectural.ifc" in response.headers["content-disposition"]


def test_download_rejects_a_file_belonging_to_no_project_of_that_id(
    client: TestClient,
) -> None:
    """An id the project does not hold is 404, not another project's model."""
    upload(client)

    response = client.get("/api/projects/7/files/9999/ifc")

    assert response.status_code == 404
    assert "9999" in response.json()["detail"]


def test_download_reports_storage_failure_apart_from_a_missing_model(
    client: TestClient, service: ProjectsService
) -> None:
    """Bytes storage cannot produce are a 502; the row still exists."""
    attached = upload(client).json()["files"]
    target = attached[1]
    service._storage.delete(target["file_path"])

    response = client.get(f"/api/projects/7/files/{target['id']}/ifc")

    assert response.status_code == 502


def test_download_from_an_unknown_project_is_404(client: TestClient) -> None:
    """A missing project is reported as such before any row is looked up."""
    response = client.get("/api/projects/404/files/1/ifc")

    assert response.status_code == 404
    assert "404" in response.json()["detail"]


# ── 2. corrosion reads the primary only ──────────────────────────────────────


def test_corrosion_reads_the_primary_model(client: TestClient, service: ProjectsService) -> None:
    """model_bytes hands the corrosion engines one model: the primary."""
    upload(client, primary_index="0")
    content, error = runner.model_bytes(7)
    assert error is None
    assert content == PIPING_MODEL


def test_corrosion_follows_a_change_of_primary(
    client: TestClient, service: ProjectsService
) -> None:
    """Promoting another model changes which one the engines assess."""
    upload(client, primary_index="0")
    target = next(f for f in service.get_ifc_files_by_project(7) if f["file_name"] == "structural.ifc")
    service.set_primary_ifc_file(7, target["id"])

    content, error = runner.model_bytes(7)
    assert error is None
    assert content == STRUCTURAL_MODEL


def test_corrosion_never_sees_the_other_models(client: TestClient) -> None:
    """The secondary models are not concatenated into the primary's bytes."""
    upload(client)
    content, _ = runner.model_bytes(7)
    assert SPF["pipe"] in content
    assert SPF["beam"] not in content
    assert SPF["wall"] not in content


# ── 3. seismic reads every model ─────────────────────────────────────────────


def test_seismic_loads_every_attached_model(client: TestClient) -> None:
    """model_bytes_all returns all three, primary first."""
    upload(client, primary_index="0")
    models, error = runner.model_bytes_all(7)
    assert error is None
    assert [name for name, _ in models] == ["plumbing.ifc", "structural.ifc", "architectural.ifc"]


def test_seismic_sees_elements_from_all_disciplines(client: TestClient, monkeypatch) -> None:
    """Every model's elements reach the kernel, not just the primary's."""
    upload(client)
    seen: list[tuple[str, bytes]] = []

    def capture(content, *, extra_models=(), **kwargs):
        seen.append(("primary", content))
        seen.extend(extra_models)
        return {
            "audit_issues": [],
            "issue_stats": {},
            "cost_impact": None,
            "compliance_error": None,
            "compliance_is_demo": False,
        }

    monkeypatch.setattr(runner, "run_seismic_analysis", capture)
    runner.run_analysis("seismic", 7, use_cache=False)

    federated = b"".join(content for _, content in seen)
    assert SPF["pipe"] in federated
    assert SPF["beam"] in federated
    assert SPF["wall"] in federated


def test_the_kernel_assesses_elements_from_every_model(client: TestClient) -> None:
    """The real kernel reports on the secondary models' elements too.

    Two braced elements sit in the primary and three more in the mechanical
    model. These fixtures carry no geometry, so each braced element yields one
    data_quality Issue -- which makes the Issue count a direct measure of how
    many models the kernel actually opened.
    """
    from app.modules.phase_6.phase_6d_seismic import run_seismic_analysis

    upload(client)
    models, error = runner.model_bytes_all(7)
    assert error is None

    single = run_seismic_analysis(models[0][1])
    federated = run_seismic_analysis(
        models[0][1], extra_models=[*models[1:], ("mechanical.ifc", MECHANICAL_MODEL)]
    )

    assert single["compliance_error"] is None
    assert federated["compliance_error"] is None
    assert len(single["audit_issues"]) == 2
    assert len(federated["audit_issues"]) == 5


def test_findings_name_the_model_they_came_from(client: TestClient) -> None:
    """A federated finding is only actionable if it says which file to open."""
    from app.modules.phase_6.phase_6d_seismic import run_seismic_analysis

    upload(client)
    models, _ = runner.model_bytes_all(7)
    result = run_seismic_analysis(
        models[0][1], extra_models=[("mechanical.ifc", MECHANICAL_MODEL)]
    )

    sources = {issue.metadata.get("source_model") for issue in result["audit_issues"]}
    assert sources == {"primary model", "mechanical.ifc"}


def test_one_element_federated_twice_is_assessed_once(client: TestClient) -> None:
    """The same GlobalId in two models is one element, not two.

    A linked reference federated twice would otherwise be given an envelope in
    each model and clash with itself, reporting a clearance failure nobody can
    fix.
    """
    from app.modules.phase_6.phase_6d_seismic import run_seismic_analysis

    doubled = run_seismic_analysis(PIPING_MODEL, extra_models=[("copy.ifc", PIPING_MODEL)])
    alone = run_seismic_analysis(PIPING_MODEL)

    assert len(doubled["audit_issues"]) == len(alone["audit_issues"]) == 2


def test_a_model_that_cannot_be_fetched_fails_the_run(
    client: TestClient, service: ProjectsService
) -> None:
    """A partial federation would report clearance where it stopped looking."""
    upload(client)
    secondary = next(
        f for f in service.get_ifc_files_by_project(7) if f["file_name"] == "structural.ifc"
    )
    service._storage.objects.pop(secondary["file_path"])

    models, error = runner.model_bytes_all(7)
    assert models == []
    assert "structural.ifc" in error


def test_seismic_cache_key_covers_every_model(client: TestClient, service: ProjectsService) -> None:
    """Attaching a model must miss the entry the primary alone produced."""
    from app.services.analysis_cache import ANALYSIS_CACHE

    ANALYSIS_CACHE.clear()
    upload(client, primary_index="0")
    before, _ = runner.model_bytes_all(7)

    service.add_ifc_file(
        7, file_path=service._storage.save_upload("extra.ifc", ARCHITECTURAL_MODEL, "x"),
        file_name="extra.ifc", role="context",
    )
    after, _ = runner.model_bytes_all(7)

    assert runner._federated_sha256(before) != runner._federated_sha256(after)


# ── merging one geometry set out of several models ───────────────────────────


def stub_geometries(monkeypatch, per_model: list[tuple[list, list]]) -> None:
    """Return a prepared ``(geometries, failures)`` for each model in turn.

    The merge is the unit under test here, not ifcopenshell's geometry
    extraction: what matters is which element wins when two models disagree
    about the same GlobalId, and that is decided in run_seismic_analysis.
    """
    from app.modules.phase_6 import phase_6d_seismic

    calls = iter(per_model)
    monkeypatch.setattr(
        phase_6d_seismic, "_geometries", lambda model, scale: next(calls, ([], []))
    )


def box(element_id: str):
    """Return an ElementGeometry for a braced element: a 1m cube at the origin."""
    from app.modules.blue_halo.halo_volume_generator import (
        BoundingBox,
        ElementGeometry,
        Point3D,
    )

    return ElementGeometry(
        element_id=element_id,
        ifc_class="IfcPipeSegment",
        bbox_mm=BoundingBox(Point3D(0.0, 0.0, 0.0), Point3D(1000.0, 1000.0, 1000.0)),
    )


def test_an_element_one_model_can_read_is_not_reported_unreadable(monkeypatch) -> None:
    """A placeholder in one discipline does not condemn another's real geometry.

    Federating a model that carries an element as a stub, alongside one that
    models it properly, is the normal case. Reporting it unassessed would be a
    finding about the federation rather than about the building.
    """
    from app.modules.phase_6.phase_6d_seismic import run_seismic_analysis

    stub_geometries(
        monkeypatch,
        [
            ([], [("SHARED-1", "IfcPipeSegment", "no readable geometry")]),
            ([box("SHARED-1")], []),
        ],
    )

    result = run_seismic_analysis(PIPING_MODEL, extra_models=[("structural.ifc", STRUCTURAL_MODEL)])

    assert result["audit_issues"] == []


def test_an_element_no_model_can_read_is_reported_once(monkeypatch) -> None:
    """Unreadable everywhere is one finding, not one per model that tried."""
    from app.modules.phase_6.phase_6d_seismic import run_seismic_analysis

    stub_geometries(
        monkeypatch,
        [
            ([], [("SHARED-1", "IfcPipeSegment", "no readable geometry")]),
            ([], [("SHARED-1", "IfcPipeSegment", "no readable geometry")]),
        ],
    )

    result = run_seismic_analysis(PIPING_MODEL, extra_models=[("structural.ifc", STRUCTURAL_MODEL)])

    assert len(result["audit_issues"]) == 1
    assert result["audit_issues"][0].element_id == "SHARED-1"
