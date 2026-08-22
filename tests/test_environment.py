"""Environment loading contracts."""

import os
from pathlib import Path

import app.environment as environment
from app.services.persistence import PersistenceService, _MemoryClient
from app.services.settings_service import SettingsService

_MODULE_CONFIG_PROBE = r"""
import json
from app.modules import config
print(json.dumps({
    "model": config.DEFAULT_LLM_MODEL,
    "openai_model": config.OPENAI_MODEL,
    "mm": config.FEATURE_PATH_B_MM,
    "xm": config.FEATURE_PATH_B_XM,
}))
"""


def test_load_env_file_prefers_project_root(monkeypatch, tmp_path):
    project_root = tmp_path / "project"
    app_dir = project_root / "app"
    working_dir = tmp_path / "working"
    app_dir.mkdir(parents=True)
    working_dir.mkdir()
    (project_root / ".env").write_text("BIM_GUARD_ENV_PROBE=project\n", encoding="utf-8")
    (working_dir / ".env").write_text("BIM_GUARD_ENV_PROBE=working\n", encoding="utf-8")

    monkeypatch.setattr(environment, "__file__", str(app_dir / "environment.py"))
    monkeypatch.chdir(working_dir)
    monkeypatch.delenv("BIM_GUARD_ENV_PROBE", raising=False)

    loaded_path = environment.load_env_file()

    assert loaded_path == (project_root / ".env").resolve()
    assert os.environ["BIM_GUARD_ENV_PROBE"] == "project"


def test_load_env_file_does_not_override_process_environment(monkeypatch, tmp_path):
    env_path = tmp_path / "custom.env"
    env_path.write_text("BIM_GUARD_ENV_PROBE=file\n", encoding="utf-8")
    monkeypatch.setenv("BIM_GUARD_ENV_PROBE", "process")

    loaded_path = environment.load_env_file(env_path)

    assert loaded_path == env_path.resolve()
    assert os.environ["BIM_GUARD_ENV_PROBE"] == "process"


def test_load_env_file_returns_none_for_missing_file(tmp_path):
    assert environment.load_env_file(Path(tmp_path / "missing.env")) is None


def test_module_config_reads_environment_without_database(run_probe):
    result = run_probe(
        _MODULE_CONFIG_PROBE,
        {
            "SUPABASE_URL": "",
            "SUPABASE_SERVICE_ROLE_KEY": "",
            "SUPABASE_KEY": "",
            "BIM_GUARD_LLM_MODEL": "openai/test-model",
            "OPENAI_MODEL": "test-openai-model",
            "FEATURE_PATH_B_MM": "1",
            "FEATURE_PATH_B_XM": "0",
        },
    )

    assert result == {
        "model": "openai/test-model",
        "openai_model": "test-openai-model",
        "mm": True,
        "xm": False,
    }


def test_settings_service_exposes_only_database_managed_values(monkeypatch):
    monkeypatch.setattr(PersistenceService, "_db", _MemoryClient())
    monkeypatch.setattr(SettingsService, "_defaults_seeded", False)
    monkeypatch.setattr(SettingsService, "_values_cache", None)

    settings = SettingsService().list_settings()

    assert [row["key"] for row in settings] == ["BIM_GUARD_LOG_LEVEL"]