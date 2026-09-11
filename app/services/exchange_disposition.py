"""ISO 19650-4 exchange disposition aggregation.

Combines the results of the four independent verification/validation tiers
BIM-Guard already runs -- Tier 1 syntactic (`IFCValidationService`), Tier 2
IDS (`IDSValidationService`), Tier 3 semantic/bSDD, and Tier 4 engineering
compliance -- into one authoritative `ExchangeDisposition` verdict, per
ISO 19650-4 SS5.1-SS5.6: a Tier 1 failure or critical Tier 2 failure is
REJECTED; Tier 3/4-only warnings are ACCEPTED_WITH_COMMENTS; a clean run is
ACCEPTED.

This module intentionally does not restructure the four tiers' existing,
independent call sites -- it reads their already-produced results rather
than forcing them into one pipeline class, so a caller assembles whichever
tier results it has (some callers may not run all four) and computes the
combined verdict without duplicating tier logic here.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.modules.contracts import ExchangeDisposition, IFCValidationReport
from app.services.ids_validation_service import IDSValidationResult


@dataclass
class DispositionInput:
    """The subset of each tier's result the aggregator needs.

    Every field is optional: a caller that only ran a subset of tiers
    (e.g. Gate 1 has no Tier 3/4 results at hand) passes `None` for the
    tiers it did not run, and those tiers contribute no failures/warnings.
    """

    tier1_report: IFCValidationReport | None = None
    tier2_result: IDSValidationResult | None = None
    tier3_warning_count: int = 0
    tier4_critical_count: int = 0
    tier4_warning_count: int = 0


def compute_disposition(result: DispositionInput) -> ExchangeDisposition:
    """Return the combined ISO 19650-4 disposition for one exchange."""
    tier1_failed = result.tier1_report is not None and not result.tier1_report.valid
    tier2_failed = result.tier2_result is not None and not result.tier2_result.passed

    if tier1_failed or tier2_failed or result.tier4_critical_count > 0:
        return ExchangeDisposition.REJECTED

    has_warnings = (
        result.tier3_warning_count > 0
        or result.tier4_warning_count > 0
        or (result.tier1_report is not None and result.tier1_report.warnings > 0)
    )
    if has_warnings:
        return ExchangeDisposition.ACCEPTED_WITH_COMMENTS

    return ExchangeDisposition.ACCEPTED
