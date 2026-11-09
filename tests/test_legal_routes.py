"""Tests for public legal, SEO, and compliance documentation routes."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_privacy_routes_return_html():
    """Verify /privacy returns 200 HTML and /privacy.html 301s to it (no duplicate URL)."""
    response = client.get("/privacy")
    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")
    assert "Privacy Policy" in response.text
    assert "Google" in response.text
    assert "bim-guard.xyz" in response.text
    redirect = client.get("/privacy.html", follow_redirects=False)
    assert redirect.status_code == 301
    assert redirect.headers["location"] == "/privacy"


def test_terms_routes_return_html():
    """Verify /terms returns 200 HTML and /terms.html 301s to it (no duplicate URL)."""
    response = client.get("/terms")
    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")
    assert "Terms of Service" in response.text
    assert "OpenBIM" in response.text
    assert "bim-guard.xyz" in response.text
    redirect = client.get("/terms.html", follow_redirects=False)
    assert redirect.status_code == 301
    assert redirect.headers["location"] == "/terms"


def test_sitemap_xml_returns_xml():
    """Verify /sitemap.xml returns 200 with XML content and valid URLs."""
    response = client.get("/sitemap.xml")
    assert response.status_code == 200
    assert "application/xml" in response.headers.get("content-type", "")
    assert "<loc>https://bim-guard.xyz/</loc>" in response.text
    assert "<loc>https://bim-guard.xyz/privacy</loc>" in response.text
    assert "<loc>https://bim-guard.xyz/terms</loc>" in response.text


def test_robots_txt_returns_text_with_sitemap():
    """Verify /robots.txt returns 200 and references the sitemap."""
    response = client.get("/robots.txt")
    assert response.status_code == 200
    assert "text/plain" in response.headers.get("content-type", "")
    assert "Sitemap: https://bim-guard.xyz/sitemap.xml" in response.text
    assert "User-agent: *" in response.text


def test_og_image_returns_png():
    """Verify /og-image.png returns 200 with image/png content type."""
    response = client.get("/og-image.png")
    assert response.status_code == 200
    assert response.headers.get("content-type") == "image/png"
    assert len(response.content) > 1000


def test_robots_keeps_openapi_crawlable_and_blocks_training_bots():
    """The API docs advertised via Link headers must not be disallowed by robots.txt."""
    text = client.get("/robots.txt").text
    assert "Allow: /api/openapi.json" in text
    assert "Allow: /api/docs" in text
    assert "Disallow: /api/\n" in text
    assert "User-agent: GPTBot" in text
    assert "User-agent: OAI-SearchBot" in text
    assert "Content-Signal: search=yes, ai-input=yes, ai-train=no" in text


def test_llms_txt_is_plain_text_index():
    """llms.txt follows llmstxt.org: H1, blockquote summary, link sections."""
    response = client.get("/llms.txt")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert response.text.startswith("# BIM Guard")
    assert "\n> " in response.text
    assert "https://bim-guard.xyz/api/openapi.json" in response.text


def test_llms_full_txt_contains_page_and_manual_text():
    """llms-full.txt inlines the public pages and the published manual."""
    text = client.get("/llms-full.txt").text
    assert "# BIM Guard features" in text
    assert "# Getting Started" in text


def test_api_paths_are_noindex_except_docs():
    """Authenticated API paths carry X-Robots-Tag; the schema and docs stay indexable."""
    assert client.get("/api/health").headers.get("x-robots-tag") == "noindex, nofollow"
    assert "x-robots-tag" not in client.get("/api/openapi.json").headers


def test_api_catalog_is_rfc9727_linkset():
    """The api-catalog is a linkset and advertises the REST API and the MCP server card."""
    import json
    from pathlib import Path

    catalog = json.loads((Path("frontend/public/.well-known/api-catalog")).read_text())
    anchors = {entry["anchor"] for entry in catalog["linkset"]}
    assert "https://bim-guard.xyz/api" in anchors
    assert "https://bim-guard.xyz/mcp/" in anchors
