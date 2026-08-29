"""Tests for the five-step project setup wizard.

WHAT IS ASSERTED, AND WHERE

    Most of this suite calls the component directly. That is where the rules
    live: :func:`validate_step` decides what "unlocked" means, and the handler
    only calls it. Driving every rule through HTTP would prove the same thing
    once per step and much more slowly.

    The HTTP tests cover what only the wiring can get wrong -- registration,
    method binding, the staging upload's contract, and that a hand-made POST
    claiming to be on step 5 does not get step 5.

WHAT IS DELIBERATELY NOT TESTED HERE

    Creating the project. That lives in
    :mod:`app.routes.wizard_routes`, reached through the ``on_submit``
    callback, and running it would leave rows in the live Supabase project this
    suite has no way to roll back. The callback contract is tested instead: the
    wizard calls it exactly once, with the emitted dict, and returns whatever
    it returns.

Run: uv run pytest tests/test_project_setup_wizard.py -v
"""

from __future__ import annotations

import asyncio
import re

import pytest
from fasthtml.common import to_xml
from starlette.testclient import TestClient

from app.components.project_setup_wizard import (
    SETTINGS_FLAGS,
    STATUS_CHOICES,
    TOTAL_STEPS,
    ProjectSetupWizard,
    clamp_step,
    collect_form_data,
    emit_form_data,
    first_incomplete_step,
    handle_wizard_post,
    human_size,
    validate_all_steps,
    validate_step,
)
from app.constants import ANALYSIS_TYPES, PROJECT_TYPES
from app.main import app

FAKE_DOCUMENTS = [
    {"id": 3, "filename": "client-spec.pdf"},
    {"id": 4, "filename": "structural-notes.pdf"},
]


def complete_data(**overrides) -> dict:
    """Answers that satisfy every step, before any override is applied."""
    data = {
        "project_name": "Harbour Pump House",
        "description": "",
        "location": "United Kingdom",
        "project_size_sqm": "2400",
        "buildings": "2",
        "floors": "4",
        "project_type": "Industrial",
        "analysis_types": ["Piping (Corrosive)"],
        "ifc_file_reference": "sb://bucket/uploads/ifc/abc_model.ifc",
        "ifc_filename": "model.ifc",
        "ifc_size_bytes": "4322",
        "document_ids": ["3"],
        "standards_codes": [],
        "status": "Draft",
    }
    data.update(overrides)
    return data


class _FakeForm:
    """The slice of Starlette's ``FormData`` the handler uses."""

    def __init__(self, scalars: dict, lists: dict | None = None):
        self._scalars = scalars
        self._lists = lists or {}

    def get(self, key, default=None):
        return self._scalars.get(key, default)

    def getlist(self, key):
        return self._lists.get(key, [])


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


# ---------------------------------------------------------------------------
# Step 1 validation
# ---------------------------------------------------------------------------


def test_step_one_accepts_a_fully_answered_screen():
    assert validate_step(1, complete_data()) == []


@pytest.mark.parametrize(
    "field",
    ["project_name", "location", "project_size_sqm", "buildings", "floors", "project_type"],
)
def test_step_one_rejects_each_missing_required_field(field: str):
    assert validate_step(1, complete_data(**{field: ""}))


def test_step_one_treats_description_as_optional():
    assert validate_step(1, complete_data(description="")) == []


def test_step_one_requires_at_least_one_analysis_type():
    assert validate_step(1, complete_data(analysis_types=[]))
    assert validate_step(1, complete_data(analysis_types=list(ANALYSIS_TYPES))) == []


def test_step_one_rejects_an_unrecognised_analysis_type():
    assert validate_step(1, complete_data(analysis_types=["Telepathy"]))


def test_step_one_rejects_an_unrecognised_project_type():
    assert validate_step(1, complete_data(project_type="Treehouse"))


def test_step_one_rejects_a_location_off_the_list():
    assert validate_step(1, complete_data(location="Atlantis"))


@pytest.mark.parametrize("bad", ["0", "-5", "abc"])
def test_project_size_must_be_a_positive_number(bad: str):
    assert validate_step(1, complete_data(project_size_sqm=bad))


def test_project_size_accepts_a_decimal_area():
    """Floor area is a measurement, not a count."""
    assert validate_step(1, complete_data(project_size_sqm="2400.5")) == []


