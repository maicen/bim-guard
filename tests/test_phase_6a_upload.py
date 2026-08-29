"""Tests for Session A's upload service.

NO LIVE STORAGE, NO LIVE DATABASE

    Both the storage backend and the metadata table are injected, so nothing
    here uploads an object or writes a row. That is not merely tidiness: this
    suite runs against the live Supabase project, where a test that stored a
    file would leave it in the bucket. See data contracts §5.1.

Run: uv run pytest tests/test_phase_6a_upload.py -v
"""

from __future__ import annotations

import hashlib

import pytest

from app.modules.phase_6.phase_6a_upload import (
    MAX_UPLOAD_BYTES,
    SUBDIR_BY_KIND,
    FileUploadService,
    StoredFileRef,
    sha256_of,
)


class FakeStorage:
    """Records what it was asked to store instead of storing it."""

    def __init__(self, fail_with: Exception | None = None):
        self.calls: list[tuple[str, bytes, str]] = []
        self._fail_with = fail_with

    def save_upload(self, filename: str, content: bytes, subdir: str) -> str:
        if self._fail_with:
            raise self._fail_with
        self.calls.append((filename, content, subdir))
        return f"sb://test-bucket/{subdir}/deadbeef_{filename}"


class FakeTable:
    """Minimal stand-in for a persistence table adapter."""

    def __init__(self, fail_on_insert: bool = False):
        self.rows: list[dict] = []
        self._fail_on_insert = fail_on_insert

    def insert(self, row: dict) -> None:
        if self._fail_on_insert:
            raise RuntimeError("table does not exist")
        self.rows.append(row)

    def rows_where(self, where: str, params: list):
        """Honour the predicate's field rather than assuming a hash lookup.

        The adapter parses a single ``<field> = ?`` comparison (see
        ``db_adapters.parse_where``), so mirroring that here is enough -- and
        it keeps this fake from silently answering a project query with hash
        results.
        """
        field = where.split(" = ?", 1)[0].strip()
        return [r for r in self.rows if r.get(field) == params[0]]

    def get(self, pk_value):
        return next((r for r in self.rows if r.get("id") == pk_value), None)


class RaisingTable(FakeTable):
    """A table whose reads fail, standing in for an unreachable database."""

    def rows_where(self, where: str, params: list):
        raise RuntimeError("relation does not exist")

    def get(self, pk_value):
        raise RuntimeError("relation does not exist")


@pytest.fixture
def storage() -> FakeStorage:
    return FakeStorage()


@pytest.fixture
def table() -> FakeTable:
    return FakeTable()


@pytest.fixture
def service(storage, table) -> FileUploadService:
    return FileUploadService(storage=storage, table=table)


IFC_BYTES = b"ISO-10303-21;\nHEADER;\nENDSEC;\nDATA;\nENDSEC;\nEND-ISO-10303-21;\n"


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


class TestUpload:
    def test_successful_upload_reports_success(self, service):
        response = service.upload("model.ifc", IFC_BYTES, project_id=1)
        assert response.success is True
        assert response.error is None
        assert isinstance(response.ref, StoredFileRef)

    def test_storage_ref_is_returned(self, service):
        ref = service.upload("model.ifc", IFC_BYTES).ref
        assert ref.storage_ref.startswith("sb://")
        assert ref.storage_ref.endswith("model.ifc")

    def test_content_reaches_storage_unmodified(self, service, storage):
        service.upload("model.ifc", IFC_BYTES)
        filename, content, subdir = storage.calls[0]
        assert content == IFC_BYTES
        assert filename == "model.ifc"
        assert subdir == SUBDIR_BY_KIND["ifc"]

    def test_kind_selects_the_subdirectory(self, service, storage):
        service.upload("spec.pdf", b"%PDF-1.7 ...", kind="document")
        assert storage.calls[0][2] == SUBDIR_BY_KIND["document"]

    def test_directory_components_are_stripped_from_filename(self, service, storage):
        """A browser can send a path; the object key must not inherit it."""
        service.upload("C:\\Users\\x\\Desktop\\model.ifc", IFC_BYTES)
        assert "\\" not in storage.calls[0][0]
        assert storage.calls[0][0] == "model.ifc"

    def test_size_is_recorded(self, service):
        ref = service.upload("model.ifc", IFC_BYTES).ref
        assert ref.size_bytes == len(IFC_BYTES)


# ---------------------------------------------------------------------------
# SHA-256 — the cross-session cache key
# ---------------------------------------------------------------------------


