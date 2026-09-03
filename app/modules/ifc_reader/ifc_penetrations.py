"""Penetration resolution: the host a pipe passes through, and the gap around it.

A penetration rule such as BIMGUARD-PC-001 (NFPA 13 Sec. 18.5 annular clearance)
asks two questions the rest of Module 2 cannot answer, because both are about a
*pair* of elements rather than one:

    "What does this pipe pass through?"   -> :func:`resolve_hosts`
    "How much gap is there around it?"    -> :func:`annular_clearance_mm`

Both are answered from the model alone. Nothing here consults the rule library,
so the same data serves any rule that needs a host or a clearance.

HOW A HOST IS FOUND

IFC offers three independent ways to say "this pipe passes through that wall",
and exporters disagree about which to write, so all three are read and their
results merged:

    1. ``IfcRelVoidsElement`` + ``IfcRelFillsElement`` -- the canonical chain.
       The wall is voided by an opening; the opening is filled by the pipe.
       This is the only one of the three that also yields the opening, and so
       the only one that can produce a clearance.
    2. ``IfcRelInterferesElements`` -- a declared clash between pipe and wall.
       Carries no opening, so it establishes the host but not the gap.
    3. Containment in the same opening via ``IfcRelFillsElement`` alone, for
       exporters that write the fill without voiding anything.

MISSING IS NOT FALSE

Every function here returns ``None`` (or an empty list) when the model does not
say, and never a default. A pipe with no resolvable host must reach the
comparator as *unknown*, so its scope and waiver predicates land UNDETERMINED
and neither suppress a check nor waive a finding. Returning ``False`` for
"not breakaway" or ``0.0`` for "no clearance" would each silently manufacture a
verdict the model never supported.
"""

from __future__ import annotations

from app.logging_config import get_logger

logger = get_logger(__name__)


#: Material name fragments that mark construction as breakaway / frangible:
#: it fails locally before it can restrain a pipe, which is the condition
#: NFPA 13's exemption turns on. Matched case-insensitively as substrings, so
#: "Gypsum Board", "5/8in Type X Gypsum" and "GYPSUM-WALLBOARD" all hit.
#:
#: Deliberately narrow. A material absent from this list yields False (it is
#: rigid), not None -- the list is the definition of the class, so a known
#: material that is not in it is a known negative. Only an element with no
#: resolvable material at all is undetermined.
BREAKAWAY_MATERIAL_TOKENS = (
    "gypsum",
    "plasterboard",
    "drywall",
    "wallboard",
    "sheetrock",
    "plaster board",
)

#: IFC classes that count as construction a pipe can penetrate. Used to filter
#: interference relationships, which are not restricted to building elements
#: and will happily report a clash with another pipe.
_HOST_CLASSES = (
    "IfcWall",
    "IfcSlab",
    "IfcRoof",
    "IfcFooting",
    "IfcPlate",
    "IfcBeam",
    "IfcColumn",
    "IfcCovering",
    "IfcMember",
)


def _is_host_class(entity) -> bool:
    """Return True when the entity is construction a pipe could pass through."""
    try:
        return any(entity.is_a(cls) for cls in _HOST_CLASSES)
    except Exception:
        return False


def resolve_openings(element) -> list:
    """Return the ``IfcOpeningElement`` entities this element fills.

    An element fills an opening through ``IfcRelFillsElement``. The inverse
    attribute ``FillsVoids`` is used where the schema provides it, since it is
    an indexed lookup; otherwise the relationship is unavailable and the caller
    falls back to interference, which yields a host but no opening.
    """
    openings = []
    try:
        for rel in getattr(element, "FillsVoids", None) or []:
            opening = getattr(rel, "RelatingOpeningElement", None)
            if opening is not None and opening not in openings:
                openings.append(opening)
    except Exception as exc:
        logger.debug("Opening resolution failed for %s: %s", element, exc)
    return openings


