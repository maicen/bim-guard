"""
Module 2 producer — IFC model to list[PipingElement].

Reads piping and distribution entities from an IFC model and emits the
canonical PipingElement contract defined in piping_schema.py, ready for the
Path B comparators (galvanic, crevice, MM-001, XM-001) in Module 4.

DESIGN NOTES

    Material vocabulary
        This module normalises to CANONICAL_MATERIALS ("SS316", "CarbonSteel",
        "GalvanisedSteel", ...). That is a DIFFERENT vocabulary from
        ifc_parser.normalise_material_name, which emits Path A keys
        ("SS_316_passive", "Carbon_steel_mild", "Galvanized_steel") for the
        ServiceElement pipeline. The two must not be interchanged: the Path B
        rule packs key off CANONICAL_MATERIALS case-sensitively.

    Media
        PipingElement has no `media` field by design. Media is derived from
        `system` (PipingSystem) by the consuming engine via SYSTEM_TO_MEDIA
        below, keeping system classification single-sourced.

    Nullability
        Follows the schema's NULLABILITY POLICY: fields the IFC does not carry
        are left None and the reason is appended to extraction_warnings rather
        than raising. Comparators emit data-quality issues for missing inputs.

    Adjacency
        joined_to is populated from spatial proximity, not from IFC port
        connectivity, because most real models leave IfcRelConnectsPorts
        unpopulated. See _build_adjacency for the tolerance semantics and
        its limitations.
"""

from __future__ import annotations

import math
from typing import Any, Optional

import ifcopenshell
import ifcopenshell.util.element
import ifcopenshell.util.placement

from app.modules.module2_ifc_read.piping_schema import (
    CANONICAL_MATERIALS,
    BoundingBox,
    Centerline,
    ElementSubtype,
    EnvironmentClass,
    JointType,
    PipingElement,
    PipingSystem,
    Point3D,
)

# Exact text appended to extraction_warnings when neither IFC ports nor
# centerline geometry could establish connectivity (Tier 3). XM-001 keys off
# this constant to decide which elements to skip, so it must not be reworded
# independently of that comparator.
CONNECTIVITY_INDETERMINABLE = "Connectivity indeterminable - XM-001 skipped for this element"

# Recorded in PipingElement.properties so downstream comparators and audits
# can tell which tier produced joined_to.
CONNECTIVITY_SOURCE_KEY = "_connectivity_source"

# ---------------------------------------------------------------------------
# Extraction scope
# ---------------------------------------------------------------------------
# IFC classes treated as piping/distribution elements. IFC4 and IFC2X3 names
# both appear because real models in the wild use either.

PIPING_IFC_CLASSES: tuple[str, ...] = (
    "IfcPipeSegment",
    "IfcPipeFitting",
    "IfcDuctSegment",
    "IfcDuctFitting",
    "IfcValve",
    "IfcPump",
    "IfcFilter",
    "IfcTank",
    "IfcHeatExchanger",
    "IfcAirTerminal",
    "IfcFlowSegment",
    "IfcFlowFitting",
    "IfcFlowController",
    "IfcFlowMovingDevice",
    "IfcFlowTerminal",
    "IfcFlowStorageDevice",
    "IfcFlowTreatmentDevice",
    "IfcDistributionElement",
)


# ---------------------------------------------------------------------------
# Material normalisation
# ---------------------------------------------------------------------------
# Ordered longest/most-specific first: "super duplex" must beat "duplex", and
# "stainless 316" must beat a bare "steel". Each entry is
# (substrings_that_must_all_appear, canonical_key).

_MATERIAL_RULES: tuple[tuple[tuple[str, ...], str], ...] = (
    # Stainless — grade numbers and EN material numbers
    (("2507",), "SuperDuplex2507"),
    (("super", "duplex"), "SuperDuplex2507"),
    (("2205",), "Duplex2205"),
    (("duplex",), "Duplex2205"),
    (("316ti",), "SS316Ti"),
    (("1.4571",), "SS316Ti"),
    (("316l",), "SS316L"),
    (("1.4404",), "SS316L"),
    (("316",), "SS316"),
    (("1.4401",), "SS316"),
    (("304l",), "SS304L"),
    (("1.4307",), "SS304L"),
    (("304",), "SS304"),
    (("1.4301",), "SS304"),
    # Copper alloys — check alloy families before bare "copper"
    (("cuni", "70"), "CuNi_7030"),
    (("cupronickel", "70"), "CuNi_7030"),
    (("cuni",), "CuNi_9010"),
    (("cupronickel",), "CuNi_9010"),
    (("brass",), "Brass_C46400"),
    (("c46400",), "Brass_C46400"),
    (("gunmetal",), "Brass_C46400"),
    (("c12200",), "Copper_C12200"),
    (("copper",), "Copper_C12200"),
    # Steels — galvanised before plain steel
    (("galvan",), "GalvanisedSteel"),
    (("hot dip",), "GalvanisedSteel"),
    (("hdg",), "GalvanisedSteel"),
    (("black", "steel"), "BlackSteel"),
    (("carbon", "steel"), "CarbonSteel"),
    (("mild", "steel"), "CarbonSteel"),
    (("s275",), "CarbonSteel"),
    (("s355",), "CarbonSteel"),
    # Cast irons — ductile before plain cast
    (("ductile",), "DuctileIron"),
    (("sg iron",), "DuctileIron"),
    (("cast iron",), "CastIron"),
    (("grey iron",), "CastIron"),
    # Non-ferrous
    (("titanium",), "Titanium"),
    (("alumin",), "Aluminium"),
    # Plastics
    (("hdpe",), "HDPE"),
    (("polyethylene",), "HDPE"),
    (("ppr",), "PPR"),
    (("polypropylene",), "PPR"),
    (("pex",), "PEX"),
    (("cross-linked",), "PEX"),
    (("upvc",), "PVC"),
    (("pvc",), "PVC"),
    # Bare "steel" last — anything more specific has already matched
    (("stainless",), "SS316"),
    (("steel",), "CarbonSteel"),
)

