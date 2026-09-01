"""Session E — export an ``AnalysisResult`` as BCF 2.1, CSV or JSON.

Consumes ``AnalysisResult`` (data contracts §2), not the engines that produced
it. Because :class:`Issue` is mechanism-agnostic by design — "every compliance
domain produces the same shape, differentiated only by the ``mechanism`` string"
— one exporter serves corrosion (Session C), seismic (Session D) and anything
added later, with no per-mechanism branch.

BCF IS NOT REIMPLEMENTED

    ``module5_reporter.bcf_generator`` already produces spec-compliant BCF 2.1
    archives, and ``blue_halo_bcf_exporter`` already renders Halo clashes
    through the same helpers. This module maps :class:`Issue` onto
    ``BCFIssue`` and calls ``generate_bcf``; it writes no XML of its own.

DATA QUALITY IS NOT A FINDING

    ``data_quality`` Issues report that something could not be assessed. They
    are exported — dropping them would restore the invisibility §4.2 failure
    mode 5 describes — but they are marked, counted separately, and never
    presented as compliance verdicts. In BCF they carry a distinct label and
    are assigned to the BIM coordinator, so a coordinator sees "fix this data"
    rather than "remediate this element".
"""

from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timezone
from typing import Any

from app.logging_config import get_logger
from app.modules.module4_comparator.issue_schema import Issue, RiskBand
from app.modules.module5_reporter.bcf_generator import BCFIssue, generate_bcf

logger = get_logger(__name__)

#: Mechanism string marking a non-verdict Issue. Must match Sessions C and D.
DATA_QUALITY = "data_quality"

#: RiskBand -> BCF priority. BCF 2.1 has no "critical"; the vocabulary in use
#: across this codebase is Critical/Major/Normal/Minor (see BCFIssue.priority).
BAND_TO_BCF_PRIORITY: dict[RiskBand, str] = {
    RiskBand.CRITICAL: "Critical",
    RiskBand.HIGH: "Major",
    RiskBand.MEDIUM: "Normal",
    RiskBand.LOW: "Minor",
}

#: Severity rank for ordering exports most-severe-first. Sorting the raw band
#: values alphabetically would put "critical" before "high" but "low" before
#: "medium" — wrong, and silently so.
BAND_RANK: dict[RiskBand, int] = {
    RiskBand.LOW: 0,
    RiskBand.MEDIUM: 1,
    RiskBand.HIGH: 2,
    RiskBand.CRITICAL: 3,
}

#: CSV column order. Fixed rather than derived from the dataclass so a field
#: added to Issue cannot silently reorder a spreadsheet someone is diffing.
CSV_COLUMNS: tuple[str, ...] = (
    "id",
    "element_id",
    "rule_id",
    "mechanism",
    "band",
    "score",
    "title",
    "description",
    "mitigation",
    "assignee_role",
    "status",
    "is_data_quality",
    "check",
    "standards",
)


def _now_iso() -> str:
    """UTC timestamp in ISO 8601, second precision."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _is_data_quality(issue: Issue) -> bool:
    """Whether this Issue reports a gap rather than a verdict."""
    return issue.mechanism == DATA_QUALITY


def sort_issues(issues: list[Issue]) -> list[Issue]:
    """Order most severe first, with data-quality entries last.

    Data quality sorts to the end regardless of band: it is Low by doctrine, but
    the reason it appears last is that it is not a finding, not that it is mild.
    """
    return sorted(
        issues,
        key=lambda i: (_is_data_quality(i), -BAND_RANK[i.band], i.element_id, i.id),
    )


def _standards(issue: Issue) -> str:
    """Semicolon-joined standards from an Issue's citations, for one CSV cell."""
    return "; ".join(c.get("standard", "") for c in issue.citations if c.get("standard"))


# ---------------------------------------------------------------------------
# CSV
# ---------------------------------------------------------------------------


def to_csv(result: dict) -> str:
    """Render an ``AnalysisResult``'s issues as CSV text.

    Args:
        result: An ``AnalysisResult`` fragment carrying ``audit_issues``.

    Returns:
        CSV text with a header row. Empty input still yields the header, so a
        consumer can tell "no findings" from "export failed".
    """
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=CSV_COLUMNS, lineterminator="\n")
    writer.writeheader()

    for issue in sort_issues(result.get("audit_issues", [])):
        writer.writerow(
            {
                "id": issue.id,
                "element_id": issue.element_id,
                "rule_id": issue.rule_id,
                "mechanism": issue.mechanism,
                "band": issue.band.value,
                "score": f"{issue.score:.4f}",
                "title": issue.title,
                "description": issue.description or "",
                "mitigation": issue.mitigation,
                "assignee_role": issue.assignee_role,
                "status": issue.status,
                # Explicit column rather than asking a reader to infer it from
                # the mechanism string.
                "is_data_quality": "yes" if _is_data_quality(issue) else "no",
                "check": issue.metadata.get("check", ""),
                "standards": _standards(issue),
            }
        )
    return buffer.getvalue()


# ---------------------------------------------------------------------------
# JSON
# ---------------------------------------------------------------------------


