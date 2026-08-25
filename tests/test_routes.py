"""
Route-level tests for the FastHTML application.

The existing suite covers the compliance layer — piping producer, comparators,
BCF export, rule registry — but nothing exercises the HTTP surface. These tests
close that gap by driving the real ASGI app through starlette's TestClient
(httpx under the hood), so route registration, path-parameter coercion, form
validation and the route->service wiring are all executed.

WHAT THESE TESTS DELIBERATELY DO NOT DO

    They never create, update or delete real records. Every POST here sends
    empty or malformed form data, which the handlers reject before touching
    persistence, and every id used against a mutating route is
    NONEXISTENT_ID. That matters because this suite runs against the live
    Supabase project — there is no test double and no transactional rollback,
    so a test that created a project would leave it there. Anything needing
    real writes belongs in a manual walkthrough, not here.

    They also cannot cover what only a browser shows: layout, form usability,
    HTMX swap behaviour, file-upload flows, or the 3D viewer actually
    rendering geometry.

KNOWN-GAP TESTS

    Several routes answer 200 for ids that do not exist, rendering an empty
    page rather than reporting "not found". Those are marked xfail with
    `strict=False` and named for the behaviour they want, so the suite records
    the gap without failing on it. When a route is fixed its xfail flips to
    XPASS, which is the signal to remove the marker.

OPEN FINDINGS NOT COVERED BY A TEST

    POST /projects/create accepts a blank name and creates the project,
    answering 303 to /projects rather than rejecting the submission. The
    empty-form case is correctly refused with 400, so the handler checks that
    the field is present but not that it holds anything — a project can be
    created with name "". This is asserted nowhere in this file on purpose:
    the only way to observe it is to perform the create, and against the live
    database that leaves a junk row behind (it left two before the test was
    narrowed). Restoring coverage needs either the validation fixed or a
    disposable database for the suite.

    POST /projects/{id}/delete answers 200 for an id that does not exist.
    Harmless if idempotent deletion is intended, but worth confirming it is a
    decision rather than a missing existence check.

Run: uv run pytest tests/test_routes.py -v
"""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from app.main import app

# An id no fixture or live record will ever use. Chosen large and numeric so
# it survives int() coercion and reaches the service layer, which is the part
# under test — a non-numeric id would be rejected by the router first.
NONEXISTENT_ID = 999_999_999


@pytest.fixture(scope="module")
def client() -> TestClient:
    """One client for the module.

    Importing app.main costs ~15s (MonsterUI compat shim, route registration,
    service construction), so this is module-scoped. raise_server_exceptions
    is False so a handler that raises surfaces as a 500 response and is
    asserted against, rather than aborting the test run with a traceback.
    """
    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Page routes render
# ---------------------------------------------------------------------------

PAGE_ROUTES = [
    "/",
    "/dashboard",
    "/projects",
    "/projects/new",
    "/library/documents",
    "/library/rules",
    "/library/rules/new",
    "/library/rules/extract",
    "/reports",
    "/settings",
    "/viewer",
    "/revit-sync",
    "/modeling-manual",
]


@pytest.mark.parametrize("path", PAGE_ROUTES)
def test_page_returns_html(client: TestClient, path: str) -> None:
    """Every page route answers 200 with an HTML body.

    This is the broadest regression net in the suite: a route whose service
    call breaks, whose template references a removed component, or whose
    import chain is severed shows up here as a 500 rather than being found
    by a person clicking through the app.
    """
    response = client.get(path)
    assert response.status_code == 200, f"{path} returned {response.status_code}"
    assert "text/html" in response.headers.get("content-type", "")
    assert len(response.content) > 500, f"{path} rendered a suspiciously small body"


@pytest.mark.parametrize("path", PAGE_ROUTES)
def test_page_is_a_complete_document(client: TestClient, path: str) -> None:
    """Pages render a full document, not a fragment or an error stub.

    Checked separately from the status code because a handler that catches
    its own exception can still answer 200 with a stub body.
    """
    body = client.get(path).text.lower()
    assert "<html" in body and "</html>" in body, "not a complete HTML document"
    assert "<body" in body


# ---------------------------------------------------------------------------
# Path parameter coercion
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "path",
    [
        "/projects/not-an-int/edit",
        "/library/documents/not-an-int",
        "/library/rules/not-an-int",
    ],
)
def test_non_numeric_id_is_rejected_by_the_router(client: TestClient, path: str) -> None:
    """A non-numeric id never reaches a handler.

    The router's int converter rejects it, which is what keeps handlers free
    of defensive parsing. A 500 here would mean the coercion moved into the
    handler and started throwing.
    """
    assert client.get(path).status_code == 404


def test_unknown_path_is_404(client: TestClient) -> None:
    assert client.get("/no/such/page").status_code == 404


