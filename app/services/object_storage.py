"""Supabase Storage adapter with a local materialization cache."""

from __future__ import annotations

import os
import uuid
from pathlib import Path

from app.logging_config import get_logger
from supabase import Client, create_client

logger = get_logger(__name__)


class ObjectStorage:
    """Persist and retrieve binary artifacts using a selectable backend."""

    def __init__(self) -> None:
        """Initialize storage settings from environment variables."""
        self._bucket = os.getenv("SUPABASE_STORAGE_BUCKET", "bim-guard-artifacts").strip()
        self._prefix = os.getenv("SUPABASE_STORAGE_PREFIX", "").strip("/")
        self._cache_dir = Path("data/cache/supabase-storage")
        self._client: Client | None = None

    def save_upload(self, filename: str, content: bytes, subdir: str) -> str:
        """Save uploaded content and return a persistent storage reference."""
        safe_name = Path(filename).name
        object_name = f"{uuid.uuid4().hex}_{safe_name}"
        key = "/".join(part.strip("/") for part in [subdir, object_name] if part).strip("/")

        object_key = self._apply_prefix(key)
        try:
            self._supabase_client().storage.from_(self._bucket).upload(
                path=object_key,
                file=content,
                file_options={"upsert": "true"},
            )
        except Exception:
            logger.exception("Storage upload failed bucket=%s key=%s bytes=%d", self._bucket, object_key, len(content))
            raise
        logger.info("Storage upload complete bucket=%s key=%s bytes=%d", self._bucket, object_key, len(content))
        return f"sb://{self._bucket}/{object_key}"

    def materialize_local_path(self, reference: str) -> Path | None:
        """Return a local path for parsing/serving, downloading remote objects when needed."""
        if not reference:
            return None

        if not reference.startswith("sb://"):
            return None

        parsed = self._parse_supabase_reference(reference)
        if parsed is None:
            return None

        bucket, key = parsed
        cache_file = self._cache_dir / key
        cache_file.parent.mkdir(parents=True, exist_ok=True)

        if cache_file.exists() and cache_file.is_file():
            logger.debug("Storage cache hit bucket=%s key=%s", bucket, key)
            return cache_file

        try:
            content = self._supabase_client().storage.from_(bucket).download(key)
        except Exception:
            logger.exception("Storage download failed bucket=%s key=%s", bucket, key)
            raise
        if not content:
            logger.warning("Storage download returned no content bucket=%s key=%s", bucket, key)
            return None

        cache_file.write_bytes(content)
        logger.info("Storage object cached bucket=%s key=%s bytes=%d", bucket, key, len(content))
        return cache_file

    def delete(self, reference: str) -> None:
        """Delete a stored object using either backend."""
        if not reference:
            return

        if not reference.startswith("sb://"):
            return

        parsed = self._parse_supabase_reference(reference)
        if parsed is None:
            return

        bucket, key = parsed
        try:
            self._supabase_client().storage.from_(bucket).remove([key])
        except Exception:
            logger.exception("Storage deletion failed bucket=%s key=%s", bucket, key)
            raise

        cache_file = self._cache_dir / key
        if cache_file.exists() and cache_file.is_file():
            cache_file.unlink()
        logger.info("Storage object deleted bucket=%s key=%s", bucket, key)

    def _apply_prefix(self, key: str) -> str:
        """Prefix object keys when SUPABASE_STORAGE_PREFIX is configured."""
        if not self._prefix:
            return key
        return f"{self._prefix}/{key}"

    def _parse_supabase_reference(self, reference: str) -> tuple[str, str] | None:
        """Parse sb://bucket/key references into bucket and key parts."""
        payload = reference.removeprefix("sb://")
        if "/" not in payload:
            return None
        bucket, key = payload.split("/", 1)
        if not bucket or not key:
            return None
        return bucket, key

    def _supabase_client(self) -> Client:
        """Return a lazy-initialized Supabase client for storage operations."""
        if self._client is not None:
            return self._client

        url = os.getenv("SUPABASE_URL", "").strip()
        key = (
            os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
            or os.getenv("SUPABASE_KEY", "").strip()
        )
        if not url:
            raise ValueError("SUPABASE_URL is required for Supabase Storage")
        if not key:
            raise ValueError(
                "SUPABASE_SERVICE_ROLE_KEY or SUPABASE_KEY is required "
                "for Supabase Storage"
            )

        self._client = create_client(url, key)
        return self._client