def to_json(result: dict, *, indent: int | None = 2) -> str:
    """Render a full ``AnalysisResult`` as JSON.

    Carries the findings, the statistics and the run's error state, so a
    consumer can distinguish "no findings" from "the analysis did not run" —
    the distinction ``compliance_error`` exists to preserve.
    """
    issues = sort_issues(result.get("audit_issues", []))
    payload: dict[str, Any] = {
        "exported_at": _now_iso(),
        "compliance_error": result.get("compliance_error"),
        "compliance_is_demo": result.get("compliance_is_demo", False),
        "issue_stats": result.get("issue_stats", {}),
        "cost_impact": result.get("cost_impact"),
        "findings": [_issue_dict(i) for i in issues if not _is_data_quality(i)],
        "data_quality": [_issue_dict(i) for i in issues if _is_data_quality(i)],
    }
    return json.dumps(payload, indent=indent, default=_encode)


def _issue_dict(issue: Issue) -> dict[str, Any]:
    """One Issue as a JSON-ready dict, with the band as its lowercase value."""
    return {
        "id": issue.id,
        "element_id": issue.element_id,
        "rule_id": issue.rule_id,
        "mechanism": issue.mechanism,
        "band": issue.band.value,
        "score": issue.score,
        "title": issue.title,
        "description": issue.description,
        "mitigation": issue.mitigation,
        "assignee_role": issue.assignee_role,
        "status": issue.status,
        "metadata": issue.metadata,
        "citations": issue.citations,
    }


def _encode(obj: Any) -> Any:
    """Fallback encoder for values json does not handle natively."""
    if isinstance(obj, RiskBand):
        return obj.value
    return str(obj)


# ---------------------------------------------------------------------------
# BCF 2.1
# ---------------------------------------------------------------------------


def _bcf_issue(issue: Issue) -> BCFIssue:
    """Map one :class:`Issue` onto the existing :class:`BCFIssue`.

    A data-quality entry is labelled and titled so a coordinator opening the
    archive sees a data fix, not a remediation instruction.
    """
    data_quality = _is_data_quality(issue)
    labels = [issue.mechanism, issue.band.value]
    if data_quality:
        labels.append("data-quality")
        check = issue.metadata.get("check", "")
        if check:
            labels.append(check)

    return BCFIssue(
        guid=issue.id,
        title=issue.title,
        description=issue.description or issue.mitigation or issue.title,
        priority=BAND_TO_BCF_PRIORITY[issue.band],
        status="Open",
        assigned_to=issue.assignee_role,
        due_date=datetime.now(timezone.utc).date().isoformat(),
        labels=labels,
        component_guid=issue.element_id,
        component_name=str(issue.metadata.get("ifc_type", "") or issue.element_id),
        service_type=str(issue.metadata.get("system", "") or ""),
        floor=str(issue.metadata.get("floor", "") or ""),
        risk_band=issue.band.value,
        mechanism=issue.mechanism,
        risk_score=issue.score,
        mitigation=issue.mitigation,
    )


def to_bcf(result: dict, *, include_data_quality: bool = True) -> bytes:
    """Render an ``AnalysisResult`` as a BCF 2.1 ZIP archive.

    Args:
        result: An ``AnalysisResult`` fragment carrying ``audit_issues``.
        include_data_quality: Whether to emit topics for non-verdict entries.
            Defaults to ``True`` — excluding them by default would hide
            unassessed elements from the coordination model, which is the
            invisibility §4.2 failure mode 5 describes.

    Returns:
        The archive as bytes, ready to write or offer as a download.
    """
    issues = sort_issues(result.get("audit_issues", []))
    if not include_data_quality:
        issues = [i for i in issues if not _is_data_quality(i)]

    logger.info(
        "BCF export issues=%d data_quality_included=%s", len(issues), include_data_quality
    )
    return generate_bcf([_bcf_issue(i) for i in issues])


def to_ids(result: dict) -> str:
    """Render rules / compliance requirements as buildingSMART IDS XML deliverable."""
    from app.modules.module3_rule_builder.ids_exporter import build_ids_document
    rules = result.get("rules", []) or result.get("audit_rules", []) or []
    return build_ids_document(rules)


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

#: Export format -> (media type, file extension).
FORMATS: dict[str, tuple[str, str]] = {
    "csv": ("text/csv", "csv"),
    "json": ("application/json", "json"),
    "bcf": ("application/octet-stream", "bcf"),
    "ids": ("application/xml", "ids"),
}


def export(result: dict, fmt: str) -> tuple[bytes, str, str]:
    """Render ``result`` in ``fmt``.

    Args:
        result: An ``AnalysisResult`` fragment.
        fmt: One of :data:`FORMATS`.

    Returns:
        ``(content, media_type, extension)``, content always as bytes so a
        route can return all formats through one code path.

    Raises:
        ValueError: If ``fmt`` is not a supported format.
    """
    key = (fmt or "").strip().lower()
    if key not in FORMATS:
        raise ValueError(f"Unsupported export format {fmt!r}; expected one of {sorted(FORMATS)}")

    media_type, extension = FORMATS[key]
    if key == "csv":
        return to_csv(result).encode("utf-8"), media_type, extension
    if key == "json":
        return to_json(result).encode("utf-8"), media_type, extension
    if key == "ids":
        return to_ids(result).encode("utf-8"), media_type, extension
    return to_bcf(result), media_type, extension