@pytest.mark.parametrize("field", ["buildings", "floors"])
def test_counts_reject_a_fraction(field: str):
    """Half a floor is not a floor."""
    assert validate_step(1, complete_data(**{field: "2.5"}))
    assert validate_step(1, complete_data(**{field: "2"})) == []


# ---------------------------------------------------------------------------
# Steps 2-5 validation
# ---------------------------------------------------------------------------


def test_step_two_is_satisfied_by_a_reference_not_a_file():
    """The file itself never reaches the step; only what the upload returned."""
    assert validate_step(2, complete_data(ifc_file_reference=""))
    assert validate_step(2, complete_data()) == []


def test_step_three_requires_at_least_one_document():
    assert validate_step(3, complete_data(document_ids=[]))
    assert validate_step(3, complete_data(document_ids=["3", "4"])) == []


def test_step_four_is_satisfied_when_left_completely_empty():
    """Settings are optional, so an untouched step 4 is a complete step 4."""
    assert validate_step(4, complete_data(standards_codes=[], status="")) == []


def test_step_four_still_rejects_a_value_that_is_present_and_wrong():
    assert validate_step(4, complete_data(standards_codes=["not-a-standard"]))
    assert validate_step(4, complete_data(status="Demolished"))


def test_step_five_rechecks_every_earlier_step():
    """Reaching review with an earlier answer edited away is not submittable."""
    assert validate_step(5, complete_data()) == []
    assert validate_step(5, complete_data(project_name=""))


def test_an_unknown_step_is_reported_rather_than_raising():
    assert validate_step(99, {})


def test_validate_all_steps_collects_every_reason():
    problems = validate_all_steps(complete_data(project_name="", document_ids=[]))
    assert len(problems) >= 2


# ---------------------------------------------------------------------------
# Navigation and locking
# ---------------------------------------------------------------------------


def test_first_incomplete_step_finds_the_earliest_gap():
    assert first_incomplete_step(complete_data(document_ids=[])) == 3


def test_first_incomplete_step_reaches_review_when_everything_is_answered():
    assert first_incomplete_step(complete_data()) == TOTAL_STEPS


def test_a_later_step_is_clamped_back_to_the_first_gap():
    """This is the lock: asking for step 5 with step 1 blank gets step 1."""
    assert clamp_step(5, {}) == 1


def test_clamping_never_leaves_the_one_to_five_range():
    assert clamp_step(-3, complete_data()) == 1
    assert clamp_step(99, complete_data()) == TOTAL_STEPS


def test_clamping_survives_a_non_numeric_step():
    assert clamp_step("banana", complete_data()) == 1


def test_next_advances_when_the_step_validates():
    node = asyncio.run(handle_wizard_post(
        _FakeForm(
            {**complete_data(), "wizard_step": "1", "action": "next"},
            {"analysis_types": ["Piping (Corrosive)"], "document_ids": ["3"]},
        ),
        documents=FAKE_DOCUMENTS,
    ))
    assert "Step 2 of 5" in to_xml(node)


def test_next_holds_the_step_and_reports_why_when_it_does_not():
    node = asyncio.run(handle_wizard_post(
        _FakeForm({"wizard_step": "1", "action": "next"}, {}),
        documents=FAKE_DOCUMENTS,
    ))
    html = to_xml(node)
    assert "Step 1 of 5" in html
    assert "Project name is required." in html


def test_previous_goes_back_a_step():
    node = asyncio.run(handle_wizard_post(
        _FakeForm(
            {**complete_data(), "wizard_step": "3", "action": "prev"},
            {"analysis_types": ["Piping (Corrosive)"], "document_ids": ["3"]},
        ),
        documents=FAKE_DOCUMENTS,
    ))
    assert "Step 2 of 5" in to_xml(node)


def test_reset_clears_everything_and_returns_to_step_one():
    node = asyncio.run(handle_wizard_post(
        _FakeForm(
            {**complete_data(), "wizard_step": "4", "action": "reset"},
            {"analysis_types": ["Piping (Corrosive)"], "document_ids": ["3"]},
        ),
        documents=FAKE_DOCUMENTS,
    ))
    html = to_xml(node)
    assert "Step 1 of 5" in html
    assert "Harbour Pump House" not in html


