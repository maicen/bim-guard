"""Tests for the Seismic (Blue Halo) analysis form and its async run endpoint.

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
    and the count-option defaults are asserted directly.

Run: uv run pytest tests/test_seismic_analysis_ui.py -v
"""

from __future__ import annotations

import json
import re
from urllib.parse import quote

import pytest
from fasthtml.common import to_xml
from starlette.testclient import TestClient

from app.components.seismic_analysis_ui import (
    COUNT_OPTIONS,
    FALLBACK_CLEARANCE_MM,
    FALLBACK_JURISDICTION,
    RUN_ENDPOINT,
    active_clearance_config,
    seismic_analysis_assets,
    seismic_analysis_form,
)
from app.main import app
from app.routes.seismic_routes import _clearance_mm

# Matches tests/test_routes.py: large and numeric so it survives int()
# coercion and reaches the service layer, which is the part under test.
NONEXISTENT_ID = 999_999_999

#: Rows shaped like the service returns, so the form can be rendered without
#: touching Supabase.
FAKE_PROJECTS = [{"id": 7, "name": "Harbour Pump House"}, {"id": 8, "name": "Chiller Plant"}]


class _FakeForm:
    """The slice of Starlette's ``FormData`` that ``_clearance_mm`` uses."""

    def __init__(self, value: str | None):
        self._value = value

    def get(self, key: str, default=None):
        if key == "clearance_mm":
            return self._value
        return default


@pytest.fixture
def form_html() -> str:
    """Render the form once with fake rows, for the markup assertions."""
    return to_xml(seismic_analysis_form(7, FAKE_PROJECTS))


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
    ["project_id", "seismic_codes", "clearance_mm"] + [name for name, _, _ in COUNT_OPTIONS],
)
def test_every_field_is_submitted_under_its_expected_name(form_html: str, field: str):
    """A renamed field would be dropped silently by the handler."""
    assert f'name="{field}"' in form_html


def test_the_named_project_is_preselected(form_html: str):
    """Arriving from /analysis/seismic/7 should not require re-picking project 7."""
    assert '<option value="7" selected>Harbour Pump House</option>' in form_html
    assert '<option value="8"' in form_html


def test_submit_button_is_labelled_for_seismic(form_html: str):
    """The page is reachable from several places; the button says which run."""
    assert "Run Seismic Analysis" in form_html


def test_clearance_is_a_bounded_number_input(form_html: str):
    """A free-text clearance would let a typo reach the log as a value."""
    row = re.search(r'<input[^>]*name="clearance_mm"[^>]*>', form_html).group(0)
    assert 'type="number"' in row
    assert 'min="0"' in row


def test_clearance_is_offered_in_millimetres_not_metres(form_html: str):
    """The config, the engine and every finding use mm; metres would mislead."""
    assert "Clearance Distance Threshold (mm)" in form_html
    assert "(m)" not in form_html


def test_clearance_is_prefilled_from_the_loaded_config(form_html: str):
    """The box should open on what the run will actually apply."""
    _, clearance_mm = active_clearance_config()
    row = re.search(r'<input[^>]*name="clearance_mm"[^>]*>', form_html).group(0)
    assert f'value="{clearance_mm}"' in row


def test_codes_field_is_prefilled_from_the_loaded_config(form_html: str):
    """The standards cited come from the config, so that is what it opens on."""
    jurisdiction, _ = active_clearance_config()
    row = re.search(r'<input[^>]*name="seismic_codes"[^>]*>', form_html).group(0)
    assert jurisdiction in row


def test_count_options_carry_the_documented_defaults(form_html: str):
    """Openings and spaces default on, type definitions off."""
    for name, _, checked in COUNT_OPTIONS:
        row = re.search(rf'<input[^>]*name="{name}"[^>]*>', form_html).group(0)
        assert ("checked" in row) is checked, name


def test_no_engine_selector_is_offered(form_html: str):
    """Blue Halo is one engine; a selector would imply a choice that is not there."""
    assert 'name="engines"' not in form_html


def test_styles_are_scoped_to_the_page(form_html: str):
    """The prototype's class names must not leak into MonsterUI's."""
    assert 'class="card"' in form_html
    css = to_xml(seismic_analysis_assets()[0])
    selectors = re.findall(r"^\s*(\.[\w.-]+)", css, flags=re.MULTILINE)
    assert selectors, "no selectors found in the scoped stylesheet"
    assert all(sel.startswith(".pp-scope") for sel in selectors), selectors


# ---------------------------------------------------------------------------
# Clearance config
# ---------------------------------------------------------------------------


def test_active_config_reads_the_shipped_jurisdiction():
    """The form states the config actually on disk, not a hardcoded label."""
    jurisdiction, clearance_mm = active_clearance_config()
    assert jurisdiction
    assert clearance_mm >= 0