# Fail loudly at import if a rule emits a key the rule packs cannot score.
# The schema requires exact case-sensitive matches, so "Galvanized_steel"
# instead of "GalvanisedSteel" would otherwise fail silently at runtime as a
# data-quality issue on every affected element.
_UNCANONICAL = {key for _, key in _MATERIAL_RULES} - CANONICAL_MATERIALS
if _UNCANONICAL:
    raise ValueError(
        f"_MATERIAL_RULES emits non-canonical material keys: {sorted(_UNCANONICAL)}"
    )


def normalise_material(raw: Optional[str]) -> str:
    """Map a free-text IFC material name to a CANONICAL_MATERIALS key.

    Returns "Unknown" when the text is empty or matches no rule. Callers
    should record a warning when "Unknown" is returned, since the Path B
    rule packs cannot score an unknown material.

    Args:
        raw: Material name as it appears in the IFC file, or None.

    Returns:
        A key guaranteed to be a member of CANONICAL_MATERIALS.
    """
    if not raw:
        return "Unknown"

    text = raw.lower().strip()
    if not text:
        return "Unknown"

    for needles, canonical in _MATERIAL_RULES:
        if all(needle in text for needle in needles):
            return canonical

    return "Unknown"


# ---------------------------------------------------------------------------
# System classification
# ---------------------------------------------------------------------------
# Matched against the IFC system name, the element name, and the predefined
# type, in that order of preference. Ordered most-specific first.

_SYSTEM_RULES: tuple[tuple[tuple[str, ...], PipingSystem], ...] = (
    (("pool", "dos"), PipingSystem.POOL_CHEMICAL_DOSING),
    (("chemical", "dos"), PipingSystem.POOL_CHEMICAL_DOSING),
    (("pool",), PipingSystem.POOL_CIRCULATION),
    (("sprinkler",), PipingSystem.FIRE_SPRINKLER),
    (("wet riser",), PipingSystem.FIRE_WET_RISER),
    (("fire",), PipingSystem.FIRE_SPRINKLER),
    (("oxygen",), PipingSystem.MEDICAL_GAS_OXYGEN),
    (("nitrous",), PipingSystem.MEDICAL_GAS_NITROUS),
    (("vacuum",), PipingSystem.MEDICAL_GAS_VACUUM),
    (("medical", "air"), PipingSystem.MEDICAL_GAS_COMPRESSED_AIR),
    (("natural gas",), PipingSystem.NATURAL_GAS),
    (("compressed air",), PipingSystem.COMPRESSED_AIR),
    (("steam", "hp"), PipingSystem.STEAM_HP),
    (("steam", "high"), PipingSystem.STEAM_HP),
    (("steam",), PipingSystem.STEAM_LP),
    (("condensate",), PipingSystem.CONDENSATE_RETURN),
    (("condenser",), PipingSystem.CONDENSER_WATER),
    (("chilled", "return"), PipingSystem.CHILLED_WATER_RETURN),
    (("chilled",), PipingSystem.CHILLED_WATER_FLOW),
    (("chw", "r"), PipingSystem.CHILLED_WATER_RETURN),
    (("chw",), PipingSystem.CHILLED_WATER_FLOW),
    (("heating", "return"), PipingSystem.HEATING_RETURN),
    (("heating",), PipingSystem.HEATING_FLOW),
    (("lthw", "r"), PipingSystem.HEATING_RETURN),
    (("lthw",), PipingSystem.HEATING_FLOW),
    (("hot water", "return"), PipingSystem.DOMESTIC_HOT_WATER_RETURN),
    (("hwsr",), PipingSystem.DOMESTIC_HOT_WATER_RETURN),
    (("hot water",), PipingSystem.DOMESTIC_HOT_WATER),
    (("hws",), PipingSystem.DOMESTIC_HOT_WATER),
    (("cold water",), PipingSystem.DOMESTIC_COLD_WATER),
    (("cws",), PipingSystem.DOMESTIC_COLD_WATER),
    (("foul",), PipingSystem.FOUL_DRAINAGE),
    (("soil",), PipingSystem.FOUL_DRAINAGE),
    (("waste",), PipingSystem.FOUL_DRAINAGE),
    (("rainwater",), PipingSystem.RAINWATER),
    (("storm",), PipingSystem.RAINWATER),
)


