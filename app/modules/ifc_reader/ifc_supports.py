"""Seismic supports: what holds a pipe up, how far apart, and how long the rods are.

Drafted for the sway-brace spacing and hanger-rod length rules. Nothing here is
wired into ``extract_for_compliance`` yet -- these are the helpers those rules
will need, built and tested on their own first.

THREE QUESTIONS, THREE LAYERS

    "What supports this pipe, and of what kind?"  -> :func:`find_supports`
    "How far apart are consecutive braces?"       -> :func:`brace_spacing`
    "How long is the unbraced rod?"               -> :func:`rod_length_mm`

The module is deliberately layered so that most of it can be tested without an
IFC file at all:

    pure math      _sub/_dot/_unit, :func:`project_station_mm`,
                   :func:`perpendicular_distance_mm`, :func:`brace_spacing`,
                   :func:`classify_orientation` -- plain tuples in, numbers out.
    IFC reading    :func:`classify_support`, :func:`element_axis`,
                   :func:`find_supports`, :func:`rod_length_mm` -- need entities.

WHY ORIENTATION IS MEASURED, NOT READ

A lateral brace resists movement across the pipe run; a longitudinal brace
resists movement along it. Which one a given brace is depends on how it sits
relative to the run, and IFC has no attribute that says so. Names claim it
("SwayBrace-Lateral-01") and names are wrong often enough that a compliance
verdict should not rest on them. So both are produced: the name gives
``declared`` and the geometry gives ``measured``, and
:func:`classify_support` reports them separately rather than silently picking
one. A rule can then decide whether to trust the label, and a disagreement is
visible instead of averaged away.

MISSING IS NOT ZERO

Every function returns ``None`` when the model cannot answer -- never 0.0, and
never a default. Two braces that cannot be located are not "0 mm apart", and a
rod whose geometry will not resolve is not "0 mm long"; both would read as
catastrophic failures of rules that were never actually evaluated. A run with
one brace has no spacing at all, which is a different statement from a spacing
of zero, and :func:`brace_spacing` says so by returning an empty list of gaps
alongside the run extent that a rule still needs.
"""

from __future__ import annotations

import math

from app.logging_config import get_logger

logger = get_logger(__name__)

Vec3 = tuple[float, float, float]

# ── Support kinds ─────────────────────────────────────────────────────────────

HANGER = "HANGER"
#: A brace known to be a brace, but not yet known to be lateral or
#: longitudinal. IFC has no enumeration for the distinction -- IfcMember's
#: PredefinedType offers only BRACE -- so this is where the type system leaves
#: us, and pretending otherwise would put a label on a coin toss.
BRACE = "BRACE"
LATERAL_BRACE = "LATERAL_BRACE"
LONGITUDINAL_BRACE = "LONGITUDINAL_BRACE"
RISER_RESTRAINT = "RISER_RESTRAINT"
UNKNOWN = "UNKNOWN"

#: Kinds that geometry can refine, and the orientations it can refine them to.
_BRACE_KINDS = (BRACE, LATERAL_BRACE, LONGITUDINAL_BRACE)

#: How specific each kind is. A signal never overwrites a more specific one
#: already found, so a name saying "longitudinal" survives a PredefinedType
#: that can only say "brace".
_SPECIFICITY = {
    UNKNOWN: 0,
    BRACE: 1,
    HANGER: 2,
    RISER_RESTRAINT: 2,
    LATERAL_BRACE: 2,
    LONGITUDINAL_BRACE: 2,
}

#: Name / ObjectType fragments that identify a support and its kind, checked in
#: order so that the more specific phrase wins: "longitudinal sway brace"
#: must not be caught by the bare "brace" entry above it.
#:
#: These read an exporter's free text, which is evidence of intent and nothing
#: stronger. Everything derived from them lands in `declared`, never in
#: `measured`.
_NAME_SIGNALS: tuple[tuple[str, str], ...] = (
    ("longitudinal brace", LONGITUDINAL_BRACE),
    ("longitudinal sway", LONGITUDINAL_BRACE),
    ("long. brace", LONGITUDINAL_BRACE),
    ("lateral brace", LATERAL_BRACE),
    ("lateral sway", LATERAL_BRACE),
    ("transverse brace", LATERAL_BRACE),
    ("riser restraint", RISER_RESTRAINT),
    ("riser clamp", RISER_RESTRAINT),
    # A four-way brace restrains both directions; naming it lateral would
    # under-report it, so it stays generic and geometry decides.
    ("four-way brace", BRACE),
    ("4-way brace", BRACE),
    ("sway brace", BRACE),
    ("seismic brace", BRACE),
    ("brace", BRACE),
    ("clevis hanger", HANGER),
    ("trapeze", HANGER),
    ("hanger rod", HANGER),
    ("threaded rod", HANGER),
    ("all-thread", HANGER),
    ("hanger", HANGER),
    ("support rod", HANGER),
)