def test_active_config_matches_the_file_on_disk():
    """Reading the JSON directly must agree with what the form displays."""
    from app.components.seismic_analysis_ui import DEFAULT_CONFIG_PATH

    if not DEFAULT_CONFIG_PATH.exists():
        pytest.skip("jurisdiction config not present in this checkout")
    raw = json.loads(DEFAULT_CONFIG_PATH.read_text(encoding="utf-8"))
    jurisdiction, clearance_mm = active_clearance_config()
    assert jurisdiction == raw["metadata"]["jurisdiction"]
    assert clearance_mm == float(raw["clearance_rules"]["base_from_structure_mm"])


def test_a_missing_config_falls_back_instead_of_raising(monkeypatch):
    """A form that cannot state the clearance still beats a 500."""
    from pathlib import Path

    import app.components.seismic_analysis_ui as ui

    monkeypatch.setattr(ui, "DEFAULT_CONFIG_PATH", Path("data/does-not-exist.json"))
    assert ui.active_clearance_config() == (FALLBACK_JURISDICTION, FALLBACK_CLEARANCE_MM)


def test_a_malformed_config_falls_back_instead_of_raising(monkeypatch, tmp_path):
    """Truncated JSON is a bad deploy, not a reason to lose the page."""
    import app.components.seismic_analysis_ui as ui

    broken = tmp_path / "broken.json"
    broken.write_text("{not json", encoding="utf-8")
    monkeypatch.setattr(ui, "DEFAULT_CONFIG_PATH", broken)
    assert ui.active_clearance_config() == (FALLBACK_JURISDICTION, FALLBACK_CLEARANCE_MM)


def test_a_non_numeric_clearance_in_config_falls_back(monkeypatch, tmp_path):
    """One bad field should not cost the jurisdiction label as well."""
    import app.components.seismic_analysis_ui as ui

    path = tmp_path / "config.json"
    path.write_text(
        json.dumps(
            {
                "metadata": {"jurisdiction": "Test Jurisdiction"},
                "clearance_rules": {"base_from_structure_mm": "not-a-number"},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(ui, "DEFAULT_CONFIG_PATH", path)
    assert ui.active_clearance_config() == ("Test Jurisdiction", FALLBACK_CLEARANCE_MM)


# ---------------------------------------------------------------------------
# Clearance parsing
# ---------------------------------------------------------------------------


def test_clearance_parses_a_plain_number():
    assert _clearance_mm(_FakeForm("250")) == 250.0


def test_clearance_accepts_a_decimal():
    assert _clearance_mm(_FakeForm("212.5")) == 212.5


def test_clearance_accepts_zero():
    """Zero is a real request -- report every intrusion -- not a missing value."""
    assert _clearance_mm(_FakeForm("0")) == 0.0


def test_a_blank_clearance_defers_to_the_config():
    assert _clearance_mm(_FakeForm("")) is None


def test_a_missing_clearance_defers_to_the_config():
    assert _clearance_mm(_FakeForm(None)) is None


def test_a_non_numeric_clearance_defers_to_the_config():
    """The value arrives from the client and is not trusted."""
    assert _clearance_mm(_FakeForm("wide")) is None


def test_a_negative_clearance_is_rejected():
    """No envelope is smaller than nothing."""
    assert _clearance_mm(_FakeForm("-5")) is None


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


def test_the_form_page_is_registered(client: TestClient):
    """A missing project renders the not-found block, not a 500."""
    response = client.get(f"/analysis/seismic/{NONEXISTENT_ID}")
    assert response.status_code == 200
    assert "not found" in response.text.lower()


def test_the_run_endpoint_does_not_answer_get(client: TestClient):
    """POST-only, so a refresh of the run URL cannot re-dispatch a run."""
    assert client.get(RUN_ENDPOINT).status_code in (404, 405)


def test_the_piping_page_is_still_registered(client: TestClient):
    """Two pages now sit under /analysis/<slug>/{id}; neither may shadow the other."""
    assert client.get(f"/analysis/piping/{NONEXISTENT_ID}").status_code == 200


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        ({"project_id": ""}, "select a project"),
        ({"project_id": "not-a-number"}, "Invalid project selection"),
        ({"project_id": str(NONEXISTENT_ID)}, "no longer exists"),
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
    # The reason is percent-encoded into the query string, so the phrase is
    # encoded the same way before looking for it.
    assert quote(expected) in location


def test_an_htmx_rejection_is_a_400_not_a_redirect(client: TestClient):
    """HTMX follows a 303 itself, which would swap a whole page into the form."""
    response = client.post(
        RUN_ENDPOINT, data={"project_id": ""}, headers={"hx-request": "true"}
    )
    assert response.status_code == 400
    assert "select a project" in response.text