def _host_of_opening(opening):
    """Return the element an opening is cut from, via ``IfcRelVoidsElement``."""
    try:
        for rel in getattr(opening, "VoidsElements", None) or []:
            host = getattr(rel, "RelatingBuildingElement", None)
            if host is not None:
                return host
    except Exception as exc:
        logger.debug("Void resolution failed for %s: %s", opening, exc)
    return None


def build_interference_index(ifc_file) -> dict[int, list]:
    """Index ``IfcRelInterferesElements`` once, as element id -> host elements.

    ``IfcRelInterferesElements`` has no inverse attribute to follow, so the
    only way to answer "what interferes with this pipe?" is to scan every such
    relationship in the file. Scanning once per run rather than once per
    (rule, element) pair is the difference between a constant and a product:
    the same pipe is re-examined by every rule targeting its class.

    The relationship is symmetric in practice -- exporters write the pipe on
    either side -- so both directions are indexed and the *other* participant
    recorded, filtered to construction classes.
    """
    index: dict[int, list] = {}
    if ifc_file is None:
        return index
    try:
        relationships = ifc_file.by_type("IfcRelInterferesElements")
    except Exception as exc:
        logger.debug("Interference index unavailable: %s", exc)
        return index

    for rel in relationships:
        try:
            relating = getattr(rel, "RelatingElement", None)
            related = getattr(rel, "RelatedElement", None)
            if relating is None or related is None:
                continue
            for subject, other in ((relating, related), (related, relating)):
                if not _is_host_class(other):
                    continue
                bucket = index.setdefault(subject.id(), [])
                if other not in bucket:
                    bucket.append(other)
        except Exception:
            continue
    return index


def resolve_hosts(element, interference_index: dict[int, list] | None = None) -> list:
    """Return every element this one passes through, best evidence first.

    Openings come first because they are the only route that also yields a
    measurable gap; interference-only hosts follow. Order matters to callers
    that take the first host, not to the predicates, which test all of them.

    ``interference_index`` comes from :func:`build_interference_index`. Without
    it only the opening route is read -- a host may go unfound, which lands the
    predicate UNDETERMINED rather than wrong.
    """
    hosts = []
    for opening in resolve_openings(element):
        host = _host_of_opening(opening)
        if host is not None and host not in hosts:
            hosts.append(host)
    try:
        for host in (interference_index or {}).get(element.id(), []):
            if host not in hosts:
                hosts.append(host)
    except Exception as exc:
        logger.debug("Interference lookup failed for %s: %s", element, exc)
    return hosts


def is_breakaway(material_names: list[str] | None) -> bool | None:
    """Whether construction of these materials is breakaway / frangible.

    ``None`` when the list is empty -- the model does not say what this is
    built from, so the question cannot be answered. Any element whose
    materials are known but match nothing in
    :data:`BREAKAWAY_MATERIAL_TOKENS` is a definite ``False``.

    EVERY layer must be breakaway, not merely one. A layered wall is only as
    frangible as its most rigid layer: gypsum board over a concrete core is
    faced in a breakaway material and is not itself breakaway, and the pipe is
    restrained by the core regardless of what is in front of it. Requiring all
    layers also errs toward reporting -- a wall this cannot confidently call
    frangible leaves the clearance finding standing.

    This is a domain judgement, not something the standard spells out, and it
    is the reason a gypsum-on-steel-stud partition whose layer set also names
    the studs reads as False here.
    """
    names = [str(n).strip().casefold() for n in (material_names or []) if str(n).strip()]
    if not names:
        return None
    return all(
        any(token in name for token in BREAKAWAY_MATERIAL_TOKENS) for name in names
    )


# ── Annular clearance ─────────────────────────────────────────────────────────


