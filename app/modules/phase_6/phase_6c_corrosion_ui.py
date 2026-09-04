"""Session C — run the corrosion engines over a ParsedIFC and emit Issues.

Takes Session B's ``ParsedIFC`` and produces the corrosion half of
``AnalysisResult`` (data contracts §2): a list of :class:`Issue` plus the
statistics the analyse pages render.

WHAT THIS DOES NOT DO

    It does not implement GC-001, CC-001, MC-001, MM-001 or XM-001. Those
    engines already exist — GC/CC/MC in ``app/engines/``, MM/XM in
    ``app/modules/comparator/`` — and are thesis-backing work; this
    module is the wiring that feeds them elements and turns their results into
    the shared ``Issue`` shape.

TWO KINDS OF MECHANISM

    GC-001, CC-001 and MC-001 score one element at a time and return an engine
    result carrying a band, which this module turns into an Issue. MM-001 and
    XM-001 do not: they are comparators that take a whole network and return
    ``Issue`` objects directly, already banded, already cited.

    XM-001 in particular *cannot* be run per element — it derives dissimilar
    metal couples from what each element is joined to, so an element handed to
    it alone has nothing to couple with and would score clean every time.
    Calling it once per element would report a model with no galvanic couples,
    which is a false all-clear rather than a missing feature.

    So :data:`MECHANISMS` names all five, and the run splits into
    :data:`ELEMENT_MECHANISMS` (per element, via :func:`_assess`) and
    :data:`NETWORK_MECHANISMS` (once over the network, via
    :func:`_assess_network`).

    The two halves also read different element shapes. GC/CC/MC take the
    ``ServiceElement`` rows in ``parsed["elements"]``; MM/XM take the
    ``PipingElement`` rows in ``parsed["piping_elements"]``, because they need
    the operating temperature and the connectivity that ``ServiceElement`` does
    not carry. A parse that did not request the piping view leaves MM/XM with
    nothing to assess, which is reported, not assumed clean.

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
from app.modules.ifc_reader.ifc_parser import ServiceElement
from app.modules.comparator import cross_material, material_media
from app.modules.comparator.issue_adapter import IssueIdAllocator
from app.modules.comparator.issue_schema import Issue, RiskBand, make_issue

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
MM = MechanismSpec("MM-001", "MM-001.01", "MM", "Material-media compatibility")
XM = MechanismSpec("XM-001", "XM-001.01", "XM", "Cross-material compatibility")

#: Scored one element at a time; each returns an engine result carrying a band.
ELEMENT_MECHANISMS: tuple[MechanismSpec, ...] = (GALVANIC, CREVICE, MIC)

#: Scored once over the whole network; each returns finished Issues. See "TWO
#: KINDS OF MECHANISM" in the module docstring for why these cannot be folded
#: into the per-element loop.
NETWORK_MECHANISMS: tuple[MechanismSpec, ...] = (MM, XM)

#: Every mechanism a corrosion run drives, in report order.
MECHANISMS: tuple[MechanismSpec, ...] = ELEMENT_MECHANISMS + NETWORK_MECHANISMS


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
    """Run one :data:`ELEMENT_MECHANISMS` mechanism against one element.

    MM-001 and XM-001 are not reachable from here: they take a network, not an
    element, and return finished Issues rather than a bandable engine result.
    They are dispatched by :func:`_assess_network` instead.

    Returns:
        ``(result, citations, error)``. On success ``error`` is ``None``; on
        failure ``result`` is ``None`` and ``error`` explains why, so the caller
        can raise a data-quality Issue instead of inventing a band.
    """
    try:
        if spec.code == "GC-001":
            result = assess_galvanic_risk(_gc_element(element))
            return result, _galvanic_citations(result), None
        if spec.code == "CC-001":
            result = assess_crevice_risk(_cc_element(element))
            return result, _crevice_citations(result), None
        if spec.code == "MC-001":
            result = assess_mic_risk(_mic_element(element))
            return result, _mic_citations(result), None
        raise ValueError(
            f"{spec.code} is not a per-element mechanism; it runs over the network"
        )
    except Exception as exc:
        logger.warning(
            "Mechanism did not run element=%s mechanism=%s error=%s",
            element.guid,
            spec.code,
            exc,
        )
        return None, [], str(exc)


# ---------------------------------------------------------------------------
# Network mechanisms: MM-001 and XM-001
# ---------------------------------------------------------------------------


#: NASA-STD-6012 compatibility class -> the GC-001 environment class carrying
#: that class's max safe voltage. XM-001's pack maps its own environment values
#: onto the three NASA classes but deliberately omits the voltages, so that the
#: numbers live in exactly one place; this is the other half of that mapping.
#: The three GC-001 classes named here carry 0.50 V, 0.25 V and 0.15 V, which
#: are the published NASA-STD-6012 limits for controlled, normal and harsh.
XM_THRESHOLD_ENVIRONMENTS: dict[str, str] = {
    "controlled": "E1_CONTROLLED",
    "normal": "E2_NORMAL",
    "harsh": "E3_HUMID",
}


#: Canonical piping material -> GC-001 galvanic series key.
#:
#: The two taxonomies name the same metals differently: ``PipingElement.material``
#: uses the Module 2 canonical set (``"SS316L"``, ``"Copper_C12200"``) and the
#: GC-001 series uses its own keys (``"ss316_passive"``, ``"copper"``). Every
#: pairing below is the one GC-001's own ``MATERIAL_ALIASES`` already makes for
#: the same metal, so this table introduces no new corrosion judgement -- it
#: only states the join explicitly.
#:
#: ``resolve_material`` is deliberately not used for this. Its substring
#: fallback resolves ``"GalvanisedSteel"`` to ``carbon_steel``, because
#: ``"steel"`` is tested before ``"galvanised"``, which would score a
#: galvanised-to-carbon-steel junction as no couple at all.
#:
#: Absences are meaningful. The non-metallics (PVC, HDPE, PEX, PPR) and
#: ``"Unknown"`` have no entry, and neither do the cupronickels, which the
#: GC-001 series does not carry. XM-001 reports an unlisted material as a
#: data-quality Issue -- once per material, not once per couple -- rather than
#: assuming it benign, which is the correct answer for a material whose
#: position in the series this project has not established.
XM_MATERIAL_TO_SERIES_KEY: dict[str, str] = {
    "Aluminium": "aluminium",
    "BlackSteel": "carbon_steel",
    "Brass_C46400": "brass",
    "CarbonSteel": "carbon_steel",
    "CastIron": "cast_iron",
    "Copper_C12200": "copper",
    "DuctileIron": "cast_iron",
    "Duplex2205": "ss316_passive",
    "GalvanisedSteel": "galv_steel",
    "SS304": "ss304_passive",
    "SS304L": "ss304_passive",
    "SS316": "ss316_passive",
    "SS316L": "ss316_passive",
    "SS316Ti": "ss316_passive",
    "SuperDuplex2507": "ss316_passive",
    "Titanium": "titanium",
}


def _xm_galvanic_series() -> dict:
    """Return the GC-001 series keyed and shaped the way XM-001 reads it.

    There is one galvanic series in this project and it belongs to GC-001.
    XM-001 stores none of its own -- its pack has no ``galvanic_series`` key at
    all -- so the series is injected at load time rather than duplicated under
    a second name.

    Two things are translated: the key, via
    :data:`XM_MATERIAL_TO_SERIES_KEY`, so that the series is looked up by the
    material name a ``PipingElement`` actually carries; and the potential
    field, which GC-001 calls ``potential`` and XM-001 reads as
    ``potential_v``. Both are renames. The values are GC-001's throughout,
    including the ``noble`` flags XM-001 uses to name the anode.

    A material whose series entry is missing from the catalog is omitted rather
    than given a null potential: a null would make every couple it appears in
    score a zero voltage gap, which reads as a safe pairing.
    """
    from app.engines.bimguard_corrosion_engine import GALVANIC_SERIES

    series: dict[str, dict] = {}
    for material, series_key in XM_MATERIAL_TO_SERIES_KEY.items():
        entry = GALVANIC_SERIES.get(series_key)
        if not entry or entry.get("potential") is None:
            continue
        series[material] = {
            "potential_v": float(entry["potential"]),
            "noble": entry.get("noble"),
            "label": entry.get("label", material),
        }
    return series


def _xm_compatibility_thresholds() -> dict:
    """Return the NASA-STD-6012 max safe voltages, read from the GC-001 catalog.

    Same single-source rule as the series: the voltages already exist as GC-001
    environment thresholds, so they are read from there rather than restated.
    A class the catalog does not carry is omitted, which XM-001 treats as an
    unresolvable floor and therefore fails open -- a finding, never silence.
    """
    from app.engines.bimguard_corrosion_engine import ENVIRONMENT_CLASSES

    thresholds: dict[str, dict] = {}
    for nasa_class, env_key in XM_THRESHOLD_ENVIRONMENTS.items():
        limit = (ENVIRONMENT_CLASSES.get(env_key) or {}).get("voltage_threshold")
        if limit is not None:
            thresholds[nasa_class] = {"max_safe_voltage_v": float(limit)}
    return thresholds


def _assess_mm001(elements: list, spec: MechanismSpec, allocator: IssueIdAllocator):
    """Run MM-001 over the piping network.

    Args:
        elements: The ``PipingElement`` network.
        spec: The MM-001 mechanism spec, for the id prefix and logging.
        allocator: The run-wide id allocator.

    Returns:
        ``(issues, error)``. On failure ``issues`` is empty and ``error`` says
        why, so the caller reports the absence rather than an empty all-clear.
    """
    try:
        rule_pack = material_media.load_rule_pack()
        # The run-wide allocator is passed straight through: material_media
        # calls .next() with its own "MM" prefix, which keeps these ids inside
        # the run's numbering instead of a sequence of the engine's own.
        issues = material_media.compare(elements, rule_pack, allocator)
        return issues, None
    except Exception as exc:
        logger.warning("Mechanism did not run mechanism=%s error=%s", spec.code, exc)
        return [], str(exc)


def _assess_xm001(elements: list, spec: MechanismSpec, allocator: IssueIdAllocator):
    """Run XM-001 over the piping network.

    The pack on disk carries neither the galvanic series nor the compatibility
    voltages; both are injected from the GC-001 catalog so that no galvanic
    constant exists twice in the repository.

    Args:
        elements: The ``PipingElement`` network.
        spec: The XM-001 mechanism spec, for the id prefix and logging.
        allocator: The run-wide id allocator.

    Returns:
        ``(issues, error)``, with the same contract as :func:`_assess_mm001`.
    """
    try:
        rule_pack = cross_material.load_rule_pack(
            galvanic_series=_xm_galvanic_series(),
            compatibility_thresholds=_xm_compatibility_thresholds(),
        )
        issues = cross_material.compare(elements, rule_pack, allocator)
        return issues, None
    except Exception as exc:
        logger.warning("Mechanism did not run mechanism=%s error=%s", spec.code, exc)
        return [], str(exc)


def _assess_network(elements: list, spec: MechanismSpec, allocator: IssueIdAllocator):
    """Route one :data:`NETWORK_MECHANISMS` mechanism to its comparator."""
    if spec.code == "MM-001":
        return _assess_mm001(elements, spec, allocator)
    if spec.code == "XM-001":
        return _assess_xm001(elements, spec, allocator)
    return [], f"{spec.code} is not a network mechanism"


def _provenance(element: ServiceElement) -> dict[str, str]:
    """Report where this element's material and environment actually came from.

    GC-001, CC-001 and MC-001 are decided by ``material_a`` and
    ``location_tag``, and neither is guaranteed to be a reading: an IFC with no
    material yields ``"Unknown"``, and a space name matching no
    ``SPACE_TO_ENV`` keyword yields the module's indoor default. Both then look
    identical to values read off the model by the time an engine scores them.

    Every finding carries this block so a reviewer can see whether a Critical
    band rests on the building or on an assumption — the same question
    ``assumed_nominal_diameter_m`` already answers for MC-001's diameter, asked
    of the two inputs that matter most.
    """
    return {
        "material_source": element.material_source,
        "material_confidence": element.material_confidence,
        "environment_source": element.environment_source,
        "environment_confidence": element.environment_confidence,
    }


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
            # Often the explanation for the absence: an engine that could not
            # resolve a material usually could not because none was read.
            **_provenance(element),
        },
        citations=[],
    )


def _network_data_quality_issue(
    spec: MechanismSpec,
    reason: str,
    allocator: IssueIdAllocator,
) -> Issue:
    """Report that a network mechanism could not be evaluated at all.

    The four-step rule applies to MM-001 and XM-001 exactly as it does to the
    per-element engines, but the absence is not attributable to one element:
    the engine either ran over the network or it did not. ``element_id`` is
    therefore empty, which is the honest answer -- inventing an element to hang
    it on would be worse than an unattributed finding.
    """
    return make_issue(
        id=allocator.next(spec.prefix),
        element_id="",
        rule_id=f"{spec.code}.DATA",
        title=f"{spec.label} could not be evaluated on this model",
        mechanism=DATA_QUALITY,
        band=RiskBand.LOW,
        score=0.10,
        mitigation=(
            f"Review the IFC source for this model. {spec.label} compliance "
            "cannot be evaluated until the missing data is corrected."
        ),
        assignee_role="BIM coordinator",
        description=f"{spec.code} did not run against this model.",
        metadata={
            "check": "network_unassessed",
            "mechanism_code": spec.code,
            "reason": reason,
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
            **_provenance(element),
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
    active_elementwise = tuple(spec for spec in active if spec in ELEMENT_MECHANISMS)
    active_network = tuple(spec for spec in active if spec in NETWORK_MECHANISMS)
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
        for spec in active_elementwise:
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

    # The network mechanisms. Their comparators return finished Issues -- banded
    # and cited -- so there is nothing here to band, only the same include_low
    # filter the per-element loop applies, under the same step 4 exemption.
    issues.extend(
        _run_network_mechanisms(
            parsed, allocator, include_low=include_low, mechanisms=active_network
        )
    )

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


def _run_network_mechanisms(
    parsed: dict,
    allocator: IssueIdAllocator,
    *,
    include_low: bool = False,
    mechanisms: tuple[MechanismSpec, ...] | None = None,
) -> list[Issue]:
    """Run MM-001 and XM-001 over the model's piping network.

    An empty network produces nothing. A model that holds no piping has nothing
    for these two to assess and nothing was missed, and a caller that did not
    ask ``parse_ifc_bytes`` for the piping view has made a configuration choice
    rather than uncovered a defect in the model -- neither is a finding about
    the building. Both are logged, and a piping extraction that actually failed
    is already reported as a parse quality warning where it happened.

    What *is* a finding is a mechanism that had a network and still could not
    run: that is reported as a data-quality Issue, because an engine that did
    not run has not cleared the model and step 1 of the four-step rule forbids
    saying otherwise.

    MM-001 suppresses its own Low band, but XM-001 reports every surviving
    couple including Low ones, so the filter is applied here rather than
    assumed. ``data_quality`` Issues are exempt, which is step 4: they are the
    record that something was not assessed, and dropping them is what turns a
    gap back into a silent pass.

    Args:
        parsed: The ``ParsedIFC`` being assessed.
        allocator: The run-wide id allocator, shared with the per-element loop
            so ids stay unique across all five mechanisms.
        include_low: Keep Low-band findings. Matches
            :func:`run_corrosion_analysis`.
        mechanisms: The network mechanisms the caller selected. ``None`` runs
            both; an empty tuple runs neither, which is a selection rather
            than a failure and therefore raises no data-quality Issue.

    Returns:
        Every Issue the network mechanisms produced, after the filter.
    """
    selected = NETWORK_MECHANISMS if mechanisms is None else mechanisms
    if not selected:
        return []

    piping = parsed.get("piping_elements") or []
    issues: list[Issue] = []

    if not piping:
        logger.info(
            "Network mechanisms skipped; no piping network on this parse "
            "(mechanisms=%s)",
            ", ".join(spec.code for spec in selected),
        )
        return issues

    for spec in selected:
        found, error = _assess_network(piping, spec, allocator)
        if error is not None:
            issues.append(_network_data_quality_issue(spec, error, allocator))
            continue
        issues.extend(
            issue
            for issue in found
            if include_low
            or issue.band is not RiskBand.LOW
            or issue.mechanism == DATA_QUALITY
        )

    return issues


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
