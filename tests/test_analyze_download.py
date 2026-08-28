"""Tests for the file download endpoints.

Drives the real ASGI app, so route registration, path-parameter coercion and
the response headers are all exercised.

READ-ONLY AGAINST LIVE SUPABASE

    These are GETs that compute a result and render it; nothing is created,
    updated or deleted. Project ids come from the live database, so the tests
    assert on shape and headers rather than on specific finding counts, which
    would change whenever a model is re-uploaded. See data contracts §5.1.

Run: uv run pytest tests/test_analyze_download.py -v
"""

from __future__ import annotations

import io
import zipfile

import pytest
from starlette.testclient import TestClient

from app.main import app
from app.services.analysis_cache import ANALYSIS_CACHE

#: A project with an IFC model attached and MEP content in it.
PROJECT_WITH_MODEL = 3

#: A project with no IFC model, used for the 409 path.
NONEXISTENT_PROJECT = 999_999_999


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture(autouse=True)
def _clear_cache():
    """Each test starts from a cold cache so hit/miss assertions mean something."""
    ANALYSIS_CACHE.clear()
    yield


class TestFormats:
    @pytest.mark.parametrize(
        "fmt,media_type,extension",
        [
            ("csv", "text/csv", "csv"),
            ("json", "application/json", "json"),
            ("bcf", "application/octet-stream", "bcf"),
        ],
    )
    def test_each_format_downloads(self, client, fmt, media_type, extension):
        response = client.get(f"/download/{fmt}/{PROJECT_WITH_MODEL}")
        assert response.status_code == 200
        assert response.content
        assert media_type in response.headers["content-type"]
        assert extension in response.headers["content-disposition"]

    def test_csv_has_a_header_row(self, client):
        text = client.get(f"/download/csv/{PROJECT_WITH_MODEL}").text
        assert text.splitlines()[0].startswith("id,element_id,rule_id")

    def test_json_separates_findings_from_data_quality(self, client):
        payload = client.get(f"/download/json/{PROJECT_WITH_MODEL}").json()
        assert "findings" in payload
        assert "data_quality" in payload

    def test_bcf_is_a_valid_archive(self, client):
        content = client.get(f"/download/bcf/{PROJECT_WITH_MODEL}").content
        assert zipfile.is_zipfile(io.BytesIO(content))
        with zipfile.ZipFile(io.BytesIO(content)) as zf:
            assert "bcf.version" in zf.namelist()


class TestHeaders:
    """A download must save, not render."""

    def test_disposition_is_attachment(self, client):
        response = client.get(f"/download/csv/{PROJECT_WITH_MODEL}")
        assert response.headers["content-disposition"].startswith("attachment;")

    def test_filename_names_project_and_analysis(self, client):
        disposition = client.get(f"/download/csv/{PROJECT_WITH_MODEL}").headers[
            "content-disposition"
        ]
        assert f"project-{PROJECT_WITH_MODEL}" in disposition
        assert "corrosion" in disposition

    def test_seismic_filename_differs(self, client):
        disposition = client.get(
            f"/download/csv/{PROJECT_WITH_MODEL}?slug=seismic"
        ).headers["content-disposition"]
        assert "seismic" in disposition

    def test_content_length_matches_the_body(self, client):
        response = client.get(f"/download/csv/{PROJECT_WITH_MODEL}")
        assert int(response.headers["content-length"]) == len(response.content)

    def test_downloads_are_not_cached_by_the_browser(self, client):
        """A stored copy could outlive the model it describes."""
        assert client.get(f"/download/csv/{PROJECT_WITH_MODEL}").headers[
            "cache-control"
        ] == "no-store"


class TestSlugSelection:
    def test_defaults_to_corrosion(self, client):
        disposition = client.get(f"/download/csv/{PROJECT_WITH_MODEL}").headers[
            "content-disposition"
        ]
        assert "corrosion" in disposition

    def test_seismic_is_selectable(self, client):
        assert (
            client.get(f"/download/csv/{PROJECT_WITH_MODEL}?slug=seismic").status_code
            == 200
        )

    def test_unknown_slug_is_refused(self, client):
        response = client.get(f"/download/csv/{PROJECT_WITH_MODEL}?slug=nonsense")
        assert response.status_code == 400
        assert "nonsense" in response.text

    def test_refusal_names_the_valid_slugs(self, client):
        response = client.get(f"/download/csv/{PROJECT_WITH_MODEL}?slug=nonsense")
        assert "corrosion" in response.text and "seismic" in response.text


class TestFailures:
    """Errors carry a readable reason and an honest status."""

    def test_missing_project_id_is_a_bad_request(self, client):
        response = client.get("/download/csv/0")
        assert response.status_code == 400

    def test_unknown_project_is_a_conflict_not_a_crash(self, client):
        """409: the request is well-formed, the analysis just cannot be produced."""
        response = client.get(f"/download/csv/{NONEXISTENT_PROJECT}")
        assert response.status_code == 409
        assert "project" in response.text.lower()

    def test_unknown_format_has_no_route(self, client):
        assert client.get(f"/download/pdf/{PROJECT_WITH_MODEL}").status_code == 404

    def test_non_numeric_project_id_is_rejected(self, client):
        assert client.get("/download/csv/abc").status_code in (404, 422)


class TestCaching:
    """Three downloads of one analysis should compute it once."""

    def test_first_download_misses_then_second_hits(self, client):
        client.get(f"/download/csv/{PROJECT_WITH_MODEL}")
        after_first = ANALYSIS_CACHE.stats()
        client.get(f"/download/json/{PROJECT_WITH_MODEL}")
        after_second = ANALYSIS_CACHE.stats()

        assert after_first["misses"] >= 1
        assert after_second["hits"] > after_first["hits"]

    def test_all_three_formats_share_one_computed_result(self, client):
        for fmt in ("csv", "json", "bcf"):
            client.get(f"/download/{fmt}/{PROJECT_WITH_MODEL}")
        assert ANALYSIS_CACHE.stats()["misses"] == 1

    def test_different_analyses_are_cached_separately(self, client):
        client.get(f"/download/csv/{PROJECT_WITH_MODEL}")
        client.get(f"/download/csv/{PROJECT_WITH_MODEL}?slug=seismic")
        assert ANALYSIS_CACHE.stats()["entries"] == 2

    def test_content_is_identical_cached_and_uncached(self, client):
        first = client.get(f"/download/csv/{PROJECT_WITH_MODEL}").content
        ANALYSIS_CACHE.clear()
        recomputed = client.get(f"/download/csv/{PROJECT_WITH_MODEL}").content
        assert first == recomputed, "a cached download must equal a fresh one"
