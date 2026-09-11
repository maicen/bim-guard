"""Unit tests for the ISO 19650-4 exchange disposition aggregator."""

from app.modules.contracts import ExchangeDisposition, IFCValidationReport, IFCValidationStageResult
from app.services.exchange_disposition import DispositionInput, compute_disposition
from app.services.ids_validation_service import IDSValidationResult


def _tier1_report(*, valid: bool, warnings: int = 0) -> IFCValidationReport:
    stage = IFCValidationStageResult(stage_name="syntax", passed=valid, issues_count=0, details=[])
    return IFCValidationReport(
        valid=valid,
        schema_version="IFC4",
        file_size_bytes=1024,
        syntax_stage=stage,
        schema_stage=stage,
        rules_stage=stage,
        total_issues=0,
        fatal_errors=0 if valid else 1,
        warnings=warnings,
        summary_message="ok",
    )


def test_clean_run_is_accepted():
    result = compute_disposition(DispositionInput())
    assert result == ExchangeDisposition.ACCEPTED


def test_tier1_failure_is_rejected():
    result = compute_disposition(DispositionInput(tier1_report=_tier1_report(valid=False)))
    assert result == ExchangeDisposition.REJECTED


def test_tier2_failure_is_rejected():
    ids_result = IDSValidationResult(ruleset_id="R-1", passed=False)
    result = compute_disposition(DispositionInput(tier2_result=ids_result))
    assert result == ExchangeDisposition.REJECTED


def test_tier4_critical_issues_are_rejected():
    result = compute_disposition(DispositionInput(tier4_critical_count=2))
    assert result == ExchangeDisposition.REJECTED


def test_tier3_warnings_are_accepted_with_comments():
    result = compute_disposition(DispositionInput(tier3_warning_count=1))
    assert result == ExchangeDisposition.ACCEPTED_WITH_COMMENTS


def test_tier1_warnings_are_accepted_with_comments():
    result = compute_disposition(DispositionInput(tier1_report=_tier1_report(valid=True, warnings=3)))
    assert result == ExchangeDisposition.ACCEPTED_WITH_COMMENTS


def test_passing_tier2_does_not_block_acceptance():
    ids_result = IDSValidationResult(ruleset_id="R-1", passed=True)
    result = compute_disposition(DispositionInput(tier2_result=ids_result))
    assert result == ExchangeDisposition.ACCEPTED
