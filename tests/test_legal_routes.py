"""Tests for public legal, SEO, and compliance documentation routes."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_privacy_routes_return_html():
    """Verify /privacy and /privacy.html return 200 with HTML content."""
    for path in ["/privacy", "/privacy.html"]:
        response = client.get(path)
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")
        assert "Privacy Policy" in response.text
        assert "Google" in response.text
        assert "bim-guard.xyz" in response.text


def test_terms_routes_return_html():
    """Verify /terms and /terms.html return 200 with HTML content."""
    for path in ["/terms", "/terms.html"]:
        response = client.get(path)
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")
        assert "Terms of Service" in response.text
        assert "OpenBIM" in response.text
        assert "bim-guard.xyz" in response.text


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
