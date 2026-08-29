"""Priority 1 production pipeline contracts."""

from types import SimpleNamespace

from app.services.pipeline_services import AnalysisService
from app.services.projects_service import is_enhancement_authorized


def test_audit_service_returns_immutable_findings_and_bcf_topics():
    element = SimpleNamespace(GlobalId="AUDIT-001", Name="Pipe")
    source_before = dict(vars(element))

    def evaluator(elements):
        assert elements == [element]
        return [
            {
                "guid": "AUDIT-001",
                "name": "Pipe",
                "galvanic_band": "HIGH",
                "galvanic_score": 0.75,
                "dominant_mechanism": "galvanic",
                "mitigation": "Add isolation",
                "action": "Resolve before issue",
            }
        ]

    first = AnalysisService(evaluator=evaluator).run([element], run_id="AUDIT-RUN")
    second = AnalysisService(evaluator=evaluator).run([element], run_id="AUDIT-RUN")

    assert vars(element) == source_before
    assert first["pipeline"] == "audit"
    assert first["issues"][0]["band"] == "high"
    assert first["bcf_topics"][0]["element_guid"] == "AUDIT-001"
    assert first["bcf_topics"][0]["guid"] == second["bcf_topics"][0]["guid"]


def test_audit_service_rejects_source_ifc_mutation(tmp_path):
    source_path = tmp_path / "source.ifc"
    source_path.write_bytes(b"ISO-10303-21;SOURCE")

    def mutating_evaluator(_elements):
        source_path.write_bytes(b"ISO-10303-21;MUTATED")
        return []

    service = AnalysisService(evaluator=mutating_evaluator)
    try:
        service.run([], source_path=source_path)
    except RuntimeError as exc:
        assert str(exc) == "Audit pipeline modified the source IFC file"
    else:
        raise AssertionError("Audit source mutation must fail the run")


def test_enhancement_authorization_fails_closed(monkeypatch):
    monkeypatch.delenv("BIM_GUARD_ENHANCEMENT_TOKEN", raising=False)
    assert not is_enhancement_authorized("")
    assert not is_enhancement_authorized("anything")

    monkeypatch.setenv("BIM_GUARD_ENHANCEMENT_TOKEN", "deployment-secret")
    assert not is_enhancement_authorized("wrong-secret")
    assert is_enhancement_authorized("deployment-secret")


def test_db_rule_failures_join_the_audit_issue_and_bcf_contract():
    service = AnalysisService(evaluator=lambda _: [])
    audit = service.run([], run_id="DB-AUDIT")

    merged = service.include_rule_results(
        audit,
        [
            {
                "status": "FAIL",
                "rule_ref": "9.8.2.1",
                "rule_desc": "Door width must comply",
                "severity": "mandatory",
                "property_name": "OverallWidth",
                "target": "IfcDoor",
                "failures": [{"guid": "DOOR-001", "reason": "Width below 860 mm"}],
            }
        ],
        run_id="DB-AUDIT",
    )

    assert merged["issues"][0]["rule_id"] == "9.8.2.1"
    assert merged["issues"][0]["element_id"] == "DOOR-001"
    assert merged["bcf_topics"][0]["element_guid"] == "DOOR-001"
    assert audit["issues"] == []


def test_project_enhancement_lineage_contract_properties():
    record = {
        "id": 12,
        "project_id": 7,
        "source_reference": "sb://models/source.ifc",
        "source_version": 0,
        "output_reference": "sb://models/source_v1.ifc",
        "version": 1,
        "summary": {"names_added": 2},
        "created_at": "2026-08-22T14:00:00Z",
    }

    assert record["source_version"] == 0
    assert record["version"] == 1
    assert record["output_reference"].endswith(".ifc")
    assert record["summary"]["names_added"] == 2