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
from functools import lru_cache
from typing import Any

from app.constants import NOTEBOOK_STANDARDS
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


#: Engine id -> the domain segment of a topic title. Corrosion engines all
#: assess pipework; SB-001 assesses seismic bracing.
_ENGINE_DOMAIN: dict[str, str] = {
    "GC-001": "PIP",
    "CC-001": "PIP",
    "MC-001": "PIP",
    "MM-001": "PIP",
    "XM-001": "PIP",
    "SB-001": "SEI",
}

#: Title segment used where a finding records no floor. An explicit marker of
#: absence, not a guess at a level: every SB-001 finding on project 1542 has an
#: empty floor, and inventing "L00" for them would place 2,937 clashes on a
#: storey nothing measured.
_NO_FLOOR = "NA"

_LEVEL_RE = re.compile(r"(?:level|floor|storey|story)\s*(-?\d+)", re.IGNORECASE)


def _floor_code(floor: str) -> str:
    """Abbreviate a floor name to a title segment: ``"Level 03 Roof"`` -> ``"L03"``.

    Falls back to the first alphanumeric run, upper-cased and truncated, for a
    floor that names no level number ("Roof", "Basement"), and to
    :data:`_NO_FLOOR` when there is no floor at all.
    """
    text = (floor or "").strip()
    if not text:
        return _NO_FLOOR
    match = _LEVEL_RE.search(text)
    if match:
        number = int(match.group(1))
        return f"L{number:02d}" if number >= 0 else f"LB{abs(number):02d}"
    word = re.sub(r"[^A-Za-z0-9]", "", text)[:4].upper()
    return word or _NO_FLOOR


def _title(issue: Issue, sequence: int) -> str:
    """Return the title in the ``{DOMAIN}-{ENGINE}-{FLOOR}-{seq}`` convention.

    A coordinator sorting a BCF by title gets topics grouped by domain, then
    engine, then storey, with a stable per-archive sequence — where before the
    titles began with free prose and sorted into no useful order.

    The seismic title also names both elements. It previously read "Seismic
    bracing clearance clash on 19FnYm9E": one element, and its GUID truncated
    to eight characters, so the topic did not say what clashed with what.

    Falls back to the engine's own title unchanged when the finding carries no
    recognisable engine, rather than emitting a malformed prefix.
    """
    engine = _engine_code(issue)
    if not engine:
        return issue.title
    domain = _ENGINE_DOMAIN.get(engine, "GEN")
    short_engine = engine.split("-", 1)[0]
    floor = _floor_code(str((issue.metadata or {}).get("floor", "") or ""))
    prefix = f"{domain}-{short_engine}-{floor}-{sequence:04d}"

    partner = str((issue.metadata or {}).get("clashing_element_id", "") or "")
    if partner:
        return f"{prefix} Bracing clearance clash {issue.element_id} vs {partner}"
    return f"{prefix} {issue.title}"


def _fmt(value: Any) -> str:
    """Render a metadata value for the description, thousands-separated."""
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, float):
        return f"{value:,.4f}".rstrip("0").rstrip(".") if abs(value) < 1000 else f"{value:,.1f}"
    if isinstance(value, int):
        return f"{value:,}"
    return str(value)


def _line(label: str, value: Any, unit: str = "") -> str | None:
    """Return ``"  Label: value unit"``, or ``None`` when there is no value.

    Returning ``None`` for an absent value is the whole point: a description
    that prints ``Material: `` for an element with no material asserts an empty
    material, where saying nothing asserts nothing.
    """
    if value is None or value == "":
        return None
    rendered = _fmt(value)
    return f"  {label}: {rendered}{unit}"


