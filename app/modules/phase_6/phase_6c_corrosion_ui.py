"""Session C — run the corrosion engines over a ParsedIFC and emit Issues.

Takes Session B's ``ParsedIFC`` and produces the corrosion half of
``AnalysisResult`` (data contracts §2): a list of :class:`Issue` plus the
statistics the analyse pages render.

WHAT THIS DOES NOT DO

    It does not implement GC-001, CC-001 or MC-001. Those engines already exist
    in ``app/engines/`` and are thesis-backing work; this module is the wiring
    that feeds them ``ServiceElement`` rows and turns their results into the
    shared ``Issue`` shape.

    It also leaves ``compliance_runner``/``issue_adapter`` untouched. Those feed
    the shipped analyse routes, where changing the element set or the Issue list
    changes published results.

THE FOUR-STEP data_quality RULE (contracts §4.2, failure mode 5)

    ``compliance_runner`` substitutes ``"LOW"`` when an engine returns no band,
    which makes "not assessed" indistinguishable from "assessed and cleared"
    and then drops the element under ``include_low=False``. This module does
    not repeat that:

    1. It never invents a band. A mechanism that did not produce one is
       recorded as unassessed.
    2. The absence is reported as an Issue, not skipped.
    3. That Issue is ``mechanism="data_quality"``, Low severity, carries
       ``metadata["check"]`` and is assigned to the BIM coordinator — the shape
       ``galvanic.py:_data_quality_issue`` established and
       ``test_data_quality_never_masquerades_as_a_verdict`` enforces.
    4. ``data_quality`` Issues are **exempt** from the ``include_low`` filter.
       Without this step the Issue created in step 2 is deleted one line later
       and the whole fix is undone.

BAND CASING

    The engines emit Title-case (``"Critical"``); ``RiskBand`` stores lowercase.
    Normalisation happens once, on entry, via :func:`normalise_band`, which
    raises with the element and mechanism named rather than letting a bad label
    fall through to a grey badge or a rank of 0.

CITATIONS

    ``issue_adapter`` emits ``citations=[]`` because Path A's runner flattens
    the engine results and discards their standards references — "an empty list
    is a visible gap; a hardcoded standard is a false audit trail". This module
    calls the engines directly, so the references are still in hand and the
    citations here are real: each names the standard the engine itself declares
    and the threshold value it actually applied.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any

from app.engines.bimguard_corrosion_engine import GCElement, assess_galvanic_risk
from app.engines.bimguard_crevice_engine import CCElement, assess_crevice_risk
from app.engines.bimguard_mic_engine import MICElement, assess_mic_risk
from app.logging_config import get_logger
from app.modules.module2_ifc_read.ifc_parser import ServiceElement
from app.modules.module4_comparator.issue_adapter import IssueIdAllocator
from app.modules.module4_comparator.issue_schema import Issue, RiskBand, make_issue

logger = get_logger(__name__)

#: Severity rank. RiskBand values are lowercase strings, so comparing them
#: directly sorts alphabetically ("critical" < "high" < "low" < "medium") and
#: silently picks the wrong winner — the same trap _BAND_RANK guards in
#: issue_adapter.
BAND_RANK: dict[RiskBand, int] = {
    RiskBand.LOW: 0,
    RiskBand.MEDIUM: 1,
    RiskBand.HIGH: 2,
    RiskBand.CRITICAL: 3,
}

#: The mechanism a data-quality Issue reports under. Kept as a constant because
#: the include_low exemption keys on it, and a typo would silently reinstate
#: failure mode 5.
DATA_QUALITY = "data_quality"


@dataclass(frozen=True)
class MechanismSpec:
    """One corrosion mechanism and how to reach it.

    Attributes:
        code: Ruleset code, e.g. ``"GC-001"``.
        rule_id: Rule reference recorded on the Issue.
        prefix: Issue-id prefix handed to :class:`IssueIdAllocator`.
        label: Human name used in Issue titles.
    """

    code: str
    rule_id: str
    prefix: str
    label: str


GALVANIC = MechanismSpec("GC-001", "GC-001.01", "GC", "Galvanic corrosion")
CREVICE = MechanismSpec("CC-001", "CC-001.01", "CC", "Crevice corrosion")
MIC = MechanismSpec("MC-001", "MC-001.01", "MC", "Microbiologically influenced corrosion")

MECHANISMS: tuple[MechanismSpec, ...] = (GALVANIC, CREVICE, MIC)


def resolve_mechanisms(engines: list[str] | None) -> tuple[MechanismSpec, ...]:
    """Return the mechanisms an ``engines`` selection asks this run to execute.

    Selection is resolved once, before the element loop, so an unselected
    mechanism is never assessed. Filtering its findings out afterwards would
    produce the same list at the cost of running the engine anyway.

    Args:
        engines: Engine codes from the caller, e.g. ``["GC-001", "CC"]``.
            ``None`` means no selection was made and every mechanism runs.
            An empty list is an explicit selection of nothing and runs none.
            Entries match case-insensitively against the ruleset code
            (``"GC-001"``), its Issue-id prefix (``"GC"``) and any rule id
            built on the code (``"GC-001.01"``), because the checkbox UI sends
            prefixes while the rules table stores full ids.

    Returns:
        The subset of :data:`MECHANISMS` to run, in declaration order.
    """
    if engines is None:
        return MECHANISMS

    wanted = {str(code).strip().upper() for code in engines if str(code).strip()}
    # "GC-001.01" selects GC-001: a rule id names the ruleset it belongs to.
    wanted |= {code.split(".", 1)[0] for code in wanted}
    return tuple(
        spec
        for spec in MECHANISMS
        if spec.code.upper() in wanted or spec.prefix.upper() in wanted
    )


def resolve_engine_codes(engines: list[str] | None) -> tuple[str, ...]:
    """Return the ruleset codes :func:`resolve_mechanisms` would run.

    The canonical form of a selection: ``None``, ``["gc"]`` and ``["GC-001"]``
    all reduce to what actually executes, which is what a cache key and a
    progress report need rather than the caller's spelling.
    """
    return tuple(spec.code for spec in resolve_mechanisms(engines))


def normalise_band(raw: Any, *, element: str, mechanism: str) -> RiskBand:
    """Convert an engine's band label to a :class:`RiskBand` member.

    One normalisation point, and it raises. The engines emit Title-case, the
    schema stores lowercase, and a legacy path emits upper — all three resolve
    here, and anything unrecognised fails loudly naming the element and
    mechanism rather than becoming a grey badge or the lowest rank.

    Args:
        raw: Whatever the engine reported as its band.
        element: Element name or GlobalId, for the error message.
        mechanism: Mechanism code, for the error message.

    Returns:
        The matching :class:`RiskBand`.

    Raises:
        ValueError: If ``raw`` is not a recognised band.
    """
    try:
        return RiskBand(str(raw).strip().lower())
    except ValueError:
        raise ValueError(f"Unknown band {raw!r} for {element} / {mechanism}") from None


# ---------------------------------------------------------------------------
# Coercion: ServiceElement -> engine inputs
# ---------------------------------------------------------------------------


def _gc_element(element: ServiceElement) -> GCElement:
    """Build the GC-001 input for one service element.

    ``material_b`` is the second material at a bimetallic junction. When the
    IFC carries only one, both sides are the same material, which the engine
    scores as no galvanic couple rather than as a fault.
    """
    x, y, z = (list(element.position) + [0.0, 0.0, 0.0])[:3]
    return GCElement(
        global_id_anode=element.guid,
        global_id_cathode=element.guid,
        material_anode=element.material_a,
        material_cathode=element.material_b or element.material_a,
        anode_area_m2=element.anode_area_m2,
        cathode_area_m2=element.cathode_area_m2,
        zone_category=element.location_tag,
        floor=element.floor,
        system_type=element.system,
        position_x=float(x or 0.0),
        position_y=float(y or 0.0),
        position_z=float(z or 0.0),
    )


def _cc_element(element: ServiceElement) -> CCElement:
    """Build the CC-001 input for one service element."""
    return CCElement(
        global_id=element.guid,
        element_type=element.ifc_type,
        material=element.material_a,
        joint_description=element.joint_type,
        zone_category=element.location_tag,
        system_type=element.system,
        floor=element.floor,
    )


#: Fallback pipe diameter, metres. ``ServiceElement`` carries no diameter — the
#: Module 2 reader does not extract one — but MC-001 requires it. 0.1 m (DN100)
#: is a common service main and is recorded in the Issue metadata so a reviewer
#: can see the assessment used an assumed value, not a measured one.
ASSUMED_NOMINAL_DIAMETER_M: float = 0.1


def _mic_element(element: ServiceElement) -> MICElement:
    """Build the MC-001 input for one service element.

    ``nominal_diameter_m`` is required by the engine but absent from
    ``ServiceElement``, so an assumed value is supplied. See
    :data:`ASSUMED_NOMINAL_DIAMETER_M`.
    """
    return MICElement(
        global_id=element.guid,
        element_type=element.ifc_type,
        system_type=element.system,
        material=element.material_a,
        nominal_diameter_m=ASSUMED_NOMINAL_DIAMETER_M,
        floor=element.floor,
        zone=element.location_tag,
    )


# ---------------------------------------------------------------------------
# Citations — real, from the engine result
# ---------------------------------------------------------------------------


def _galvanic_citations(result) -> list[dict]:
    """Cite the standards and the threshold GC-001 actually applied."""
    return [
        {
            "standard": "NASA-STD-6012",
            "clause": "Voltage threshold by environment class",
            "reason": (
                f"threshold {result.env_threshold_v}V for {result.environment_label}; "
                f"measured gap {result.voltage_gap_v}V"
            ),
        },
        {
            "standard": result.ruleset_version,
            "clause": "Composite scoring",
            "reason": f"area ratio {result.area_ratio} banded {result.area_ratio_band}",
        },
    ]


def _crevice_citations(result) -> list[dict]:
    """Cite the standards and the values CC-001 actually applied."""
    return [
        {
            "standard": "EN ISO 15329:2007",
            "clause": "Wetting class framework",
            "reason": f"geometry class {result.geometry_class}",
        },
        {
            "standard": "ASTM G48 Method B",
            "clause": "Critical crevice temperature",
            "reason": f"CCT adequacy {result.cct_adequacy_score}",
        },
        {
            "standard": result.ruleset_version,
            "clause": "Composite scoring",
            "reason": f"environment severity {result.environment_severity_key}",
        },
    ]


def _mic_citations(result) -> list[dict]:
    """Cite the standards and the classes MC-001 actually applied."""
    return [
        {
            "standard": "ASTM G-187",
            "clause": "MIC assessment standard practice",
            "reason": f"flow class {result.flow_velocity_class}",
        },
        {
            "standard": "EN ISO 9308-1",
            "clause": "Microbiological water quality",
            "reason": f"temperature class {result.temperature_class}",
        },
        {
            "standard": result.ruleset_version,
            "clause": "Composite scoring",
            "reason": f"dead-leg class {result.dead_leg_class}",
        },
    ]


# ---------------------------------------------------------------------------
# Assessment
# ---------------------------------------------------------------------------


def _assess(element: ServiceElement, spec: MechanismSpec):
    """Run one mechanism against one element.

    Returns:
        ``(result, citations, error)``. On success ``error`` is ``None``; on
        failure ``result`` is ``None`` and ``error`` explains why, so the caller
        can raise a data-quality Issue instead of inventing a band.
    """
    try:
        if spec is GALVANIC:
            result = assess_galvanic_risk(_gc_element(element))
            return result, _galvanic_citations(result), None
        if spec is CREVICE:
            result = assess_crevice_risk(_cc_element(element))
            return result, _crevice_citations(result), None
        result = assess_mic_risk(_mic_element(element))
        return result, _mic_citations(result), None
    except Exception as exc:
        logger.warning(
            "Mechanism did not run element=%s mechanism=%s error=%s",
            element.guid,
            spec.code,
            exc,
        )
        return None, [], str(exc)


def _data_quality_issue(
    element: ServiceElement,
    spec: MechanismSpec,
    reason: str,
    allocator: IssueIdAllocator,
) -> Issue:
    """Report that a mechanism could not be evaluated for this element.

    Step 3 of the four-step rule. Low severity because it is not a finding, but
    ``mechanism="data_quality"`` and a populated ``metadata["check"]`` make it
    impossible to mistake for one — the separation
    ``test_data_quality_never_masquerades_as_a_verdict`` asserts.
    """
    return make_issue(
        id=allocator.next(spec.prefix),
        element_id=element.guid,
        rule_id=f"{spec.code}.DATA",
        title=f"{spec.label} could not be evaluated on {element.name or element.guid[:8]}",
        mechanism=DATA_QUALITY,
        band=RiskBand.LOW,
        score=0.10,
        mitigation=(
            f"Review the IFC source for this element. {spec.label} compliance "
            "cannot be evaluated until the missing data is corrected."
        ),
        assignee_role="BIM coordinator",
        description=f"{spec.code} did not produce a result for this element.",
        metadata={
            "check": "band_unassessed",
            "mechanism_code": spec.code,
            "reason": reason,
            "ifc_type": element.ifc_type,
            "material_a": element.material_a,
        },
        citations=[],
    )


def _finding_issue(
    element: ServiceElement,
    spec: MechanismSpec,
    result,
    band: RiskBand,
    citations: list[dict],
    allocator: IssueIdAllocator,
) -> Issue:
    """Build the Issue for a mechanism that did produce a band."""
    mitigations = list(getattr(result, "mitigations", []) or [])
    return make_issue(
        id=allocator.next(spec.prefix),
        element_id=element.guid,
        rule_id=spec.rule_id,
        title=f"{spec.label} risk on {element.name or element.guid[:8]}",
        mechanism=f"{spec.code} {spec.label.lower()}",
        band=band,
        score=float(getattr(result, "composite_score", 0.0) or 0.0),
        mitigation="; ".join(str(m) for m in mitigations),
        description=f"{spec.code} assessed this element as {band.value}.",
        metadata={
            "mechanism_code": spec.code,
            "ruleset_version": getattr(result, "ruleset_version", ""),
            "floor": element.floor,
            "system": element.system,
            "ifc_type": element.ifc_type,
            # Recorded so a reviewer can see which inputs were assumed rather
            # than read from the model.
            **(
                {"assumed_nominal_diameter_m": ASSUMED_NOMINAL_DIAMETER_M}
                if spec is MIC
                else {}
            ),
        },
        citations=citations,
    )


def run_corrosion_analysis(
    parsed: dict,
    *,
    include_low: bool = False,
    run_id: str = "BGR",
    engines: list[str] | None = None,
) -> dict:
    """Assess every element in ``parsed`` and return the corrosion result.

    Args:
        parsed: A ``ParsedIFC`` from :mod:`phase_6b_parsing`.
        include_low: Emit Low-band findings too. ``data_quality`` Issues are
            emitted regardless — see step 4.
        run_id: Prefix for allocated Issue ids.
        engines: Ruleset codes to execute, as resolved by
            :func:`resolve_mechanisms`. ``None`` runs every mechanism; a list
            runs only the mechanisms it names, and the others are not assessed
            at all rather than assessed and filtered.

    Returns:
        A dict carrying the ``AnalysisResult`` keys this session owns:
        ``audit_issues``, ``issue_stats``, ``cost_impact``,
        ``compliance_error`` and ``compliance_is_demo``.
    """
    if not parsed.get("quality", {}).get("valid", False):
        error = parsed.get("quality", {}).get("error") or "The IFC model could not be read."
        logger.warning("Corrosion analysis skipped; model invalid: %s", error)
        return _result([], error=error)

    elements: list[ServiceElement] = parsed.get("elements", [])
    allocator = IssueIdAllocator(run_id)
    issues: list[Issue] = []

    active = resolve_mechanisms(engines)
    if not active:
        # An empty selection is a valid request for nothing, not a fault: the
        # caller unchecked every engine. Returning here also keeps the catalog
        # reload below off the DB for a run that would assess nothing.
        logger.info("Corrosion analysis selected no mechanism engines=%s", engines)
        return _result([])

    try:
        from app.services.corrosion_rule_catalog import reload_all_catalogs
        reload_all_catalogs()
    except Exception:
        pass

    for element in elements:
        for spec in active:
            result, citations, error = _assess(element, spec)

            # Step 1: never invent a band.
            if result is None:
                # Step 2 and 3: report the absence as a visible, attributable,
                # non-verdict finding.
                issues.append(_data_quality_issue(element, spec, error or "no result", allocator))
                continue

            raw_band = getattr(result, "risk_band", None)
            if raw_band in (None, ""):
                issues.append(
                    _data_quality_issue(element, spec, "engine returned no band", allocator)
                )
                continue

            band = normalise_band(raw_band, element=element.guid, mechanism=spec.code)

            # Step 4: the include_low filter never applies to data_quality —
            # those were emitted above and are already past this point.
            if band is RiskBand.LOW and not include_low:
                continue

            issues.append(_finding_issue(element, spec, result, band, citations, allocator))

    logger.info(
        "Corrosion analysis complete elements=%d issues=%d data_quality=%d "
        "include_low=%s mechanisms=%s",
        len(elements),
        len(issues),
        sum(1 for i in issues if i.mechanism == DATA_QUALITY),
        include_low,
        ",".join(spec.code for spec in active),
    )
    return _result(issues)


def _result(issues: list[Issue], *, error: str | None = None) -> dict:
    """Assemble the AnalysisResult fragment this session owns."""
    return {
        "audit_issues": issues,
        "issue_stats": issue_stats(issues),
        # No cost model exists in this codebase — the only cost figures live in
        # app/engines/demo_data.py and are demo values. Returning None matches
        # what the orchestrator already does; inventing numbers here would put
        # fabricated costs into a compliance report.
        "cost_impact": None,
        "compliance_error": error,
        "compliance_is_demo": False,
    }


def issue_stats(issues: list[Issue]) -> dict:
    """Count findings by band, keeping data quality separate from verdicts.

    Data-quality Issues are excluded from the band counts on purpose: they are
    not findings, and folding them into ``low`` would report unassessed
    elements as assessed-and-safe — the very confusion §4.2 failure mode 5
    describes.
    """
    findings = [i for i in issues if i.mechanism != DATA_QUALITY]
    data_quality = [i for i in issues if i.mechanism == DATA_QUALITY]
    counts = Counter(i.band.value for i in findings)
    return {
        "total": len(findings),
        "critical": counts.get(RiskBand.CRITICAL.value, 0),
        "high": counts.get(RiskBand.HIGH.value, 0),
        "medium": counts.get(RiskBand.MEDIUM.value, 0),
        "low": counts.get(RiskBand.LOW.value, 0),
        "data_quality": len(data_quality),
    }


def worst_band(issues: list[Issue]) -> RiskBand | None:
    """Return the most severe band among findings, or ``None`` if there are none.

    Ranked through :data:`BAND_RANK`; ``max()`` over the raw values would sort
    alphabetically and return ``"medium"`` for a set containing ``"critical"``.
    """
    findings = [i for i in issues if i.mechanism != DATA_QUALITY]
    if not findings:
        return None
    return max((i.band for i in findings), key=lambda b: BAND_RANK[b])