def test_submit_calls_on_submit_once_with_the_emitted_dict():
    seen: list[dict] = []
    node = asyncio.run(handle_wizard_post(
        _FakeForm(
            {**complete_data(), "wizard_step": "5", "action": "submit"},
            {"analysis_types": ["Piping (Corrosive)"], "document_ids": ["3"]},
        ),
        documents=FAKE_DOCUMENTS,
        on_submit=lambda emitted: seen.append(emitted) or "HANDED OFF",
    ))
    assert node == "HANDED OFF"
    assert len(seen) == 1
    assert seen[0]["project_name"] == "Harbour Pump House"


def test_submit_does_not_call_on_submit_when_something_is_missing():
    seen: list[dict] = []
    node = asyncio.run(handle_wizard_post(
        _FakeForm({"wizard_step": "5", "action": "submit"}, {}),
        documents=FAKE_DOCUMENTS,
        on_submit=lambda emitted: seen.append(emitted),
    ))
    assert seen == []
    assert "Step 1 of 5" in to_xml(node)


# ---------------------------------------------------------------------------
# Collecting and emitting
# ---------------------------------------------------------------------------


def test_collect_reads_multi_valued_fields_as_lists():
    """FormData.get would collapse three analyses to the last one."""
    data = collect_form_data(
        _FakeForm(
            {"project_name": "Harbour"},
            {"analysis_types": list(ANALYSIS_TYPES), "document_ids": ["3", "4"]},
        )
    )
    assert data["analysis_types"] == list(ANALYSIS_TYPES)
    assert data["document_ids"] == ["3", "4"]


def test_collect_defaults_location_and_status():
    data = collect_form_data(_FakeForm({}, {}))
    assert data["location"]
    assert data["status"] == STATUS_CHOICES[0]


def test_emit_uses_the_specified_output_keys():
    emitted = emit_form_data(complete_data())
    assert set(emitted) == {
        "project_name",
        "description",
        "location",
        "project_size_sqm",
        "buildings",
        "floors",
        "project_type",
        "analysis_types",
        "ifc_file_reference",
        "document_ids",
        "standards_codes",
        "settings",
    }


def test_emit_converts_numbers_instead_of_handing_back_strings():
    """The caller should not re-parse what has already been validated."""
    emitted = emit_form_data(complete_data())
    assert emitted["project_size_sqm"] == 2400
    assert emitted["buildings"] == 2
    assert emitted["floors"] == 4
    assert emitted["document_ids"] == [3]


def test_emit_carries_the_file_reference_through():
    emitted = emit_form_data(complete_data())
    assert emitted["ifc_file_reference"] == "sb://bucket/uploads/ifc/abc_model.ifc"
    assert emitted["settings"]["ifc_filename"] == "model.ifc"


def test_emit_puts_configuration_under_settings():
    emitted = emit_form_data(complete_data(include_openings=True, include_spaces=False))
    assert emitted["settings"]["status"] == "Draft"
    assert emitted["settings"]["include_openings"] is True
    assert emitted["settings"]["include_spaces"] is False


def test_emit_tolerates_missing_optional_values():
    emitted = emit_form_data(complete_data(description="", standards_codes=[], ifc_size_bytes=""))
    assert emitted["description"] == ""
    assert emitted["standards_codes"] == []
    assert emitted["settings"]["ifc_size_bytes"] is None


def test_human_size_reports_bytes_and_kilobytes():
    assert human_size(512) == "512 B"
    assert human_size(4322).endswith("KB")


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def render(step: int, data: dict | None = None) -> str:
    return to_xml(
        ProjectSetupWizard().render(
            current_step=step, form_data=data or {}, documents=FAKE_DOCUMENTS
        )
    )


def test_step_one_renders_all_eight_fields():
    html = render(1, complete_data())
    for field in (
        "project_name",
        "description",
        "location",
        "project_size_sqm",
        "buildings",
        "floors",
        "project_type",
        "analysis_types",
    ):
        assert f'name="{field}"' in html, field


def test_step_one_renders_eight_project_type_cards_with_icons():
    html = render(1, complete_data())
    assert html.count('data-role="typecard"') == len(PROJECT_TYPES) == 8
    assert html.count("<svg") == 8


def test_the_progress_counter_names_the_step_and_the_total():
    assert f"Step 3 of {TOTAL_STEPS}" in render(3, complete_data())


def test_the_file_reference_is_carried_through_every_later_step():
    """The whole reason the upload happens at step 2 rather than at submit."""
    for step in (3, 4, 5):
        html = render(step, complete_data())
        assert "sb://bucket/uploads/ifc/abc_model.ifc" in html, step


