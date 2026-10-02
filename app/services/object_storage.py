"""Supabase Storage adapter with a local materialization cache."""

from __future__ import annotations

import os
import threading
import uuid
from pathlib import Path

import httpx

from app.environment import load_env_file
from app.logging_config import get_logger
from supabase import Client, ClientOptions, create_client

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
        except Exception as exc:
            logger.exception("Storage upload failed bucket=%s key=%s bytes=%d", self._bucket, object_key, len(content))
            # Translate raw SDK / network errors into a concise message.  The
            # original exception is chained so tracebacks are not lost, but the
            # string that surfaces to the caller (and ultimately the user) never
            # leaks internal bucket names, paths, or SDK implementation details.
            msg = str(exc)
            if "payload too large" in msg.lower() or "entity too large" in msg.lower():
                friendly = f"The file is too large for the storage backend ({len(content) // (1024 * 1024)} MB). Check the bucket's file_size_limit in Supabase Storage settings."
            elif "not found" in msg.lower() or "bucket" in msg.lower():
                friendly = "Storage bucket not found or inaccessible. Contact your administrator."
            elif "unauthorized" in msg.lower() or "jwt" in msg.lower() or "403" in msg:
                friendly = "Storage authentication failed. The server's Supabase credentials may be expired or missing."
            elif "connect" in msg.lower() or "timeout" in msg.lower() or "network" in msg.lower():
                friendly = "Could not reach the storage service. Check network connectivity between the app server and Supabase."
            else:
                friendly = f"The file could not be stored. Storage error: {msg}"
            raise OSError(friendly) from exc
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
            from app.services.ssrf_protection import is_safe_url

            if not is_safe_url(reference, allow_localhost=False):
                logger.warning("Blocked unsafe remote model URL ref=%s (SSRF protection)", reference)
                return None

            import hashlib

            import httpx
            url_hash = hashlib.md5(reference.encode("utf-8")).hexdigest()
            filename = Path(reference.split("?")[0]).name or "model.ifc"
            if not filename.endswith(".ifc") and not filename.endswith(".zip") and not filename.endswith(".ifczip"):
                filename += ".ifc"
            cache_file = self._cache_dir / "http" / f"{url_hash}_{filename}"
            cache_file.parent.mkdir(parents=True, exist_ok=True)

            if cache_file.exists() and cache_file.is_file() and cache_file.stat().st_size > 0:
                logger.debug("HTTP model storage cache hit ref=%s", reference)
                return cache_file

            try:
                logger.info("Downloading remote model from URL ref=%s", reference)
                # follow_redirects is deliberately off: a validated public URL
                # could otherwise 302 to an internal/metadata address that
                # is_safe_url never re-checks. Each hop is re-validated here.
                with httpx.Client(timeout=60.0, follow_redirects=False) as client:
                    current_url = reference
                    for _ in range(5):
                        resp = client.get(current_url)
                        if resp.is_redirect:
                            next_url = resp.headers.get("location")
                            if not next_url:
                                resp.raise_for_status()
                            next_url = str(httpx.URL(current_url).join(next_url))
                            if not is_safe_url(next_url, allow_localhost=False):
                                logger.warning(
                                    "Blocked unsafe redirect target ref=%s -> %s (SSRF protection)",
                                    reference,
                                    next_url,
                                )
                                return None
                            current_url = next_url
                            continue
                        resp.raise_for_status()
                        cache_file.write_bytes(resp.content)
                        logger.info("Downloaded remote model ref=%s bytes=%d", reference, len(resp.content))
                        return cache_file
                logger.warning("Too many redirects downloading remote model ref=%s", reference)
                return None
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

    def create_signed_url(self, reference: str, expires_in: int = 3600) -> str | None:
        """Generate a time-limited signed download URL for Supabase Storage objects."""
        if not reference or not reference.startswith("sb://"):
            return None

        parsed = self._parse_supabase_reference(reference)
        if parsed is None:
            return None

        bucket, key = parsed
        try:
            res = self._supabase_client().storage.from_(bucket).create_signed_url(key, expires_in)
            if isinstance(res, dict):
                return res.get("signedURL") or res.get("signedUrl")
            return str(res)
        except Exception:
            logger.warning("Failed generating signed URL bucket=%s key=%s", bucket, key, exc_info=True)
            return None

    def create_presigned_upload_url(self, filename: str, subdir: str) -> dict[str, str]:
        """
        Generate a short-lived URL for direct client-side upload to Supabase Storage.
        Returns a dictionary with 'signed_url', 'storage_reference', and 'token'.
        """
        safe_name = Path(filename).name
        object_name = f"{uuid.uuid4().hex}_{safe_name}"
        key = "/".join(part.strip("/") for part in [subdir, object_name] if part).strip("/")

        object_key = self._apply_prefix(key)
        try:
            res = self._supabase_client().storage.from_(self._bucket).create_signed_upload_url(object_key)
            
            signed_url = res.get("signed_url") or res.get("signedUrl")
            token = res.get("token", "")
            
            if not signed_url:
                raise ValueError("No signed URL returned from Supabase")
                
            storage_reference = f"sb://{self._bucket}/{object_key}"
            
            logger.info("Generated presigned upload URL bucket=%s key=%s", self._bucket, object_key)
            return {
                "signed_url": signed_url,
                "storage_reference": storage_reference,
                "token": token
            }
        except Exception as exc:
            logger.exception("Failed generating presigned upload URL bucket=%s key=%s", self._bucket, object_key)
            raise OSError(f"Could not generate upload URL: {exc}") from exc


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

        self._client = _shared_storage_client(url, key)
        return self._client


_storage_clients: dict[tuple[str, str], Client] = {}
_storage_clients_lock = threading.Lock()


def _shared_storage_client(url: str, key: str) -> Client:
    """Return the per-process Supabase client for ``(url, key)``.

    WHY: ObjectStorage is constructed ad hoc in many routes and services, and
    each instance used to create its own Supabase client with a new
    ``httpx.Client`` -- so no storage request reused a pooled connection
    (every upload/download paid a fresh TCP/TLS handshake) and the clients
    were never closed. One shared client per credentials pair fixes both;
    ``httpx.Client`` is safe to share across threads.
    """
    with _storage_clients_lock:
        client = _storage_clients.get((url, key))
        if client is None:
            options = ClientOptions(httpx_client=httpx.Client(timeout=120.0))
            client = create_client(url, key, options=options)
            _storage_clients[(url, key)] = client
        return client
