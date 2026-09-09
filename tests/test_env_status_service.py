"""Test suite for the admin Environment tab's env-var status report."""

from __future__ import annotations

from app.services.env_status_service import ENV_VAR_REGISTRY, get_env_status


def test_registry_has_unique_names():
    names = [spec.name for spec in ENV_VAR_REGISTRY]
    assert len(names) == len(set(names))


def test_get_env_status_never_includes_values(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://secret-project.supabase.co")

    rows = get_env_status()

    assert rows, "registry should not be empty"
    assert all(set(row.keys()) == {"name", "category", "description", "required", "is_set"} for row in rows)
    dumped = str(rows)
    assert "secret-project" not in dumped


def test_get_env_status_reports_set_and_missing(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test-value")
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)

    rows = {row["name"]: row for row in get_env_status()}

    assert rows["OPENROUTER_API_KEY"]["is_set"] is True
    assert rows["GITHUB_TOKEN"]["is_set"] is False


def test_get_env_status_treats_blank_value_as_missing(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "   ")

    rows = {row["name"]: row for row in get_env_status()}

    assert rows["GEMINI_API_KEY"]["is_set"] is False
