"""Session E — export an ``AnalysisResult`` as BCF 2.1, CSV or JSON.

Consumes ``AnalysisResult`` (data contracts §2), not the engines that produced
it. Because :class:`Issue` is mechanism-agnostic by design — "every compliance
domain produces the same shape, differentiated only by the ``mechanism`` string"
— one exporter serves corrosion (Session C), seismic (Session D) and anything
added later, with no per-mechanism branch.

BCF IS NOT REIMPLEMENTED

    ``reporter.bcf_generator`` already produces spec-compliant BCF 2.1
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
import re
from datetime import datetime, timezone
from typing import Any

from app.logging_config import get_logger
from app.modules.comparator.issue_schema import Issue, RiskBand
from app.modules.reporter.bcf_generator import (
    DEFAULT_CREATION_AUTHOR,
    BCFIssue,
    generate_bcf,
)

logger = get_logger(__name__)

#: Engine ids as they appear at the head of a ``rule_id``: two letters, a dash
#: and three digits (``GC-001``, ``SB-001``). Anchored so a malformed rule id
#: yields no engine rather than a fragment.
_ENGINE_CODE_RE = re.compile(r"^[A-Z]{2}-\d{3}$")

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
    # SB-001 clash geometry. Blank on every other mechanism, which is the point:
    # a seismic row is the only one where a reviewer can ask "by how much?" and
    # the column answers without them opening the JSON export.
    #
    # NOT intrusion_depth_mm. The client-side CSV that pagination removed
    # carried an IntrusionDepthMM column reading issue.details.intrusion_depth_mm
    # -- and details is dict(issue.metadata) (app/api/analyze.py), so that column
    # was blank on every row ever exported: phase_6d_seismic records the overlap
    # as a volume and the requirement as a clearance, and has never written an
    # intrusion depth. These two are what the mechanism actually measures.
    "overlap_volume_mm3",
    "clearance_mm",
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
                # "" rather than 0 for a non-seismic row: a blank cell reads as
                # "not applicable to this mechanism", a zero as "measured, and
                # it was nothing".
                "overlap_volume_mm3": issue.metadata.get("overlap_volume_mm3", ""),
                "clearance_mm": issue.metadata.get("clearance_mm", ""),
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


def _engine_code(issue: Issue) -> str:
    """Return the engine id that raised ``issue``, e.g. ``"GC-001"``.

    Read from ``rule_id`` rather than ``metadata["mechanism_code"]`` because
    only ``rule_id`` is populated on every finding: XM-001's 510 verdicts and
    the MM-001/XM-001 data-quality notes carry no ``mechanism_code``, while
    every finding — verdict or note, corrosion or seismic — has a ``rule_id``
    of the form ``"<ENGINE>.<rule>"``.

    Returns an empty string if ``rule_id`` is missing or unshaped, so callers
    fall back to a generic author rather than inventing an engine.
    """
    head = str(issue.rule_id or "").split(".", 1)[0].strip()
    return head if _ENGINE_CODE_RE.match(head) else ""


def _creation_author(issue: Issue) -> str:
    """Return ``Topic/CreationAuthor`` for ``issue``.

    ``"BIMGUARD AI <ENGINE> <revision>"`` where the finding records a ruleset
    version, ``"BIMGUARD AI <ENGINE>"`` where it does not. XM-001 and SB-001
    carry no ``ruleset_version``, so they take the shorter form: naming a
    revision they never recorded would be a fabricated value.

    The stored ``ruleset_version`` is a full label such as
    ``"BIMGUARD-MC-001 v1.0.0"``, which already contains the engine id. Only
    the revision token is appended, so the author reads
    ``"BIMGUARD AI MC-001 v1.0.0"`` rather than repeating the engine twice.
    """
    engine = _engine_code(issue)
    if not engine:
        return DEFAULT_CREATION_AUTHOR
    version = str(issue.metadata.get("ruleset_version", "") or "").strip()
    if not version:
        return f"{DEFAULT_CREATION_AUTHOR} {engine}"
    revision = version.rsplit(" ", 1)[-1] if version.startswith(f"BIMGUARD-{engine}") else version
    return f"{DEFAULT_CREATION_AUTHOR} {engine} {revision}"


#: Engines whose findings are geometric interferences rather than compliance
#: verdicts. SB-001 reports one element intruding into another's clearance
#: halo, which is a clash in every coordination tool's vocabulary.
_CLASH_ENGINES: frozenset[str] = frozenset({"SB-001"})


def _topic_type(issue: Issue) -> str:
    """Return the BCF ``TopicType`` for ``issue``.

    Three kinds of thing reach the archive and they are not interchangeable:

    * ``Warning`` — a data-quality note. Something could not be assessed; it is
      a modelling gap for the BIM coordinator, not a defect in the building.
    * ``Clash`` — a geometric interference (SB-001).
    * ``Issue`` — a compliance verdict against a scored element.

    Emitting ``Issue`` for all three, as this did before, made 2,937 seismic
    clashes and every data-quality note indistinguishable from a verdict in
    any tool that filters on topic type.
    """
    if _is_data_quality(issue):
        return "Warning"
    if _engine_code(issue) in _CLASH_ENGINES:
        return "Clash"
    return "Issue"


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
            labels.append(f"check:{check}")

    engine = _engine_code(issue)
    if engine:
        labels.append(engine)
    ruleset_version = str(issue.metadata.get("ruleset_version", "") or "").strip()
    if ruleset_version:
        labels.append(f"ruleset:{ruleset_version}")

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
        creation_author=_creation_author(issue),
        topic_type=_topic_type(issue),
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
    from app.modules.rule_builder.ids_exporter import build_ids_document
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

