"""Unit tests for crawler/agent routing rules in app/seo_routing.py."""

import pytest

from app.seo_routing import canonical_redirect, is_spa_path, prefers_markdown, x_robots_for_api


@pytest.mark.parametrize(
    ("accept", "expected"),
    [
        ("text/markdown", True),
        ("text/markdown, text/html;q=0.5", True),
        ("text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8", False),
        ("text/html, text/markdown", False),
        ("*/*", False),
        ("", False),
        ("text/markdown;q=0", False),
    ],
)
def test_prefers_markdown(accept, expected):
    assert prefers_markdown(accept) is expected


@pytest.mark.parametrize(("path", "expected"), [("", True), ("viewer", True), ("oauth/consent", True), ("llms.txt", False), ("nope", False)])
def test_is_spa_path(path, expected):
    assert is_spa_path(path) is expected


@pytest.mark.parametrize(
    ("path", "target"),
    [("features.html", "/features"), ("features/", "/features"), ("features", None), ("index.html", None), ("", None)],
)
def test_canonical_redirect(path, target):
    assert canonical_redirect(path) == target


def test_x_robots_for_api():
    assert x_robots_for_api("/api/projects") == "noindex, nofollow"
    assert x_robots_for_api("/api/openapi.json") is None
    assert x_robots_for_api("/features") is None