#: IFC PredefinedType values that identify a support without any name reading.
#: Keyed by (ifc_class, predefined_type), both upper-cased. Far more reliable
#: than a name, and so consulted first.
_PREDEFINED_SIGNALS: dict[tuple[str, str], str] = {
    # BRACE, not LATERAL_BRACE: the enumeration says a member braces something,
    # never in which direction. Refined by name or geometry, or left generic.
    ("IFCMEMBER", "BRACE"): BRACE,
    ("IFCMEMBERTYPE", "BRACE"): BRACE,
    ("IFCDISCRETEACCESSORY", "HANGER"): HANGER,
    ("IFCDISCRETEACCESSORYTYPE", "HANGER"): HANGER,
    ("IFCDISCRETEACCESSORY", "BRACKET"): HANGER,
    ("IFCELEMENTASSEMBLY", "BRACED_FRAME"): BRACE,
}

#: Property names that state the support kind outright, in whatever Pset an
#: exporter put them. Checked before names because a property is authored data
#: rather than a label, though still an assertion rather than a measurement.
_KIND_PROPERTY_NAMES = (
    "SupportType",
    "BraceType",
    "SeismicBraceType",
    "RestraintType",
    "HangerType",
)

#: IFC classes worth examining as a possible support. Anything else attached to
#: a pipe -- a fitting, a valve, another pipe -- is not one.
_SUPPORT_CLASSES = (
    "IfcDiscreteAccessory",
    "IfcMechanicalFastener",
    "IfcMember",
    "IfcElementAssembly",
    "IfcBuildingElementProxy",
    "IfcActuator",
)

#: Angle from the pipe axis, in degrees, within which a brace counts as running
#: ALONG the pipe (longitudinal) or ACROSS it (lateral). The dead band between
#: the two is deliberate: a brace at 45 degrees to the run is genuinely
#: ambiguous, and calling it either would be a guess presented as a
#: measurement. It resolves to UNKNOWN instead.
_LONGITUDINAL_MAX_DEG = 30.0
_LATERAL_MIN_DEG = 60.0


# ── Pure vector math ──────────────────────────────────────────────────────────
# Plain tuples and the standard library only: no numpy import, so these stay
# usable and testable wherever they are called from.


def _sub(a: Vec3, b: Vec3) -> Vec3:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _dot(a: Vec3, b: Vec3) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _norm(v: Vec3) -> float:
    return math.sqrt(_dot(v, v))


def _unit(v: Vec3) -> Vec3 | None:
    """Return ``v`` scaled to unit length, or None if it has no direction."""
    length = _norm(v)
    if length < 1e-9:
        return None
    return (v[0] / length, v[1] / length, v[2] / length)


def axis_from_points(start: Vec3, end: Vec3) -> Vec3 | None:
    """Return the unit direction from ``start`` to ``end``, or None if identical."""
    return _unit(_sub(end, start))


def project_station_mm(point: Vec3, origin: Vec3, axis_unit: Vec3) -> float:
    """Return how far along the axis a point lies, in mm, signed from ``origin``.

    This is the whole idea behind spacing: a brace is not measured to another
    brace through space, it is measured along the run. Projecting every support
    onto the run axis turns a 3-D scatter into positions on a line, which can
    then simply be sorted and differenced. A brace offset sideways from the
    pipe -- as every brace is, since it reaches away to the structure --
    projects to the station where it meets the run, not to its own centre.
    """
    return _dot(_sub(point, origin), axis_unit)


def perpendicular_distance_mm(point: Vec3, origin: Vec3, axis_unit: Vec3) -> float:
    """Return the point's distance from the axis line, in mm.

    Used to decide whether a support is plausibly attached to this run rather
    than to a parallel one on the same rack.
    """
    offset = _sub(point, origin)
    along = _dot(offset, axis_unit)
    projected = (
        offset[0] - along * axis_unit[0],
        offset[1] - along * axis_unit[1],
        offset[2] - along * axis_unit[2],
    )
    return _norm(projected)