def test_the_step_being_edited_is_not_also_hidden():
    """A duplicate name would shadow the real value: FormData.get takes the last."""
    html = render(2, complete_data())
    assert 'type="hidden" name="ifc_file_reference"' in html
    # Step 1 owns project_name, so on step 2 it is carried hidden exactly once.
    assert html.count('name="project_name"') == 1


def test_step_two_offers_a_drop_zone_and_no_named_file_input():
    """A named file input would post the file into the step navigation."""
    html = render(2, complete_data(ifc_file_reference=""))
    assert 'data-role="drop"' in html
    assert 'type="file"' in html
    assert 'type="file" name=' not in html


def test_step_two_shows_a_staged_model_back_with_its_size():
    html = render(2, complete_data())
    assert "model.ifc" in html
    assert "KB" in html


def test_step_three_lists_documents_the_caller_supplied():
    """The component takes no database; the rows are passed in."""
    html = render(3, complete_data())
    assert "client-spec.pdf" in html
    assert 'value="4"' in html


def test_step_three_explains_an_empty_document_list():
    html = to_xml(
        ProjectSetupWizard().render(current_step=3, form_data=complete_data(), documents=[])
    )
    assert "No documents have been uploaded yet" in html


def test_step_four_offers_standards_and_the_configuration_flags():
    html = render(4, complete_data())
    assert 'name="standards_codes"' in html
    assert 'name="status"' in html
    for flag, _, _ in SETTINGS_FLAGS:
        assert f'name="{flag}"' in html, flag


def test_step_five_summarises_every_answer():
    html = render(5, complete_data())
    for expected in ("Harbour Pump House", "United Kingdom", "Industrial", "2400 m²"):
        assert expected in html, expected


def test_step_five_names_the_selected_documents():
    html = render(5, complete_data(document_ids=["3"]))
    assert "client-spec.pdf" in html


def test_validation_errors_render_above_the_step():
    html = to_xml(
        ProjectSetupWizard().render(
            current_step=1, form_data={}, documents=[], errors=["Project name is required."]
        )
    )
    assert "Project name is required." in html


def test_the_component_imports_no_persistence():
    """The scope rule, enforced rather than trusted."""
    import app.components.project_setup_wizard as wizard_module

    source = open(wizard_module.__file__, encoding="utf-8").read()
    for banned in ("ProjectsService", "DocumentService", "app.services"):
        assert banned not in source, f"component reaches persistence via {banned}"


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


def test_the_wizard_page_is_registered(client: TestClient):
    response = client.get("/wizard")
    assert response.status_code == 200
    assert f"Step 1 of {TOTAL_STEPS}" in response.text


def test_a_post_claiming_a_later_step_is_held_at_the_first_gap(client: TestClient):
    """The lock has to hold against a hand-made POST, not just the UI."""
    response = client.post("/wizard", data={"wizard_step": "5", "action": "next"})
    assert response.status_code == 200
    assert "Step 1 of 5" in response.text


def test_the_upload_endpoint_refuses_a_request_with_no_file(client: TestClient):
    response = client.post("/wizard/upload", data={})
    assert response.json() == {"ok": False, "error": "Choose an IFC file to upload."}


def test_the_upload_endpoint_refuses_a_file_that_is_not_ifc(client: TestClient):
    """Rejected on extension, before anything reaches storage."""
    response = client.post(
        "/wizard/upload", files={"ifc_file": ("notes.txt", b"hello", "text/plain")}
    )
    payload = response.json()
    assert payload["ok"] is False
    assert payload["error"]


def test_the_upload_endpoint_does_not_answer_get(client: TestClient):
    assert client.get("/wizard/upload").status_code in (404, 405)


def test_the_analysis_route_helper_prefers_the_first_selection():
    from app.routes.wizard_routes import analysis_route_for

    assert analysis_route_for(["Halo", "Piping (Corrosive)"]) == "seismic"
    assert analysis_route_for(["Architecture"]) == "architecture"


def test_the_analysis_route_helper_falls_back_rather_than_404ing():
    from app.routes.wizard_routes import analysis_route_for

    assert analysis_route_for([]) == "corrosion"
    assert analysis_route_for(["Telepathy"]) == "corrosion"


def test_no_stray_markup_leaks_between_steps():
    """Each render is one form; a nested one would break submission."""
    for step in range(1, TOTAL_STEPS + 1):
        html = render(step, complete_data())
        assert len(re.findall(r"<form", html)) == 1, step