def _swept_circle_radius(product, unit_scale_mm: float) -> float | None:
    """Radius in mm of a product drawn as a circular extrusion, else None.

    Reads the profile directly rather than measuring the tessellation, because
    a profile radius is exact while a triangulated cylinder is a polygon that
    understates its own radius by up to a few percent depending on facet count.
    """
    representation = getattr(product, "Representation", None)
    if representation is None:
        return None
    radii: list[float] = []

    def _walk(items, depth: int = 0) -> None:
        # Depth-capped: mapped representations can in principle nest, and a
        # malformed file could make that cyclic.
        if depth > 4:
            return
        for item in items or []:
            try:
                if item.is_a("IfcMappedItem"):
                    source = getattr(item, "MappingSource", None)
                    mapped = getattr(source, "MappedRepresentation", None)
                    if mapped is not None:
                        _walk(getattr(mapped, "Items", None), depth + 1)
                    continue
                if item.is_a("IfcBooleanResult") or item.is_a("IfcBooleanClippingResult"):
                    _walk([getattr(item, "FirstOperand", None)], depth + 1)
                    continue
                if item.is_a("IfcSweptAreaSolid"):
                    profile = getattr(item, "SweptArea", None)
                    if profile is not None and profile.is_a("IfcCircleProfileDef"):
                        radius = getattr(profile, "Radius", None)
                        if radius:
                            radii.append(float(radius) * unit_scale_mm)
            except Exception:
                continue

    try:
        for rep in getattr(representation, "Representations", None) or []:
            _walk(getattr(rep, "Items", None))
    except Exception as exc:
        logger.debug("Profile radius read failed for %s: %s", product, exc)
        return None
    # Largest profile: a pipe drawn as concentric solids (bore plus wall) must
    # measure to its outside surface, which is what the clearance is from.
    return max(radii) if radii else None


def _bbox_cross_section_mm(bbox: dict, axis: str) -> tuple[float, float] | None:
    """Return the two bounding-box extents perpendicular to ``axis``, in mm."""
    if not bbox:
        return None
    try:
        spans = {
            "x": float(bbox["max_x"]) - float(bbox["min_x"]),
            "y": float(bbox["max_y"]) - float(bbox["min_y"]),
            "z": float(bbox["max_z"]) - float(bbox["min_z"]),
        }
    except (KeyError, TypeError, ValueError):
        return None
    others = [v for k, v in spans.items() if k != axis]
    return (min(others), max(others)) if len(others) == 2 else None


def _longest_axis(bbox: dict) -> str | None:
    """Return 'x', 'y' or 'z' -- the axis the element mostly runs along."""
    if not bbox:
        return None
    try:
        spans = {
            "x": float(bbox["max_x"]) - float(bbox["min_x"]),
            "y": float(bbox["max_y"]) - float(bbox["min_y"]),
            "z": float(bbox["max_z"]) - float(bbox["min_z"]),
        }
    except (KeyError, TypeError, ValueError):
        return None
    return max(spans, key=spans.get)


def _effective_radius_mm(
    product, geometry_extractor, unit_scale_mm: float, axis: str | None, largest: bool
) -> float | None:
    """Radius in mm of a product's cross-section, profile first then bounding box.

    ``largest`` picks which half-extent to use when the cross-section is not
    square: the pipe takes its largest (its widest point is what the gap is
    measured from) and the opening its smallest (the tightest point is what
    the pipe has to fit through). Both choices report the *worst* clearance,
    which is the one the standard cares about.
    """
    radius = _swept_circle_radius(product, unit_scale_mm)
    if radius is not None:
        return radius
    if geometry_extractor is None or axis is None:
        return None
    try:
        bbox = geometry_extractor.get_bounding_box(product)
    except Exception:
        return None
    cross = _bbox_cross_section_mm(bbox, axis)
    if cross is None:
        return None
    smallest_span, largest_span = cross
    return (largest_span if largest else smallest_span) / 2.0