def classify_system(*hints: Optional[str]) -> PipingSystem:
    """Classify a piping system from free-text hints.

    Args:
        *hints: Candidate strings (system name, element name, predefined
            type). Checked in the order given; the first hint that matches
            any rule wins.

    Returns:
        A PipingSystem member, or PipingSystem.UNKNOWN when nothing matches.
    """
    for hint in hints:
        if not hint:
            continue
        text = hint.lower().strip()
        for needles, system in _SYSTEM_RULES:
            if all(needle in text for needle in needles):
                return system
    return PipingSystem.UNKNOWN


# ---------------------------------------------------------------------------
# Media derivation (Issue #16 — MM-001 / XM-001)
# ---------------------------------------------------------------------------
# PipingElement deliberately carries no `media` field. Media is a function of
# system, so deriving it here keeps one source of truth and prevents the two
# from drifting apart. Engines call media_for_system(element.system).

SYSTEM_TO_MEDIA: dict[PipingSystem, str] = {
    PipingSystem.DOMESTIC_COLD_WATER: "cold_water",
    PipingSystem.DOMESTIC_HOT_WATER: "hot_water",
    PipingSystem.DOMESTIC_HOT_WATER_RETURN: "hot_water",
    PipingSystem.CHILLED_WATER_FLOW: "chilled_water",
    PipingSystem.CHILLED_WATER_RETURN: "chilled_water",
    PipingSystem.HEATING_FLOW: "hot_water",
    PipingSystem.HEATING_RETURN: "hot_water",
    PipingSystem.CONDENSER_WATER: "condenser_water",
    PipingSystem.MEDICAL_GAS_OXYGEN: "oxygen",
    PipingSystem.MEDICAL_GAS_NITROUS: "nitrous_oxide",
    PipingSystem.MEDICAL_GAS_VACUUM: "vacuum",
    PipingSystem.MEDICAL_GAS_COMPRESSED_AIR: "compressed_air",
    PipingSystem.NATURAL_GAS: "natural_gas",
    PipingSystem.COMPRESSED_AIR: "compressed_air",
    PipingSystem.STEAM_LP: "steam",
    PipingSystem.STEAM_HP: "steam",
    PipingSystem.CONDENSATE_RETURN: "condensate",
    PipingSystem.FOUL_DRAINAGE: "foul_water",
    PipingSystem.RAINWATER: "rainwater",
    PipingSystem.POOL_CHEMICAL_DOSING: "pool_chemical",
    PipingSystem.POOL_CIRCULATION: "pool_water",
    PipingSystem.FIRE_WET_RISER: "stagnant_water",
    PipingSystem.FIRE_SPRINKLER: "stagnant_water",
    PipingSystem.UNKNOWN: "unknown",
}


def media_for_system(system: PipingSystem) -> str:
    """Return the corrosive medium carried by a piping system.

    Args:
        system: The element's classified PipingSystem.

    Returns:
        A media key for the MM-001 compatibility matrix, or "unknown".
    """
    return SYSTEM_TO_MEDIA.get(system, "unknown")


# ---------------------------------------------------------------------------
# Environment classification
# ---------------------------------------------------------------------------
# Maps space/storey/zone text onto the EnvironmentClass enum already used by
# the crevice and MIC engines. Ordered most-severe first so that a space
# named "coastal plant room" resolves to the chloride class, not the dry one.

_ENVIRONMENT_RULES: tuple[tuple[tuple[str, ...], EnvironmentClass], ...] = (
    (("marine", "splash"), EnvironmentClass.T4_MARINE),
    (("splash zone",), EnvironmentClass.T4_MARINE),
    (("marine",), EnvironmentClass.T4_MARINE),
    (("jetty",), EnvironmentClass.T4_MARINE),
    (("pool",), EnvironmentClass.T3_CHLORIDE),
    (("coastal",), EnvironmentClass.T3_CHLORIDE),
    (("spa",), EnvironmentClass.T3_CHLORIDE),
    (("industrial",), EnvironmentClass.T5_INDUSTRIAL),
    (("chemical",), EnvironmentClass.T5_INDUSTRIAL),
    (("process",), EnvironmentClass.T5_INDUSTRIAL),
    (("wet room",), EnvironmentClass.T2_HUMID),
    (("shower",), EnvironmentClass.T2_HUMID),
    (("laundry",), EnvironmentClass.T2_HUMID),
    (("kitchen",), EnvironmentClass.T2_HUMID),
    (("bathroom",), EnvironmentClass.T2_HUMID),
    (("basement",), EnvironmentClass.T1_INDOOR_DAMP),
    (("plant",), EnvironmentClass.T1_INDOOR_DAMP),
    (("roof",), EnvironmentClass.T1_INDOOR_DAMP),
    (("external",), EnvironmentClass.T1_INDOOR_DAMP),
    (("car park",), EnvironmentClass.T1_INDOOR_DAMP),
    (("office",), EnvironmentClass.T0_DRY),
    (("corridor",), EnvironmentClass.T0_DRY),
    (("bedroom",), EnvironmentClass.T0_DRY),
)