class TestSha256:
    def test_matches_hashlib(self, service):
        ref = service.upload("model.ifc", IFC_BYTES).ref
        assert ref.file_hash_sha256 == hashlib.sha256(IFC_BYTES).hexdigest()

    def test_is_deterministic(self, service):
        a = service.upload("a.ifc", IFC_BYTES).ref.file_hash_sha256
        b = service.upload("b.ifc", IFC_BYTES).ref.file_hash_sha256
        assert a == b, "the digest is over content, not filename"

    def test_differs_for_different_content(self, service):
        a = service.upload("a.ifc", IFC_BYTES).ref.file_hash_sha256
        b = service.upload("b.ifc", IFC_BYTES + b"\n").ref.file_hash_sha256
        assert a != b

    def test_agrees_with_the_phase_6b_parser(self, service):
        """The whole point of the digest: both sessions derive the same key.

        If these ever diverge, an uploaded model and its parse would occupy
        different cache entries and every re-upload would re-parse.

        Skips while the sessions are on separate branches — ``phase_6b_parsing``
        lands with Session B — and becomes a live cross-session assertion the
        moment both are merged.
        """
        phase_6b_parsing = pytest.importorskip(
            "app.modules.phase_6.phase_6b_parsing",
            reason="Session B not merged into this branch yet",
        )
        ref = service.upload("model.ifc", IFC_BYTES).ref
        assert ref.file_hash_sha256 == phase_6b_parsing.sha256_of(IFC_BYTES)

    def test_helper_agrees_with_service(self, service):
        ref = service.upload("model.ifc", IFC_BYTES).ref
        assert sha256_of(IFC_BYTES) == ref.file_hash_sha256


# ---------------------------------------------------------------------------
# Validation — rejected before anything is stored
# ---------------------------------------------------------------------------


class TestValidation:
    @pytest.mark.parametrize(
        "filename,content,kind",
        [
            pytest.param("model.ifc", b"", "ifc", id="empty-content"),
            pytest.param("", IFC_BYTES, "ifc", id="no-filename"),
            pytest.param("model.txt", IFC_BYTES, "ifc", id="wrong-extension"),
            pytest.param("model.ifc", IFC_BYTES, "nonsense", id="unknown-kind"),
        ],
    )
    def test_rejected_upload_reports_failure(self, service, filename, content, kind):
        response = service.upload(filename, content, kind=kind)
        assert response.success is False
        assert response.error
        assert response.ref is None

    def test_rejected_upload_never_reaches_storage(self, service, storage):
        service.upload("model.txt", IFC_BYTES)
        assert storage.calls == [], "validation must run before the write"

    def test_oversize_upload_is_refused(self, service, storage):
        response = service.upload("big.ifc", b"x" * (MAX_UPLOAD_BYTES + 1))
        assert response.success is False
        assert "limit" in response.error
        assert storage.calls == []

    def test_extension_check_is_case_insensitive(self, service):
        assert service.upload("MODEL.IFC", IFC_BYTES).success is True


# ---------------------------------------------------------------------------
# Failures are values, not exceptions
# ---------------------------------------------------------------------------


class TestFailuresAreValues:
    def test_storage_error_does_not_propagate(self, table):
        service = FileUploadService(
            storage=FakeStorage(fail_with=RuntimeError("bucket unreachable")), table=table
        )
        response = service.upload("model.ifc", IFC_BYTES)
        assert response.success is False
        assert "could not be stored" in response.error

    def test_storage_error_records_nothing(self, table):
        service = FileUploadService(
            storage=FakeStorage(fail_with=RuntimeError("bucket unreachable")), table=table
        )
        service.upload("model.ifc", IFC_BYTES)
        assert table.rows == []

    def test_metadata_failure_does_not_lose_the_upload(self, storage):
        """The bytes are already stored; a bookkeeping failure must not undo it."""
        service = FileUploadService(storage=storage, table=FakeTable(fail_on_insert=True))
        response = service.upload("model.ifc", IFC_BYTES)
        assert response.success is True
        assert response.recorded is False
        assert response.ref.storage_ref


# ---------------------------------------------------------------------------
# Metadata
# ---------------------------------------------------------------------------


class TestMetadata:
    def test_row_is_written_on_success(self, service, table):
        service.upload("model.ifc", IFC_BYTES, project_id=42)
        assert len(table.rows) == 1

    def test_row_carries_the_contract_fields(self, service, table):
        service.upload("model.ifc", IFC_BYTES, project_id=42)
        row = table.rows[0]
        assert set(row) == {
            "project_id",
            "kind",
            "filename",
            "storage_ref",
            "file_hash_sha256",
            "size_bytes",
            "created_at",
        }
        assert row["project_id"] == 42
        assert row["file_hash_sha256"] == hashlib.sha256(IFC_BYTES).hexdigest()

    def test_recorded_flag_is_true_on_success(self, service):
        assert service.upload("model.ifc", IFC_BYTES).recorded is True

    def test_find_by_hash_locates_a_previous_upload(self, service):
        digest = service.upload("model.ifc", IFC_BYTES).ref.file_hash_sha256
        assert len(service.find_by_hash(digest)) == 1

    def test_find_by_hash_is_empty_for_unknown_content(self, service):
        service.upload("model.ifc", IFC_BYTES)
        assert service.find_by_hash("0" * 64) == []