def angle_between_deg(a: Vec3, b: Vec3) -> float | None:
    """Return the unsigned angle between two directions, 0-90 degrees.

    Folded onto 0-90 on purpose: a brace's axis has no meaningful sign -- one
    drawn from the structure down to the pipe and one drawn from the pipe up to
    the structure describe the same brace, and their raw angles to the run
    would be supplementary. Only the alignment matters.
    """
    ua, ub = _unit(a), _unit(b)
    if ua is None or ub is None:
        return None
    cos = max(-1.0, min(1.0, abs(_dot(ua, ub))))
    return math.degrees(math.acos(cos))


def classify_orientation(brace_axis: Vec3, pipe_axis: Vec3) -> str:
    """Return LATERAL_BRACE, LONGITUDINAL_BRACE or UNKNOWN from geometry alone.

    A brace running along the pipe resists longitudinal movement; one running
    across it resists lateral movement. Between the two bands the answer is
    UNKNOWN rather than a coin toss -- see :data:`_LONGITUDINAL_MAX_DEG`.
    """
    angle = angle_between_deg(brace_axis, pipe_axis)
    if angle is None:
        return UNKNOWN
    if angle <= _LONGITUDINAL_MAX_DEG:
        return LONGITUDINAL_BRACE
    if angle >= _LATERAL_MIN_DEG:
        return LATERAL_BRACE
    return UNKNOWN


def brace_spacing(
    stations_mm: list[float],
    run_start_mm: float | None = None,
    run_end_mm: float | None = None,
) -> dict:
    """Reduce positions along a run to the spacings a rule needs.

    ``stations_mm`` are projected positions from :func:`project_station_mm`, in
    any order. ``run_start_mm`` / ``run_end_mm`` are the run's own extent on the
    same axis, which the caller has and this function does not.

    Returns a dict carrying, all in mm:

        ``stations_mm``      the input, sorted
        ``gaps_mm``          distance between each consecutive pair
        ``max_gap_mm``       the governing spacing, or None
        ``count``            how many supports were positioned
        ``start_offset_mm``  run start to the first support, or None
        ``end_offset_mm``    last support to the run end, or None
        ``span_mm``          first support to last, or None

    Three cases the caller must not conflate, and which is why this returns a
    dict rather than a single number:

    * **No supports.** ``max_gap_mm`` is None and both offsets are None. An
      unbraced run is a serious finding, but it is a finding about absence, not
      a spacing of zero.
    * **One support.** Still no gap -- ``gaps_mm`` is empty and ``max_gap_mm``
      is None -- yet the end offsets are real and may themselves exceed a
      limit. A rule that looked only at ``max_gap_mm`` would pass a 30 m run
      held by a single brace.
    * **Two or more.** ``max_gap_mm`` governs, and the end offsets still
      matter: NFPA 13 limits the distance from the end of a run to its first
      brace, not only the distance between braces.

    Duplicate stations are kept rather than collapsed. Two braces modelled at
    the same position produce a genuine 0 mm gap, which is a modelling error
    worth surfacing, not something to quietly deduplicate.
    """
    ordered = sorted(float(s) for s in stations_mm or [])
    gaps = [round(b - a, 4) for a, b in zip(ordered, ordered[1:])]

    result: dict = {
        "stations_mm": ordered,
        "gaps_mm": gaps,
        "max_gap_mm": max(gaps) if gaps else None,
        "count": len(ordered),
        "start_offset_mm": None,
        "end_offset_mm": None,
        "span_mm": round(ordered[-1] - ordered[0], 4) if len(ordered) >= 2 else None,
    }

    if ordered and run_start_mm is not None:
        result["start_offset_mm"] = round(ordered[0] - float(run_start_mm), 4)
    if ordered and run_end_mm is not None:
        result["end_offset_mm"] = round(float(run_end_mm) - ordered[-1], 4)
    return result


# ── IFC reading: axis ─────────────────────────────────────────────────────────

try:
    import ifcopenshell.util.element
    import ifcopenshell.util.placement
    import numpy as _np

    _IFC_UTIL_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised only without ifcopenshell
    _IFC_UTIL_AVAILABLE = False