def classify_environment(*hints: Optional[str]) -> EnvironmentClass:
    """Classify environmental severity from space and storey names.

    Args:
        *hints: Candidate strings (space name, zone name, storey name).

    Returns:
        An EnvironmentClass member, or UNCLASSIFIED when nothing matches.
        UNCLASSIFIED is deliberate: it lets comparators distinguish "we know
        it is dry" from "we do not know", which T0_DRY would conflate.
    """
    combined = " ".join(h.lower() for h in hints if h).strip()
    if not combined:
        return EnvironmentClass.UNCLASSIFIED

    for needles, environment in _ENVIRONMENT_RULES:
        if all(needle in combined for needle in needles):
            return environment
    return EnvironmentClass.UNCLASSIFIED


# ---------------------------------------------------------------------------
# Subtype classification
# ---------------------------------------------------------------------------
# subtype is one of only three required PipingElement fields and has no
# direct IFC equivalent, so it is derived from the IFC class plus name text.

_SUBTYPE_BY_IFC_CLASS: dict[str, ElementSubtype] = {
    "IfcPipeSegment": "pipe_segment",
    "IfcDuctSegment": "pipe_segment",
    "IfcFlowSegment": "pipe_segment",
    "IfcPipeFitting": "fitting",
    "IfcDuctFitting": "fitting",
    "IfcFlowFitting": "fitting",
    "IfcValve": "valve",
    "IfcFlowController": "valve",
    "IfcPump": "pump",
    "IfcFlowMovingDevice": "pump",
    "IfcTank": "tank",
    "IfcFlowStorageDevice": "tank",
    "IfcFilter": "filter",
    "IfcFlowTreatmentDevice": "filter",
    "IfcHeatExchanger": "heat_exchanger",
    "IfcAirTerminal": "other",
    "IfcFlowTerminal": "other",
    "IfcDistributionElement": "other",
}

_SUBTYPE_NAME_HINTS: tuple[tuple[str, ElementSubtype], ...] = (
    ("strainer", "strainer"),
    ("flange", "flange"),
    ("manifold", "manifold"),
    ("heat exchanger", "heat_exchanger"),
    ("calorifier", "tank"),
    ("expansion vessel", "tank"),
    ("hanger", "support"),
    ("clamp", "support"),
    ("bracket", "support"),
    ("meter", "meter"),
    ("gauge", "meter"),
    ("ahu", "ahu"),
    ("air handling", "ahu"),
    ("fcu", "fcu"),
    ("fan coil", "fcu"),
)


def classify_subtype(ifc_class: str, name: Optional[str]) -> ElementSubtype:
    """Derive the required `subtype` discriminator for a PipingElement.

    Name hints win over the IFC class, because a generic IfcFlowTerminal
    named "FCU-03" is more usefully typed as an fcu than as "other".

    Args:
        ifc_class: The entity's IFC class name.
        name: The entity's Name attribute, if any.

    Returns:
        One of the ElementSubtype literal values, defaulting to "other".
    """
    text = (name or "").lower()
    for needle, subtype in _SUBTYPE_NAME_HINTS:
        if needle in text:
            return subtype
    return _SUBTYPE_BY_IFC_CLASS.get(ifc_class, "other")


# ---------------------------------------------------------------------------
# Joint type
# ---------------------------------------------------------------------------

_JOINT_RULES: tuple[tuple[str, JointType], ...] = (
    ("dielectric", JointType.JT014_DIELECTRIC_UNION),
    ("push fit", JointType.JT013_PUSH_FIT),
    ("push-fit", JointType.JT013_PUSH_FIT),
    ("press fit", JointType.JT008_PRESS_FIT),
    ("press-fit", JointType.JT008_PRESS_FIT),
    ("grooved", JointType.JT007_GROOVED_COUPLING),
    ("victaulic", JointType.JT007_GROOVED_COUPLING),
    ("compression", JointType.JT006_COMPRESSION),
    ("socket weld", JointType.JT002_SOCKET_WELDED),
    ("threaded", JointType.JT003_THREADED),
    ("screwed", JointType.JT003_THREADED),
    ("flange", JointType.JT004_FLANGED_FULL_GASKET),
    ("soldered", JointType.JT009_SOLDERED),
    ("brazed", JointType.JT010_BRAZED),
    ("clamp", JointType.JT011_MECHANICAL_CLAMP),
    ("welded", JointType.JT001_PLAIN_WELDED),
)


def classify_joint_type(*hints: Optional[str]) -> Optional[JointType]:
    """Classify a joint from free-text hints, or None when unstated.

    None rather than JointType.UNKNOWN is returned when no hint matches, so
    that comparators can tell "no joint information in the model" apart from
    "a joint that could not be classified".

    Args:
        *hints: Candidate strings (element name, description, type name).

    Returns:
        A JointType member, or None.
    """
    for hint in hints:
        if not hint:
            continue
        text = hint.lower()
        for needle, joint in _JOINT_RULES:
            if needle in text:
                return joint
    return None


# ---------------------------------------------------------------------------
# IFC attribute helpers
# ---------------------------------------------------------------------------


