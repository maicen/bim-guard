"""
BIMGUARD AI — IFC Parser Module
OpenBIM compliant: reads any IFC 2x3 or IFC4 file regardless of authoring tool.
Standard: ISO 16739-1
Library:  ifcopenshell (open source)
"""

import re
import uuid
from dataclasses import dataclass
from typing import Optional

import ifcopenshell
import ifcopenshell.guid
import ifcopenshell.util.element
import ifcopenshell.util.placement

# ---------------------------------------------------------------------------
# Provenance vocabulary
#
# Shared with piping_producer's ENVIRONMENT_SOURCE_*/MATERIAL_SOURCE_* strings
# where the two producers mean the same thing, so one reviewer-facing
# vocabulary describes both the ServiceElement path (GC/CC/MC) and the
# PipingElement path (MM/XM) rather than two that have to be learned apart.
# ---------------------------------------------------------------------------

#: An IFC material was read and mapped onto a known BIMGUARD material key.
MATERIAL_SOURCE_IFC = "ifc_metadata"
#: An IFC material was read but matches no known key, so it was passed through
#: as free text. The engines will not resolve it, which is a data-quality fact
#: about the model and must not read as a confident material.
MATERIAL_SOURCE_UNMAPPED = "ifc_metadata_unmapped"
#: The IFC carried no material at all.
MATERIAL_SOURCE_ABSENT = "absent"
#: The element was authored by the demo generator, not read from a model.
SOURCE_SYNTHETIC = "synthetic_fixture"

#: The environment class came from matching a space or storey name.
ENVIRONMENT_SOURCE_SPATIAL = "inferred from spatial names"
#: Nothing matched, so DEFAULT_ENVIRONMENT was assumed.
ENVIRONMENT_SOURCE_DEFAULT = "default_indoor"

#: A hydraulic value was read from an IFC property set. Deliberately the same
#: string as piping_producer.TEMPERATURE_SOURCE_IFC: both producers read the
#: same property off the same element, and one reviewer-facing vocabulary is
#: the point of the note at the top of this block.
HYDRAULIC_SOURCE_IFC = "ifc_property"
#: No property set on the element carried the value. There is deliberately no
#: inference counterpart: MC-001's pre-flight gate exists precisely because a
#: substituted hydraulic input scores as a real one, so a value this parser
#: cannot read stays None and the gate refuses the element.
HYDRAULIC_SOURCE_ABSENT = "absent"

CONFIDENCE_HIGH = "high"
CONFIDENCE_MEDIUM = "medium"
CONFIDENCE_LOW = "low"
#: There is no value to have confidence in.
CONFIDENCE_NONE = "none"

#: What classify_environment_from_space assumes when no keyword matches. Named
#: because ENVIRONMENT_SOURCE_DEFAULT exists to mark exactly this value.
DEFAULT_ENVIRONMENT = "interior_dry"