def _extrusion_axis(product, unit_scale_mm: float = 1.0) -> tuple[Vec3, float] | None:
    """Return (world direction, depth in mm) of a product drawn as an extrusion.

    Exact, and cheap: it composes the object placement with the solid's own
    position instead of tessellating. That matters most for braces, which run
    diagonally -- a diagonal member's bounding box says nothing useful about
    its direction, so the fallback in :func:`element_axis` cannot replace this.
    """
    if not _IFC_UTIL_AVAILABLE:
        return None
    representation = getattr(product, "Representation", None)
    if representation is None:
        return None

    solid = None

    def _walk(items, depth: int = 0):
        nonlocal solid
        if depth > 4 or solid is not None:
            return
        for item in items or []:
            try:
                if item.is_a("IfcMappedItem"):
                    source = getattr(item, "MappingSource", None)
                    mapped = getattr(source, "MappedRepresentation", None)
                    if mapped is not None:
                        _walk(getattr(mapped, "Items", None), depth + 1)
                elif item.is_a("IfcBooleanResult"):
                    _walk([getattr(item, "FirstOperand", None)], depth + 1)
                elif item.is_a("IfcExtrudedAreaSolid"):
                    solid = item
                    return
            except Exception:
                continue

    try:
        for rep in getattr(representation, "Representations", None) or []:
            _walk(getattr(rep, "Items", None))
    except Exception as exc:
        logger.debug("Extrusion axis walk failed for %s: %s", product, exc)
        return None
    if solid is None:
        return None

    try:
        direction = getattr(solid, "ExtrudedDirection", None)
        ratios = list(getattr(direction, "DirectionRatios", None) or (0.0, 0.0, 1.0))
        local = _np.array([ratios[0], ratios[1], ratios[2], 0.0], dtype=float)

        # The extrusion direction is expressed in the solid's own coordinate
        # system, which is itself placed inside the product, which is placed in
        # the world. Both hops are needed or a rotated brace reads as vertical.
        solid_placement = _np.eye(4)
        if getattr(solid, "Position", None) is not None:
            solid_placement = ifcopenshell.util.placement.get_axis2placement(solid.Position)
        world_placement = _np.eye(4)
        if getattr(product, "ObjectPlacement", None) is not None:
            world_placement = ifcopenshell.util.placement.get_local_placement(
                product.ObjectPlacement
            )

        world_vector = world_placement @ solid_placement @ local
        axis = _unit((float(world_vector[0]), float(world_vector[1]), float(world_vector[2])))
        if axis is None:
            return None
        depth = float(getattr(solid, "Depth", 0.0) or 0.0) * unit_scale_mm
        if depth <= 0:
            return None
        return axis, depth
    except Exception as exc:
        logger.debug("Extrusion axis math failed for %s: %s", product, exc)
        return None


def _bbox_axis(bbox: dict) -> tuple[Vec3, Vec3, float] | None:
    """Return (start, end, length) along a bounding box's longest dimension.

    A crude stand-in used only when the extrusion route fails. It is correct
    for an axis-aligned member and WRONG for a diagonal one, whose box is
    merely the volume it occupies -- so callers are told which method produced
    the answer and can refuse the approximate one.
    """
    try:
        spans = {
            "x": (float(bbox["max_x"]) - float(bbox["min_x"])),
            "y": (float(bbox["max_y"]) - float(bbox["min_y"])),
            "z": (float(bbox["max_z"]) - float(bbox["min_z"])),
        }
    except (KeyError, TypeError, ValueError):
        return None
    longest = max(spans, key=spans.get)
    if spans[longest] <= 0:
        return None
    mid = {
        "x": (float(bbox["min_x"]) + float(bbox["max_x"])) / 2.0,
        "y": (float(bbox["min_y"]) + float(bbox["max_y"])) / 2.0,
        "z": (float(bbox["min_z"]) + float(bbox["max_z"])) / 2.0,
    }
    start = [mid["x"], mid["y"], mid["z"]]
    end = [mid["x"], mid["y"], mid["z"]]
    index = {"x": 0, "y": 1, "z": 2}[longest]
    start[index] = float(bbox[f"min_{longest}"])
    end[index] = float(bbox[f"max_{longest}"])
    return (tuple(start), tuple(end), spans[longest])


