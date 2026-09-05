"""The batch driver records what actually happened, not placeholders.

WHY THIS FILE EXISTS

    Every run in docs/validation/data/batch_corrosion_metrics.json reported
    analysis_time_s = 0.0 and a single data_quality reason, "unspecified",
    7,960 times over. Neither was true. The driver timed each parse and each
    engine run and then passed literal 0.0 to extract_metrics, and it looked
    for the reason in the one place the Issues in that batch did not keep it.

    So these tests are about the driver's bookkeeping, not about the engines.

Run: uv run pytest tests/test_batch_corrosion_driver.py -v
"""

from __future__ import annotations

from app.modules.comparator.issue_schema import RiskBand, make_issue
from scripts.batch_corrosion_runs import (
    REASON_KEY_MAX_CHARS,
    _data_quality_reason,
    extract_metrics,
)


def dq_issue(metadata: dict, description: str = ""):
    """Build one data_quality Issue with the metadata under test."""
    return make_issue(
        id="GC-0001",
        element_id="GUID-01",
        rule_id="GC-001.DATA",
        title="GC-001 could not be evaluated",
        mechanism="data_quality",
        band=RiskBand.LOW,
        score=0.10,
        mitigation="Review the IFC source.",
        assignee_role="BIM coordinator",
        description=description,
        metadata=metadata,
        citations=[],
    )


class TestDataQualityReason:
    """Both families of data_quality Issue must yield a real sentence."""

    def test_the_per_element_gate_keeps_its_reason_in_metadata(self):
        """phase_6c writes metadata["reason"]."""
        issue = dq_issue({"check": "material_unresolved", "reason": "no material is associated"})
        assert _data_quality_reason(issue) == "no material is associated"

    def test_a_comparator_issue_falls_back_to_its_description(self):
        """MM-001 and XM-001 build their own Issues and carry no reason key.

        Every data_quality Issue in the September batch came from these two,
        which is the whole reason the report read "unspecified" 7,960 times.
        """
        issue = dq_issue(
            {"check": "unmapped_pairing"},
            description="The pairing CarbonSteel / unknown has no cell in the MM-001 matrix.",
        )
        assert _data_quality_reason(issue).startswith("The pairing CarbonSteel / unknown")

    def test_metadata_wins_when_both_are_present(self):
        issue = dq_issue({"check": "x", "reason": "from metadata"}, description="from description")
        assert _data_quality_reason(issue) == "from metadata"

    def test_only_a_genuinely_empty_issue_is_unspecified(self):
        assert _data_quality_reason(dq_issue({"check": "x"})) == "unspecified"

    def test_a_blank_reason_is_treated_as_absent(self):
        issue = dq_issue({"check": "x", "reason": "   "}, description="the real one")
        assert _data_quality_reason(issue) == "the real one"

    def test_long_reasons_are_truncated_so_they_group(self):
        """These are counter keys; an element id in each would give one bucket per element."""
        issue = dq_issue({"check": "x", "reason": "y" * (REASON_KEY_MAX_CHARS + 50)})
        reason = _data_quality_reason(issue)
        assert len(reason) == REASON_KEY_MAX_CHARS + len("...")
        assert reason.endswith("...")


class TestMetricsRecordWhatTheyAreGiven:
    """The timings reach the record rather than being replaced by 0.0."""

    def _metrics(self, issues, parsed_time=1.25, analysis_time=6.5):
        return extract_metrics(
            "model.ifc",
            "all",
            {"element_count": 4, "piping_elements": [1, 2, 3, 4]},
            {"audit_issues": issues},
            parsed_time,
            analysis_time,
        )

    def test_timings_are_carried_through(self):
        m = self._metrics([])
        assert (m.parsed_time_s, m.analysis_time_s) == (1.25, 6.5)

    def test_verdicts_and_gaps_are_counted_apart(self):
        verdict = make_issue(
            id="GC-0002",
            element_id="GUID-02",
            rule_id="GC-001.01",
            title="galvanic risk",
            mechanism="GC-001 galvanic",
            band=RiskBand.HIGH,
            score=0.7,
            mitigation="Isolate.",
            assignee_role="Mechanical engineer",
            description="Assessed as high risk.",
            metadata={},
            citations=[],
        )
        m = self._metrics([verdict, dq_issue({"check": "material_unresolved", "reason": "none"})])
        assert m.findings_by_band == {"high": 1}
        assert m.data_quality_by_check == {"material_unresolved": 1}
        assert m.data_quality_reason_top5 == [("none", 1)]