@dataclass
class ServiceElement:
    """Represents one MEP service element extracted from the IFC model."""

    guid: str
    name: str
    ifc_type: str
    description: str
    material_a: str
    material_b: Optional[str]
    location_tag: str
    floor: str
    system: str
    joint_type: str
    anode_area_m2: float
    cathode_area_m2: float
    position: tuple  # (x, y, z) in metres
    length_m: float
    notes: str = ""

    # --- Provenance -------------------------------------------------------
    # material_a and location_tag are the two inputs that decide a GC-001,
    # CC-001 or MC-001 verdict, and neither is always read from the model:
    # an IFC carrying no material yields "Unknown", and a space name matching
    # no SPACE_TO_ENV keyword yields DEFAULT_ENVIRONMENT. Without these four
    # fields the finding built from them cannot say which happened, so a
    # reviewer cannot tell an assessment of the building from an assessment
    # of this module's defaults. Defaults below describe an element built
    # without going through the resolvers.
    #: MATERIAL_SOURCE_* — read from IFC metadata, read but unmapped, or absent.
    material_source: str = MATERIAL_SOURCE_ABSENT
    #: CONFIDENCE_* — how far material_a may be trusted as a reading.
    material_confidence: str = CONFIDENCE_NONE
    #: ENVIRONMENT_SOURCE_* — inferred from spatial names, or the indoor default.
    environment_source: str = ENVIRONMENT_SOURCE_DEFAULT
    #: CONFIDENCE_* — how far location_tag may be trusted as a reading.
    environment_confidence: str = CONFIDENCE_LOW

    # --- Hydraulics -------------------------------------------------------
    # The three inputs MC-001 scores flow, temperature and stagnation from.
    # Every one is Optional and defaults to None, which is load-bearing: the
    # pre-flight gate in phase_6c distinguishes "absent" from "zero", and 0.0
    # m/s is not a missing velocity but the worst one (FV0_STAGNANT, risk 1.0).
    # A default of 0.0 here would silently score every element that carries no
    # property set as stagnant, which is the exact failure the gate was added
    # to stop. Anything this parser cannot read stays None.
    #: Flow velocity in m/s, or None when no property set stated one.
    flow_velocity_ms: Optional[float] = None
    #: Operating temperature in Celsius, or None.
    operating_temp_c: Optional[float] = None
    #: Dead-leg length in metres, or None. 0.0 means "measured, and it is a
    #: through-flow element" — a different fact from None.
    dead_leg_length_m: Optional[float] = None
    #: HYDRAULIC_SOURCE_* — read from an IFC property set, or absent.
    velocity_source: str = HYDRAULIC_SOURCE_ABSENT
    #: HYDRAULIC_SOURCE_* — read from an IFC property set, or absent.
    temperature_source: str = HYDRAULIC_SOURCE_ABSENT
    #: HYDRAULIC_SOURCE_* — read from an IFC property set, or absent.
    dead_leg_source: str = HYDRAULIC_SOURCE_ABSENT


# Mapping from IFC type to plain English service category
IFC_SERVICE_LABELS = {
    "IfcPipeSegment": "Pipework",
    "IfcFlowSegment": "Flow segment",
    "IfcPipeFitting": "Pipe fitting",
    "IfcFlowFitting": "Flow fitting",
    "IfcValve": "Valve",
    "IfcPump": "Pump",
    "IfcHeatExchanger": "Heat exchanger",
    "IfcDistributionElement": "Distribution element",
    "IfcMember": "Structural member",
    "IfcPlate": "Structural plate",
    "IfcFastener": "Fastener / fixing",
    "IfcCableSegment": "Cable",
    "IfcDuctSegment": "Ductwork",
    "IfcDuctFitting": "Duct fitting",
}

# Infer joint type from IFC element type
IFC_TO_JOINT = {
    "IfcPipeFitting": "JT-001",  # Flanged connections most common
    "IfcFlowFitting": "JT-001",
    "IfcValve": "JT-013",
    "IfcFastener": "JT-010",
    "IfcMember": "JT-005",
    "IfcPlate": "JT-014",
    "IfcHeatExchanger": "JT-009",
    "IfcPipeSegment": "JT-012",  # Pipe clamp connection
    "IfcFlowSegment": "JT-012",
}

# Space type → environment class mapping
SPACE_TO_ENV = {
    "pool": "swimming_pool",
    "swimming": "swimming_pool",
    "plant": "interior_conditioned",
    "riser": "interior_conditioned",
    "mechanical": "interior_conditioned",
    "roof": "urban_exterior",
    "facade": "coastal",
    "external": "urban_exterior",
    "coastal": "coastal",
    "marine": "marine_splash",
    "industrial": "industrial",
    "office": "interior_dry",
    "retail": "interior_dry",
    "residential": "interior_dry",
}


def get_material_name(element, ifc_model) -> str:
    """Extract primary material name from an IFC element."""
    try:
        mats = ifcopenshell.util.element.get_materials(element)
        if mats:
            return mats[0].Name if hasattr(mats[0], "Name") else str(mats[0])
    except Exception:
        pass

    # Fallback: check material associations directly
    for rel in getattr(element, "HasAssociations", []):
        if rel.is_a("IfcRelAssociatesMaterial"):
            mat = rel.RelatingMaterial
            if hasattr(mat, "Name"):
                return mat.Name
            if hasattr(mat, "ForLayerSet"):
                layers = mat.ForLayerSet.MaterialLayers
                if layers:
                    return layers[0].Material.Name
    return "Unknown"


