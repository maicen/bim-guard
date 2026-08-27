"""Session B — turn a stored IFC file into the ``ParsedIFC`` contract.

Implements ``docs/PHASE_6_DATA_CONTRACTS.md`` §1. The contract's four rules
drive every design decision here:

1. ``guid`` is the join key. Every downstream ``Issue.element_id`` is a guid
   from ``elements``, so a blank or duplicated guid is reported as a quality
   warning rather than passed on silently.
2. A file that cannot be read is **not** an exception. It returns
   ``quality.valid = False`` with ``quality.error`` set and ``elements: []``.
   Callers render the message; they never see a traceback.
3. Parsing never writes. No Supabase writes, no storage mutation, no disk
   cache. :func:`parse_ifc_bytes` is the primary entry point precisely so the
   bytes can come straight from storage without being materialised first.
4. ``source_sha256`` is the cache key, computed over the same bytes that were
   parsed. ``ProjectsService.resolve_analysis_ifc`` already keys model lineage
   on a sha256 of the source, so re-parses can be avoided with the existing
   mechanism rather than a second one.

The element shape is :class:`~app.modules.module2_ifc_read.ifc_parser.ServiceElement`,
which already exists and is **not** redefined here — this module composes the
Module 2 reader into the envelope the Phase 6+ sessions agreed on.
"""

from __future__ import annotations

import hashlib
from collections import Counter
from pathlib import Path
from typing import Any, TypedDict

from app.logging_config import get_logger
from app.modules.module2_ifc_read.ifc_parser import (
    ServiceElement,
    get_schema_compatibility_note,
    parse_ifc_model,
)

logger = get_logger(__name__)

#: Materials the normaliser could not resolve. ``ifc_parser`` writes this
#: sentinel into ``material_a`` when the IFC carries no usable material name.
UNKNOWN_MATERIAL = "Unknown"


class ParsedIFCQuality(TypedDict):
    """The ``quality`` block of :class:`ParsedIFC`."""

    valid: bool
    error: str | None
    warnings: list[str]
    improvements: list[dict]


class ParsedIFC(TypedDict):
    """Session B's output envelope. See data contracts §1."""

    source_ref: str
    source_sha256: str
    schema: str
    schema_note: str | None
    elements: list[ServiceElement]
    element_count: int
    type_counts: dict[str, int]
    quality: ParsedIFCQuality


def sha256_of(content: bytes) -> str:
    """Return the hex sha256 digest of ``content``.

    Exposed because callers frequently need the digest before deciding whether
    to parse at all — the point of rule 4.
    """
    return hashlib.sha256(content).hexdigest()


def _empty_result(source_ref: str, source_sha256: str, error: str) -> ParsedIFC:
    """Build the failure envelope required by rule 2.

    Args:
        source_ref: Storage reference the parse was attempted against.
        source_sha256: Digest of the bytes, when they were readable at all.
        error: Human-readable reason, rendered directly to the user.

    Returns:
        A well-formed :class:`ParsedIFC` with no elements and ``valid: False``.
    """
    return ParsedIFC(
        source_ref=source_ref,
        source_sha256=source_sha256,
        schema="",
        schema_note=None,
        elements=[],
        element_count=0,
        type_counts={},
        quality=ParsedIFCQuality(valid=False, error=error, warnings=[], improvements=[]),
    )