#: Description sections, in render order, as
#: ``(heading, [(label, metadata key, unit), ...])``. Only keys the finding
#: actually carries are rendered, so an engine that records none of a
#: section's keys drops the whole section rather than printing empty labels.
_DESCRIPTION_SECTIONS: tuple[tuple[str, tuple[tuple[str, str, str], ...]], ...] = (
    (
        "INPUTS",
        (
            ("Material", "material", ""),
            ("Material (anode)", "anode_material", ""),
            ("Material (cathode)", "cathode_material", ""),
            ("Material source", "material_source", ""),
            ("Material confidence", "material_confidence", ""),
            ("Medium", "medium", ""),
            ("Environment class", "environment_class", ""),
            ("Environment source", "environment_source", ""),
            ("Environment confidence", "environment_confidence", ""),
            ("Environment severity", "environment_severity", ""),
            ("Operating temperature", "operating_temperature_c", " °C"),
            ("Galvanic couple basis", "galvanic_couple", ""),
            ("Voltage gap", "voltage_gap_v", " V"),
            ("Separation", "separation", ""),
            ("Nominal diameter (assumed)", "assumed_nominal_diameter_m", " m"),
        ),
    ),
    (
        "CLASH GEOMETRY",
        (
            ("Halo element", "halo_id", ""),
            ("Clashing element", "clashing_element_id", ""),
            ("Clashing element class", "clashing_element_class", ""),
            ("Overlap volume", "overlap_volume_mm3", " mm³"),
            ("Required clearance", "clearance_mm", " mm"),
            ("Brace type", "brace_type", ""),
            ("Rule variant", "rule_variant", ""),
            ("Jurisdiction", "jurisdiction", ""),
            ("Source model", "source_model", ""),
            ("Clashing source model", "clashing_source_model", ""),
        ),
    ),
)


def _description(issue: Issue) -> str:
    """Render a structured, self-contained ``Topic/Description``.

    A coordinator opening a topic in Revit or Solibri sees only this text. It
    previously read, in full, "MC-001 assessed this element as medium." —
    which names no element, no input, no threshold and no standard, so the
    topic could not be acted on without going back to the web UI.

    Every line is drawn from what the finding actually recorded. Absent values
    produce no line and an entirely absent section produces no heading, so the
    description never asserts a value the engine did not measure.

    Sections, in order: the engine's own sentence, ELEMENT, INPUTS, CLASH
    GEOMETRY (seismic only), ASSESSMENT, STANDARDS, MITIGATION.
    """
    meta = issue.metadata or {}
    blocks: list[str] = []

    headline = (issue.description or "").strip()
    if headline:
        blocks.append(headline)

    element = [
        _line("Type", meta.get("ifc_type")),
        _line("GUID", issue.element_id),
        _line("System", meta.get("system")),
        _line("Floor", meta.get("floor")),
    ]
    element = [line for line in element if line]
    if element:
        blocks.append("ELEMENT\n" + "\n".join(element))

    for heading, fields in _DESCRIPTION_SECTIONS:
        lines = [_line(label, meta.get(key), unit) for label, key, unit in fields]
        lines = [line for line in lines if line]
        if lines:
            blocks.append(f"{heading}\n" + "\n".join(lines))

    assessment = [
        _line("Band", issue.band.value),
        _line("Score", round(float(issue.score or 0.0), 4)),
        _line("Ruleset", meta.get("ruleset_version")),
        _line("Check", meta.get("check")),
    ]
    assessment = [line for line in assessment if line]
    if assessment:
        blocks.append("ASSESSMENT\n" + "\n".join(assessment))

    citations = [
        f"  {c.get('standard', '')} — {c.get('clause', '')}: {c.get('reason', '')}".rstrip(": ")
        for c in (issue.citations or [])
        if isinstance(c, dict) and c.get("standard")
    ]
    if citations:
        blocks.append("STANDARDS\n" + "\n".join(citations))

    if (issue.mitigation or "").strip():
        blocks.append("MITIGATION\n  " + issue.mitigation.strip())

    return "\n\n".join(blocks)


@lru_cache(maxsize=1)
def _canonical_standard_names() -> dict[str, str]:
    """Map a lower-cased standard name to its canonical form from constants.

    Citations spell a standard as the engine happened to write it — ``"EN ISO
    15329"`` — while ``app.constants.NOTEBOOK_STANDARDS`` holds the normative
    form, ``"EN ISO 15329:2007"``. Preferring the catalogue's spelling means a
    document reference names the standard as the thesis cites it.

    Keyed on both the full name and its pre-colon stem so an undated citation
    still resolves. Built once; the catalogue is a module constant.
    """
    mapping: dict[str, str] = {}
    for entry in NOTEBOOK_STANDARDS:
        name = str((entry or {}).get("name") or "").strip()
        if not name:
            continue
        mapping.setdefault(name.casefold(), name)
        mapping.setdefault(name.split(":", 1)[0].strip().casefold(), name)
    return mapping