def normalise_material_name(raw: str) -> str:
    """Map free-text material names from IFC to BIMGUARD AI material keys."""
    return resolve_material_name(raw)[0]


def resolve_material_name(raw: str) -> tuple[str, str, str]:
    """Map an IFC material string to a key, and say where the key came from.

    :func:`normalise_material_name` answers only "what material", which cannot
    distinguish a grade read off the model from free text that matched nothing
    and was passed through unchanged. Both reach the engines as a string; only
    one is a reading.

    Args:
        raw: The material name as the IFC carried it, or ``"Unknown"`` when
            :func:`get_material_name` found none.

    Returns:
        ``(material_key, source, confidence)`` — source is one of the
        ``MATERIAL_SOURCE_*`` constants, confidence one of ``CONFIDENCE_*``.
    """
    text = (raw or "").strip()
    if not text or text.lower() == "unknown":
        return "Unknown", MATERIAL_SOURCE_ABSENT, CONFIDENCE_NONE

    key = _match_material_key(text)
    if key is not None:
        return key, MATERIAL_SOURCE_IFC, CONFIDENCE_HIGH

    # Passed through as free text. The value is genuinely from the IFC, so the
    # source says so, but no engine will resolve it and the confidence must not
    # claim otherwise.
    return text.replace(" ", "_")[:30], MATERIAL_SOURCE_UNMAPPED, CONFIDENCE_LOW


def _spaced(raw: str) -> str:
    """Lower-case ``raw`` with separators and camelCase boundaries as spaces.

    ``"CarbonSteel"`` -> ``"carbon steel"``, ``"Ductile_Iron"`` -> ``"ductile
    iron"``, ``"SS_316_passive"`` -> ``"ss 316 passive"``. Digits are treated as
    their own run so ``"Grade316L"`` separates too.
    """
    text = re.sub(r"[_\-/]+", " ", raw or "")
    text = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", text)
    text = re.sub(r"(?<=[A-Za-z])(?=\d)|(?<=\d)(?=[A-Za-z])", " ", text)
    return re.sub(r"\s+", " ", text).lower().strip()


def _match_material_key(raw: str) -> Optional[str]:
    """Return the BIMGUARD material key ``raw`` names, or ``None`` for no match.

    The comparisons below are written as English phrases -- ``"carbon steel"``,
    ``"cast iron"`` -- but IFC authoring tools write the same materials without
    the space: ``"CarbonSteel"``, ``"Ductile_Iron"``. Those failed every test
    and fell through as unrecognised, which since the pre-flight gate landed
    means a real, named material is refused as unresolvable. So the string is
    normalised to spaced lower case first: separators become spaces, and a
    camelCase boundary gets one inserted.
    """
    r = _spaced(raw)
    if "316" in r or "1.4401" in r:
        return "SS_316_passive"
    if "304" in r or "1.4301" in r:
        return "SS_304_passive"
    if "duplex" in r and ("2507" in r or "super" in r):
        return "SS_super_duplex_2507"
    if "duplex" in r or "2205" in r:
        return "SS_duplex_2205"
    if "copper" in r or "cu " in r:
        return "Copper"
    if "brass" in r:
        return "Brass_naval"
    if "galvan" in r or "hdg" in r or "hot dip" in r:
        return "Galvanized_steel"
    if "alumin" in r or "aluminum" in r:
        return "Aluminum_alloy_6063"
    if "carbon steel" in r or "mild steel" in r or "s275" in r or "s355" in r:
        return "Carbon_steel_mild"
    if "cast iron" in r:
        return "Cast_iron"
    if "titanium" in r:
        return "Titanium"
    if "zinc" in r:
        return "Zinc"
    if "lead" in r:
        return "Lead"
    # No match. The caller decides what to do with the raw string; returning it
    # from here would make an unmapped material indistinguishable from a
    # recognised one, which is the distinction this split exists to keep.
    return None


def classify_environment_from_space(space_name: str, floor: str) -> str:
    """Infer environment class from space name and floor tag."""
    return resolve_environment_from_space(space_name, floor)[0]


