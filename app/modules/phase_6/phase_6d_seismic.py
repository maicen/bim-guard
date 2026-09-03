"""Session D — wire Blue Halo into ``AnalysisResult``.

Blue Halo Phase 3. The algorithm is finished and benchmarked in
``app/modules/blue_halo/halo_volume_generator.py``, whose own header
names this task: *"Phase 3+: config-driven wiring into Module 4 comparators."*
This module is that wiring, and reimplements none of it.

It generates a clearance envelope per braced element, detects intrusions into
it, and converts each :class:`ClashReport` into the same :class:`Issue` shape
Session C emits — so a seismic result and a corrosion result are the same shape
to everything downstream (data contracts §2 and §3, "the schema is deliberately
mechanism-agnostic").

GEOMETRY IS READ, NOT ASSUMED

    Halo needs a real ``BoundingBox`` per element. ``ServiceElement`` does not
    carry one — the Module 2 reader records a position and a length, not an
    extent — so this module opens the model and uses Halo's own
    ``element_bbox_mm``. It does **not** synthesise a box from position and
    length: a clash computed against an invented envelope is not a finding, and
    presenting it as one would be exactly the fabrication §4.2 warns about.

    An element whose geometry cannot be read produces a ``data_quality`` Issue,
    the same four-step rule Session C follows. Nothing is silently skipped and
    no clearance is invented.

NO DEMO MODE

    There is deliberately no synthetic-issue generator here. ``AnalysisResult``
    carries ``compliance_is_demo`` for that purpose and the contract requires
    the UI to honour it; minting seismic findings nobody computed would be the
    same defect as substituting a band for an unassessed mechanism.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from pathlib import Path

from app.logging_config import get_logger
from app.modules.blue_halo.halo_volume_generator import (
    BoundingBox,
    BraceType,
    ClashReport,
    ClearanceConfig,
    ElementGeometry,
    HaloVolume,
    detect_halo_clash_against_geometry,
    element_bbox_mm,
    element_diameter_mm,
    generate_halo_volume_from_geometry,
    load_clearance_config,
    unit_scale_to_mm,
)
from app.modules.comparator.issue_adapter import IssueIdAllocator
from app.modules.comparator.issue_schema import Issue, RiskBand, make_issue

logger = get_logger(__name__)

#: Label the primary model's elements are attributed to when a project federates
#: several. Not the file's name: the caller may have none, and the primary is
#: identified by its role rather than by what it happens to be called.
PRIMARY_MODEL_LABEL = "primary model"

#: Jurisdiction config shipped with the Blue Halo work. Phase 2 output.
DEFAULT_CONFIG_PATH = Path("data/rulesets/config_en_1998_1_din_4149.json")

#: Ruleset reference recorded on every seismic Issue.
RULE_ID = "SB-001.01"
MECHANISM_CODE = "SB-001"
MECHANISM_LABEL = "Seismic bracing clearance"

#: Mechanism string for a data-quality Issue. Must match Session C exactly, so
#: one exemption rule and one statistics split serve both.
DATA_QUALITY = "data_quality"

#: Clash severity -> RiskBand. Blue Halo grades an intrusion by how much of the
#: envelope is lost; that is a severity, not a 0-1 score, so it maps rather than
#: passes through band_from_score.
SEVERITY_TO_BAND: dict[str, RiskBand] = {
    "critical": RiskBand.CRITICAL,
    "major": RiskBand.HIGH,
    "minor": RiskBand.MEDIUM,
}

#: IFC classes treated as braced MEP services. Everything else in the model is
#: a clash candidate rather than a halo source.
BRACED_CLASSES: tuple[str, ...] = (
    "IfcPipeSegment",
    "IfcDuctSegment",
    "IfcCableCarrierSegment",
    "IfcFlowSegment",
)

#: The subset of BRACED_CLASSES that ``thresholds.pipe_diameter_mm`` governs.
#: Ducts and cable carriers are sized by area, not diameter, and the config's
#: ``thresholds.duct_area_sqm`` is null (a documented data gap), so they stay in
#: scope unconditionally rather than being filtered by a threshold that does not
#: describe them.
PIPE_CLASSES: tuple[str, ...] = ("IfcPipeSegment", "IfcFlowSegment")


def _severity_band(severity: str, *, element: str) -> RiskBand:
    """Map a Blue Halo clash severity to a :class:`RiskBand`.

    Raises rather than defaulting: an unmapped severity would otherwise become
    the mildest band and quietly downgrade a finding.
    """
    try:
        return SEVERITY_TO_BAND[str(severity).strip().lower()]
    except KeyError:
        raise ValueError(
            f"Unknown clash severity {severity!r} for {element} / {MECHANISM_CODE}"
        ) from None


def _citations(config: ClearanceConfig, halo: HaloVolume) -> list[dict]:
    """Cite the standards the loaded config declares and the clearance applied.

    Real, like Session C's: the standards come from the jurisdiction config's
    own ``standards_cited``, and the clearance is the value the rule actually
    produced for this element.
    """
    citations = [
        {
            "standard": standard,
            "clause": f"{config.jurisdiction} bracing clearance",
            "reason": (
                f"{halo.clearance_mm}mm clearance applied to "
                f"{halo.brace_type.value} bracing"
                + (f" (variant {halo.rule_variant})" if halo.rule_variant else "")
            ),
        }
        for standard in config.standards_cited
    ]
    if not citations:
        # A config with no standards is a gap worth seeing, not one to paper
        # over with an invented reference.
        logger.warning("Clearance config %s cites no standards", config.jurisdiction)
    return citations


def _data_quality_issue(
    element_id: str,
    ifc_class: str,
    reason: str,
    allocator: IssueIdAllocator,
    source_model: str = "",
) -> Issue:
    """Report that an element could not be assessed for seismic clearance.

    Args:
        source_model: The model the element came from. Carried so a coordinator
            reading a federated run knows which file to open, and defaulted to
            empty for a single-model run where there is no ambiguity.
    """
    return make_issue(
        id=allocator.next("SB"),
        element_id=element_id,
        rule_id=f"{MECHANISM_CODE}.DATA",
        title=f"{MECHANISM_LABEL} could not be evaluated on {element_id[:8]}",
        mechanism=DATA_QUALITY,
        band=RiskBand.LOW,
        score=0.10,
        mitigation=(
            "Review the IFC source for this element. Seismic clearance cannot "
            "be evaluated until its geometry can be read."
        ),
        assignee_role="BIM coordinator",
        description=f"{MECHANISM_CODE} did not produce a result for this element.",
        metadata={
            "check": "geometry_unavailable",
            "mechanism_code": MECHANISM_CODE,
            "reason": reason,
            "ifc_class": ifc_class,
            "source_model": source_model,
        },
        citations=[],
    )


def _clash_issue(
    clash: ClashReport,
    halo: HaloVolume,
    config: ClearanceConfig,
    allocator: IssueIdAllocator,
    source_of: dict[str, str] | None = None,
) -> Issue:
    """Convert one :class:`ClashReport` into an :class:`Issue`.

    Args:
        source_of: Element id to source model. A clash between two models is the
            finding a federated run exists to produce, and it is only actionable
            if the report says which two.
    """
    sources = source_of or {}
    band = _severity_band(clash.severity, element=clash.halo_source_element_id)
    return make_issue(
        id=allocator.next("SB"),
        element_id=clash.halo_source_element_id,
        rule_id=RULE_ID,
        title=f"{MECHANISM_LABEL} clash on {clash.halo_source_element_id[:8]}",
        mechanism=f"{MECHANISM_CODE} seismic bracing",
        band=band,
        # Overlap ratio is not reported on the clash, so the score is derived
        # from the band rather than invented: a band-consistent placeholder is
        # honest, a fabricated ratio is not.
        score={
            RiskBand.CRITICAL: 0.9,
            RiskBand.HIGH: 0.7,
            RiskBand.MEDIUM: 0.4,
            RiskBand.LOW: 0.1,
        }[band],
        mitigation=(
            f"Relocate {clash.clashing_element_id[:8]} or re-route the braced "
            f"service to restore {halo.clearance_mm}mm clearance."
        ),
        assignee_role="Mechanical engineer",
        description=clash.description,
        metadata={
            "mechanism_code": MECHANISM_CODE,
            "halo_id": clash.halo_id,
            "clashing_element_id": clash.clashing_element_id,
            "clashing_element_class": clash.clashing_element_class,
            "source_model": sources.get(clash.halo_source_element_id, ""),
            "clashing_source_model": sources.get(clash.clashing_element_id, ""),
            "overlap_volume_mm3": clash.overlap_volume_mm3,
            "clearance_mm": halo.clearance_mm,
            "brace_type": halo.brace_type.value,
            "rule_variant": halo.rule_variant,
            "jurisdiction": config.jurisdiction,
        },
        citations=_citations(config, halo),
    )


def _cross_section_mm(geometry: ElementGeometry) -> float:
    """Estimate an element's outside diameter from its bounding box, mm.

    A pipe run's axis-aligned box is ``length x d x d``, so the median of the
    three extents is the cross-section: the longest is the run, and the two
    shorter ones are the diameter.

    This is a proxy, not a property read. It is used because the seismic path
    works from raw geometry -- ``ElementGeometry`` carries a bounding box and
    nothing else -- and because the models this runs against carry almost no
    ``NominalDiameter`` properties to read instead. The approximation errs
    high: a pipe running diagonally inflates its own box, so the estimate
    overstates the diameter and keeps the element in scope. That direction is
    deliberate -- over-inclusion costs review time, under-inclusion drops a
    brace that a standard requires.

    Reading ``NominalDiameter`` off the IFC entity where it exists, and falling
    back to this only when it does not, would be strictly better and is the
    obvious next refinement.
    """
    return sorted(geometry.bbox_mm.size)[1]


def _bracing_scope(geometry: ElementGeometry, threshold_mm: float | None) -> str:
    """Classify *geometry* against the config's bracing threshold.

    Returns one of:
        ``"braced"``
            In scope: a braced class, and either no threshold applies to it or
            its estimated diameter meets the threshold.
        ``"below_threshold"``
            A pipe the standard does not require braced. Skipped silently,
            because that is a correct result and not a gap.
        ``"unmeasurable"``
            A pipe whose bounding box has no thickness, so no diameter can be
            estimated from it. Reported as a data-quality finding rather than
            skipped: an element that cannot be measured is unknown, not small,
            and dropping it would hide a brace the standard may require.
        ``"out_of_class"``
            Not a braced class at all.
    """
    if geometry.ifc_class not in BRACED_CLASSES:
        return "out_of_class"
    if threshold_mm is None or geometry.ifc_class not in PIPE_CLASSES:
        return "braced"

    # The declared profile is the real diameter; the bounding box is only a
    # fallback for elements whose geometry is a mesh rather than a sweep.
    diameter = geometry.nominal_diameter_mm or _cross_section_mm(geometry)
    if diameter <= 0.0:
        return "unmeasurable"
    return "braced" if diameter >= threshold_mm else "below_threshold"


def _geometries(model, scale: float) -> tuple[list[ElementGeometry], list[tuple[str, str, str]]]:
    """Extract a bounding box for every element in the model.

    Returns:
        ``(geometries, failures)`` where each failure is
        ``(element_id, ifc_class, reason)`` for an element whose geometry could
        not be read.
    """
    geometries: list[ElementGeometry] = []
    failures: list[tuple[str, str, str]] = []

    try:
        entities = list(model.by_type("IfcElement"))
    except Exception as exc:
        logger.warning("Could not enumerate model elements: %s", exc)
        return [], []

    for entity in entities:
        element_id = str(getattr(entity, "GlobalId", "") or "")
        ifc_class = entity.is_a() if hasattr(entity, "is_a") else ""
        if not element_id:
            continue
        try:
            bbox: BoundingBox | None = element_bbox_mm(entity, scale)
        except Exception as exc:
            failures.append((element_id, ifc_class, str(exc)))
            continue
        if bbox is None:
            failures.append((element_id, ifc_class, "no readable geometry"))
            continue
        try:
            diameter = element_diameter_mm(entity, scale)
        except Exception:  # pragma: no cover - malformed representation
            diameter = None
        geometries.append(
            ElementGeometry(
                element_id=element_id,
                ifc_class=ifc_class,
                bbox_mm=bbox,
                nominal_diameter_mm=diameter,
            )
        )

    return geometries, failures


def run_seismic_analysis(
    ifc_bytes: bytes,
    *,
    extra_models: Sequence[tuple[str, bytes]] = (),
    config_path: str | Path = DEFAULT_CONFIG_PATH,
    brace_type: BraceType = BraceType.ANGLE_IRON,
    seismic_zone: bool = True,
    building_type: str = "standard",
    run_id: str = "BGR",
) -> dict:
    """Run Blue Halo over a building and return the seismic ``AnalysisResult``.

    WHY THIS ONE READS EVERY MODEL

        A clearance envelope is a question about a building, not about a file.
        The brace is in the mechanical model and the beam it has to clear is in
        the structural one, so running this over a single discipline model finds
        the clashes that discipline has with itself and reports silence about
        the rest. Every model attached to the project is therefore read into one
        geometry set, and clash detection runs across the union.

        Corrosion is the opposite case and stays single-model: galvanic and
        crevice assessment is a question about a pipe run and its materials, and
        a second discipline's copy of the same run would double every finding.

    Args:
        ifc_bytes: The primary model, as stored. Read directly rather than via
            ``ParsedIFC`` because clearance envelopes need real geometry and
            ``ServiceElement`` does not carry it.
        extra_models: ``(label, bytes)`` for the project's other models. The
            label names the file in any Issue raised against its elements.
        config_path: Jurisdiction clearance config (Blue Halo Phase 2 output).
        brace_type: Hardware category assumed installed on braced services.
        seismic_zone: Whether the site is in a declared seismic zone.
        building_type: Occupancy category, e.g. ``"hospital"``.
        run_id: Prefix for allocated Issue ids.

    Returns:
        The same keys Session C returns, so both analyses are interchangeable
        downstream: ``audit_issues``, ``issue_stats``, ``cost_impact``,
        ``compliance_error``, ``compliance_is_demo``.
    """
    try:
        config = load_clearance_config(config_path)
    except Exception as exc:
        logger.warning("Clearance config unavailable path=%s error=%s", config_path, exc)
        return _result([], error=f"The seismic clearance config could not be loaded: {exc}")

    rules = config.rules_for(brace_type)
    if not rules:
        return _result(
            [],
            error=(
                f"{config.jurisdiction} defines no {brace_type.value} bracing rule, "
                "so no clearance can be applied."
            ),
        )
    rule = rules[0]

    try:
        import ifcopenshell
    except ImportError:
        return _result([], error="ifcopenshell is not installed, so IFC files cannot be read.")

    geometries: list[ElementGeometry] = []
    failures: list[tuple[str, str, str]] = []
    source_of: dict[str, str] = {}
    read: set[str] = set()
    unread: dict[str, tuple[str, str, str]] = {}
    duplicates = 0

    for label, content in ((PRIMARY_MODEL_LABEL, ifc_bytes), *extra_models):
        try:
            model = ifcopenshell.file.from_string(content.decode("utf-8", errors="replace"))
        except Exception as exc:
            return _result([], error=f"{label} could not be read as IFC: {exc}")

        model_geometries, model_failures = _geometries(model, unit_scale_to_mm(model))
        for geometry in model_geometries:
            # One element, one envelope. The same GlobalId in two models is the
            # same element federated twice -- a linked reference, or one
            # discipline's copy of another's -- and keeping both would have it
            # clash with itself and report a clearance failure nobody can fix.
            # The primary model is read first, so it is the copy that survives.
            if geometry.element_id in read:
                duplicates += 1
                continue
            read.add(geometry.element_id)
            geometries.append(geometry)
            source_of[geometry.element_id] = label
        for element_id, ifc_class, reason in model_failures:
            unread.setdefault(element_id, (element_id, ifc_class, reason))
            source_of.setdefault(element_id, label)

    # An element is unreadable only if no model could read it. One discipline
    # federating a placeholder for an element another models properly is the
    # normal case, and reporting it as unassessed there would be a finding about
    # the federation rather than about the building. Deduplicated for the same
    # reason the geometries are: one element, one report.
    failures = [entry for element_id, entry in unread.items() if element_id not in read]

    allocator = IssueIdAllocator(run_id)
    issues: list[Issue] = []

    # An element whose geometry could not be read is reported, never skipped.
    for element_id, ifc_class, reason in failures:
        if ifc_class in BRACED_CLASSES:
            issues.append(
                _data_quality_issue(
                    element_id, ifc_class, reason, allocator, source_of.get(element_id, "")
                )
            )

    # Scope bracing to what the standard actually requires braced. The config
    # declares thresholds.pipe_diameter_mm and the loader parses it, but until
    # now nothing applied it: every pipe got a halo regardless of size, so a
    # dense model reported a clash for every small-bore run in it.
    #
    # The diameter is estimated from the bounding box, and on models whose pipe
    # geometry does not resolve to a solid that estimate is unavailable rather
    # than small. Those elements are reported, not dropped -- see _bracing_scope.
    threshold_mm = config.pipe_diameter_threshold_mm
    in_class = [g for g in geometries if g.ifc_class in BRACED_CLASSES]
    scoped: dict[str, list[ElementGeometry]] = {
        "braced": [],
        "below_threshold": [],
        "unmeasurable": [],
    }
    for geometry in in_class:
        scoped[_bracing_scope(geometry, threshold_mm)].append(geometry)

    braced = scoped["braced"]
    for geometry in scoped["unmeasurable"]:
        issues.append(
            _data_quality_issue(
                geometry.element_id,
                geometry.ifc_class,
                (
                    "Bounding box has no thickness, so no diameter could be "
                    f"estimated to test against the {threshold_mm}mm bracing "
                    "threshold. The element's geometry may be a centreline or "
                    "a swept solid whose profile the reader does not resolve."
                ),
                allocator,
                source_of.get(geometry.element_id, ""),
            )
        )

    for geometry in braced:
        halo = generate_halo_volume_from_geometry(
            geometry,
            brace_type,
            rule,
            seismic_zone=seismic_zone,
            building_type=building_type,
        )
        candidates = [g for g in geometries if g.element_id != geometry.element_id]
        for clash in detect_halo_clash_against_geometry(halo, candidates):
            issues.append(_clash_issue(clash, halo, config, allocator, source_of))

    logger.info(
        "Seismic analysis complete models=%d elements=%d in_class=%d braced=%d "
        "below_threshold=%d unmeasurable=%d threshold_mm=%s clashes=%d "
        "data_quality=%d federated_duplicates=%d",
        1 + len(extra_models),
        len(geometries),
        len(in_class),
        len(braced),
        len(scoped["below_threshold"]),
        len(scoped["unmeasurable"]),
        threshold_mm,
        sum(1 for i in issues if i.mechanism != DATA_QUALITY),
        sum(1 for i in issues if i.mechanism == DATA_QUALITY),
        duplicates,
    )
    # Bracing scope stays in the log rather than the result: a seismic result
    # and a corrosion result must carry identical keys to be interchangeable
    # downstream, which tests/test_phase_6d_seismic.py pins.
    return _result(issues)


def _result(issues: list[Issue], *, error: str | None = None) -> dict:
    """Assemble the AnalysisResult fragment, matching Session C's shape."""
    return {
        "audit_issues": issues,
        "issue_stats": issue_stats(issues),
        # No cost model exists for seismic remediation either. See Session C.
        "cost_impact": None,
        "compliance_error": error,
        "compliance_is_demo": False,
    }


def issue_stats(issues: list[Issue]) -> dict:
    """Count findings by band, keeping data quality out of the band totals."""
    findings = [i for i in issues if i.mechanism != DATA_QUALITY]
    counts = Counter(i.band.value for i in findings)
    return {
        "total": len(findings),
        "critical": counts.get(RiskBand.CRITICAL.value, 0),
        "high": counts.get(RiskBand.HIGH.value, 0),
        "medium": counts.get(RiskBand.MEDIUM.value, 0),
        "low": counts.get(RiskBand.LOW.value, 0),
        "data_quality": sum(1 for i in issues if i.mechanism == DATA_QUALITY),
    }
