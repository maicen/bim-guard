"""Tests for /api/evaluation endpoints.

Uses an isolated in-process SQLite table (via PersistenceService's
get_isolated_sqlite_db, the same test-isolation seam RuleService uses) for
evaluation_findings, and a fake ArchAnalysisService so capture doesn't need a
real IFC model or the live Supabase project -- see EvaluationService's own
docstring for why capture_results() recomputes server-side rather than
trusting a client-supplied payload.
"""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from app.api.dependencies import get_evaluation_service
from app.main import app
from app.services.evaluation_service import EvaluationService
from app.services.persistence import PersistenceService

client = TestClient(app)
NONEXISTENT_ID = 999_999_999


class _FakeArchAnalysisService:
    """Stub returning a canned rule_compliance payload, shaped like ComplianceComparator._result()."""

    def __init__(self, rule_compliance: list[dict]):
        self._rule_compliance = rule_compliance

    def compute_rule_compliance(self, project_id: int, rule_folder: str = ""):
        return self._rule_compliance, {}


def _rule_compliance_fixture() -> list[dict]:
    return [
        {
            "rule_id": 42,
            "rule_ref": "OBC-9.6.4",
            "rule_desc": "Door width >= 900mm",
            "ruleset_id": "TEST-RULESET",
            "target": "IfcDoor",
            "property_name": "Width",
            "property_set": "Pset_DoorCommon",
            "operator": ">=",
            "check_value": 900,
            "value_min": None,
            "value_max": None,
            "unit": "mm",
            "severity": "mandatory",
            "all_elements": [
                {
                    "element_name": "Door-01",
                    "guid": "3Kf7q8XzR1pPguid0001",
                    "storey": "L1",
                    "space": "Lobby",
                    "actual": 950,
                    "status": "PASS",
                    "reason": "",
                },
                {
                    "element_name": "Door-02",
                    "guid": "3Kf7q8XzR1pPguid0002",
                    "storey": "L1",
                    "space": "Corridor",
                    "actual": 800,
                    "status": "FAIL",
                    "reason": "800mm < required 900mm",
                },
            ],
        }
    ]


@pytest.fixture
def evaluation_service(tmp_path):
    """Wire a real EvaluationService onto an isolated SQLite table + fake analysis service."""
    db = PersistenceService.get_isolated_sqlite_db(str(tmp_path / "evaluation_findings.db"))
    repo = PersistenceService.get_table(
        "evaluation_findings",
        {
            "id": int,
            "project_id": int,
            "ifc_file_id": int,
            "rule_id": int,
            "rule_snapshot": dict,
            "element_global_id": str,
            "element_name": str,
            "storey": str,
            "space": str,
            "bimguard_verdict": str,
            "bimguard_reason": str,
            "captured_by_email": str,
            "captured_at": str,
            "human_verdict": str,
            "reviewer_email": str,
            "reviewed_at": str,
            "review_notes": str,
            "created_at": str,
        },
        db=db,
    )
    service = EvaluationService(
        findings_repo=repo,
        arch_analysis_service=_FakeArchAnalysisService(_rule_compliance_fixture()),
    )
    app.dependency_overrides[get_evaluation_service] = lambda: service
    try:
        yield service
    finally:
        app.dependency_overrides.pop(get_evaluation_service, None)


def test_capture_persists_one_row_per_element(evaluation_service):
    response = client.post("/api/evaluation/capture", json={"project_id": 1, "rule_folder": "TEST-RULESET"})
    assert response.status_code == 200, response.text
    assert response.json() == {"captured_count": 2}

    findings = client.get("/api/evaluation/findings", params={"project_id": 1}).json()["findings"]
    assert len(findings) == 2
    by_guid = {f["element_global_id"]: f for f in findings}
    assert by_guid["3Kf7q8XzR1pPguid0001"]["bimguard_verdict"] == "PASS"
    assert by_guid["3Kf7q8XzR1pPguid0002"]["bimguard_verdict"] == "FAIL"
    assert by_guid["3Kf7q8XzR1pPguid0002"]["rule_snapshot"]["rule_ref"] == "OBC-9.6.4"
    assert all(f["human_verdict"] is None for f in findings)