def element_axis(element, geometry_extractor=None, unit_scale_mm: float = 1.0) -> dict | None:
    """Return the centreline of a slender element, in world mm.

    ``{start, end, axis, length_mm, method}`` or None when neither route
    resolves. ``method`` is ``"extrusion"`` (exact) or ``"bounding_box"``
    (axis-aligned only) so a caller measuring a diagonal brace can reject the
    approximation rather than quietly trusting it.

    The extrusion route gives a direction and a length but no position, so the
    centroid supplies the midpoint; the box route gives endpoints directly.
    """
    centroid = None
    if geometry_extractor is not None:
        try:
            centroid = geometry_extractor.get_centroid_or_none(element)
        except Exception:
            centroid = None

    extrusion = _extrusion_axis(element, unit_scale_mm)
    if extrusion is not None and centroid is not None:
        axis, length = extrusion
        half = length / 2.0
        start = (
            centroid[0] - axis[0] * half,
            centroid[1] - axis[1] * half,
            centroid[2] - axis[2] * half,
        )
        end = (
            centroid[0] + axis[0] * half,
            centroid[1] + axis[1] * half,
            centroid[2] + axis[2] * half,
        )
        return {
            "start": start,
            "end": end,
            "axis": axis,
            "length_mm": round(length, 4),
            "method": "extrusion",
        }

    if geometry_extractor is None:
        return None
    try:
        bbox = geometry_extractor.get_bounding_box(element)
    except Exception:
        bbox = None
    if not bbox:
        return None
    fallback = _bbox_axis(bbox)
    if fallback is None:
        return None
    start, end, length = fallback
    axis = axis_from_points(start, end)
    if axis is None:
        return None
    return {
        "start": start,
        "end": end,
        "axis": axis,
        "length_mm": round(length, 4),
        "method": "bounding_box",
    }


# ── IFC reading: classification ───────────────────────────────────────────────


def _text_signals(element) -> tuple[str, str] | tuple[None, None]:
    """Return (kind, matched phrase) from an element's Name / ObjectType."""
    haystack = " ".join(
        str(getattr(element, attr, "") or "")
        for attr in ("Name", "ObjectType", "Description", "Tag")
    ).lower()
    if not haystack.strip():
        return (None, None)
    for phrase, kind in _NAME_SIGNALS:
        if phrase in haystack:
            return (kind, phrase)
    return (None, None)


def _property_signal(element) -> tuple[str, str] | tuple[None, None]:
    """Return (kind, "Pset.Property=value") from an authored support-type property."""
    if not _IFC_UTIL_AVAILABLE:
        return (None, None)
    try:
        psets = ifcopenshell.util.element.get_psets(element, psets_only=False)
    except Exception:
        return (None, None)
    for pset_name, props in (psets or {}).items():
        if not isinstance(props, dict):
            continue
        for prop_name in _KIND_PROPERTY_NAMES:
            raw = props.get(prop_name)
            if raw in (None, ""):
                continue
            text = str(raw).lower()
            for phrase, kind in _NAME_SIGNALS:
                if phrase in text:
                    return (kind, f"{pset_name}.{prop_name}={raw}")
            # An authored value that names no kind still proves the element is
            # a support, which is worth more than nothing even when the kind
            # stays unknown.
            return (UNKNOWN, f"{pset_name}.{prop_name}={raw}")
    return (None, None)


def _predefined_signal(element) -> tuple[str, str] | tuple[None, None]:
    """Return (kind, "Class.PREDEFINED_TYPE") from the IFC type enumeration."""
    try:
        ifc_class = element.is_a().upper()
        predefined = str(getattr(element, "PredefinedType", "") or "").upper()
    except Exception:
        return (None, None)
    if not predefined:
        return (None, None)
    kind = _PREDEFINED_SIGNALS.get((ifc_class, predefined))
    if kind:
        return (kind, f"{element.is_a()}.{predefined}")
    return (None, None)


def is_support_class(element) -> bool:
    """Return True when the element's IFC class could carry a pipe."""
    try:
        return any(element.is_a(cls) for cls in _SUPPORT_CLASSES)
    except Exception:
        return False


