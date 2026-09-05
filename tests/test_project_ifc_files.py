"""Tests for the project_ifc_files access layer on ProjectsService.

The table itself is verified against a real Postgres by the migration
(``supabase/migrations/20260830003000_create_project_ifc_files.sql``); what is
verified here is the read side that sits on top of it:

1. ``get_ifc_files_by_project`` returns a project's models, primary first.
2. ``get_primary_ifc_file`` resolves the one model an analysis run starts from.
3. Both degrade to ``projects.ifc_file_path`` where the child table has no rows
   — a project created before the migration, or a database where it has not
   been applied yet.

Every case runs against injected in-memory repositories, so the suite neither
needs the migration applied nor touches the live database.
"""

from __future__ import annotations

from typing import Any

import pytest

from app.services.projects_service import ProjectsService


class FakeTable:
    """In-memory table that honours the ``project_id = ?`` predicate.

    ``MockTableAdapter`` in test_dependency_inversion.py returns every row from
    ``rows_where`` regardless of the predicate, which would let a broken filter
    pass here unnoticed.
    """

    def __init__(self, rows: list[dict[str, Any]] | None = None) -> None:
        self._rows = [dict(row) for row in (rows or [])]

    @property
    def columns_dict(self) -> dict[str, Any]:
        return {"id": int, "project_id": int}

    @property
    def rows(self) -> list[dict[str, Any]]:
        return [dict(row) for row in self._rows]

    def get(self, pk_value: Any) -> dict[str, Any] | None:
        for row in self._rows:
            if row.get("id") == pk_value:
                return dict(row)
        return None

    def insert(self, payload: dict[str, Any]) -> dict[str, Any]:
        row = dict(payload)
        row.setdefault("id", len(self._rows) + 1)
        self._rows.append(row)
        return dict(row)

    def update(self, *, updates: dict[str, Any], pk_values: Any) -> None:
        for row in self._rows:
            if row.get("id") == pk_values:
                row.update(updates)

    def delete(self, pk_value: Any) -> None:
        self._rows = [row for row in self._rows if row.get("id") != pk_value]

    def rows_where(
        self,
        where_sql: str = "",
        params: list[Any] | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        rows = self.rows
        if where_sql.strip() == "project_id = ?" and params:
            rows = [row for row in rows if row.get("project_id") == params[0]]
        return rows[:limit] if limit is not None else rows


class MissingTable(FakeTable):
    """Stands in for a table whose migration has not been applied yet."""

    def rows_where(self, *args: Any, **kwargs: Any) -> list[dict[str, Any]]:
        raise RuntimeError('relation "public.project_ifc_files" does not exist')


class NoopStorage:
    """Storage stub; these tests never read or write real bytes."""

    def __init__(self) -> None:
        self.deleted: list[str] = []

    def save_upload(self, filename: str, content: bytes, subdir: str) -> str:
        return f"mock://{subdir}/{filename}"

    def materialize_local_path(self, reference: str) -> None:
        return None

    def delete(self, reference: str) -> None:
        self.deleted.append(reference)


def build_service(
    projects: list[dict], ifc_files: Any, storage: NoopStorage | None = None
) -> ProjectsService:
    """Return a ProjectsService wired to in-memory repositories."""
    return ProjectsService(
        projects_repo=FakeTable(projects),
        standards_repo=FakeTable(),
        client_documents_repo=FakeTable(),
        ifc_files_repo=ifc_files,
        storage=storage or NoopStorage(),
    )


PROJECTS = [
    {"id": 10, "name": "Multi model", "ifc_file_path": "sb://m/legacy_10.ifc", "created_at": "2026-08-01"},
    {"id": 11, "name": "Legacy only", "ifc_file_path": "sb://m/uploads/ifc/abc_Clinic.ifc", "created_at": "2026-08-02"},
    {"id": 12, "name": "No model", "ifc_file_path": "", "created_at": "2026-08-03"},
    {"id": 13, "name": "Windows path", "ifc_file_path": "C:\\models\\Tower.ifc", "created_at": "2026-08-04"},
    {"id": 14, "name": "No primary flag", "ifc_file_path": "", "created_at": "2026-08-05"},
]

IFC_FILES = [
    {"id": 1, "project_id": 10, "file_path": "sb://m/arch.ifc", "file_name": "arch.ifc", "is_primary": False, "role": "architectural"},
    {"id": 2, "project_id": 10, "file_path": "sb://m/plumb.ifc", "file_name": "plumb.ifc", "is_primary": True, "role": "primary"},
    {"id": 3, "project_id": 10, "file_path": "sb://m/struct.ifc", "file_name": "struct.ifc", "is_primary": False, "role": "structural"},
    {"id": 4, "project_id": 14, "file_path": "sb://m/a.ifc", "file_name": "a.ifc", "is_primary": False, "role": "context"},
    {"id": 5, "project_id": 14, "file_path": "sb://m/b.ifc", "file_name": "b.ifc", "is_primary": False, "role": "context"},
]


@pytest.fixture
def service() -> ProjectsService:
    """Build a service holding both child rows and legacy-only projects."""
    return build_service(PROJECTS, FakeTable(IFC_FILES))


def test_lists_every_model_attached_to_the_project(service: ProjectsService) -> None:
    """get_ifc_files_by_project returns all of a project's rows and no others."""
    files = service.get_ifc_files_by_project(10)

    assert [row["file_name"] for row in files] == ["plumb.ifc", "arch.ifc", "struct.ifc"]
    assert {row["project_id"] for row in files} == {10}


def test_primary_model_sorts_first(service: ProjectsService) -> None:
    """The primary row leads the list regardless of insertion order."""
    files = service.get_ifc_files_by_project(10)

    assert files[0]["is_primary"] is True
    assert files[0]["role"] == "primary"


def test_primary_ifc_file_resolves_the_analysis_model(service: ProjectsService) -> None:
    """get_primary_ifc_file returns the row flagged primary."""
    primary = service.get_primary_ifc_file(10)

    assert primary is not None
    assert primary["file_path"] == "sb://m/plumb.ifc"


def test_falls_back_to_the_projects_column_when_no_rows_exist(service: ProjectsService) -> None:
    """A project migrated before the child table still reports its model."""
    files = service.get_ifc_files_by_project(11)

    assert len(files) == 1
    assert files[0]["file_path"] == "sb://m/uploads/ifc/abc_Clinic.ifc"
    assert files[0]["file_name"] == "abc_Clinic.ifc"
    assert files[0]["is_primary"] is True
    assert service.get_primary_ifc_file(11) == files[0]


def test_fallback_derives_file_name_from_a_windows_path(service: ProjectsService) -> None:
    """Legacy rows may hold local Windows paths rather than storage refs."""
    primary = service.get_primary_ifc_file(13)

    assert primary is not None
    assert primary["file_name"] == "Tower.ifc"


def test_project_without_a_model_reports_nothing(service: ProjectsService) -> None:
    """No child rows and no ifc_file_path means no files, not a fabricated one."""
    assert service.get_ifc_files_by_project(12) == []
    assert service.get_primary_ifc_file(12) is None


def test_rows_with_no_primary_flag_still_resolve_to_a_model(service: ProjectsService) -> None:
    """A project that owns models has a model to analyse."""
    primary = service.get_primary_ifc_file(14)

    assert primary is not None
    assert primary["file_path"] == "sb://m/a.ifc"


def test_missing_table_degrades_to_the_legacy_column() -> None:
    """Reads survive a database where the migration has not been applied."""
    service = build_service(PROJECTS, MissingTable())

    files = service.get_ifc_files_by_project(11)

    assert [row["file_path"] for row in files] == ["sb://m/uploads/ifc/abc_Clinic.ifc"]
    assert service.get_primary_ifc_file(12) is None


# ── delete_ifc_file ──────────────────────────────────────────────────────────


def test_delete_removes_a_non_primary_file_and_the_stored_bytes() -> None:
    """Deleting a context model drops its row and frees its storage object."""
    storage = NoopStorage()
    service = build_service(PROJECTS, FakeTable(IFC_FILES), storage=storage)

    deleted = service.delete_ifc_file(10, 1)

    assert deleted is not None
    assert deleted["file_name"] == "arch.ifc"
    assert storage.deleted == ["sb://m/arch.ifc"]
    remaining = service.get_ifc_files_by_project(10)
    assert [row["file_name"] for row in remaining] == ["plumb.ifc", "struct.ifc"]
    assert remaining[0]["is_primary"] is True


def test_delete_of_the_primary_promotes_the_next_remaining_file() -> None:
    """The project keeps a model to analyse as long as one is left."""
    service = build_service(PROJECTS, FakeTable(IFC_FILES))

    deleted = service.delete_ifc_file(10, 2)

    assert deleted is not None
    assert deleted["is_primary"] is True
    primary = service.get_primary_ifc_file(10)
    assert primary is not None
    assert primary["file_name"] == "arch.ifc"
    assert primary["is_primary"] is True
    # The mirror column follows the newly promoted model.
    assert service.get_project(10)["ifc_file_path"] == "sb://m/arch.ifc"


def test_delete_of_the_last_file_clears_the_projects_mirror_column() -> None:
    """A project can end up with no model, and the mirror column agrees."""
    ifc_files = FakeTable(
        [{"id": 99, "project_id": 12, "file_path": "sb://m/only.ifc", "file_name": "only.ifc", "is_primary": True, "role": "primary"}]
    )
    service = build_service(PROJECTS, ifc_files)

    deleted = service.delete_ifc_file(12, 99)

    assert deleted is not None
    assert service.get_ifc_files_by_project(12) == []
    assert service.get_project(12)["ifc_file_path"] == ""


def test_delete_of_an_unknown_file_returns_none() -> None:
    """A file_id belonging to another project, or no project, is a no-op."""
    service = build_service(PROJECTS, FakeTable(IFC_FILES))

    assert service.delete_ifc_file(10, 999) is None
    # id 4 belongs to project 14, not 10 -- must not be deletable through it.
    assert service.delete_ifc_file(10, 4) is None
    assert len(service.get_ifc_files_by_project(14)) == 2
