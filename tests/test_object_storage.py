from types import SimpleNamespace

import pytest

from app.services.object_storage import ObjectStorage


class FakeBucket:
    def __init__(self) -> None:
        self.downloads = 0
        self.uploaded_payload = None

    def download(self, key: str) -> bytes:
        self.downloads += 1
        assert key == "uploads/ifc/model.ifc"
        return b"ISO-10303-21;CLOUD"

    def upload(self, **payload) -> None:
        self.uploaded_payload = payload


class FakeStorageNamespace:
    def __init__(self, bucket: FakeBucket) -> None:
        self.bucket = bucket

    def from_(self, bucket_name: str) -> FakeBucket:
        assert bucket_name == "bim-guard-artifacts"
        return self.bucket


def test_materialized_ifc_cache_is_disposable_and_recreated(tmp_path) -> None:
    bucket = FakeBucket()
    storage = ObjectStorage()
    storage._cache_dir = tmp_path
    storage._client = SimpleNamespace(storage=FakeStorageNamespace(bucket))
    reference = "sb://bim-guard-artifacts/uploads/ifc/model.ifc"

    first_path = storage.materialize_local_path(reference)

    assert first_path is not None
    assert first_path.read_bytes() == b"ISO-10303-21;CLOUD"
    first_path.unlink()

    second_path = storage.materialize_local_path(reference)

    assert second_path == first_path
    assert second_path.read_bytes() == b"ISO-10303-21;CLOUD"
    assert bucket.downloads == 2


def test_upload_returns_cloud_reference_without_writing_cache(tmp_path) -> None:
    bucket = FakeBucket()
    storage = ObjectStorage()
    storage._cache_dir = tmp_path
    storage._client = SimpleNamespace(storage=FakeStorageNamespace(bucket))

    reference = storage.save_upload("model.ifc", b"IFC", "uploads/ifc")

    assert reference.startswith("sb://bim-guard-artifacts/uploads/ifc/")
    assert bucket.uploaded_payload["file"] == b"IFC"
    assert list(tmp_path.rglob("*")) == []


def test_storage_does_not_masquerade_local_files_as_cloud(monkeypatch) -> None:
    monkeypatch.setenv("SUPABASE_URL", "")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "")
    monkeypatch.setenv("SUPABASE_KEY", "")

    with pytest.raises(RuntimeError, match="Supabase Storage requires"):
        ObjectStorage().save_upload("model.ifc", b"IFC", "uploads/ifc")