def classify_support(
    element, pipe_axis: Vec3 | None = None, geometry_extractor=None, unit_scale_mm: float = 1.0
) -> dict:
    """Classify one element as a kind of seismic support.

    Returns ``{kind, declared, measured, evidence, is_support}``.

    ``declared`` is what the model SAYS -- an authored property first, then the
    PredefinedType enumeration, then the name. ``measured`` is what the
    geometry SHOWS, available only for braces and only when ``pipe_axis`` is
    supplied: a member running along the pipe braces it longitudinally, one
    running across it braces it laterally.

    ``kind`` prefers ``measured`` over ``declared`` where the two disagree,
    because a brace's orientation is a fact about the model rather than a claim
    about it -- but ``evidence`` records both, so the disagreement is
    inspectable and a rule that would rather trust the label still can. A
    hanger is never reclassified by geometry: a vertical rod has no meaningful
    angle to a horizontal run, and "lateral" would be nonsense.
    """
    evidence: list[str] = []
    declared = None
    found_any = False

    # Every signal is read, not just the first: the PredefinedType may prove
    # the element is a brace while only the name says which way it faces.
    for signal in (_property_signal, _predefined_signal, _text_signals):
        kind, detail = signal(element)
        if kind is None:
            continue
        found_any = True
        evidence.append(f"{signal.__name__.strip('_')}: {detail}")
        if _SPECIFICITY.get(kind, 0) > _SPECIFICITY.get(declared or UNKNOWN, 0):
            declared = kind

    measured = None
    if declared in _BRACE_KINDS and pipe_axis is not None:
        axis_info = element_axis(element, geometry_extractor, unit_scale_mm)
        if axis_info is not None:
            measured = classify_orientation(axis_info["axis"], pipe_axis)
            angle = angle_between_deg(axis_info["axis"], pipe_axis)
            evidence.append(
                f"geometry: {axis_info['method']} axis at "
                f"{angle:.1f} deg to the run" if angle is not None
                else f"geometry: {axis_info['method']} axis, angle unresolved"
            )

    kind = measured if measured not in (None, UNKNOWN) else declared
    return {
        "kind": kind or UNKNOWN,
        "declared": declared or UNKNOWN,
        "measured": measured or UNKNOWN,
        "evidence": evidence,
        # Class alone never proves a support -- IfcBuildingElementProxy is a
        # catch-all and IfcMember is usually structure. Some positive signal
        # is required.
        "is_support": found_any and is_support_class(element),
    }


# ── IFC reading: attachment ───────────────────────────────────────────────────

#: How far a support's centroid may sit from the pipe's centreline and still be
#: taken as holding THIS pipe. A brace reaches away to the structure, so the
#: distance is never zero; but on a crowded rack the next pipe is often only a
#: few hundred millimetres away, and a proximity match that is too generous
#: credits one pipe with its neighbour's bracing. Only the declared
#: relationships are trusted by default -- see `include_proximity`.
DEFAULT_MAX_OFFSET_MM = 1500.0


def build_support_index(ifc_file) -> list:
    """Return every element in the model whose class could be a support.

    Scanned once and reused, for the same reason the interference index in
    ``ifc_penetrations`` is: the proximity route has no relationship to follow
    and would otherwise re-scan the file per pipe.
    """
    candidates: list = []
    if ifc_file is None:
        return candidates
    for cls in _SUPPORT_CLASSES:
        try:
            candidates.extend(ifc_file.by_type(cls))
        except Exception:
            continue
    return candidates


def _connected_elements(element) -> list:
    """Return elements joined to this one by IfcRelConnectsElements.

    Read through the ``ConnectedTo`` / ``ConnectedFrom`` inverse attributes, so
    no file scan is needed. Both directions are read because exporters put the
    pipe on either side.
    """
    found: list = []
    for attr, other_attr in (
        ("ConnectedTo", "RelatedElement"),
        ("ConnectedFrom", "RelatingElement"),
    ):
        try:
            for rel in getattr(element, attr, None) or []:
                other = getattr(rel, other_attr, None)
                if other is not None and other != element and other not in found:
                    found.append(other)
        except Exception as exc:
            logger.debug("Connection read failed for %s: %s", element, exc)
    return found


def _assembly_siblings(element) -> list:
    """Return elements sharing an IfcElementAssembly with this one.

    A pipe and the hangers carrying it are frequently exported as one assembly
    rather than as connected elements -- the two routes catch different
    exporters, so both are read.
    """
    siblings: list = []
    try:
        for rel in getattr(element, "Decomposes", None) or []:
            parent = getattr(rel, "RelatingObject", None)
            if parent is None:
                continue
            for child_rel in getattr(parent, "IsDecomposedBy", None) or []:
                for child in getattr(child_rel, "RelatedObjects", None) or []:
                    if child != element and child not in siblings:
                        siblings.append(child)
    except Exception as exc:
        logger.debug("Assembly sibling read failed for %s: %s", element, exc)
    return siblings