def _safe_str(value: Any) -> Optional[str]:
    """Coerce an IFC attribute to a stripped string, or None if empty."""
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _all_property_values(entity: Any) -> dict:
    """Flatten every Pset on an entity into one dict.

    Later property sets win on key collision. Returns an empty dict when
    ifcopenshell cannot read the psets rather than propagating the error.
    """
    try:
        psets = ifcopenshell.util.element.get_psets(entity) or {}
    except Exception:
        return {}

    flattened: dict = {}
    for pset_name, props in psets.items():
        if not isinstance(props, dict):
            continue
        for key, value in props.items():
            if key == "id":
                continue
            flattened[key] = value
            flattened[f"{pset_name}.{key}"] = value
    return flattened


def _first_number(properties: dict, *keys: str) -> Optional[float]:
    """Return the first key that holds a finite number, or None."""
    for key in keys:
        value = properties.get(key)
        if isinstance(value, bool) or value is None:
            continue
        try:
            number = float(value)
        except (TypeError, ValueError):
            continue
        if math.isfinite(number):
            return number
    return None


def _first_text(properties: dict, *keys: str) -> Optional[str]:
    """Return the first key that holds non-empty text, or None."""
    for key in keys:
        text = _safe_str(properties.get(key))
        if text:
            return text
    return None


def _material_name(entity: Any) -> Optional[str]:
    """Read the primary material name from an entity, or None."""
    try:
        materials = ifcopenshell.util.element.get_materials(entity)
        if materials:
            first = materials[0]
            return _safe_str(getattr(first, "Name", None)) or _safe_str(first)
    except Exception:
        pass

    for rel in getattr(entity, "HasAssociations", []) or []:
        try:
            if not rel.is_a("IfcRelAssociatesMaterial"):
                continue
            material = rel.RelatingMaterial
            name = _safe_str(getattr(material, "Name", None))
            if name:
                return name
            layer_set = getattr(material, "ForLayerSet", None)
            if layer_set and layer_set.MaterialLayers:
                return _safe_str(getattr(layer_set.MaterialLayers[0].Material, "Name", None))
        except Exception:
            continue
    return None


def _unit_scale_to_metres(model: Any) -> float:
    """Return the factor converting model length units to metres.

    IFC files routinely use millimetres. get_local_placement returns raw
    model units, but the schema mandates metres throughout, so every
    coordinate must be scaled. Defaults to 1.0 when the model declares no
    usable unit — wrong, but no worse than not scaling at all.
    """
    try:
        import ifcopenshell.util.unit

        scale = float(ifcopenshell.util.unit.calculate_unit_scale(model))
        return scale if math.isfinite(scale) and scale > 0 else 1.0
    except Exception:
        return 1.0


def _centroid(entity: Any, unit_scale: float) -> Optional[Point3D]:
    """Read the element's placement origin in world coordinates, in metres.

    This is the placement origin, not a true geometric centroid. For long
    runs the origin sits at one end, which _build_adjacency compensates for
    via its tolerance. Computing real centroids needs ifcopenshell.geom and
    a full tessellation pass, which is far too slow for whole-model reads.

    Args:
        entity: The IFC entity.
        unit_scale: Factor converting model units to metres.
    """
    placement = getattr(entity, "ObjectPlacement", None)
    if placement is None:
        return None
    try:
        matrix = ifcopenshell.util.placement.get_local_placement(placement)
        return Point3D(
            x=round(float(matrix[0][3]) * unit_scale, 4),
            y=round(float(matrix[1][3]) * unit_scale, 4),
            z=round(float(matrix[2][3]) * unit_scale, 4),
        )
    except Exception:
        return None


def _placement_matrix(entity: Any) -> Optional[Any]:
    """Return the 4x4 local-placement matrix, or None."""
    placement = getattr(entity, "ObjectPlacement", None)
    if placement is None:
        return None
    try:
        return ifcopenshell.util.placement.get_local_placement(placement)
    except Exception:
        return None


def _apply(matrix: Any, x: float, y: float, z: float) -> tuple[float, float, float]:
    """Transform a local point by a 4x4 placement matrix."""
    # float() casts away numpy scalars from ifcopenshell's matrix so the
    # schema carries plain Python floats.
    return (
        float(matrix[0][0] * x + matrix[0][1] * y + matrix[0][2] * z + matrix[0][3]),
        float(matrix[1][0] * x + matrix[1][1] * y + matrix[1][2] * z + matrix[1][3]),
        float(matrix[2][0] * x + matrix[2][1] * y + matrix[2][2] * z + matrix[2][3]),
    )


def _local_vertices(entity: Any) -> list[tuple[float, float, float]]:
    """Collect raw vertices from an entity's shape representation.

    Handles the three shapes seen in practice: tessellated face sets
    (IfcTriangulatedFaceSet / IfcPolygonalFaceSet), explicit axis curves
    (IfcPolyline), and swept solids (IfcExtrudedAreaSolid, reduced to its
    extrusion axis). Anything else yields no vertices, which pushes the
    element to Tier 3.
    """
    representation = getattr(entity, "Representation", None)
    if representation is None:
        return []

    vertices: list[tuple[float, float, float]] = []
    for shape in getattr(representation, "Representations", []) or []:
        for item in getattr(shape, "Items", []) or []:
            try:
                kind = item.is_a()
                if kind in ("IfcTriangulatedFaceSet", "IfcPolygonalFaceSet"):
                    coords = item.Coordinates.CoordList or []
                    vertices.extend((float(c[0]), float(c[1]), float(c[2])) for c in coords)
                elif kind == "IfcPolyline":
                    for point in item.Points or []:
                        c = point.Coordinates
                        vertices.append((float(c[0]), float(c[1]), float(c[2] if len(c) > 2 else 0)))
                elif kind == "IfcExtrudedAreaSolid":
                    origin = (0.0, 0.0, 0.0)
                    if item.Position is not None:
                        c = item.Position.Location.Coordinates
                        origin = (float(c[0]), float(c[1]), float(c[2]))
                    ratios = item.ExtrudedDirection.DirectionRatios
                    depth = float(item.Depth)
                    vertices.append(origin)
                    vertices.append(
                        (
                            origin[0] + float(ratios[0]) * depth,
                            origin[1] + float(ratios[1]) * depth,
                            origin[2] + float(ratios[2]) * depth,
                        )
                    )
            except Exception:
                continue
    return vertices


