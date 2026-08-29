"""Every sidebar link must point at a route that exists.

A dead entry in ``layout._NAV_SECTIONS`` is invisible until someone clicks it,
because the sidebar renders whatever tuples it is given. This walks the real
constant and drives each href through the app, so a link to a route that was
renamed or never existed fails here instead of in the browser.

WHAT THIS DELIBERATELY DOES NOT ASSERT

    Which analyses belong in the sidebar. The Analysis section currently lists
    ARCH, MEP and Reports; the corrosion (``/analyze/corrosion``) and seismic
    (``/analyze/seismic``) landing pages are reachable only from a project or
    the wizard redirect. Whether they deserve their own entries is a product
    decision, so the count below is recorded rather than required -- change it
    when the sidebar changes on purpose.

Run: uv run pytest tests/test_sidebar_nav.py -v
"""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from app.components.layout import _NAV_SECTIONS
from app.main import app

#: (section, label, href) for every entry, flattened for parametrisation.
NAV_LINKS = [
    (section, label, href)
    for section, entries in _NAV_SECTIONS
    for label, href in entries
]


@pytest.fixture(scope="module")
def client() -> TestClient:
    """One client for the module — importing app.main is slow."""
    return TestClient(app, raise_server_exceptions=False)


@pytest.mark.parametrize(
    ("section", "label", "href"),
    NAV_LINKS,
    ids=[f"{s}:{label}" for s, label, _ in NAV_LINKS],
)
def test_sidebar_link_resolves(client, section, label, href):
    """No sidebar entry may 404.

    404 is the only outright failure asserted: a page that answers 500 because
    the database is unreachable in this environment is still a registered
    route, which is what this test is about.
    """
    response = client.get(href)

    assert response.status_code != 404, f"{section} → {label} points at {href}, which 404s"


def test_every_link_is_rooted():
    """Relative hrefs would resolve differently depending on the current page."""
    for section, label, href in NAV_LINKS:
        assert href.startswith("/"), f"{section} → {label} has a relative href: {href}"


def test_labels_are_unique_within_a_section():
    for section, entries in _NAV_SECTIONS:
        labels = [label for label, _ in entries]
        assert len(labels) == len(set(labels)), f"duplicate label in {section}"


def test_analysis_section_contents_are_recorded():
    """Pin what the Analysis section holds today.

    Not a claim that this is the right set -- it is a tripwire, so that adding
    or removing an analysis entry is a deliberate edit to this list rather than
    something that drifts unnoticed.
    """
    analysis = dict(dict(_NAV_SECTIONS)["Analysis"])

    assert analysis == {
        "ARCH": "/analysis/ARCH",
        "MEP": "/analysis/MEP",
        "Reports": "/reports",
    }