@pytest.mark.parametrize(
    "path",
    [
        f"/projects/{NONEXISTENT_ID}/edit",
        f"/library/documents/{NONEXISTENT_ID}",
        f"/library/rules/{NONEXISTENT_ID}",
        f"/projects/{NONEXISTENT_ID}/ifc",
        f"/projects/{NONEXISTENT_ID}/enhancements",
        f"/reports/bcf/{NONEXISTENT_ID}",
    ],
)
def test_missing_record_does_not_crash(client: TestClient, path: str) -> None:
    """A well-formed id for a record that does not exist is handled, not fatal.

    Deliberately permissive: it asserts only that the route answers something
    a client can act on. Whether that answer *should* be 404 is asserted
    separately below, where the current 200 is recorded as a known gap.
    """
    status = client.get(path).status_code
    assert status < 500, f"{path} returned {status}"


@pytest.mark.parametrize(
    "path",
    [
        f"/projects/{NONEXISTENT_ID}/edit",
        f"/library/documents/{NONEXISTENT_ID}",
        f"/library/rules/{NONEXISTENT_ID}",
        f"/reports/bcf/{NONEXISTENT_ID}",
    ],
)
@pytest.mark.xfail(
    strict=False,
    reason="Known gap: these routes render 200 with an empty page for ids that "
    "do not exist, instead of 404. A caller cannot distinguish 'no such record' "
    "from 'record with no data'. XPASS here means the route was fixed — remove "
    "the marker.",
)
def test_missing_record_should_be_404(client: TestClient, path: str) -> None:
    assert client.get(path).status_code == 404


# ---------------------------------------------------------------------------
# Form validation — non-mutating by construction
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "path",
    [
        "/projects/create",
        "/library/rules/create",
        f"/projects/{NONEXISTENT_ID}/update",
    ],
)
def test_post_without_required_fields_is_rejected(client: TestClient, path: str) -> None:
    """Submitting an empty form is refused before anything is persisted.

    Asserting 4xx rather than a specific code: the contract under test is
    "rejected client-side error", and pinning 400 exactly would make the test
    brittle against a handler that reasonably chose 422.
    """
    response = client.post(path, data={})
    assert 400 <= response.status_code < 500, (
        f"{path} answered {response.status_code} to an empty form; a 2xx would "
        "mean malformed input reached persistence"
    )


@pytest.mark.parametrize("path", ["/library/rules/create"])
def test_post_with_blank_values_is_rejected(client: TestClient, path: str) -> None:
    """Present-but-empty fields are rejected too.

    Distinct from the empty-form case: a handler that checks key presence
    rather than value emptiness passes the test above and fails this one.

    /projects/create is deliberately NOT covered here. It accepts blank
    values and creates the record (303 to /projects), so running this
    assertion against it writes a junk row to the live database — which it
    did, twice, before this test was narrowed. There is no rollback in this
    suite, so a create endpoint that fails open cannot be probed safely
    until either the validation is fixed or the suite gets a disposable
    database. The gap is recorded in the module docstring under OPEN
    FINDINGS instead.
    """
    response = client.post(path, data={"name": "", "description": ""})
    assert 400 <= response.status_code < 500


# ---------------------------------------------------------------------------
# Static assets
# ---------------------------------------------------------------------------


def test_known_static_asset_is_served(client: TestClient) -> None:
    """The viewer's loader script is served.

    Chosen because the IFC viewer is the one page whose function depends on a
    static asset resolving; a broken static mount is invisible on every other
    page.
    """
    # static/js/ifc-viewer.js, not ifc-viewer-loader.js. CLAUDE.md states the
    # latter ("The loader script is at static/js/ifc-viewer-loader.js"); no such
    # file exists, and app/routes/viewer.py references ifc-viewer.js. The name
    # in the documentation is stale.
    response = client.get("/static/js/ifc-viewer.js")
    assert response.status_code == 200
    assert len(response.content) > 0


def test_missing_static_asset_is_not_a_server_error(client: TestClient) -> None:
    assert client.get("/static/js/does-not-exist.js").status_code < 500


# ---------------------------------------------------------------------------
# Cross-cutting
# ---------------------------------------------------------------------------


def test_no_page_route_returns_a_server_error(client: TestClient) -> None:
    """No page route 500s.

    Redundant against the per-route assertions above, and kept deliberately:
    it fails with the full list of broken routes in one message rather than
    stopping at the first, which is what you want when a shared dependency
    breaks several at once.
    """
    broken = {p: client.get(p).status_code for p in PAGE_ROUTES}
    assert not [p for p, s in broken.items() if s >= 500], f"server errors: {broken}"


def test_head_is_supported_where_get_is(client: TestClient) -> None:
    """HEAD works on the dashboard.

    Health checks and uptime probes use HEAD; a route registered GET-only
    answers 405 and reads as an outage.
    """
    assert client.head("/dashboard").status_code < 400