def _deduplicate_by_guid(
    elements: list[ServiceElement],
) -> tuple[list[ServiceElement], int]:
    """Collapse the repeats ``parse_ifc_model`` produces, keeping the first.

    ``parse_ifc_model`` calls ``model.by_type()`` once per entry in
    ``IFC_SERVICE_LABELS``, but IFC classes are a hierarchy: an
    ``IfcPipeSegment`` is also an ``IfcFlowSegment`` and an
    ``IfcDistributionElement``, so ``by_type`` returns it three times. One
    physical element therefore arrives as three ``ServiceElement`` rows sharing
    a GlobalId and differing only in ``ifc_type``.

    A GlobalId identifies exactly one entity in IFC, so repeats are always the
    same element and collapsing them is safe. First occurrence wins, which
    keeps the most specific class: ``IFC_SERVICE_LABELS`` is ordered specific
    to general, and ``parse_ifc_model`` iterates it in order.

    This is corrected here rather than in ``parse_ifc_model`` because that
    function feeds the shipped corrosion pipeline, where changing the element
    set changes published results. Fixing it there is a real repair with a real
    blast radius and belongs to whoever owns that path; rule 1 only requires
    that *this* contract hands downstream a unique join key.

    Args:
        elements: Rows as ``parse_ifc_model`` returned them.

    Returns:
        ``(unique_elements, collapsed_count)`` where ``collapsed_count`` is how
        many rows were dropped as repeats.
    """
    seen: set[str] = set()
    unique: list[ServiceElement] = []
    collapsed = 0
    for element in elements:
        guid = (element.guid or "").strip()
        if not guid:
            # Kept: a blank guid is a distinct data-quality problem, reported
            # by _quality_warnings rather than silently discarded here.
            unique.append(element)
            continue
        if guid in seen:
            collapsed += 1
            continue
        seen.add(guid)
        unique.append(element)
    return unique, collapsed


def _quality_warnings(elements: list[ServiceElement]) -> list[str]:
    """Report facts about the parse that a reviewer would want to act on.

    Deliberately limited to what can be observed from the elements themselves.
    Anything requiring the file on disk belongs to ``ifc_quality.validator``,
    and anything that would rewrite the model belongs to the improver — which
    writes, and so cannot run here (rule 3).
    """
    warnings: list[str] = []
    if not elements:
        warnings.append(
            "No MEP service elements were extracted. The model may contain no "
            "supported classes, or the relevant elements may sit in a linked file."
        )
        return warnings

    blank_guids = sum(1 for e in elements if not (e.guid or "").strip())
    if blank_guids:
        warnings.append(
            f"{blank_guids} of {len(elements)} elements have no GlobalId. Findings "
            "cannot be joined back to them, so they will be missing from reports."
        )

    guids = [e.guid for e in elements if (e.guid or "").strip()]
    duplicates = [g for g, n in Counter(guids).items() if n > 1]
    if duplicates:  # pragma: no cover - _deduplicate_by_guid runs first
        warnings.append(
            f"{len(duplicates)} GlobalId(s) appear on more than one element. "
            "Findings against them will be ambiguous."
        )

    unknown_material = sum(1 for e in elements if e.material_a == UNKNOWN_MATERIAL)
    if unknown_material:
        warnings.append(
            f"{unknown_material} of {len(elements)} elements have an unidentified "
            "material. Corrosion compliance cannot be evaluated for them."
        )

    return warnings