# ---------------------------------------------------------------------------
# Listing a project's uploads — the viewer's data source
# ---------------------------------------------------------------------------

PROJECT_ID = 42
OTHER_PROJECT_ID = 99


def _row(file_id: int, project_id: int | None, kind: str, filename: str, created_at: str) -> dict:
    """Build an ``uploaded_files`` row.

    The key set mirrors the columns declared in
    ``FileUploadService._default_table`` and created by migration
    ``20260827004000_create_uploaded_files``. Note there is no ``status``
    column: a row's existence *is* its status, so anything wanting one needs a
    migration first.
    """
    return {
        "id": file_id,
        "project_id": project_id,
        "kind": kind,
        "filename": filename,
        "storage_ref": f"sb://bucket/uploads/{kind}/{file_id}_{filename}",
        "file_hash_sha256": f"{file_id:064d}",
        "size_bytes": len(IFC_BYTES),
        "created_at": created_at,
    }


@pytest.fixture
def populated(table) -> FileUploadService:
    """Return a service over four rows spanning both projects and two kinds."""
    table.rows.extend(
        [
            _row(1, PROJECT_ID, "ifc", "tower.ifc", "2026-08-01T00:00:00Z"),
            _row(2, PROJECT_ID, "ifc", "podium.ifc", "2026-08-03T00:00:00Z"),
            _row(3, PROJECT_ID, "document", "spec.pdf", "2026-08-02T00:00:00Z"),
            _row(4, OTHER_PROJECT_ID, "ifc", "secret.ifc", "2026-08-04T00:00:00Z"),
            # project_id NULL: uploaded before the project row existed. The
            # migration allows this on purpose for the wizard's step 4.
            _row(5, None, "ifc", "orphan.ifc", "2026-08-05T00:00:00Z"),
        ]
    )
    return FileUploadService(storage=FakeStorage(), table=table)


class TestListForProject:
    """``list_for_project`` — what the multi-model viewer reads."""

    def test_returns_rows_for_a_valid_project_id(self, populated):
        rows = populated.list_for_project(PROJECT_ID, kind="ifc")

        assert [row["filename"] for row in rows] == ["podium.ifc", "tower.ifc"]

    def test_rows_carry_the_fields_the_viewer_needs(self, populated):
        row = populated.list_for_project(PROJECT_ID, kind="ifc")[0]

        # id, filename, storage_ref and size_bytes are what ViewerModel reads.
        assert row["id"] == 2
        assert row["filename"] == "podium.ifc"
        assert row["storage_ref"].startswith("sb://bucket/uploads/ifc/")
        assert row["size_bytes"] == len(IFC_BYTES)

    def test_orders_newest_first(self, populated):
        rows = populated.list_for_project(PROJECT_ID, kind="ifc")

        assert [row["created_at"] for row in rows] == [
            "2026-08-03T00:00:00Z",
            "2026-08-01T00:00:00Z",
        ]

    def test_filters_out_other_kinds(self, populated):
        assert all(
            row["kind"] == "ifc" for row in populated.list_for_project(PROJECT_ID, kind="ifc")
        )

    def test_omitting_kind_returns_every_kind(self, populated):
        kinds = {row["kind"] for row in populated.list_for_project(PROJECT_ID)}

        assert kinds == {"ifc", "document"}

    def test_excludes_other_projects(self, populated):
        names = {row["filename"] for row in populated.list_for_project(PROJECT_ID)}

        assert "secret.ifc" not in names

    def test_orphan_uploads_are_unreachable_by_project(self, populated):
        """A NULL ``project_id`` row cannot be found by any project id.

        This is the constraint the wizard integration runs into: a file
        uploaded before the project exists is only recoverable by its own id,
        because ``project_id = ?`` never matches NULL.
        """
        for project_id in (PROJECT_ID, OTHER_PROJECT_ID, 0):
            assert "orphan.ifc" not in {
                row["filename"] for row in populated.list_for_project(project_id)
            }

    def test_empty_for_a_project_with_no_uploads(self, populated):
        assert populated.list_for_project(123_456) == []

    def test_returns_empty_rather_than_raising_when_the_lookup_fails(self, storage):
        service = FileUploadService(storage=storage, table=RaisingTable())

        assert service.list_for_project(PROJECT_ID, kind="ifc") == []


class TestGetRecorded:
    """``get_recorded`` — what the per-file download route reads."""

    def test_returns_the_row_for_a_known_id(self, populated):
        row = populated.get_recorded(1)

        assert row is not None
        assert row["filename"] == "tower.ifc"
        assert row["project_id"] == PROJECT_ID

    def test_returns_none_for_an_unknown_id(self, populated):
        assert populated.get_recorded(999_999) is None

    def test_returns_none_rather_than_raising_when_the_lookup_fails(self, storage):
        service = FileUploadService(storage=storage, table=RaisingTable())

        assert service.get_recorded(1) is None
