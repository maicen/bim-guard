"""Fetch publicly link-shared Google Drive files via the Drive v3 REST API.

API-key-only access (no OAuth/service-account flow) — works only for files
shared "Anyone with the link". A private file, a bad/unset key, or the
Drive API not being enabled on that key's Google Cloud project all surface
as a clear GoogleDriveError rather than a generic HTTP failure.
"""

from __future__ import annotations

import re

import httpx

from app.logging_config import get_logger

logger = get_logger(__name__)

_DRIVE_API_BASE = "https://www.googleapis.com/drive/v3"
# Matches both share-link shapes: /file/d/{id}/... and open?id={id}
_FILE_ID_URL_PATTERN = re.compile(r"/file/d/([a-zA-Z0-9_-]+)")
_FILE_ID_QUERY_PATTERN = re.compile(r"[?&]id=([a-zA-Z0-9_-]+)")
# A bare Drive file id, when the caller passes one directly instead of a URL.
_BARE_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{10,}$")

# Native Google Docs/Sheets/Slides have no downloadable binary — they must be
# exported to a concrete format instead of fetched with alt=media.
_EXPORT_MIME_TYPES = {
    "application/vnd.google-apps.document": "application/pdf",
    "application/vnd.google-apps.spreadsheet": (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    ),
    "application/vnd.google-apps.presentation": "application/pdf",
}
_EXPORT_EXTENSIONS = {
    "application/pdf": ".pdf",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
}


class GoogleDriveError(RuntimeError):
    """Raised when a Drive file can't be resolved/fetched with the configured API key."""


class GoogleDriveService:
    """Resolve a Drive share link/id and fetch its content via the v3 REST API."""

    def __init__(self, *, api_key: str | None = None, client: httpx.Client | None = None) -> None:
        """Initialize with an injectable API key and HTTP client (dependency injection)."""
        from app.modules.config import GOOGLE_DRIVE_API_KEY

        self._api_key = api_key if api_key is not None else GOOGLE_DRIVE_API_KEY
        self._client = client

    @staticmethod
    def resolve_file_id(url_or_id: str) -> str:
        """Extract a Drive file id from a share URL, or pass a bare id through."""
        candidate = (url_or_id or "").strip()
        if not candidate:
            raise GoogleDriveError("Empty Google Drive URL/ID.")

        match = _FILE_ID_URL_PATTERN.search(candidate) or _FILE_ID_QUERY_PATTERN.search(candidate)
        if match:
            return match.group(1)

        if "drive.google.com" in candidate or "docs.google.com" in candidate:
            raise GoogleDriveError(f"Could not parse a Drive file ID out of URL: {candidate}")

        if _BARE_ID_PATTERN.match(candidate):
            return candidate

        raise GoogleDriveError(f"Not a recognizable Google Drive URL or file ID: {candidate}")

    def fetch(self, url_or_id: str) -> tuple[str, str, bytes]:
        """Fetch one Drive file's (filename, mimetype, content bytes).

        Raises GoogleDriveError with a clear message when the API key is
        missing, the file isn't publicly shared, or the file doesn't exist.
        """
        if not self._api_key:
            raise GoogleDriveError(
                "GOOGLE_DRIVE_API_KEY is not configured — set it in .env to import from Google Drive."
            )

        file_id = self.resolve_file_id(url_or_id)
        client = self._client or httpx.Client(timeout=60.0, follow_redirects=True)
        owns_client = self._client is None
        try:
            name, mimetype = self._fetch_metadata(client, file_id)
            export_mimetype = _EXPORT_MIME_TYPES.get(mimetype)
            if export_mimetype:
                content = self._export(client, file_id, export_mimetype)
                name = name + _EXPORT_EXTENSIONS.get(export_mimetype, "")
                return name, export_mimetype, content

            content = self._download(client, file_id)
            return name, mimetype, content
        finally:
            if owns_client:
                client.close()

    def _fetch_metadata(self, client: httpx.Client, file_id: str) -> tuple[str, str]:
        response = client.get(
            f"{_DRIVE_API_BASE}/files/{file_id}",
            params={"fields": "name,mimeType,size", "key": self._api_key},
        )
        self._raise_for_drive_error(response, file_id)
        data = response.json()
        return data.get("name") or f"drive-{file_id}", data.get("mimeType") or "application/octet-stream"

    def _download(self, client: httpx.Client, file_id: str) -> bytes:
        response = client.get(
            f"{_DRIVE_API_BASE}/files/{file_id}",
            params={"alt": "media", "key": self._api_key},
        )
        self._raise_for_drive_error(response, file_id)
        return response.content

    def _export(self, client: httpx.Client, file_id: str, export_mimetype: str) -> bytes:
        response = client.get(
            f"{_DRIVE_API_BASE}/files/{file_id}/export",
            params={"mimeType": export_mimetype, "key": self._api_key},
        )
        self._raise_for_drive_error(response, file_id)
        return response.content

    @staticmethod
    def _raise_for_drive_error(response: httpx.Response, file_id: str) -> None:
        if response.status_code == 200:
            return
        if response.status_code == 403:
            raise GoogleDriveError(
                f"Google Drive file {file_id} is not accessible with this API key — "
                "it must be shared 'Anyone with the link', and the Drive API must be "
                "enabled on the Google Cloud project the key belongs to."
            )
        if response.status_code == 404:
            raise GoogleDriveError(f"Google Drive file {file_id} was not found.")
        logger.warning("Google Drive request failed file_id=%s status=%s body=%s", file_id, response.status_code, response.text[:500])
        raise GoogleDriveError(f"Google Drive request failed for file {file_id} (HTTP {response.status_code}).")