def test_review_finding_records_human_verdict(evaluation_service):
    client.post("/api/evaluation/capture", json={"project_id": 1, "rule_folder": "TEST-RULESET"})
    findings = client.get("/api/evaluation/findings", params={"project_id": 1}).json()["findings"]
    fail_finding = next(f for f in findings if f["bimguard_verdict"] == "FAIL")

    response = client.patch(
        f"/api/evaluation/findings/{fail_finding['id']}",
        json={"human_verdict": "FAIL", "review_notes": "Confirmed short door"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["human_verdict"] == "FAIL"
    assert body["reviewer_email"]
    assert body["reviewed_at"]
    assert body["review_notes"] == "Confirmed short door"


def test_review_nonexistent_finding_returns_404(evaluation_service):
    response = client.patch(
        f"/api/evaluation/findings/{NONEXISTENT_ID}",
        json={"human_verdict": "PASS"},
    )
    assert response.status_code == 404


def test_bulk_review_updates_all_listed_findings(evaluation_service):
    client.post("/api/evaluation/capture", json={"project_id": 1, "rule_folder": "TEST-RULESET"})
    findings = client.get("/api/evaluation/findings", params={"project_id": 1}).json()["findings"]
    ids = [f["id"] for f in findings]

    response = client.post(
        "/api/evaluation/findings/bulk-review",
        json={"finding_ids": ids, "human_verdict": "NOT_APPLICABLE", "review_notes": "Bulk-confirmed"},
    )
    assert response.status_code == 200
    assert response.json() == {"updated_count": 2}

    findings = client.get("/api/evaluation/findings", params={"project_id": 1}).json()["findings"]
    assert all(f["human_verdict"] == "NOT_APPLICABLE" for f in findings)


def test_bulk_delete_removes_findings(evaluation_service):
    client.post("/api/evaluation/capture", json={"project_id": 1, "rule_folder": "TEST-RULESET"})
    findings = client.get("/api/evaluation/findings", params={"project_id": 1}).json()["findings"]
    ids = [f["id"] for f in findings]

    response = client.post("/api/evaluation/findings/bulk-delete", json={"finding_ids": ids})
    assert response.status_code == 200
    assert response.json() == {"deleted_count": 2}

    findings = client.get("/api/evaluation/findings", params={"project_id": 1}).json()["findings"]
    assert findings == []


def test_get_evaluation_matrix_computes_confusion_and_kappa(evaluation_service):
    """Confirm /api/evaluation/matrix accurately tabulates TP/FP/FN/TN and agreement metrics."""
    # Capture canned 2 findings (1 PASS, 1 FAIL)
    client.post("/api/evaluation/capture", json={"project_id": 1, "rule_folder": "TEST-RULESET"})
    findings = client.get("/api/evaluation/findings", params={"project_id": 1}).json()["findings"]
    assert len(findings) == 2

    # Before review: reviewed=0, metrics=None
    pre = client.get("/api/evaluation/matrix", params={"project_id": 1}).json()
    assert pre["total_findings"] == 2
    assert pre["reviewed_findings"] == 0
    assert pre["confusion_matrix"] == {"tp": 0, "fp": 0, "fn": 0, "tn": 0}
    assert pre["metrics"]["accuracy"] is None

    # Review finding 1 (status FAIL) with human verdict FAIL -> True Positive
    fail_f = next(f for f in findings if f["bimguard_verdict"] == "FAIL")
    pass_f = next(f for f in findings if f["bimguard_verdict"] == "PASS")

    client.patch(f"/api/evaluation/findings/{fail_f['id']}", json={"human_verdict": "FAIL"})
    client.patch(f"/api/evaluation/findings/{pass_f['id']}", json={"human_verdict": "PASS"})

    post = client.get("/api/evaluation/matrix", params={"project_id": 1}).json()
    assert post["total_findings"] == 2
    assert post["reviewed_findings"] == 2
    assert post["unreviewed_findings"] == 0
    assert post["confusion_matrix"] == {"tp": 1, "fp": 0, "fn": 0, "tn": 1}
    assert post["metrics"]["accuracy"] == 1.0
    assert post["metrics"]["precision"] == 1.0
    assert post["metrics"]["recall"] == 1.0
    assert post["metrics"]["specificity"] == 1.0
    assert post["metrics"]["f1"] == 1.0
    assert post["metrics"]["cohens_kappa"] == 1.0
    assert post["cross_tabulation"]["FAIL"]["FAIL"] == 1
    assert post["cross_tabulation"]["PASS"]["PASS"] == 1