def _geometry(entity: Any, unit_scale: float) -> tuple[Optional[Centerline], Optional[BoundingBox]]:
    """Derive a centerline and bounding box in world metres.

    The centerline is approximated as the two extreme points along the
    element's dominant axis, taken at the mid-point of the other two axes.
    For a pipe run that is the pair of end-face centres, which is what
    endpoint-proximity adjacency needs. It is an approximation: a bent pipe
    reduces to the straight line between its ends.

    Args:
        entity: The IFC entity.
        unit_scale: Factor converting model length units to metres.

    Returns:
        (centerline, bbox), either of which may be None when the entity has
        no usable geometry.
    """
    matrix = _placement_matrix(entity)
    if matrix is None:
        return None, None

    local = _local_vertices(entity)
    if not local:
        return None, None

    world = [_apply(matrix, x, y, z) for x, y, z in local]
    xs = [p[0] * unit_scale for p in world]
    ys = [p[1] * unit_scale for p in world]
    zs = [p[2] * unit_scale for p in world]

    lo = (min(xs), min(ys), min(zs))
    hi = (max(xs), max(ys), max(zs))
    bbox = BoundingBox(
        min=Point3D(x=round(lo[0], 4), y=round(lo[1], 4), z=round(lo[2], 4)),
        max=Point3D(x=round(hi[0], 4), y=round(hi[1], 4), z=round(hi[2], 4)),
    )

    extents = (hi[0] - lo[0], hi[1] - lo[1], hi[2] - lo[2])
    axis = extents.index(max(extents))
    if extents[axis] <= 0:
        return None, bbox

    mid = [(lo[i] + hi[i]) / 2.0 for i in range(3)]
    start, end = list(mid), list(mid)
    start[axis], end[axis] = lo[axis], hi[axis]

    centerline = Centerline(
        points=[
            Point3D(x=round(start[0], 4), y=round(start[1], 4), z=round(start[2], 4)),
            Point3D(x=round(end[0], 4), y=round(end[1], 4), z=round(end[2], 4)),
        ]
    )
    return centerline, bbox


def _storey(entity: Any) -> tuple[Optional[str], Optional[str]]:
    """Return (level_id, level_name) for the containing building storey."""
    for rel in getattr(entity, "ContainedInStructure", []) or []:
        try:
            container = rel.RelatingStructure
            if container.is_a("IfcBuildingStorey"):
                return _safe_str(container.GlobalId), _safe_str(container.Name)
        except Exception:
            continue
    return None, None


def _space(entity: Any) -> tuple[Optional[str], Optional[str]]:
    """Return (space_id, space_name) for the containing IfcSpace."""
    for rel in getattr(entity, "ContainedInStructure", []) or []:
        try:
            container = rel.RelatingStructure
            if container.is_a("IfcSpace"):
                return _safe_str(container.GlobalId), _safe_str(container.Name)
        except Exception:
            continue
    return None, None


def _groups(model: Any, entity: Any) -> tuple[Optional[str], list[str]]:
    """Return (system_name, zone_ids) from the entity's group assignments."""
    system_name: Optional[str] = None
    zone_ids: list[str] = []
    try:
        inverse = model.get_inverse(entity)
    except Exception:
        return None, []

    for rel in inverse:
        try:
            if not rel.is_a("IfcRelAssignsToGroup"):
                continue
            group = rel.RelatingGroup
            if group.is_a("IfcZone"):
                group_id = _safe_str(group.GlobalId)
                if group_id:
                    zone_ids.append(group_id)
            elif group.is_a("IfcSystem") or group.is_a("IfcDistributionSystem"):
                system_name = system_name or _safe_str(group.Name)
        except Exception:
            continue
    return system_name, zone_ids


# ---------------------------------------------------------------------------
# Adjacency
# ---------------------------------------------------------------------------