def _document_references(issue: Issue) -> list[dict]:
    """Return one document reference per distinct standard ``issue`` cites.

    ``Description`` is ``"<standard> — <clause>"``, the clause being the one
    the engine actually applied, so the reference says which part of the
    standard produced the finding rather than just naming the document.

    ``referenced_document`` is left empty. It is a URL, and the repository
    holds no URL or DOI for any of these standards -- ``NOTEBOOK_STANDARDS``
    carries name, domain and description only. Emitting a plausible-looking
    link would be a fabricated citation, so the field is omitted and the gap
    recorded.
    """
    canonical = _canonical_standard_names()
    references: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for citation in issue.citations or []:
        if not isinstance(citation, dict):
            continue
        standard = str(citation.get("standard") or "").strip()
        if not standard:
            continue
        clause = str(citation.get("clause") or "").strip()
        key = (standard.casefold(), clause.casefold())
        if key in seen:
            continue
        seen.add(key)
        name = canonical.get(standard.casefold(), standard)
        references.append(
            {
                "description": f"{name} — {clause}" if clause else name,
                "referenced_document": "",
            }
        )
    return references


def _source_files(issue: Issue, model_dates: dict[str, str], fallback: list[dict]) -> list[dict]:
    """Return the ``Header/File`` entries naming the model(s) behind ``issue``.

    Seismic findings record which model each side of the clash came from, in
    ``metadata["source_model"]`` and ``metadata["clashing_source_model"]``, so
    a cross-model clash names both files — on project 1542 that is 886 of
    2,937 findings. Corrosion findings carry no per-finding model, so they take
    the project's attached model(s) as supplied by the caller.

    Args:
        issue: The finding being exported.
        model_dates: ``{filename: upload timestamp}`` for the project, used to
            date a per-finding model. A filename absent from the map is still
            named, just without a date.
        fallback: Entries to use when the finding names no model of its own.

    Returns:
        Entries in ``[{"filename": ..., "date": ...}]`` shape, the finding's
        own model first, de-duplicated and order-preserving.
    """
    names: list[str] = []
    for key in ("source_model", "clashing_source_model"):
        value = str(issue.metadata.get(key, "") or "").strip()
        if value and value not in names:
            names.append(value)
    if not names:
        return list(fallback)
    return [
        {"filename": name, "date": model_dates.get(name, "")}
        for name in names
    ]


def _bcf_issue(
    issue: Issue,
    model_dates: dict[str, str] | None = None,
    fallback_files: list[dict] | None = None,
    sequence: int = 0,
) -> BCFIssue:
    """Map one :class:`Issue` onto the existing :class:`BCFIssue`.

    A data-quality entry is labelled and titled so a coordinator opening the
    archive sees a data fix, not a remediation instruction.

    Args:
        model_dates: ``{filename: upload timestamp}`` for the project.
        fallback_files: ``Header/File`` entries for findings that name no model
            of their own — every corrosion finding.
        sequence: This finding's position in the export, for the title's
            ``{seq:04d}`` segment. Stable because ``sort_issues`` is.
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
        title=_title(issue, sequence),
        description=_description(issue) or issue.title,
        priority=BAND_TO_BCF_PRIORITY[issue.band],
        status="Open",
        assigned_to=issue.assignee_role,
        # No due date. Nothing in a project, a rule or a finding carries one,
        # and this previously emitted the export date -- so every topic in
        # every archive claimed to be due the day it was downloaded, which is
        # a fabricated commitment a coordinator could plan against.
        # ``_markup_xml`` omits the element entirely when this is empty.
        due_date="",
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
        source_files=_source_files(issue, model_dates or {}, fallback_files or []),
        document_references=_document_references(issue),
        snippet_json=json.dumps(_issue_dict(issue), indent=2, default=_encode),
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

    ``result["source_files"]`` — ``[{"filename": ..., "date": ...}, ...]`` for
    the project's attached models — names the model in each topic's
    ``Header``. It is optional: a caller that omits it gets the placeholder
    filename rather than an error, which keeps the harness scripts and the
    cached results computed before this field existed working.
    """
    issues = sort_issues(result.get("audit_issues", []))
    if not include_data_quality:
        issues = [i for i in issues if not _is_data_quality(i)]

    source_files = [
        entry for entry in (result.get("source_files") or []) if (entry or {}).get("filename")
    ]
    model_dates = {
        str(entry["filename"]): str(entry.get("date") or "") for entry in source_files
    }

    logger.info(
        "BCF export issues=%d data_quality_included=%s models=%d",
        len(issues),
        include_data_quality,
        len(source_files),
    )
    return generate_bcf(
        [
            _bcf_issue(i, model_dates, source_files, sequence)
            for sequence, i in enumerate(issues, start=1)
        ]
    )


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

