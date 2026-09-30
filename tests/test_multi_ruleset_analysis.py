"""Tests for checking one model against several selected rulesets in a single run."""

from __future__ import annotations

from typing import Any

import pytest

from app.modules.orchestrator import BIMGuard_App
from app.services.arch_analysis_service import ArchAnalysisService
from app.services.rules_service import RuleService


def _noop_log_progress(*_args, **_kwargs) -> None:
    return None


class _FakeRulesService:
    """Serves rules per ruleset id and records which rulesets were loaded."""

    def __init__(self, rules_by_ruleset: dict[str, list[dict[str, Any]]]) -> None:
        self._rules_by_ruleset = rules_by_ruleset
        self.loaded: list[str] = []

    def list_by_ruleset(self, ruleset_id: str) -> list[dict[str, Any]]:
        self.loaded.append(ruleset_id)
        return list(self._rules_by_ruleset.get(ruleset_id, []))

    def list_by_theme(self, _theme: str) -> list[dict[str, Any]]:
        raise AssertionError("a scoped run must not fall back to every rule")

    def get_folder(self, ruleset_id: str) -> dict[str, Any] | None:
        return {"ruleset_id": ruleset_id, "display_name": f"{ruleset_id} name"}


class _FakeProjectsService:
    def get_project(self, project_id: int) -> dict[str, Any]:
        return {"id": project_id, "organization_id": 10}


class _FakeRulesetAccess:
    def __init__(self, granted: list[str]) -> None:
        self._granted = granted

    def list_org_grants(self, _organization_id: int) -> list[str]:
        return list(self._granted)


def test_normalize_ruleset_ids_accepts_one_id_or_a_list():
    assert RuleService.normalize_ruleset_ids("") == []
    assert RuleService.normalize_ruleset_ids(None) == []
    assert RuleService.normalize_ruleset_ids(" A ") == ["A"]
    assert RuleService.normalize_ruleset_ids(["B", "", "A", "B"]) == ["B", "A"]


def test_rule_compliance_loads_rules_from_every_selected_ruleset():
    rules = _FakeRulesService(
        {
            "WINDOWS": [{"reference": "WR-001", "ruleset_id": "WINDOWS", "target_ifc_class": "IfcWindow"}],
            "PART9": [{"reference": "CODE 9.7.2", "ruleset_id": "PART9", "target_ifc_class": "IfcWindow"}],
            "UNSELECTED": [{"reference": "X-1", "ruleset_id": "UNSELECTED", "target_ifc_class": "IfcDoor"}],
        }
    )

    result = BIMGuard_App()._run_rule_compliance(
        rules_service=rules,
        rule_folders=["WINDOWS", "PART9"],
        selected_theme="Architecture",
        ifc={"m2_reader": None, "ifc_error": None, "ifc_type_counts": {}},
        project_id=1,
        log_progress=_noop_log_progress,
    )

    assert rules.loaded == ["WINDOWS", "PART9"]
    assert [row["reference"] for row in result["rule_validations"]] == ["WR-001", "CODE 9.7.2"]


def test_arch_analysis_checks_access_for_each_selected_ruleset():
    service = ArchAnalysisService(
        projects_service=_FakeProjectsService(),
        rules_service=_FakeRulesService({}),
        documents_service=object(),
        report_service=object(),
        ruleset_access_service=_FakeRulesetAccess(["WINDOWS"]),
    )

    with pytest.raises(ValueError, match="'PART9' is not granted"):
        service.run_analysis(project_id=1, rule_folder=["WINDOWS", "PART9"])


def test_arch_analysis_passes_all_selected_rulesets_to_the_orchestrator(monkeypatch):
    import app.services.pipeline_services as pipeline_services

    seen: dict[str, Any] = {}

    def fake_orchestrate(**kwargs):
        seen.update(kwargs)
        return {"error": "stopped before real orchestration"}

    monkeypatch.setattr(
        pipeline_services.PipelineOrchestratorService, "orchestrate_workflow", staticmethod(fake_orchestrate)
    )
    service = ArchAnalysisService(
        projects_service=_FakeProjectsService(),
        rules_service=_FakeRulesService({}),
        documents_service=object(),
        report_service=object(),
        ruleset_access_service=_FakeRulesetAccess(["WINDOWS", "PART9"]),
    )

    with pytest.raises(ValueError, match="stopped before real orchestration"):
        service.run_analysis(project_id=1, rule_folder=["WINDOWS", "PART9"])

    assert seen["rule_folder"] == ["WINDOWS", "PART9"]
    assert service.resolve_ruleset_name(["WINDOWS", "PART9"]) == "WINDOWS name, PART9 name"