def resolve_environment_from_space(space_name: str, floor: str) -> tuple[str, str, str]:
    """Infer an environment class, and say whether it was inferred or assumed.

    The two outcomes are not comparable evidence. A keyword match means the
    model named a space this module recognises; the fallback means it named
    nothing recognisable and :data:`DEFAULT_ENVIRONMENT` was assumed. Both
    arrive at the engines as ``zone_category``, where the difference is no
    longer visible — hence the source.

    Returns:
        ``(environment_class, source, confidence)`` — source is one of the
        ``ENVIRONMENT_SOURCE_*`` constants, confidence one of ``CONFIDENCE_*``.
    """
    combined = (space_name + " " + floor).lower()
    for keyword, env in SPACE_TO_ENV.items():
        if keyword in combined:
            # Medium, not high: a name matched a keyword, which is weaker
            # evidence than an IFC property stating the class outright.
            return env, ENVIRONMENT_SOURCE_SPATIAL, CONFIDENCE_MEDIUM
    return DEFAULT_ENVIRONMENT, ENVIRONMENT_SOURCE_DEFAULT, CONFIDENCE_LOW


def get_element_position(element, ifc_model) -> tuple:
    """Extract (x, y, z) position in metres from IFC element placement."""
    try:
        mat = ifcopenshell.util.placement.get_local_placement(element.ObjectPlacement)
        return (round(float(mat[0][3]), 2), round(float(mat[1][3]), 2), round(float(mat[2][3]), 2))
    except Exception:
        return (0.0, 0.0, 0.0)


def get_floor_name(element, ifc_model) -> str:
    """Find the storey this element belongs to."""
    for rel in getattr(element, "ContainedInStructure", []):
        container = rel.RelatingStructure
        if container.is_a("IfcBuildingStorey"):
            return container.Name or "Unknown floor"
    return "Unknown floor"


# ---------------------------------------------------------------------------
# Hydraulics
# ---------------------------------------------------------------------------
# Property names are matched against every Pset on the element, flattened, so
# an authoring tool's choice of property-set name does not matter. That mirrors
# piping_producer._all_property_values, which already reads the temperature
# this way; reading the same value by a different route would let the two
# producers disagree about the same element.
#
# The temperature keys are piping_producer.TEMPERATURE_PROPERTY_KEYS verbatim
# rather than a second list that has to be kept in step with it.

#: Property names an authoring tool may use for flow velocity, in m/s. IFC4
#: defines no flow-velocity property for a pipe segment, so there is no
#: buildingSMART name to prefer here; these are the conventions seen in
#: practice plus the one this repo's generator writes.
VELOCITY_PROPERTY_KEYS = (
    "FlowVelocity",
    "Velocity",
    "FluidVelocity",
    "DesignFlowVelocity",
    "AverageVelocity",
)

#: Property names for the operating temperature, in Celsius. Shared with the
#: PipingElement path so both read the same property.
TEMPERATURE_PROPERTY_KEYS = (
    "OperatingTemperature",
    "WorkingTemperature",
    "FluidTemperature",
    "DesignTemperature",
    "MediumTemperature",
)

#: Property names for a dead-leg length, in metres.
DEAD_LEG_PROPERTY_KEYS = (
    "DeadLegLength",
    "StagnationLength",
    "DeadLegLengthM",
)

#: Boolean property names that flag an element as a dead leg without giving a
#: length. See _read_hydraulics for why a bare True is not turned into a length.
DEAD_LEG_FLAG_KEYS = (
    "IsDeadLeg",
    "Stagnant",
    "IsStagnant",
)


def _flatten_psets(element) -> dict:
    """Flatten every property set on an element into one dict.

    Both the bare property name and ``"Pset.Property"`` are keyed, so a caller
    can match loosely or exactly. Returns ``{}`` when the psets cannot be read,
    rather than propagating: an unreadable pset is an absent value, and the
    caller's provenance already says so.
    """
    try:
        psets = ifcopenshell.util.element.get_psets(element) or {}
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


def _first_number(properties: dict, keys: tuple[str, ...]) -> Optional[float]:
    """Return the first key holding a finite, non-boolean number, or None."""
    for key in keys:
        value = properties.get(key)
        if value is None or isinstance(value, bool):
            continue
        try:
            number = float(value)
        except (TypeError, ValueError):
            continue
        if number == number and abs(number) != float("inf"):  # finite
            return number
    return None