def _port_adjacency(model: Any) -> dict[str, set[str]]:
    """Tier 1 — read authored connectivity from IFC ports.

    Walks IfcRelConnectsPorts, resolving each port back to its owning
    element via IfcRelConnectsPortToElement (IFC2X3) or IfcRelNests (IFC4).
    This is authoritative: it is what the authoring tool recorded, not an
    inference from geometry.

    Args:
        model: The open IFC model.

    Returns:
        Symmetric adjacency keyed by element GlobalId. Empty when the model
        carries no port connectivity.
    """
    port_owner: dict[int, str] = {}

    for rel_type, port_attr, element_attr in (
        ("IfcRelConnectsPortToElement", "RelatingPort", "RelatedElement"),
        ("IfcRelNests", None, "RelatingObject"),
    ):
        try:
            rels = model.by_type(rel_type)
        except Exception:
            continue
        for rel in rels:
            try:
                owner = getattr(rel, element_attr, None)
                owner_id = _safe_str(getattr(owner, "GlobalId", None))
                if not owner_id:
                    continue
                if port_attr:
                    port = getattr(rel, port_attr, None)
                    if port is not None and port.is_a("IfcPort"):
                        port_owner[port.id()] = owner_id
                else:
                    for nested in getattr(rel, "RelatedObjects", []) or []:
                        if nested.is_a("IfcPort"):
                            port_owner[nested.id()] = owner_id
            except Exception:
                continue

    adjacency: dict[str, set[str]] = {}
    try:
        connections = model.by_type("IfcRelConnectsPorts")
    except Exception:
        connections = []

    for rel in connections:
        try:
            a = port_owner.get(rel.RelatingPort.id())
            b = port_owner.get(rel.RelatedPort.id())
        except Exception:
            continue
        if not a or not b or a == b:
            continue
        adjacency.setdefault(a, set()).add(b)
        adjacency.setdefault(b, set()).add(a)

    return adjacency


def _endpoints(element: PipingElement) -> list[Point3D]:
    """Return the points used for Tier 2 proximity testing."""
    if element.centerline and element.centerline.points:
        points = element.centerline.points
        return [points[0], points[-1]]
    if element.centroid is not None:
        return [element.centroid]
    return []


def _build_adjacency(
    model: Any,
    elements: list[PipingElement],
    tolerance_m: float,
) -> dict[str, int]:
    """Populate joined_to in place using the three-tier resolution.

    Tier 1  IFC ports (IfcRelConnectsPorts) — authoritative, used whenever
            the model carries any port connectivity at all.
    Tier 2  Centerline endpoint proximity within tolerance_m — endpoints,
            not placement origins, so pipes joined end to end register even
            when their origins are a full pipe-length apart.
    Tier 3  Neither available — joined_to stays empty and
            CONNECTIVITY_INDETERMINABLE is appended to extraction_warnings
            so XM-001 skips the element rather than reading the empty list
            as "isolated".

    Tiers are resolved per element, not per model: an element with ports
    uses Tier 1 even when its neighbours fall back to Tier 2.

    Args:
        model: The open IFC model, for port lookups.
        elements: Elements to link, mutated in place.
        tolerance_m: Endpoint separation counting as joined, in metres.

    Returns:
        Counts keyed "ports", "centerline", "indeterminable", "pairs".
    """
    ports = _port_adjacency(model)
    by_id = {e.id: e for e in elements}
    counts = {"ports": 0, "centerline": 0, "indeterminable": 0, "pairs": 0}
    linked: set[tuple[str, str]] = set()

    def link(a: PipingElement, b: PipingElement) -> None:
        key = (a.id, b.id) if a.id < b.id else (b.id, a.id)
        if key in linked:
            return
        linked.add(key)
        a.joined_to.append(b.id)
        b.joined_to.append(a.id)
        counts["pairs"] += 1

    # ── Tier 1 ────────────────────────────────────────────────────────────
    for element_id, neighbours in ports.items():
        element = by_id.get(element_id)
        if element is None:
            continue
        element.properties[CONNECTIVITY_SOURCE_KEY] = "ports"
        counts["ports"] += 1
        for neighbour_id in neighbours:
            neighbour = by_id.get(neighbour_id)
            if neighbour is not None:
                link(element, neighbour)

    # ── Tier 2 ────────────────────────────────────────────────────────────
    remaining = [e for e in elements if CONNECTIVITY_SOURCE_KEY not in e.properties]
    geometric = [(e, _endpoints(e)) for e in remaining]
    geometric = [(e, pts) for e, pts in geometric if pts]

    for element, _ in geometric:
        element.properties[CONNECTIVITY_SOURCE_KEY] = "centerline"
        counts["centerline"] += 1

    for index, (element, points) in enumerate(geometric):
        for other, other_points in geometric[index + 1 :]:
            nearest = min(
                math.dist((p.x, p.y, p.z), (q.x, q.y, q.z)) for p in points for q in other_points
            )
            if nearest <= tolerance_m:
                link(element, other)

    # ── Tier 3 ────────────────────────────────────────────────────────────
    for element in elements:
        if CONNECTIVITY_SOURCE_KEY in element.properties:
            continue
        element.properties[CONNECTIVITY_SOURCE_KEY] = "indeterminable"
        element.extraction_warnings.append(CONNECTIVITY_INDETERMINABLE)
        counts["indeterminable"] += 1

    return counts


# ---------------------------------------------------------------------------
# Producer
# ---------------------------------------------------------------------------


