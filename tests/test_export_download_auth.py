"""The export download must authenticate from the URL, not only from a header.

MISMATCH 1 of ``docs/validation/final-verification-2026-09-09.md``: since
47cf29b every /api/analyze route requires authentication, and the SPA opens the
report export by navigating the browser to its URL rather than fetching it. A
browser navigation cannot carry an ``Authorization`` header, so all three export
buttons landed on ``{"detail":"Missing bearer token"}`` instead of a file.

The backend was already right: ``get_current_user_flexible`` (app/auth.py)
accepts the token as ``?token=`` for exactly this case. The frontend was not
sending it. These tests pin the contract the frontend now relies on -- that the
route really does accept a query token, and really does refuse without one --
so a future change to either side cannot quietly take the downloads away again.

WHAT IS AND IS NOT UNDER TEST

    ``app.auth._verify`` is monkeypatched. Signature and expiry checking is its
    own concern and needs a live JWKS; what these tests are about is where the
    route is willing to read the token from. The dependency chain that reads it
    is the real one -- only the project access lookup is replaced, by a
    dependency that still requires the same authenticated user.

Run: uv run pytest tests/test_export_download_auth.py -v
"""

from __future__ import annotations

import io
import zipfile
from typing import Annotated
from unittest.mock import patch
from xml.etree import ElementTree as ET

import pytest
from fastapi import Depends
from starlette.testclient import TestClient

from app import auth as auth_module
from app.api.projects import get_project_access_checker_flexible
from app.auth import CurrentUser, get_current_user_flexible
from app.main import app
from tests.test_api_analyze import _synthetic_analysis_result_for_export_tests

#: The project id the synthetic export result is served for. No row is read:
#: run_analysis is patched out and the access check is replaced.
PROJECT_ID = 119

#: Stands in for a signed Supabase JWT. _verify is monkeypatched to accept it.
VALID_TOKEN = "test-access-token"

TEST_USER = CurrentUser(
    id="99999999-9999-9999-9999-999999999999",
    email="test@example.com",
    claims={"sub": "99999999-9999-9999-9999-999999999999"},
)


def _authenticated_no_op_checker(
    _user: Annotated[CurrentUser, Depends(get_current_user_flexible)],
):
    """Replace the project access lookup, keeping the authentication in front of it.

    The export route's only authentication is the one inside
    ``get_project_access_checker_flexible``. Overriding that dependency with a
    plain lambda would remove the 401 these tests exist to assert, so the
    override keeps ``get_current_user_flexible`` as its own dependency and
    drops only the organization/ownership lookup, which needs live rows.
    """
    return lambda project_id: None


@pytest.fixture
def client(monkeypatch) -> TestClient:
    """A client whose auth is the real dependency, with only _verify stubbed."""
    monkeypatch.setattr(
        auth_module,
        "_verify",
        lambda token: TEST_USER if token == VALID_TOKEN else _reject(token),
    )

    # tests/conftest.py authenticates every request app-wide. That override has
    # to come off for this file, or "no token" could not be expressed at all.
    saved = dict(app.dependency_overrides)
    app.dependency_overrides.pop(get_current_user_flexible, None)
    app.dependency_overrides[get_project_access_checker_flexible] = (
        _authenticated_no_op_checker
    )
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(saved)


def _reject(token: str):
    from fastapi import HTTPException, status

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired authentication token",
    )


def _export(client: TestClient, fmt: str, *, token: str | None, header: bool = False):
    url = f"/api/analyze/export?project_id={PROJECT_ID}&slug=corrosion&fmt={fmt}"
    headers = {}
    if token and header:
        headers["Authorization"] = f"Bearer {token}"
    elif token:
        url += f"&token={token}"
    with patch(
        "app.api.analyze.run_analysis",
        return_value=_synthetic_analysis_result_for_export_tests(),
    ):
        return client.get(url, headers=headers)


class TestQueryTokenIsAccepted:
    """?token= is the frontend's only way to authenticate a navigation."""

    def test_bcf_export_with_a_query_token_returns_the_archive(self, client):
        """200, and the body is a real BCF archive rather than an error page."""
        response = _export(client, "bcf", token=VALID_TOKEN)
        assert response.status_code == 200

        assert response.content[:2] == b"PK", "not a zip"
        archive = zipfile.ZipFile(io.BytesIO(response.content))
        names = archive.namelist()
        assert "bcf.version" in names
        markups = [n for n in names if n.endswith("markup.bcf")]
        assert markups, f"no topic markup in the archive: {names}"

        topics = 0
        for name in markups:
            topics += len(ET.fromstring(archive.read(name).decode("utf-8")).findall(".//Topic"))
        # 3 Critical + 4 High + 5 Medium. BCF's defaults drop Low ("asset
        # register only -- no BCF issue") and the data-quality notes, which is
        # why this is 12 where the CSV below carries all 25 rows.
        assert topics == 12, topics

        assert ".bcf" in response.headers["content-disposition"]

    def test_csv_export_with_a_query_token_returns_the_register(self, client):
        """The CSV body is the asset register, header row and all 25 rows."""
        response = _export(client, "csv", token=VALID_TOKEN)
        assert response.status_code == 200
        lines = response.text.strip().splitlines()
        assert lines[0].startswith("id,element_id,rule_id")
        assert len(lines) == 26
        assert "text/csv" in response.headers["content-type"]

    def test_json_export_with_a_query_token_returns_the_findings(self, client):
        """The JSON body carries the findings and the data-quality notes."""
        response = _export(client, "json", token=VALID_TOKEN)
        assert response.status_code == 200
        payload = response.json()
        assert len(payload["findings"]) == 18
        assert len(payload["data_quality"]) == 7

    def test_a_header_token_still_works(self, client):
        """The query parameter is additive: fetch-based callers are unaffected."""
        response = _export(client, "csv", token=VALID_TOKEN, header=True)
        assert response.status_code == 200
        assert response.text.strip().splitlines()[0].startswith("id,element_id,rule_id")


class TestNoTokenIsRefused:
    """The 401 the demo hit. Without it the test above proves nothing."""

    @pytest.mark.parametrize("fmt", ["bcf", "csv", "json"])
    def test_export_without_a_token_is_401(self, client, fmt):
        response = _export(client, fmt, token=None)
        assert response.status_code == 401
        assert response.json()["detail"] == "Missing bearer token"

    def test_an_invalid_token_is_401(self, client):
        """A token that does not verify is refused, not waved through."""
        response = _export(client, "csv", token="not-a-real-token")
        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid or expired authentication token"
