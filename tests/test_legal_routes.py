"""Tests for public legal and compliance documentation routes (/privacy and /terms)."""

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