def parse_ifc_bytes(content: bytes, *, source_ref: str = "") -> ParsedIFC:
    """Parse IFC ``content`` into the ``ParsedIFC`` contract.

    The primary entry point. Takes bytes rather than a path so an object can be
    parsed straight out of Supabase Storage without being written to disk
    first, satisfying rule 3.

    Never raises for a bad model: an unreadable or non-IFC payload comes back
    as ``quality.valid = False`` with the reason in ``quality.error``.

    Args:
        content: Raw bytes of an IFC (SPF) file.
        source_ref: Storage reference these bytes came from, recorded on the
            result so a caller can trace it. Optional.

    Returns:
        A :class:`ParsedIFC`. ``element_count`` always equals
        ``len(elements)``, and ``type_counts`` always sums to it.
    """
    if not content:
        logger.warning("IFC parse called with empty content source_ref=%s", source_ref)
        return _empty_result(source_ref, sha256_of(b""), "The IFC file is empty.")

    source_sha256 = sha256_of(content)

    try:
        text = content.decode("utf-8", errors="replace")
    except Exception as exc:  # pragma: no cover - decode with replace does not raise
        logger.warning("IFC decode failed source_ref=%s error=%s", source_ref, exc)
        return _empty_result(source_ref, source_sha256, f"The IFC file could not be decoded: {exc}")

    try:
        import ifcopenshell
    except ImportError:
        logger.error("ifcopenshell is not installed; IFC parsing unavailable")
        return _empty_result(
            source_ref,
            source_sha256,
            "ifcopenshell is not installed, so IFC files cannot be read on this server.",
        )

    try:
        model = ifcopenshell.file.from_string(text)
    except Exception as exc:
        logger.warning(
            "IFC parse failed source_ref=%s sha256=%s error=%s", source_ref, source_sha256, exc
        )
        return _empty_result(
            source_ref, source_sha256, f"The file could not be read as IFC: {exc}"
        )

    try:
        elements = parse_ifc_model(model)
    except Exception as exc:
        logger.warning(
            "IFC element extraction failed source_ref=%s sha256=%s error=%s",
            source_ref,
            source_sha256,
            exc,
        )
        return _empty_result(
            source_ref, source_sha256, f"The model opened but its elements could not be read: {exc}"
        )

    elements, collapsed = _deduplicate_by_guid(elements)

    schema = str(getattr(model, "schema", "") or "")
    schema_note = get_schema_compatibility_note(model)
    type_counts = dict(Counter(e.ifc_type for e in elements))
    warnings = _quality_warnings(elements)
    if collapsed:
        warnings.append(
            f"{collapsed} duplicate element row(s) were collapsed. IFC classes are "
            "a hierarchy, so the reader returns one element once per matching "
            "class; each GlobalId is now counted once."
        )

    logger.info(
        "IFC parsed source_ref=%s sha256=%s schema=%s elements=%d types=%d warnings=%d",
        source_ref,
        source_sha256,
        schema,
        len(elements),
        len(type_counts),
        len(warnings),
    )

    return ParsedIFC(
        source_ref=source_ref,
        source_sha256=source_sha256,
        schema=schema,
        schema_note=schema_note,
        elements=elements,
        element_count=len(elements),
        type_counts=type_counts,
        # improvements stays empty by design: generating them runs the quality
        # improver, which writes a new model. Rule 3 forbids that here, so it
        # belongs to an explicit enhancement step rather than to parsing.
        quality=ParsedIFCQuality(valid=True, error=None, warnings=warnings, improvements=[]),
    )


def parse_ifc_file(path: str | Path, *, source_ref: str = "") -> ParsedIFC:
    """Parse an IFC file from the local filesystem.

    Convenience wrapper over :func:`parse_ifc_bytes` for callers that already
    hold a path — a materialised storage cache entry, or a fixture in a test.
    Reads the file; never writes one.

    Args:
        path: Path to a ``.ifc`` file.
        source_ref: Storage reference to record. Defaults to ``str(path)``.

    Returns:
        A :class:`ParsedIFC`. A missing or unreadable file returns the failure
        envelope rather than raising.
    """
    path = Path(path)
    ref = source_ref or str(path)
    try:
        content = path.read_bytes()
    except OSError as exc:
        logger.warning("IFC file unreadable path=%s error=%s", path, exc)
        return _empty_result(ref, "", f"The IFC file could not be opened: {exc}")
    return parse_ifc_bytes(content, source_ref=ref)


def elements_by_guid(parsed: ParsedIFC) -> dict[str, ServiceElement]:
    """Index a parse result by ``guid`` for downstream joins.

    Rule 1 makes ``guid`` the join key between elements and Issues, so this is
    the lookup Sessions C and D need. Elements with a blank guid are omitted —
    they are already reported in ``quality.warnings`` — and on a duplicate guid
    the first occurrence wins, matching the order the model returned.
    """
    index: dict[str, ServiceElement] = {}
    for element in parsed["elements"]:
        guid = (element.guid or "").strip()
        if guid and guid not in index:
            index[guid] = element
    return index


def summarise(parsed: ParsedIFC) -> dict[str, Any]:
    """Return the compact shape the analyse pages show above the results.

    Keeps route code out of the envelope's internals, and maps onto the
    ``AnalysisResult`` keys named in data contracts §2.
    """
    return {
        "ifc_element_count": parsed["element_count"],
        "ifc_type_counts": parsed["type_counts"],
        "ifc_error": parsed["quality"]["error"],
        "ifc_quality_warnings": parsed["quality"]["warnings"],
        "ifc_schema_note": parsed["schema_note"],
    }
