"""Supabase Storage adapter with a local materialization cache."""

from __future__ import annotations

import os
import uuid
from pathlib import Path

from app.environment import load_env_file
from app.logging_config import get_logger
from supabase import Client, create_client

load_env_file()
logger = get_logger(__name__)


class ObjectStorage:
    """Persist and retrieve binary artifacts using a selectable backend."""

    def __init__(
        self,
        *,
        client: Client | None = None,
        bucket: str | None = None,
        prefix: str | None = None,
        cache_dir: Path | None = None,
    ) -> None:
        """Initialize storage settings with optional dependency injection."""
        self._bucket = (
            bucket
            if bucket is not None
            else os.getenv("SUPABASE_STORAGE_BUCKET", "bim-guard-artifacts").strip()
        )
        self._prefix = (
            prefix.strip("/")
            if prefix is not None
            else os.getenv("SUPABASE_STORAGE_PREFIX", "").strip("/")
        )
        self._cache_dir = (
            cache_dir if cache_dir is not None else Path("data/cache/supabase-storage")
        )
        self._client = client

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

        # 1. Direct local filesystem path check
        try:
            local_candidate = Path(reference)
            if local_candidate.is_file():
                return local_candidate
        except Exception:
            pass

        # 2. HTTP/HTTPS URL (e.g. GitHub raw model URLs)
        if reference.startswith("http://") or reference.startswith("https://"):
            import hashlib
            import httpx
            url_hash = hashlib.md5(reference.encode("utf-8")).hexdigest()
            filename = Path(reference.split("?")[0]).name or "model.ifc"
            if not filename.endswith(".ifc") and not filename.endswith(".zip"):
                filename += ".ifc"
            cache_file = self._cache_dir / "http" / f"{url_hash}_{filename}"
            cache_file.parent.mkdir(parents=True, exist_ok=True)

            if cache_file.exists() and cache_file.is_file() and cache_file.stat().st_size > 0:
                logger.debug("HTTP model storage cache hit ref=%s", reference)
                return cache_file

            try:
                logger.info("Downloading remote model from URL ref=%s", reference)
                with httpx.Client(timeout=60.0, follow_redirects=True) as client:
                    resp = client.get(reference)
                    resp.raise_for_status()
                    cache_file.write_bytes(resp.content)
                    logger.info("Downloaded remote model ref=%s bytes=%d", reference, len(resp.content))
                    return cache_file
            except Exception as exc:
                logger.exception("Failed to download remote model ref=%s: %s", reference, exc)
                return None

        # 3. Supabase Storage reference (sb://bucket/key)
        if reference.startswith("sb://"):
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

        return None


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
        """Return a lazy-initialized Supabase client."""
        if self._client is not None:
            return self._client

        url = os.getenv("SUPABASE_URL", "").strip()
        key = (
            os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
            or os.getenv("SUPABASE_KEY", "").strip()
        )
        if not url or not key:
            raise RuntimeError(
                "Supabase Storage requires SUPABASE_URL and a server-side API key"
            )

        self._client = create_client(url, key)
        return self._client
