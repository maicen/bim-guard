"""HTTP client for pulling documents from an external openCDE Documents API server.

Talks to the buildingSMART openCDE Foundation + Documents API surface
(https://github.com/buildingSMART/documents-API): a bearer-token-authenticated
admin REST listing to discover a project's documents, then per-document
content download. Verified against a self-hosted, Supabase-JWT-authenticated
openCDE server (a modernized fork of Dangl.OpenCDE) that validates the same
Supabase project BIM-Guard's own users sign in against -- so the caller's own
access token, forwarded as-is, authenticates both sides.
"""

from __future__ import annotations

import re

import httpx

from app.logging_config import get_logger

logger = get_logger(__name__)

_CONTENT_DISPOSITION_FILENAME = re.compile(r'filename\*?=(?:UTF-8\'\')?"?([^";]+)"?', re.IGNORECASE)


class OpenCDEClientError(RuntimeError):
    """Raised when an external CDE server request fails or returns unexpected data."""


class OpenCDEDocumentsClient:
    """Lists and downloads documents from an external openCDE-conformant CDE server."""

    def __init__(self, *, base_url: str, access_token: str, client: httpx.Client | None = None) -> None:
        self._base_url = base_url.rstrip("/")
        self._access_token = access_token
        self._client = client

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._access_token}"}

    def list_project_documents(self, external_project_id: str) -> list[dict]:
        """List a project's documents via the CDE's admin REST API."""
        client = self._client or httpx.Client(timeout=30.0)
        owns_client = self._client is None
        try:
            response = client.get(
                f"{self._base_url}/api/projects/{external_project_id}/documents",
                headers=self._headers(),
            )
            self._raise_for_error(response, "list documents")
            data = response.json()
            if isinstance(data, list):
                return data
            if isinstance(data, dict):
                for key in ("data", "items", "results"):
                    if isinstance(data.get(key), list):
                        return data[key]
            return []
        finally:
            if owns_client:
                client.close()

    def download_document(self, external_project_id: str, document_id: str) -> tuple[str, str, bytes]:
        """Download one document's (filename, mimetype, content bytes), following any redirect to storage."""
        client = self._client or httpx.Client(timeout=120.0, follow_redirects=True)
        owns_client = self._client is None
        try:
            response = client.get(
                f"{self._base_url}/api/projects/{external_project_id}/documents/{document_id}/content",
                headers=self._headers(),
            )
            self._raise_for_error(response, f"download document {document_id}")
            filename = _filename_from_content_disposition(response.headers.get("content-disposition"))
            content_type = response.headers.get("content-type", "").split(";", 1)[0].strip()
            return filename or document_id, content_type, response.content
        finally:
            if owns_client:
                client.close()

    @staticmethod
    def _raise_for_error(response: httpx.Response, action: str) -> None:
        if response.status_code >= 400:
            raise OpenCDEClientError(
                f"Failed to {action}: HTTP {response.status_code} - {response.text[:300]}"
            )


def _filename_from_content_disposition(header_value: str | None) -> str | None:
    if not header_value:
        return None
    match = _CONTENT_DISPOSITION_FILENAME.search(header_value)
    return match.group(1) if match else None