def find_supports(
    pipe,
    geometry_extractor=None,
    unit_scale_mm: float = 1.0,
    support_index: list | None = None,
    include_proximity: bool = False,
    max_offset_mm: float = DEFAULT_MAX_OFFSET_MM,
) -> list[dict]:
    """Return the supports holding ``pipe``, positioned along its run.

    Each entry is ``{element, guid, name, kind, declared, measured, evidence,
    station_mm, offset_mm, route}``, sorted by ``station_mm`` -- position along
    the pipe, from its start -- which is the order a spacing check needs.

    Three routes, in descending order of trust, with ``route`` recording which
    one found each support:

        ``connection``  IfcRelConnectsElements, an explicit statement
        ``assembly``    a shared IfcElementAssembly, also explicit
        ``proximity``   near the pipe's centreline and of a support class

    Proximity is OFF by default. It is a guess -- on a crowded rack the pipe
    above is within a metre too, and crediting one pipe with its neighbour's
    bracing would turn a spacing violation into a pass. Callers that know their
    models lack the relationships can enable it and read ``route`` to see how
    much of the answer rests on it.

    Supports whose station cannot be computed are still returned, with
    ``station_mm`` None, rather than dropped. A brace that exists but cannot be
    located must not silently reduce the apparent spacing between the ones that
    can.
    """
    run = element_axis(pipe, geometry_extractor, unit_scale_mm)
    if run is None:
        logger.debug("No axis for %s; supports cannot be positioned", pipe)

    seen_ids: set[int] = set()
    supports: list[dict] = []

    def _consider(candidate, route: str) -> None:
        try:
            candidate_id = candidate.id()
        except Exception:
            return
        if candidate_id in seen_ids:
            return
        if not is_support_class(candidate):
            return
        classification = classify_support(
            candidate,
            pipe_axis=run["axis"] if run else None,
            geometry_extractor=geometry_extractor,
            unit_scale_mm=unit_scale_mm,
        )
        if not classification["is_support"]:
            return

        station = offset = None
        if run is not None and geometry_extractor is not None:
            try:
                centre = geometry_extractor.get_centroid_or_none(candidate)
            except Exception:
                centre = None
            if centre is not None:
                station = round(project_station_mm(centre, run["start"], run["axis"]), 4)
                offset = round(
                    perpendicular_distance_mm(centre, run["start"], run["axis"]), 4
                )
                if route == "proximity" and offset > max_offset_mm:
                    return

        seen_ids.add(candidate_id)
        supports.append(
            {
                "element": candidate,
                "guid": getattr(candidate, "GlobalId", None),
                "name": getattr(candidate, "Name", None),
                "ifc_class": candidate.is_a(),
                "kind": classification["kind"],
                "declared": classification["declared"],
                "measured": classification["measured"],
                "evidence": classification["evidence"],
                "station_mm": station,
                "offset_mm": offset,
                "route": route,
            }
        )

    for candidate in _connected_elements(pipe):
        _consider(candidate, "connection")
    for candidate in _assembly_siblings(pipe):
        _consider(candidate, "assembly")
    if include_proximity:
        for candidate in support_index or []:
            _consider(candidate, "proximity")

    # Unpositioned supports sort last rather than at station 0, which would
    # fabricate a gap at the start of the run.
    supports.sort(key=lambda s: (s["station_mm"] is None, s["station_mm"] or 0.0))
    return supports


# ── IFC reading: rod length ───────────────────────────────────────────────────

#: Degrees from vertical within which a rod counts as hanging plumb. A rod well
#: off vertical is either not a hanger or is modelled wrongly; either way its
#: length should not be reported as a hanger-rod length without the caller
#: knowing.
_PLUMB_TOLERANCE_DEG = 15.0

_VERTICAL: Vec3 = (0.0, 0.0, 1.0)