def annular_clearance_mm(
    element, geometry_extractor=None, unit_scale_mm: float = 1.0
) -> tuple[float | None, dict]:
    """Return the radial gap in mm between this element and its opening.

    The measurement NFPA 13 Sec. 18.5 specifies is radial -- the gap from the
    pipe's outside surface to the edge of the hole, not the difference in
    diameters -- so a 50.8 mm pipe in a 63.5 mm hole clears 6.35 mm, not
    12.7 mm.

    Returns ``(clearance_mm, detail)``. ``clearance_mm`` is ``None`` whenever
    the model cannot answer: no opening, or geometry neither module can read.
    ``detail`` always records what was and was not resolved, so a rule that
    reports MISSING can say why.

    The tightest opening wins when an element fills several, since a pipe that
    passes through three walls is only as compliant as its worst penetration.
    """
    detail: dict = {"method": None, "openings_found": 0}

    openings = resolve_openings(element)
    detail["openings_found"] = len(openings)
    if not openings:
        detail["reason"] = "element fills no IfcOpeningElement"
        return None, detail

    axis = None
    if geometry_extractor is not None:
        try:
            axis = _longest_axis(geometry_extractor.get_bounding_box(element))
        except Exception:
            axis = None

    pipe_radius = _effective_radius_mm(
        element, geometry_extractor, unit_scale_mm, axis, largest=True
    )
    if pipe_radius is None:
        detail["reason"] = "element radius not resolvable from profile or geometry"
        return None, detail
    detail["element_radius_mm"] = round(pipe_radius, 4)

    best: float | None = None
    for opening in openings:
        opening_radius = _effective_radius_mm(
            opening, geometry_extractor, unit_scale_mm, axis, largest=False
        )
        if opening_radius is None:
            continue
        clearance = opening_radius - pipe_radius
        if best is None or clearance < best:
            best = clearance
            detail["opening_radius_mm"] = round(opening_radius, 4)
            detail["opening_name"] = getattr(opening, "Name", None)

    if best is None:
        detail["reason"] = "opening radius not resolvable from profile or geometry"
        return None, detail

    detail["method"] = "profile_radius_difference"
    return round(best, 4), detail


def penetration_context(
    element,
    geometry_extractor=None,
    unit_scale_mm: float = 1.0,
    interference_index: dict[int, list] | None = None,
    material_resolver=None,
) -> dict:
    """Return everything the penetration predicates need about one element.

    Gathered in one pass because the host and the gap come from the same
    traversal, and because the comparator wants plain data -- lists, a
    tri-state bool, a number -- rather than live IFC entities it would have to
    know how to walk.

    ``material_resolver`` is a callable taking an element and returning
    ``{"materials": [...]}``; Module 2 passes its own ``get_material_info`` so
    layer sets, constituent sets and profile sets resolve exactly as they do
    everywhere else rather than being re-implemented here.

    Every field is ``None`` or empty when the model does not say. Nothing is
    defaulted.
    """
    hosts = resolve_hosts(element, interference_index)

    host_classes: list[str] = []
    host_names: list[str] = []
    host_materials: list[str] = []
    for host in hosts:
        try:
            host_classes.append(host.is_a())
            name = getattr(host, "Name", None)
            if name:
                host_names.append(str(name))
            if material_resolver is not None:
                for material in (material_resolver(host) or {}).get("materials") or []:
                    if material and material not in host_materials:
                        host_materials.append(str(material))
        except Exception:
            continue

    clearance, clearance_detail = annular_clearance_mm(
        element, geometry_extractor=geometry_extractor, unit_scale_mm=unit_scale_mm
    )

    return {
        "host_classes": host_classes,
        "host_names": host_names,
        "host_materials": host_materials,
        # Tri-state: True, False, or None when no host material resolved. The
        # comparator maps None to UNDETERMINED, so an unknown host never waives.
        "host_is_breakaway": is_breakaway(host_materials) if hosts else None,
        "annular_clearance_mm": clearance,
        "annular_clearance_detail": clearance_detail,
    }
