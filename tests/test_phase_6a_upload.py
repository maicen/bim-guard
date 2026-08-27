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
        return [r for r in self.rows if r.get("file_hash_sha256") == params[0]]


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