def _first_bool(properties: dict, keys: tuple[str, ...]) -> Optional[bool]:
    """Return the first key holding a boolean, or None."""
    for key in keys:
        value = properties.get(key)
        if isinstance(value, bool):
            return value
    return None


def read_hydraulics(element) -> dict:
    """Read the three MC-001 hydraulic inputs off an element's property sets.

    Args:
        element: The IFC entity to read.

    Returns:
        A dict of the six ``ServiceElement`` hydraulic fields, ready to splat
        into the constructor. A value absent from every property set is
        ``None`` with its ``*_source`` set to :data:`HYDRAULIC_SOURCE_ABSENT`;
        it is never defaulted to a number. See the note on the dataclass
        fields for why that matters.

        A dead-leg *flag* of ``True`` with no length is reported as a source
        reading with a ``None`` length: the element is known to be a dead leg,
        but MC-001 classifies dead legs by length-to-diameter ratio and there
        is no honest length to give it. Inventing one would be the substitution
        the pre-flight gate exists to prevent. A flag of ``False`` does yield
        0.0, because "not a dead leg" is a measurement of through flow —
        exactly what DL0_THROUGH means.
    """
    properties = _flatten_psets(element)

    velocity = _first_number(properties, VELOCITY_PROPERTY_KEYS)
    temperature = _first_number(properties, TEMPERATURE_PROPERTY_KEYS)

    dead_leg = _first_number(properties, DEAD_LEG_PROPERTY_KEYS)
    dead_leg_source = (
        HYDRAULIC_SOURCE_IFC if dead_leg is not None else HYDRAULIC_SOURCE_ABSENT
    )
    if dead_leg is None:
        flag = _first_bool(properties, DEAD_LEG_FLAG_KEYS)
        if flag is False:
            dead_leg, dead_leg_source = 0.0, HYDRAULIC_SOURCE_IFC
        elif flag is True:
            dead_leg_source = HYDRAULIC_SOURCE_IFC

    return {
        "flow_velocity_ms": velocity,
        "operating_temp_c": temperature,
        "dead_leg_length_m": dead_leg,
        "velocity_source": (
            HYDRAULIC_SOURCE_IFC if velocity is not None else HYDRAULIC_SOURCE_ABSENT
        ),
        "temperature_source": (
            HYDRAULIC_SOURCE_IFC if temperature is not None else HYDRAULIC_SOURCE_ABSENT
        ),
        "dead_leg_source": dead_leg_source,
    }


def get_system_name(element, ifc_model) -> str:
    """Find MEP system this element belongs to."""
    for rel in ifc_model.get_inverse(element):
        if rel.is_a("IfcRelAssignsToGroup"):
            group = rel.RelatingGroup
            if group.is_a("IfcSystem") or group.is_a("IfcDistributionSystem"):
                return group.Name or "Unnamed system"
    return "Unassigned"


