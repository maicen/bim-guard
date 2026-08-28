"""Tests for the Piping (Corrosion) analysis form and its async run endpoint.

WHAT IS DRIVEN THROUGH HTTP AND WHAT IS NOT

    ``tests/test_routes.py`` explains the constraint this suite inherits: the
    HTTP tests run against the live Supabase project, with no test double and
    no rollback. So the requests made here are ones the handler refuses before
    it reaches the analysis -- no project id, an unparseable id, an id nothing
    owns. That covers registration, method binding and every validation branch
    without starting a background thread or leaving rows behind.

    The dispatch path is deliberately *not* driven through HTTP: a successful
    POST detaches a daemon thread that reads a real model out of storage. It is
    covered instead by calling the route's helpers directly, which is where the
    logic that could actually be wrong lives.

WHY THE RENDERED HTML IS ASSERTED ON

    The form is a plain POST with no client script, so what it submits is
    entirely determined by the ``name`` and ``checked`` attributes on its
    inputs. A renamed field or a default that silently flips stays visually
    identical while changing what the engine is asked to do, so the field names
    and the five engine defaults are asserted directly.

Run: uv run pytest tests/test_piping_analysis_ui.py -v
"""

from __future__ import annotations

import re

import pytest
from fasthtml.common import to_xml
from starlette.testclient import TestClient

from app.components.piping_analysis_ui import (
    COUNT_OPTIONS,
    RUN_ENDPOINT,
    EngineOption,
    engine_options,
    piping_analysis_form,
)
from app.main import app
from app.routes.piping_routes import _selected_engines

# Matches tests/test_routes.py: large and numeric so it survives int()
# coercion and reaches the service layer, which is the part under test.
NONEXISTENT_ID = 999_999_999

#: Rows shaped like the service returns, so the form can be rendered without
#: touching Supabase.
FAKE_PROJECTS = [{"id": 7, "name": "Harbour Pump House"}, {"id": 8, "name": "Chiller Plant"}]
FAKE_FOLDERS = [{"ruleset_id": "BIMGUARD-GC-001", "count": 12}]
FAKE_DOCUMENTS = [{"id": 3, "filename": "client-spec.pdf"}]


class _FakeForm:
    """The slice of Starlette's ``FormData`` that ``_selected_engines`` uses."""

    def __init__(self, values: list[str]):
        self._values = values

    def getlist(self, key: str) -> list[str]:
        return self._values if key == "engines" else []


@pytest.fixture
def form_html() -> str:
    """Render the form once with fake rows, for the markup assertions."""
    return to_xml(piping_analysis_form(7, FAKE_PROJECTS, FAKE_FOLDERS, FAKE_DOCUMENTS))


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


# ---------------------------------------------------------------------------
# Rendered form
# ---------------------------------------------------------------------------


def test_form_posts_to_the_run_endpoint(form_html: str):
    """The form's action must match the endpoint the route registers."""
    assert f'action="{RUN_ENDPOINT}"' in form_html
    assert 'method="post"' in form_html


@pytest.mark.parametrize(
    "field",
    ["project_id", "rule_folder", "document_ids", "engines"]
    + [name for name, _, _ in COUNT_OPTIONS],
)
def test_every_field_is_submitted_under_its_expected_name(form_html: str, field: str):
    """A renamed field would be dropped silently by the handler."""
    assert f'name="{field}"' in form_html


def test_the_named_project_is_preselected(form_html: str):
    """Arriving from /analysis/piping/7 should not require re-picking project 7."""
    assert '<option value="7" selected>Harbour Pump House</option>' in form_html
    assert '<option value="8"' in form_html


def test_all_five_engines_are_offered(form_html: str):
    """The selector shows the whole queue, gated engines included."""
    rendered = re.findall(r'<input[^>]*name="engines"[^>]*>', form_html)
    codes = [re.search(r'value="([^"]+)"', row).group(1) for row in rendered]
    assert codes == ["GC-001", "CC-001", "MC-001", "MM-001", "XM-001"]


def test_core_engines_are_checked_and_path_b_engines_are_not():
    """GC/CC/MC start ticked; MM/XM start clear, per the Path B defaults."""
    defaults = {engine.code: engine.default_checked for engine in engine_options()}
    assert defaults == {
        "GC-001": True,
        "CC-001": True,
        "MC-001": True,
        "MM-001": False,
        "XM-001": False,
    }


