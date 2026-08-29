"""The workflow page must describe the project's own analysis, not corrosion.

``GET /workflow/{project_id}`` used to default ``slug`` to the literal
``"corrosion"``. A literal cannot reflect the project, so a Halo project was
titled "Corrosion Workflow", headed "CORROSION ANALYSIS WORKFLOW", and linked
back to ``/analyze/corrosion``. The slug is now resolved from the project's
``analysis_type`` through ``constants.route_for_analysis_type``.

WHAT THIS DOES NOT COVER

    The engine rows inside the panel. Those come from
    ``pipeline_tracker.ENGINE_SPECS``, one global corrosion-only tuple shared
    by the tracker, its JSON payload and this panel, so a seismic run still
    lists GC-001/CC-001/MC-001 below a correct heading. Making that roster
    analysis-aware is a change to the tracker contract, not to this route.

NO LIVE DATABASE

    ``_projects_service`` is monkeypatched, so nothing here reads or writes.

Run: uv run pytest tests/test_workflow_page.py -v
"""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from app.main import app
from app.routes import workflow_page


class FakeProjectsService:
    """Returns one project whose analysis_type the test chooses."""

    def __init__(self, project: dict | None):
        self.project = project

    def get_project(self, project_id: int) -> dict | None:
        return self.project


@pytest.fixture(scope="module")
def client() -> TestClient:
    """One client for the module — importing app.main is slow."""
    return TestClient(app, raise_server_exceptions=False)


def _wire(monkeypatch, analysis_type: str | None):
    project = (
        None
        if analysis_type is None
        else {"id": 7, "name": "Test Project", "analysis_type": analysis_type}
    )
    monkeypatch.setattr(workflow_page, "_projects_service", FakeProjectsService(project))


@pytest.mark.parametrize(
    ("analysis_type", "slug", "heading"),
    [
        ("Halo", "seismic", "SEISMIC ANALYSIS WORKFLOW"),
        ("Piping (Corrosive)", "corrosion", "CORROSION ANALYSIS WORKFLOW"),
        ("Architecture", "architecture", "ARCHITECTURE ANALYSIS WORKFLOW"),
    ],
)
def test_page_describes_the_projects_own_analysis(
    client, monkeypatch, analysis_type, slug, heading
):
    """Title, panel heading and back-link all follow the project."""
    _wire(monkeypatch, analysis_type)

    body = client.get("/workflow/7").text

    assert f"<title>{slug.title()} Workflow - BIM Guard</title>" in body
    assert heading in body
    assert f"/analyze/{slug}?project_id=7" in body


def test_halo_project_is_not_called_corrosion(client, monkeypatch):
    """The regression itself: a seismic project must not say corrosion."""
    _wire(monkeypatch, "Halo")

    body = client.get("/workflow/7").text

    assert "Corrosion Workflow" not in body
    assert "CORROSION ANALYSIS WORKFLOW" not in body
    assert "/analyze/corrosion" not in body


def test_an_explicit_slug_still_wins(client, monkeypatch):
    """Existing links that name a slug keep working."""
    _wire(monkeypatch, "Halo")

    assert "Architecture Workflow" in client.get("/workflow/7?slug=architecture").text


def test_blank_slug_falls_back_to_the_project(client, monkeypatch):
    """An empty query value is 'not supplied', not a slug of ''."""
    _wire(monkeypatch, "Halo")

    assert "Seismic Workflow" in client.get("/workflow/7?slug=").text


@pytest.mark.parametrize("analysis_type", ["", "Nonsense Analysis"])
def test_unmapped_analysis_type_does_not_500(client, monkeypatch, analysis_type):
    """A blank or retired analysis_type falls back instead of raising."""
    _wire(monkeypatch, analysis_type)

    response = client.get("/workflow/7")

    assert response.status_code == 200
    assert "Workflow - BIM Guard" in response.text


def test_missing_project_reports_not_found(client, monkeypatch):
    _wire(monkeypatch, None)

    assert "not found" in client.get("/workflow/7").text.lower()
