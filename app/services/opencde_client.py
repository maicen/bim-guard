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
import time

import httpx

from app.logging_config import get_logger

logger = get_logger(__name__)

_CONTENT_DISPOSITION_FILENAME = re.compile(r'filename\*?=(?:UTF-8\'\')?"?([^";]+)"?', re.IGNORECASE)

_RETRY_ATTEMPTS = 3
_RETRY_BASE_DELAY_S = 0.5
#: Retried like a rate limit / transient overload; anything else 4xx/5xx is a
#: real failure worth surfacing immediately rather than masking behind delay.
_RETRYABLE_STATUS_CODES = {429, 502, 503, 504}


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

    def _get_with_retry(self, client: httpx.Client, url: str) -> httpx.Response:
        """GET with retry on transient transport failures and 429/5xx.

        Mirrors the timeout+backoff shape already used by
        ``app.services.bsdd_client.BSDDClient._http_get`` for another external
        REST API -- retries a bounded number of times with exponential
        backoff, honoring ``Retry-After`` when the server sends one, and
        raises immediately on anything not transient (auth failures, 404s,
        malformed requests) instead of masking them behind a delay.
        """
        last_exc: Exception | None = None
        for attempt in range(_RETRY_ATTEMPTS):
            try:
                response = client.get(url, headers=self._headers())
            except httpx.TransportError as exc:
                last_exc = exc
                if attempt == _RETRY_ATTEMPTS - 1:
                    raise
                logger.warning("OpenCDE request to %s failed (attempt %d): %s", url, attempt + 1, exc)
                time.sleep(_RETRY_BASE_DELAY_S * (2**attempt))
                continue
            if response.status_code in _RETRYABLE_STATUS_CODES and attempt < _RETRY_ATTEMPTS - 1:
                retry_after = response.headers.get("Retry-After")
                backoff = (
                    float(retry_after)
                    if retry_after and retry_after.strip().isdigit()
                    else _RETRY_BASE_DELAY_S * (2**attempt)
                )
                logger.warning(
                    "OpenCDE request to %s returned %d (attempt %d), retrying in %.1fs",
                    url,
                    response.status_code,
                    attempt + 1,
                    backoff,
                )
                time.sleep(backoff)
                continue
            return response
        # Unreachable: the loop either returns a response or raises on the last attempt.
        raise last_exc or OpenCDEClientError(f"Exhausted retries for {url}")

    def list_project_documents(self, external_project_id: str) -> list[dict]:
        """List a project's documents via the CDE's admin REST API."""
        client = self._client or httpx.Client(timeout=30.0)
        owns_client = self._client is None
        try:
            response = self._get_with_retry(
                client, f"{self._base_url}/api/projects/{external_project_id}/documents"
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
        except httpx.TransportError as exc:
            raise OpenCDEClientError(f"Failed to list documents: {exc}") from exc
        finally:
            if owns_client:
                client.close()

    def download_document(self, external_project_id: str, document_id: str) -> tuple[str, str, bytes]:
        """Download one document's (filename, mimetype, content bytes), following any redirect to storage."""
        client = self._client or httpx.Client(timeout=120.0, follow_redirects=True)
        owns_client = self._client is None
        try:
            response = self._get_with_retry(
                client,
                f"{self._base_url}/api/projects/{external_project_id}/documents/{document_id}/content",
            )
            self._raise_for_error(response, f"download document {document_id}")
            filename = _filename_from_content_disposition(response.headers.get("content-disposition"))
            content_type = response.headers.get("content-type", "").split(";", 1)[0].strip()
            return filename or document_id, content_type, response.content
        except httpx.TransportError as exc:
            raise OpenCDEClientError(f"Failed to download document {document_id}: {exc}") from exc
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
