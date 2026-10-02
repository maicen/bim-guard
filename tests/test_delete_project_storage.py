"""Deleting a project removes every stored file it owns, not only its rows."""

from __future__ import annotations

from app.services.models_service import ModelsService
from app.services.projects_service import ProjectsService
from app.services.report_artifacts import ReportArtifactService

BUCKET = "sb://bim-guard-artifacts/"


class _Storage:
    def __init__(self, failing: set[str] | None = None) -> None:
        self.deleted: list[str] = []
        self._failing = failing or set()

    def delete(self, reference: str) -> None:
        if reference in self._failing:
            raise OSError("storage unavailable")
        self.deleted.append(reference)


class _Table:
    def __init__(self, rows: list[dict]) -> None:
        self.rows = rows

    def rows_where(self, where_sql: str, params: list) -> list[dict]:
        assert where_sql == "project_id = ?"
        return [r for r in self.rows if r["project_id"] == params[0]]


class _Lineage:
    def __init__(self, rows: list[dict]) -> None:
        self._rows = rows

    def list_for_project(self, project_id: int) -> list[dict]:
        return [r for r in self._rows if r["project_id"] == project_id]


def test_report_artifacts_delete_only_the_projects_files() -> None:
    storage = _Storage()
    table = _Table(
        [
            {"id": 1, "project_id": 7, "storage_ref": BUCKET + "reports/bcf/a.bcf"},
            {"id": 2, "project_id": 7, "storage_ref": BUCKET + "reports/pdf/b.pdf"},
            {"id": 3, "project_id": 7, "storage_ref": ""},
            {"id": 4, "project_id": 8, "storage_ref": BUCKET + "reports/bcf/other.bcf"},
        ]
    )

    ReportArtifactService(storage=storage, table=table).delete_all_for_project(7)

    assert storage.deleted == [BUCKET + "reports/bcf/a.bcf", BUCKET + "reports/pdf/b.pdf"]


def test_report_artifacts_keep_going_when_one_delete_fails() -> None:
    first, second = BUCKET + "reports/bcf/a.bcf", BUCKET + "reports/bcf/b.bcf"
    storage = _Storage(failing={first})
    table = _Table(
        [
            {"id": 1, "project_id": 7, "storage_ref": first},
            {"id": 2, "project_id": 7, "storage_ref": second},
        ]
    )

    ReportArtifactService(storage=storage, table=table).delete_all_for_project(7)

    assert storage.deleted == [second]


def test_models_delete_removes_enhancement_outputs_but_not_sources() -> None:
    storage = _Storage()
    model = BUCKET + "uploads/ifc/model.ifc"
    enhanced = BUCKET + "enhancements/7/model_v1.ifc"
    lineage = _Lineage(
        [
            {"project_id": 7, "source_reference": model, "output_reference": enhanced},
            {"project_id": 8, "source_reference": "x", "output_reference": BUCKET + "enhancements/8/y.ifc"},
        ]
    )
    service = ModelsService(
        ifc_files_repo=_Table([{"project_id": 7, "file_path": model}]),
        storage=storage,
        lineage=lineage,
    )

    service.delete_all_for_project(7)

    assert storage.deleted == [model, enhanced]


def test_delete_project_deletes_models_and_reports_before_the_row() -> None:
    calls: list[tuple[str, int]] = []

    class _Models:
        def delete_all_for_project(self, project_id: int) -> None:
            calls.append(("models", project_id))

    class _Reports:
        def delete_all_for_project(self, project_id: int) -> None:
            calls.append(("reports", project_id))

    class _Projects:
        def get(self, project_id: int) -> dict:
            return {"id": project_id}

        def delete(self, project_id: int) -> None:
            calls.append(("row", project_id))

    service = ProjectsService(
        projects_repo=_Projects(),
        standards_repo=object(),
        client_documents_repo=_Table([]),
        storage=_Storage(),
        models_service=_Models(),
        report_artifacts=_Reports(),
    )

    service.delete_project(7)

    assert calls == [("models", 7), ("reports", 7), ("row", 7)]