def parse_ifc_model(model) -> list[ServiceElement]:
    """Parse an already opened IFC model into service elements.

    One entity yields exactly one ServiceElement. IFC classes are a hierarchy —
    an IfcPipeSegment is also an IfcFlowSegment and an IfcDistributionElement —
    so ``model.by_type()`` returns the same entity once per matching class in
    ``IFC_SERVICE_LABELS``. Without the GlobalId guard below, a three-entity
    model produced eight rows: inflated element counts, the corrosion engines
    run repeatedly over one element, and duplicate issues raised against a
    single GlobalId.

    ``IFC_SERVICE_LABELS`` is ordered specific to general and iterated in
    order, so first-occurrence-wins keeps the most specific class: a pipe
    segment is reported as IfcPipeSegment, not IfcDistributionElement.
    """
    elements = []
    # A GlobalId identifies exactly one entity in IFC, so a repeat is always
    # the same element arriving under a broader class.
    seen_guids: set[str] = set()

    target_types = list(IFC_SERVICE_LABELS.keys())

    for ifc_type in target_types:
        # IFC2X3/IFC4 differ for some MEP classes; skip unknown classes safely.
        try:
            typed_elements = model.by_type(ifc_type)
        except Exception:
            continue

        for el in typed_elements:
            guid = str(getattr(el, "GlobalId", "") or "").strip()
            if guid:
                if guid in seen_guids:
                    continue
                seen_guids.add(guid)
            mat_a_raw = get_material_name(el, model)
            mat_a, mat_a_source, mat_a_confidence = resolve_material_name(mat_a_raw)
            mat_b = None  # Second material (e.g. bracket material) — extend via Pset

            floor = get_floor_name(el, model)
            system = get_system_name(el, model)

            # Try to get space from containing zone or description
            space_name = ""
            for rel in getattr(el, "ContainedInStructure", []):
                space_name = getattr(rel.RelatingStructure, "Name", "") or ""

            env, env_source, env_confidence = resolve_environment_from_space(
                space_name + " " + (el.Name or ""), floor
            )
            joint = IFC_TO_JOINT.get(ifc_type, "JT-005")
            pos = get_element_position(el, model)

            # Estimate areas (extend with actual geometry extraction)
            anode_area = 0.05
            cathode_area = 0.50

            elements.append(
                ServiceElement(
                    guid=el.GlobalId,
                    name=el.Name or f"{ifc_type}_{el.id()}",
                    ifc_type=ifc_type,
                    description=IFC_SERVICE_LABELS.get(ifc_type, ifc_type),
                    material_a=mat_a,
                    material_b=mat_b,
                    location_tag=env,
                    floor=floor,
                    system=system,
                    joint_type=joint,
                    anode_area_m2=anode_area,
                    cathode_area_m2=cathode_area,
                    position=pos,
                    length_m=1.0,
                    material_source=mat_a_source,
                    material_confidence=mat_a_confidence,
                    environment_source=env_source,
                    environment_confidence=env_confidence,
                    **read_hydraulics(el),
                )
            )

    return elements


def get_schema_compatibility_note(model) -> str | None:
    """Return a short note when the IFC schema omits MEP classes used by this parser."""
    schema = str(getattr(model, "schema", "") or "").upper()
    if schema.startswith("IFC2X3"):
        return (
            "Schema compatibility: this IFC2X3 model may skip IFC4 MEP classes such as "
            "IfcPipeSegment; equivalent flow elements are parsed where available."
        )
    return None


def parse_ifc(ifc_path: str) -> list[ServiceElement]:
    """
    Backward-compatible wrapper that opens an IFC file and parses service elements.

    Args:
        ifc_path: Path to .ifc file (IFC 2x3 or IFC4)

    Returns:
        List of ServiceElement dataclass instances
    """
    model = ifcopenshell.open(ifc_path)
    return parse_ifc_model(model)


