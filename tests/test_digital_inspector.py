"""Digital Inspector tool wrappers and tool-call trace extraction."""

from app.digital_inspector.runner import _extract_tool_calls
from app.digital_inspector.tools import (
    bsdd_lookup,
    check_cde_transition,
    check_db_cache,
    query_ifc_model,
    run_validation,
)
from app.modules.contracts import InspectorToolCallContract


class FakeProjectsService:
    def __init__(self, project=None):
        self._project = project

    def get_project(self, project_id):
        return self._project


class FakeRulesService:
    def __init__(self, rows):
        self._rows = rows

    def list_by_ruleset(self, ruleset_id):
        return self._rows


class FakeContainer:
    def __init__(self, *, projects_service=None, rules_service=None, arch_analysis_service=None):
        self.projects_service = projects_service
        self.rules_service = rules_service
        self.arch_analysis_service = arch_analysis_service


def test_query_ifc_model_found(monkeypatch):
    project = {
        "name": "Tower A",
        "status": "active",
        "ifc_file_path": "uploads/tower-a.ifc",
        "ifc_md5_hash": "abc123",
        "analysis_type": "arch",
    }
    fake_container = FakeContainer(projects_service=FakeProjectsService(project))
    monkeypatch.setattr("app.bootstrap.get_container", lambda: fake_container)

    result = query_ifc_model.invoke({"project_id": 7})

    assert result["found"] is True
    assert result["project_id"] == 7
    assert result["ifc_file_path"] == "uploads/tower-a.ifc"


def test_query_ifc_model_not_found(monkeypatch):
    fake_container = FakeContainer(projects_service=FakeProjectsService(None))
    monkeypatch.setattr("app.bootstrap.get_container", lambda: fake_container)

    result = query_ifc_model.invoke({"project_id": 999})

    assert result == {"found": False, "project_id": 999}


def test_check_db_cache_lists_rule_references(monkeypatch):
    rows = [{"reference": "9.8.2.1"}, {"reference": "9.8.2.2"}]
    fake_container = FakeContainer(rules_service=FakeRulesService(rows))
    monkeypatch.setattr("app.bootstrap.get_container", lambda: fake_container)

    result = check_db_cache.invoke({"ruleset_id": "BUILDING-CODE-PART9"})

    assert result["rule_count"] == 2
    assert result["rule_ids"] == ["9.8.2.1", "9.8.2.2"]


def test_run_validation_summarizes_issues(monkeypatch):
    class FakeArchResult:
        issues = [{"guid": "G1", "reason": "too narrow"}, {"guid": "G2", "reason": "missing rating"}]

    class FakeArchService:
        def run_analysis(self, project_id, rule_folder=""):
            assert project_id == 5
            assert rule_folder == "BUILDING-CODE-PART9"
            return FakeArchResult()

    fake_container = FakeContainer(arch_analysis_service=FakeArchService())
    monkeypatch.setattr("app.bootstrap.get_container", lambda: fake_container)

    result = run_validation.invoke({"project_id": 5, "rule_folder": "BUILDING-CODE-PART9"})

    assert result["issue_count"] == 2
    assert result["issues_preview"][0] == {"guid": "G1", "reason": "too narrow"}


def test_run_validation_surfaces_value_error(monkeypatch):
    class FailingArchService:
        def run_analysis(self, project_id, rule_folder=""):
            raise ValueError("project not found")

    fake_container = FakeContainer(arch_analysis_service=FailingArchService())
    monkeypatch.setattr("app.bootstrap.get_container", lambda: fake_container)

    result = run_validation.invoke({"project_id": 999})

    assert result["error"] == "project not found"


def test_check_cde_transition_reports_gate_reason(monkeypatch):
    project = {"cde_state": "WIP", "ifc_file_path": "", "cde_approved_by": ""}
    fake_container = FakeContainer(projects_service=FakeProjectsService(project))
    monkeypatch.setattr("app.bootstrap.get_container", lambda: fake_container)

    result = check_cde_transition.invoke({"project_id": 3, "target_state": "SHARED"})

    assert result["current_state"] == "WIP"
    assert result["allowed"] is True
    assert result["target_state"] == "SHARED"


def test_check_cde_transition_project_not_found(monkeypatch):
    fake_container = FakeContainer(projects_service=FakeProjectsService(None))
    monkeypatch.setattr("app.bootstrap.get_container", lambda: fake_container)

    result = check_cde_transition.invoke({"project_id": 999, "target_state": "SHARED"})

    assert result["error"] == "project not found"


def test_bsdd_lookup_wraps_search_classes(monkeypatch):
    class FakeClassItem:
        def __init__(self, code, name, uri, dictionary_uri):
            self.code, self.name, self.uri, self.dictionary_uri = code, name, uri, dictionary_uri

    class FakeSearchResponse:
        query = "fire damper"
        total = 1
        classes = [FakeClassItem("FireDamper", "Fire Damper", "uri://x", "uri://dict")]

    class FakeBsddClient:
        def search_classes(self, query, dictionary_uri=None):
            assert query == "fire damper"
            return FakeSearchResponse()

    monkeypatch.setattr(
        "app.services.bsdd_client.DEFAULT_BSDD_CLIENT", FakeBsddClient()
    )

    result = bsdd_lookup.invoke({"query": "fire damper"})

    assert result["total"] == 1
    assert result["classes"][0]["code"] == "FireDamper"


def _fake_message(cls_name, **kwargs):
    """Build a minimal stand-in matching isinstance checks against real langchain classes."""
    from langchain_core.messages import AIMessage, ToolMessage

    cls = AIMessage if cls_name == "ai" else ToolMessage
    return cls(**kwargs)


def test_extract_tool_calls_pairs_ai_and_tool_messages():
    ai_message = _fake_message(
        "ai",
        content="",
        tool_calls=[{"id": "call-1", "name": "query_ifc_model", "args": {"project_id": 7}}],
    )
    tool_message = _fake_message("tool", content="{'found': true}", tool_call_id="call-1")

    calls = _extract_tool_calls([ai_message, tool_message])

    assert len(calls) == 1
    assert isinstance(calls[0], InspectorToolCallContract)
    assert calls[0].tool_name == "query_ifc_model"
    assert calls[0].input == {"project_id": 7}
    assert calls[0].status == "success"


def test_extract_tool_calls_marks_missing_result_as_error():
    ai_message = _fake_message(
        "ai",
        content="",
        tool_calls=[{"id": "call-2", "name": "bsdd_lookup", "args": {"query": "wall"}}],
    )

    calls = _extract_tool_calls([ai_message])

    assert calls[0].status == "error"
    assert calls[0].output is None