def _build_element(model: Any, entity: Any, unit_scale: float) -> Optional[PipingElement]:
    """Convert one IFC entity to a PipingElement, or None if unusable.

    Args:
        model: The open IFC model, for inverse lookups.
        entity: The entity to convert.
        unit_scale: Factor converting model length units to metres.
    """
    global_id = _safe_str(getattr(entity, "GlobalId", None))
    if not global_id:
        return None

    warnings: list[str] = []
    name = _safe_str(getattr(entity, "Name", None))
    description = _safe_str(getattr(entity, "Description", None))
    ifc_class = entity.is_a()
    properties = _all_property_values(entity)

    material_raw = _material_name(entity) or _first_text(properties, "Material", "MaterialName")
    material = normalise_material(material_raw)
    if material == "Unknown":
        warnings.append(
            f"material not identified from {material_raw!r}"
            if material_raw
            else "no material associated with element"
        )

    system_name, zone_ids = _groups(model, entity)
    predefined = _safe_str(getattr(entity, "PredefinedType", None))
    system = classify_system(system_name, name, description, predefined)
    if system is PipingSystem.UNKNOWN:
        warnings.append("piping system could not be classified")

    level_id, level_name = _storey(entity)
    space_id, space_name = _space(entity)
    environment_class = classify_environment(space_name, level_name, system_name)
    if environment_class is EnvironmentClass.UNCLASSIFIED:
        warnings.append("environment class could not be inferred from spatial names")

    centroid = _centroid(entity, unit_scale)
    centerline, bbox = _geometry(entity, unit_scale)
    if centroid is None:
        warnings.append("no placement — element excluded from adjacency detection")

    joint_type = classify_joint_type(name, description, predefined)

    return PipingElement(
        id=global_id,
        ifc_class=ifc_class,
        subtype=classify_subtype(ifc_class, name),
        name=name,
        bbox=bbox,
        centroid=centroid,
        centerline=centerline,
        level_id=level_id,
        level_name=level_name,
        space_id=space_id,
        space_name=space_name,
        zone_ids=zone_ids,
        material=material,
        material_raw=material_raw,
        nominal_diameter_mm=_first_number(
            properties, "NominalDiameter", "NominalDiameterMM", "DN", "Size"
        ),
        outside_diameter_mm=_first_number(properties, "OutsideDiameter", "OuterDiameter", "OD"),
        wall_thickness_mm=_first_number(properties, "WallThickness", "Thickness"),
        insulation_thickness_mm=_first_number(
            properties, "InsulationThickness", "ThermalInsulationThickness"
        ),
        insulation_material=_first_text(properties, "InsulationMaterial", "InsulationType"),
        system=system,
        operating_temperature_c=_first_number(
            properties, "OperatingTemperature", "WorkingTemperature", "FluidTemperature"
        ),
        design_pressure_bar=_first_number(
            properties, "DesignPressure", "WorkingPressure", "PressureRating"
        ),
        environment_class=environment_class,
        environment_source="inferred from spatial names",
        joint_type=joint_type,
        properties=properties,
        extraction_warnings=warnings,
    )


def produce_piping_elements(
    ifc_path: str,
    *,
    adjacency_tolerance_m: float = 0.05,
) -> list[PipingElement]:
    """Read an IFC file and emit the canonical PipingElement list.

    Args:
        ifc_path: Path to the IFC file.
        adjacency_tolerance_m: Tier 2 endpoint separation counting as
            joined, in metres. Ignored for elements resolved by Tier 1
            ports. Defaults to 50 mm.

    Returns:
        One PipingElement per piping entity found, with joined_to populated.
        Returns an empty list when the model holds no piping entities.

    Raises:
        OSError: If the file cannot be opened by ifcopenshell.
    """
    model = ifcopenshell.open(ifc_path)
    unit_scale = _unit_scale_to_metres(model)

    seen: set[str] = set()
    elements: list[PipingElement] = []

    for ifc_class in PIPING_IFC_CLASSES:
        try:
            entities = model.by_type(ifc_class)
        except Exception:
            # Class absent from this IFC schema version — expected for
            # IFC4-only names when reading an IFC2X3 file.
            continue

        for entity in entities:
            global_id = _safe_str(getattr(entity, "GlobalId", None))
            if not global_id or global_id in seen:
                # by_type returns subtypes too, so the same entity can be
                # yielded under both its own class and a supertype.
                continue
            element = _build_element(model, entity, unit_scale)
            if element is None:
                continue
            seen.add(global_id)
            elements.append(element)

    _build_adjacency(model, elements, adjacency_tolerance_m)
    return elements


def summarise(elements: list[PipingElement]) -> str:
    """Return a one-line extraction summary for logs and smoke tests.

    Args:
        elements: The producer's output.

    Returns:
        Human-readable counts of elements, adjacencies, and data gaps.
    """
    adjacencies = sum(len(e.joined_to) for e in elements) // 2
    unknown_material = sum(1 for e in elements if e.material == "Unknown")
    unknown_system = sum(1 for e in elements if e.system is PipingSystem.UNKNOWN)
    unclassified_env = sum(
        1 for e in elements if e.environment_class is EnvironmentClass.UNCLASSIFIED
    )
    return (
        f"Extracted {len(elements)} elements, {adjacencies} adjacencies found "
        f"({unknown_material} unknown material, {unknown_system} unknown system, "
        f"{unclassified_env} unclassified environment)"
    )