def rod_length_mm(
    element, geometry_extractor=None, unit_scale_mm: float = 1.0
) -> tuple[float | None, dict]:
    """Return the free length of a suspension rod in mm, with its provenance.

    Returns ``(length_mm, detail)``. ``length_mm`` is None whenever the
    geometry will not resolve -- never 0.0, which a slenderness rule would read
    as a perfect result rather than as no result.

    ``detail`` carries:

        ``method``                 "extrusion" (exact) or "bounding_box"
        ``angle_from_vertical_deg``how far off plumb the rod hangs
        ``is_plumb``               within :data:`_PLUMB_TOLERANCE_DEG`
        ``intermediate_restraints``always None -- see below
        ``unbraced_equals_total``  always None, for the same reason

    UNBRACED LENGTH IS NOT YET DISTINGUISHABLE FROM TOTAL LENGTH. The unbraced
    length of a rod is the free span between restraints; where a rod is
    stiffened partway down, it is shorter than the rod. Nothing in the model
    reliably marks such a stiffener, and this function does not guess: it
    returns the rod's total length and reports the two "unknown" fields above
    so a caller cannot mistake one quantity for the other. For the common case
    of an unstiffened rod the two are equal, but that equality is an assumption
    the RULE must make and record, not one this function will make silently.
    """
    detail: dict = {
        "method": None,
        "angle_from_vertical_deg": None,
        "is_plumb": None,
        "intermediate_restraints": None,
        "unbraced_equals_total": None,
    }

    axis_info = element_axis(element, geometry_extractor, unit_scale_mm)
    if axis_info is None:
        detail["reason"] = "rod axis not resolvable from profile or geometry"
        return None, detail

    detail["method"] = axis_info["method"]
    angle = angle_between_deg(axis_info["axis"], _VERTICAL)
    if angle is not None:
        # angle_between_deg folds onto 0-90, which is what is wanted: a rod
        # drawn top-down and one drawn bottom-up are equally plumb.
        detail["angle_from_vertical_deg"] = round(angle, 4)
        detail["is_plumb"] = angle <= _PLUMB_TOLERANCE_DEG

    return axis_info["length_mm"], detail


def support_context(
    pipe,
    geometry_extractor=None,
    unit_scale_mm: float = 1.0,
    support_index: list | None = None,
    include_proximity: bool = False,
) -> dict:
    """Gather everything the bracing rules will need about one pipe.

    The shape a future ``extract_for_compliance`` hook would attach to an
    element record, assembled here so the traversal is written and tested once.
    Deliberately NOT called from the extraction loop yet.

    Spacing is reported per brace kind as well as overall, because the two
    rules differ: NFPA 13 allows lateral braces at one spacing and longitudinal
    braces at roughly double it, so mixing them into one series would compare
    each against the wrong limit.
    """
    run = element_axis(pipe, geometry_extractor, unit_scale_mm)
    supports = find_supports(
        pipe,
        geometry_extractor=geometry_extractor,
        unit_scale_mm=unit_scale_mm,
        support_index=support_index,
        include_proximity=include_proximity,
    )

    run_start = run_end = None
    if run is not None:
        run_start = 0.0
        run_end = run["length_mm"]

    def _spacing_for(kinds: tuple[str, ...]) -> dict:
        stations = [
            s["station_mm"]
            for s in supports
            if s["kind"] in kinds and s["station_mm"] is not None
        ]
        return brace_spacing(stations, run_start, run_end)

    hangers = [s for s in supports if s["kind"] == HANGER]
    rod_lengths = []
    for hanger in hangers:
        length, rod_detail = rod_length_mm(
            hanger["element"], geometry_extractor, unit_scale_mm
        )
        rod_lengths.append(
            {"guid": hanger["guid"], "length_mm": length, **rod_detail}
        )

    return {
        "run_axis_method": run["method"] if run else None,
        "run_length_mm": run["length_mm"] if run else None,
        "support_count": len(supports),
        "supports": [
            {k: v for k, v in s.items() if k != "element"} for s in supports
        ],
        "lateral_spacing": _spacing_for((LATERAL_BRACE,)),
        "longitudinal_spacing": _spacing_for((LONGITUDINAL_BRACE,)),
        "hanger_spacing": _spacing_for((HANGER,)),
        # Every support merged into one series, for a rule that limits the
        # distance between supports of any kind. Never a substitute for the
        # per-kind series above: dense hangers close the gaps in a merged
        # series and would hide a run with no braces at all.
        "support_spacing": _spacing_for(
            (HANGER, BRACE, LATERAL_BRACE, LONGITUDINAL_BRACE, RISER_RESTRAINT)
        ),
        "rod_lengths": rod_lengths,
        # Tri-state. False means supports were found and none is a hanger;
        # None means none were found at all, which is not evidence that the
        # run is unsupported -- an exporter that writes no relationships
        # produces the same emptiness as a genuinely unsupported pipe.
        "is_suspended": (bool(hangers) if supports else None),
        # Positioned nowhere on the run: counted so a rule can see that its
        # spacing series is incomplete rather than trusting a gap computed
        # across a brace it could not locate.
        "unpositioned_support_count": sum(
            1 for s in supports if s["station_mm"] is None
        ),
    }
