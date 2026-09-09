"""_to_feedback_record: shaping a reviewed draft into an LLM-vs-human record."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from export_review_feedback import _to_feedback_record  # noqa: E402


def _row(**overrides) -> dict:
    row = {
        "id": 1,
        "source_document_id": 4,
        "status": "accepted",
        "extraction_method": "llamaindex_pydantic",
        "confidence": 0.9,
        "clause": {"clause_id": "9.8.2.1"},
        "source_snippet": "Stairs shall be at least 900mm wide.",
        "proposed_rule": {"rule_id": "9.8.2.1", "check_value": "900"},
        "original_proposed_rule": None,
        "reviewer_email": "reviewer@example.com",
        "review_notes": "",
        "created_at": "2026-09-01T00:00:00Z",
        "reviewed_at": "2026-09-02T00:00:00Z",
    }
    row.update(overrides)
    return row


def test_accepted_draft_llm_output_is_proposed_rule_no_correction():
    record = _to_feedback_record(_row(status="accepted"), filenames={4: "doc.pdf"})

    assert record["llm_proposed_rule"] == {"rule_id": "9.8.2.1", "check_value": "900"}
    assert record["reviewer_corrected_rule"] is None
    assert record["document_filename"] == "doc.pdf"


def test_rejected_draft_llm_output_is_proposed_rule_no_correction():
    record = _to_feedback_record(_row(status="rejected"), filenames={})

    assert record["llm_proposed_rule"] == {"rule_id": "9.8.2.1", "check_value": "900"}
    assert record["reviewer_corrected_rule"] is None


def test_edited_draft_splits_original_from_correction():
    row = _row(
        status="edited",
        proposed_rule={"rule_id": "9.8.2.1", "check_value": "1000"},
        original_proposed_rule={"rule_id": "9.8.2.1", "check_value": "900"},
    )

    record = _to_feedback_record(row, filenames={})

    assert record["llm_proposed_rule"] == {"rule_id": "9.8.2.1", "check_value": "900"}
    assert record["reviewer_corrected_rule"] == {"rule_id": "9.8.2.1", "check_value": "1000"}


def test_edited_draft_without_captured_original_falls_back_to_proposed_rule():
    # Edited before the original_proposed_rule column existed -- no original
    # to diff against, so llm_proposed_rule falls back rather than erroring.
    row = _row(status="edited", original_proposed_rule=None)

    record = _to_feedback_record(row, filenames={})

    assert record["llm_proposed_rule"] == row["proposed_rule"]
    assert record["reviewer_corrected_rule"] == row["proposed_rule"]


def test_missing_document_filename_defaults_to_empty_string():
    record = _to_feedback_record(_row(source_document_id=999), filenames={4: "doc.pdf"})

    assert record["document_filename"] == ""
