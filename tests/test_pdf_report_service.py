"""Structured PDF rendering for a rule-configuration snapshot (pdf_report_service)."""

from app.services.pdf_report_service import render_snapshot_pdf


def _snapshot() -> dict:
    return {
        "name": "Test Configuration",
        "source_ruleset_id": "FOLDER-A",
        "source_mode": "manual",
        "category": "Arch",
        "created_at": "2026-09-02T12:00:00+00:00",
        "rule_count": 2,
    }


def _rules() -> list[dict]:
    return [
        {
            "reference": "R-1",
            "target_ifc_class": "IfcWindow",
            "property_set": "Pset_WindowCommon",
            "property_name": "FireRating",
            "operator": ">=",
            "check_value": 30.0,
            "unit": "min",
            "severity": "mandatory",
        },
        {
            "reference": "R-2",
            "target_ifc_class": "IfcWindow",
            "property_name": "AcousticRating",
            "operator": "exists",
            "severity": "recommended",
        },
    ]


def test_render_snapshot_pdf_returns_valid_pdf_bytes():
    pdf_bytes = render_snapshot_pdf(_snapshot(), _rules())
    assert isinstance(pdf_bytes, bytes)
    assert pdf_bytes[:5] == b"%PDF-"
    assert len(pdf_bytes) > 500


def test_render_snapshot_pdf_with_no_rules_is_still_valid():
    empty_snapshot = {**_snapshot(), "rule_count": 0}
    pdf_bytes = render_snapshot_pdf(empty_snapshot, [])
    assert pdf_bytes[:5] == b"%PDF-"
    assert len(pdf_bytes) > 0


def test_render_snapshot_pdf_handles_missing_optional_fields():
    """Rule dicts from the frozen rules_json may not carry every column
    (e.g. classification/material rows from IDS import have no value_min/
    value_max) — None values must not raise."""
    sparse_rules = [{"reference": "R-3", "target_ifc_class": "IfcDoor"}]
    pdf_bytes = render_snapshot_pdf(_snapshot(), sparse_rules)
    assert pdf_bytes[:5] == b"%PDF-"