@pytest.mark.parametrize("flag_enabled", [True, False])
def test_a_flag_gated_engine_renders_disabled_and_unchecked(monkeypatch, flag_enabled: bool):
    """A control that cannot affect the run must not look like one that can.

    Both flag states are exercised because the environment the suite runs in
    decides the real one, and a test that only passes with the flags off would
    stop proving anything the moment Path B is switched on.
    """
    monkeypatch.setattr(
        "app.components.piping_analysis_ui.engine_options",
        lambda: (
            EngineOption("MM-001", "Material / media", "detail", True, flag_enabled=flag_enabled),
        ),
    )
    html = to_xml(piping_analysis_form(7, FAKE_PROJECTS, FAKE_FOLDERS, FAKE_DOCUMENTS))
    row = re.search(r'<input[^>]*value="MM-001"[^>]*>', html).group(0)

    # default_checked stays True in both cases: the renderer clears the box off
    # the flag, rather than the spec being rewritten per deployment.
    assert ("disabled" in row) is not flag_enabled
    assert ("checked" in row) is flag_enabled


def test_count_options_carry_the_documented_defaults(form_html: str):
    """Openings and spaces default on, type definitions off."""
    for name, _, checked in COUNT_OPTIONS:
        row = re.search(rf'<input[^>]*name="{name}"[^>]*>', form_html).group(0)
        assert ("checked" in row) is checked, name


def test_documents_render_as_a_multi_select(form_html: str):
    """Each document is its own checkbox under one repeated name."""
    assert 'name="document_ids" value="3"' in form_html
    assert "client-spec.pdf" in form_html


def test_empty_document_list_explains_itself():
    """An empty list is a state to describe, not an empty box."""
    html = to_xml(piping_analysis_form(7, FAKE_PROJECTS, FAKE_FOLDERS, []))
    assert "No documents have been uploaded yet" in html
    assert 'name="document_ids"' not in html


def test_styles_are_scoped_to_the_page(form_html: str):
    """The prototype's class names must not leak into MonsterUI's."""
    # The form itself carries the prototype class names; the stylesheet that
    # gives them meaning is scoped, and lives in piping_analysis_assets().
    assert 'class="card"' in form_html
    from app.components.piping_analysis_ui import piping_analysis_assets

    css = to_xml(piping_analysis_assets()[0])
    selectors = re.findall(r"^\s*(\.[\w.-]+)", css, flags=re.MULTILINE)
    assert selectors, "no selectors found in the scoped stylesheet"
    assert all(sel.startswith(".pp-scope") for sel in selectors), selectors


# ---------------------------------------------------------------------------
# Engine selection
# ---------------------------------------------------------------------------


def test_selected_engines_keeps_queue_order_regardless_of_submission_order():
    """The log reads the same however the browser serialised the boxes."""
    assert _selected_engines(_FakeForm(["MC-001", "GC-001"])) == ["GC-001", "MC-001"]


def test_selected_engines_drops_codes_the_selector_never_offered():
    """The value arrives from the client and is not trusted."""
    assert _selected_engines(_FakeForm(["GC-001", "ZZ-999", ""])) == ["GC-001"]


def test_selected_engines_is_empty_when_nothing_was_ticked():
    """Empty is a valid answer; the caller reads it as 'default engines'."""
    assert _selected_engines(_FakeForm([])) == []


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


def test_the_form_page_is_registered(client: TestClient):
    """A missing project renders the not-found block, not a 500."""
    response = client.get(f"/analysis/piping/{NONEXISTENT_ID}")
    assert response.status_code == 200
    assert "not found" in response.text.lower()


def test_the_run_endpoint_does_not_answer_get(client: TestClient):
    """POST-only, so a refresh of the run URL cannot re-dispatch a run."""
    assert client.get(RUN_ENDPOINT).status_code in (404, 405)


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        ({"project_id": ""}, "Please+select+a+project."),
        ({"project_id": "not-a-number"}, "Invalid+project+selection."),
        ({"project_id": str(NONEXISTENT_ID)}, "no+longer+exists"),
    ],
)
def test_a_rejected_submission_redirects_with_its_reason(
    client: TestClient, payload: dict, expected: str
):
    """Rejections land back on a page that exists, carrying the reason."""
    response = client.post(RUN_ENDPOINT, data=payload, follow_redirects=False)
    assert response.status_code == 303
    location = response.headers["location"]
    assert location.startswith("/projects?error=")
    assert expected.replace("+", "%20") in location or expected in location


def test_an_htmx_rejection_is_a_400_not_a_redirect(client: TestClient):
    """HTMX follows a 303 itself, which would swap a whole page into the form."""
    response = client.post(
        RUN_ENDPOINT, data={"project_id": ""}, headers={"hx-request": "true"}
    )
    assert response.status_code == 400
    assert "select a project" in response.text