def generate_synthetic_elements(n: int = 25) -> list[ServiceElement]:
    """
    Generates realistic synthetic MEP service elements for demo use
    when no IFC file is available. Covers a range of risk levels,
    environments, and service types — matching real building scenarios.
    """
    import random

    random.seed(42)

    scenarios = [
        # (name, ifc_type, mat_a, mat_b, env, joint, floor, system, aa, ca, pos)
        (
            "CHW Supply Pipe",
            "IfcPipeSegment",
            "SS_316_passive",
            "Galvanized_steel",
            "interior_conditioned",
            "JT-012",
            "B1 Plant Room",
            "Chilled Water",
            0.05,
            0.50,
            (10, 5, 0),
        ),
        (
            "HWS Return Pipe",
            "IfcPipeSegment",
            "Copper",
            "Galvanized_steel",
            "interior_conditioned",
            "JT-012",
            "B1 Plant Room",
            "Hot Water Services",
            0.10,
            0.40,
            (12, 5, 0),
        ),
        (
            "Pool Heating Pipe",
            "IfcPipeSegment",
            "SS_316_passive",
            "SS_316_passive",
            "swimming_pool",
            "JT-001",
            "Pool Level",
            "Pool Heating",
            0.08,
            0.08,
            (5, 20, 0),
        ),
        (
            "Pool Plant Flange",
            "IfcPipeFitting",
            "SS_316_passive",
            None,
            "swimming_pool",
            "JT-001",
            "Pool Level",
            "Pool Heating",
            0.02,
            0.02,
            (5, 22, 0),
        ),
        (
            "Coastal Facade Fix",
            "IfcFastener",
            "Aluminum_alloy_6063",
            "SS_316_passive",
            "coastal",
            "JT-010",
            "Level 3",
            "Facade",
            0.002,
            0.85,
            (30, 0, 9),
        ),
        (
            "Roof Drainage Fix",
            "IfcFastener",
            "Galvanized_steel",
            "SS_316_passive",
            "urban_exterior",
            "JT-010",
            "Roof",
            "Drainage",
            0.03,
            0.50,
            (15, 15, 12),
        ),
        (
            "Structural Bracket",
            "IfcMember",
            "Carbon_steel_mild",
            "SS_316_passive",
            "urban_exterior",
            "JT-005",
            "Level 1",
            "Structure",
            0.15,
            0.40,
            (8, 8, 3),
        ),
        (
            "Cold Water Feed",
            "IfcPipeSegment",
            "Copper",
            "Cast_iron",
            "interior_dry",
            "JT-003",
            "Ground Floor",
            "CWS",
            0.50,
            0.20,
            (4, 4, 0),
        ),
        (
            "SS Pipe Clamp",
            "IfcPipeSegment",
            "SS_316_passive",
            None,
            "interior_conditioned",
            "JT-011",
            "B1 Plant Room",
            "Chilled Water",
            0.10,
            0.10,
            (11, 6, 0),
        ),
        (
            "Unlined Pipe Clamp",
            "IfcPipeSegment",
            "SS_316_passive",
            "Carbon_steel_mild",
            "coastal",
            "JT-012",
            "Roof",
            "External Services",
            0.05,
            0.20,
            (20, 20, 12),
        ),
        (
            "HX Tube Joint",
            "IfcHeatExchanger",
            "SS_316_passive",
            None,
            "swimming_pool",
            "JT-009",
            "Pool Level",
            "Pool Heating",
            0.01,
            0.50,
            (6, 21, 0),
        ),
        (
            "Drainage Transition",
            "IfcPipeFitting",
            "Cast_iron",
            "Copper",
            "interior_dry",
            "JT-002",
            "Ground Floor",
            "Drainage",
            0.50,
            0.20,
            (3, 3, 0),
        ),
        (
            "Gas Pipe Riser",
            "IfcPipeSegment",
            "Carbon_steel_mild",
            "Galvanized_steel",
            "interior_conditioned",
            "JT-003",
            "Riser Shaft",
            "Gas",
            0.30,
            0.30,
            (7, 7, 6),
        ),
        (
            "Marine Plant Pipe",
            "IfcPipeSegment",
            "SS_316_passive",
            None,
            "marine_splash",
            "JT-001",
            "Ground Floor",
            "Marine Services",
            0.10,
            0.10,
            (25, 5, 0),
        ),
        (
            "Electrical Tray",
            "IfcDistributionElement",
            "Aluminum_alloy_6063",
            "Carbon_steel_mild",
            "interior_conditioned",
            "JT-005",
            "Level 1",
            "Electrical",
            0.80,
            0.20,
            (9, 2, 3),
        ),
        (
            "Vent Duct Bracket",
            "IfcDuctSegment",
            "Galvanized_steel",
            "Carbon_steel_mild",
            "interior_dry",
            "JT-005",
            "Level 2",
            "Ventilation",
            0.60,
            0.30,
            (6, 10, 6),
        ),
        (
            "Condenser Pipe",
            "IfcPipeSegment",
            "Copper",
            "Aluminum_alloy_6063",
            "urban_exterior",
            "JT-012",
            "Roof",
            "Cooling",
            0.08,
            0.30,
            (18, 18, 12),
        ),
        (
            "Fix Plate Coastal",
            "IfcPlate",
            "SS_316_passive",
            None,
            "coastal",
            "JT-014",
            "Level 3",
            "Facade",
            0.02,
            0.02,
            (31, 1, 9),
        ),
        (
            "Sprinkler Header",
            "IfcPipeSegment",
            "Carbon_steel_mild",
            "SS_316_passive",
            "interior_conditioned",
            "JT-001",
            "Level 1",
            "Fire Protection",
            0.10,
            0.50,
            (10, 10, 3),
        ),
        (
            "Threaded SS Riser",
            "IfcPipeSegment",
            "SS_304_passive",
            None,
            "interior_conditioned",
            "JT-003",
            "Riser Shaft",
            "Domestic Hot Water",
            0.05,
            0.05,
            (7, 8, 3),
        ),
        (
            "Pool Valve Body",
            "IfcValve",
            "SS_304_passive",
            None,
            "swimming_pool",
            "JT-013",
            "Pool Level",
            "Pool Heating",
            0.03,
            0.03,
            (5, 23, 0),
        ),
        (
            "Industrial Flange",
            "IfcPipeFitting",
            "SS_316_passive",
            None,
            "industrial",
            "JT-001",
            "Ground Floor",
            "Process",
            0.04,
            0.04,
            (22, 8, 0),
        ),
        (
            "Lead Flashing Fix",
            "IfcFastener",
            "Aluminum_alloy_6063",
            "Lead",
            "urban_exterior",
            "JT-010",
            "Roof",
            "Weathering",
            0.30,
            0.10,
            (14, 14, 12),
        ),
        (
            "Bronze Valve",
            "IfcValve",
            "Bronze",
            "Copper",
            "interior_dry",
            "JT-013",
            "Ground Floor",
            "CWS",
            0.05,
            0.30,
            (3, 5, 0),
        ),
        (
            "Stainless Header",
            "IfcPipeSegment",
            "SS_316_passive",
            "SS_316_passive",
            "urban_exterior",
            "JT-002",
            "Roof",
            "Cooling",
            0.20,
            0.20,
            (19, 19, 12),
        ),
    ]

    elements = []
    for i, sc in enumerate(scenarios[:n]):
        name, ifc_type, mat_a, mat_b, env, joint, floor, system, aa, ca, pos = sc
        elements.append(
            ServiceElement(
                # A real IfcGuid, not a sliced UUID. BCF's IfcGuid type is
                # 22 characters drawn from [0-9A-Za-z_$]; truncating a UUID
                # string hits the length but keeps the hyphens, so every
                # viewpoint built from synthetic elements failed schema
                # validation. ifcopenshell.guid.compress does the real
                # base64 encoding IFC specifies.
                guid=ifcopenshell.guid.compress(uuid.uuid4().hex),
                name=name,
                ifc_type=ifc_type,
                description=IFC_SERVICE_LABELS.get(ifc_type, ifc_type),
                material_a=mat_a,
                material_b=mat_b or mat_a,
                location_tag=env,
                floor=floor,
                system=system,
                joint_type=joint,
                anode_area_m2=aa,
                cathode_area_m2=ca,
                position=pos,
                length_m=round(random.uniform(0.5, 8.0), 1),
                # Authored here, not read from a model. The value is exactly
                # what the scenario declares, so the confidence is high; the
                # source is what stops a demo finding from being mistaken for
                # an assessment of a real building.
                material_source=SOURCE_SYNTHETIC,
                material_confidence=CONFIDENCE_HIGH,
                environment_source=SOURCE_SYNTHETIC,
                environment_confidence=CONFIDENCE_HIGH,
            )
        )
    return elements


def extract_ifc_header_iso_metadata(ifc_model) -> dict:
    """Extract IfcProject and IfcDocumentInformation header attributes from an opened IFC model or file path."""
    from pathlib import Path
    if isinstance(ifc_model, (str, Path)):
        try:
            ifc_model = ifcopenshell.open(str(ifc_model))
        except Exception:
            return {}

    header = {}
    try:
        projects = ifc_model.by_type("IfcProject")
        if projects:
            p = projects[0]
            header["project_name"] = getattr(p, "Name", "") or ""
            header["project_description"] = getattr(p, "Description", "") or ""
            header["project_long_name"] = getattr(p, "LongName", "") or ""

        doc_infos = ifc_model.by_type("IfcDocumentInformation")
        if doc_infos:
            d = doc_infos[0]
            header["document_id"] = getattr(d, "Identification", "") or getattr(d, "DocumentId", "") or ""
            header["document_name"] = getattr(d, "Name", "") or ""
            header["document_revision"] = getattr(d, "Revision", "") or ""
            header["document_status"] = getattr(d, "Status", "") or ""
    except Exception:
        pass

    return header

