"""Seismic restraint inputs: mass, coefficient, flexible couplings, detail flags.

The bracing rules need six things the model does not hand over directly. Each
is resolved here, and each answers ``None`` when it cannot be resolved:

    "How heavy is this component?"            -> :func:`element_mass_kg`
    "What seismic coefficient governs?"       -> :func:`seismic_force_coefficient`
    "Is a flexible coupling near the brace?"  -> :func:`nearest_flexible_coupling_mm`
    "Do the details prevent rod bending?"     -> :func:`restraint_flag`
    "By how much may spacing be extended?"    -> :func:`spacing_extension_multiplier`
    "Are there dual structural supports?"     -> :func:`restraint_flag`

:func:`seismic_context` assembles all six for one element, in the shape
``extract_for_compliance`` attaches to an element record -- the same
arrangement ``ifc_penetrations`` and ``ifc_supports`` already use.

MISSING IS NOT FALSE, AND NOT ZERO

Every function is tri-state. A boolean is ``True``, ``False``, or ``None`` for
"the model does not say", and the three are never collapsed. The distinction is
not academic here: ``details_prevent_rod_bending`` and
``has_dual_structural_supports`` both *relax* a rule when true, so a ``False``
invented out of silence would fail compliant work, while a ``True`` invented
out of silence would pass non-compliant work. Both are wrong; only ``None``
says what actually happened, and the comparator turns that into UNDETERMINED,
which neither narrows scope nor grants a waiver.

The same applies to the numbers. A mass of ``0.0`` kg would zero out a seismic
force and pass every restraint rule trivially; a flexible-coupling distance of
``0.0`` mm would earn an exemption the model never evidenced. Neither is ever
returned in place of "unknown".

WHAT "AUTHORED" BUYS, AND WHAT IT DOES NOT

Mass has two routes and they are not equal. An explicit ``Qto_*.NetWeight`` is
data someone wrote down; density times volume is arithmetic this module did.
The second is genuinely useful -- most models carry a material and a solid, and
almost none carry a weight -- but a rule reading it should know which it got,
so :func:`element_mass_kg` returns the route in its detail and marks the
derived one ``is_estimate``. It is a fallback, never a substitute.

WHY EVERY BRACE HAS TO CLEAR THE LIMIT

Where a value is aggregated over several supports, the WORST one governs, for
the same reason ``ifc_supports`` reports the longest rod and the largest gap:
an exemption written as "flexible couplings within 300 mm" is earned only when
every brace has one, and a spacing extension is earned only when every support
carries the detail that grants it. Reporting the best case would let one
compliant hanger excuse a run of non-compliant ones.
"""

from __future__ import annotations

import math

from app.logging_config import get_logger

logger = get_logger(__name__)

try:
    import ifcopenshell.util.element

    _IFC_UTIL_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised only without ifcopenshell
    _IFC_UTIL_AVAILABLE = False

try:
    from .ifc_supports import find_supports

    _SUPPORTS_AVAILABLE = True
except ImportError:  # pragma: no cover
    _SUPPORTS_AVAILABLE = False

Vec3 = tuple[float, float, float]


# ── Tri-state value parsing ───────────────────────────────────────────────────

#: Tokens an exporter may write for a boolean it means as true. IFC's own
#: IfcBoolean arrives as a Python bool and never reaches these, but Revit and
#: several IFC exporters write shared parameters as IfcLabel text, and a
#: "Yes" discarded as unreadable is a fact about the model thrown away.
_TRUE_TOKENS = frozenset(
    {"true", "t", ".t.", "yes", "y", "1", "on", "provided", "present", "complies"}
)
_FALSE_TOKENS = frozenset(
    {"false", "f", ".f.", "no", "n", "0", "off", "notprovided", "absent", "none"}
)


def as_tristate_bool(raw) -> bool | None:
    """Return True/False for a value that states one, else ``None``.

    ``None`` covers both "nothing was authored" and "something was authored
    that this cannot read". The second is deliberately not an error: an
    unrecognised token is a value whose meaning is unknown, which is exactly
    what ``None`` is for, and guessing at it would rest a verdict on a string
    nobody validated.
    """
    if isinstance(raw, bool):
        return raw
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        # 1 and 0 are the only numbers that state a boolean. 2 is not "very true".
        if raw == 1:
            return True
        if raw == 0:
            return False
        return None
    token = str(raw).strip().casefold().replace(" ", "").replace("_", "")
    if token in _TRUE_TOKENS:
        return True
    if token in _FALSE_TOKENS:
        return False
    return None


def as_float(raw) -> float | None:
    """Return a finite float, or ``None``.

    Booleans are rejected rather than read as 1.0 / 0.0: ``True`` in a numeric
    slot is a mis-typed property, not the number one, and converting it
    silently would put a multiplier of 1.0 on a rule that was never given one.
    """
    if isinstance(raw, bool) or raw is None:
        return None
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    if math.isnan(value) or math.isinf(value):
        return None
    return value


def _normalize(name) -> str:
    """Fold a property name for comparison: case, spaces and separators away."""
    return (
        str(name or "").strip().casefold().replace(" ", "").replace("_", "").replace("-", "")
    )


# ── Property-set scanning ─────────────────────────────────────────────────────


def _psets_of(entity) -> dict:
    """Return every property and quantity set on one entity, or ``{}``.

    ``psets_only=False`` so Qto sets come through too -- ``Qto_*.NetWeight``
    and ``Qto_*.NetVolume`` are where authored mass and volume actually live,
    and a Pset-only read would miss both.
    """
    if entity is None or not _IFC_UTIL_AVAILABLE:
        return {}
    try:
        return ifcopenshell.util.element.get_psets(entity, psets_only=False) or {}
    except Exception as exc:
        logger.debug("Pset read failed for %s: %s", entity, exc)
        return {}


def _psets_via_relationships(entity) -> dict:
    """Read property sets straight off ``IsDefinedBy``.

    ``ifcopenshell.util.element.get_psets`` is written for products; IfcProject
    is an IfcContext in IFC4 and does not reliably come back through it. The
    seismic coefficient is authored on exactly those entities, so the
    relationship is walked directly rather than reported as absent.
    """
    collected: dict[str, dict] = {}
    try:
        for rel in getattr(entity, "IsDefinedBy", None) or []:
            definition = getattr(rel, "RelatingPropertyDefinition", None)
            if definition is None:
                continue
            props: dict = {}
            for prop in getattr(definition, "HasProperties", None) or []:
                nominal = getattr(prop, "NominalValue", None)
                value = getattr(nominal, "wrappedValue", None) if nominal is not None else None
                if value is None:
                    continue
                props[str(getattr(prop, "Name", "") or "")] = value
            if props:
                collected[str(getattr(definition, "Name", "") or "Unnamed")] = props
    except Exception as exc:
        logger.debug("Relationship pset read failed for %s: %s", entity, exc)
    return collected


def find_property(entity, names: tuple[str, ...], include_type: bool = True):
    """Return ``(value, "Pset.Property")`` for the first name that is present.

    Names are matched case- and separator-insensitively, so a rule asking for
    ``SpacingExtensionMultiplier`` also finds ``Spacing Extension Multiplier``
    and ``spacing_extension_multiplier``. Exporters disagree about all three
    and the difference carries no meaning.

    The instance is searched before the type, because a value set on one hanger
    overrides whatever its family says.

    Returns ``(None, None)`` when nothing matches -- including when a matching
    property is present but empty, since an empty string states nothing.
    """
    wanted = {_normalize(n) for n in names}

    instance_psets = _psets_of(entity)
    if not instance_psets:
        instance_psets = _psets_via_relationships(entity)
    sources: list[tuple[str, dict]] = [("", instance_psets)]

    if include_type and _IFC_UTIL_AVAILABLE:
        try:
            entity_type = ifcopenshell.util.element.get_type(entity)
        except Exception:
            entity_type = None
        if entity_type is not None:
            sources.append(("type:", _psets_of(entity_type)))

    for prefix, psets in sources:
        for pset_name, props in (psets or {}).items():
            if not isinstance(props, dict):
                continue
            for prop_name, value in props.items():
                if _normalize(prop_name) not in wanted:
                    continue
                if value is None or (isinstance(value, str) and not value.strip()):
                    continue
                return value, f"{prefix}{pset_name}.{prop_name}"
    return None, None


# ── 1. Mass ───────────────────────────────────────────────────────────────────

#: Property names that state a component's mass outright, in whatever set an
#: exporter put them. ``Qto_*BaseQuantities.NetWeight`` is the IFC-standard
#: home; the rest are Revit shared parameters seen in practice.
#:
#: "Weight" is read as mass, which is a physics abuse the whole construction
#: industry commits: every authoring tool writes kilograms into a field it
#: calls weight. Reading it as newtons would misread every real model.
MASS_PROPERTY_NAMES = (
    "NetWeight",
    "GrossWeight",
    "Mass",
    "NetMass",
    "GrossMass",
    "Weight",
    "TotalWeight",
    "NominalMass",
    "OperatingWeight",
    "SeismicWeight",
)

#: Density property names, checked on the element itself before its material is
#: consulted -- some exporters copy the value onto the element.
DENSITY_PROPERTY_NAMES = (
    "MassDensity",
    "Density",
    "MaterialDensity",
    "BulkDensity",
)

#: Volume quantity names. These are in model length units cubed, NOT m3 -- a
#: millimetre model writes NetVolume in mm3 -- which is why reading them needs
#: the caller's ``unit_scale_mm``.
VOLUME_PROPERTY_NAMES = (
    "NetVolume",
    "GrossVolume",
    "Volume",
)

#: Densities outside this band, in kg/m3, are refused rather than multiplied
#: into a mass. The floor sits below expanded foam (~10) and the ceiling above
#: lead (11340) with room to spare, so every construction material passes. What
#: does not pass is a density authored in g/cm3 (steel as 7.85) or kg/mm3
#: (7.85e-6) -- each wrong by a factor of a thousand or a billion, and each a
#: perfectly plausible-looking number once multiplied by a volume. This module
#: cannot tell which unit was meant, so it declines to guess.
_PLAUSIBLE_DENSITY_KG_M3 = (12.0, 25000.0)


def mass_unit_scale_kg(ifc_file) -> float:
    """Return the model's mass unit expressed in kilograms.

    IFC's SI mass unit is the GRAM, so an unprefixed declaration means grams
    and a model writing ``50.0`` means 50 g, not 50 kg. Defaults to 1.0
    (kilograms) when no mass unit is declared, which is what exporters that
    omit the assignment actually write.
    """
    _PREFIX_FACTORS = {
        "": 1.0,
        "MICRO": 1e-6,
        "MILLI": 1e-3,
        "CENTI": 1e-2,
        "DECI": 1e-1,
        "DECA": 1e1,
        "HECTO": 1e2,
        "KILO": 1e3,
        "MEGA": 1e6,
    }
    if ifc_file is None:
        return 1.0
    try:
        for assignment in ifc_file.by_type("IfcUnitAssignment"):
            for unit in getattr(assignment, "Units", None) or []:
                if "MASSUNIT" not in str(getattr(unit, "UnitType", "") or "").upper():
                    continue
                if unit.is_a("IfcSIUnit"):
                    prefix = str(getattr(unit, "Prefix", "") or "").upper()
                    # GRAM -> kg is 1e-3; the prefix multiplies that.
                    return 1e-3 * _PREFIX_FACTORS.get(prefix, 1.0)
                if unit.is_a("IfcConversionBasedUnit"):
                    name = str(getattr(unit, "Name", "") or "").upper()
                    if "POUND" in name or name in ("LB", "LBM"):
                        return 0.45359237
                    if "TON" in name:
                        return 1000.0
    except Exception as exc:
        logger.debug("Mass unit read failed: %s", exc)
    return 1.0


def _materials_of(element) -> list:
    """Return the IfcMaterial entities associated with an element."""
    if not _IFC_UTIL_AVAILABLE:
        return []
    try:
        material = ifcopenshell.util.element.get_material(element, should_inherit=True)
    except Exception:
        return []
    if material is None:
        return []

    if material.is_a("IfcMaterial"):
        return [material]
    if material.is_a("IfcMaterialLayerSetUsage"):
        material = getattr(material, "ForLayerSet", None)
    if material is None:
        return []

    found: list = []
    for attr in ("MaterialLayers", "MaterialConstituents", "MaterialProfiles", "Materials"):
        for entry in getattr(material, attr, None) or []:
            if entry is None:
                continue
            candidate = entry if entry.is_a("IfcMaterial") else getattr(entry, "Material", None)
            if candidate is not None and candidate not in found:
                found.append(candidate)
    return found


def _density_of_material(material, ifc_file=None) -> float | None:
    """Read MassDensity off an IfcMaterial, across the IFC2X3 and IFC4 shapes."""
    wanted = {_normalize(n) for n in DENSITY_PROPERTY_NAMES}

    # IFC4: IfcMaterial.HasProperties -> IfcMaterialProperties.Properties
    try:
        for properties in getattr(material, "HasProperties", None) or []:
            for prop in getattr(properties, "Properties", None) or []:
                if _normalize(getattr(prop, "Name", "")) not in wanted:
                    continue
                nominal = getattr(prop, "NominalValue", None)
                value = as_float(getattr(nominal, "wrappedValue", None))
                if value is not None:
                    return value
    except Exception as exc:
        logger.debug("IFC4 material property read failed: %s", exc)

    # IFC2X3: IfcGeneralMaterialProperties.MassDensity, found by scanning --
    # that schema gives IfcMaterial no inverse back to its properties.
    if ifc_file is None:
        return None
    try:
        for properties in ifc_file.by_type("IfcGeneralMaterialProperties"):
            if getattr(properties, "Material", None) != material:
                continue
            value = as_float(getattr(properties, "MassDensity", None))
            if value is not None:
                return value
    except Exception as exc:
        logger.debug("IFC2X3 material property read failed: %s", exc)
    return None


def material_density_kg_m3(element, ifc_file=None) -> tuple[float | None, dict]:
    """Return the density of the element's material, with its provenance.

    ``None`` whenever the material is absent, carries no density, or carries
    one outside :data:`_PLAUSIBLE_DENSITY_KG_M3`.

    A LAYERED OR MULTI-MATERIAL ELEMENT IS UNDETERMINED unless every material
    agrees. Volume is known for the element as a whole and never per layer, so
    picking one layer's density would apply it to the others' volume too -- a
    steel pipe in an insulation jacket would weigh whatever the jacket is made
    of. Agreement is the one case where that ambiguity does not arise.
    """
    detail: dict = {"source": None, "material": None, "unit_assumed": "kg/m3"}

    direct, where = find_property(element, DENSITY_PROPERTY_NAMES)
    density = as_float(direct)
    if density is not None:
        detail["source"] = where
    else:
        densities: list[tuple[float, str]] = []
        for material in _materials_of(element):
            value = _density_of_material(material, ifc_file)
            if value is not None:
                densities.append((value, str(getattr(material, "Name", "") or "")))
        if not densities:
            detail["reason"] = "no material density authored"
            return None, detail
        if len({round(v, 6) for v, _ in densities}) > 1:
            detail["reason"] = "materials disagree on density; volume cannot be apportioned"
            detail["material"] = [name for _, name in densities]
            return None, detail
        density = densities[0][0]
        detail["source"] = "material"
        detail["material"] = densities[0][1]

    low, high = _PLAUSIBLE_DENSITY_KG_M3
    if not low <= density <= high:
        detail["reason"] = f"density {density} outside {low}-{high} kg/m3; unit is ambiguous"
        return None, detail

    detail["density_kg_m3"] = round(density, 6)
    return density, detail


def element_volume_m3(
    element, geometry_extractor=None, unit_scale_mm: float = 1.0
) -> tuple[float | None, dict]:
    """Return the element's solid volume in cubic metres, with its provenance.

    An authored quantity is preferred over a meshed one: ``Qto_*.NetVolume`` is
    what the modeller asserted, while the mesh is what this reader managed to
    tessellate, and the two disagree on anything the mesher approximates.
    """
    detail: dict = {"source": None}

    raw, where = find_property(element, VOLUME_PROPERTY_NAMES)
    authored = as_float(raw)
    if authored is not None and authored > 0:
        # IfcVolumeMeasure is in model length units cubed, so a millimetre
        # model states mm3. unit_scale_mm takes model units to mm; dividing by
        # 1000 takes those to metres, and the cube takes the volume with them.
        metres_per_model_unit = unit_scale_mm / 1000.0
        volume = authored * (metres_per_model_unit**3)
        detail["source"] = where
        detail["volume_m3"] = round(volume, 9)
        return volume, detail

    if geometry_extractor is not None:
        try:
            meshed = as_float(geometry_extractor.get_volume_m3(element))
        except Exception as exc:
            logger.debug("Volume mesh failed for %s: %s", element, exc)
            meshed = None
        if meshed is not None and meshed > 0:
            detail["source"] = "geometry"
            detail["volume_m3"] = round(meshed, 9)
            return meshed, detail

    detail["reason"] = "no authored volume quantity and no meshable solid"
    return None, detail


def element_mass_kg(
    element,
    ifc_file=None,
    geometry_extractor=None,
    unit_scale_mm: float = 1.0,
    mass_scale_kg: float | None = None,
) -> tuple[float | None, dict]:
    """Return the element's mass in kilograms, with its provenance.

    Two routes, in descending order of trust:

        ``authored``          a mass or weight quantity someone wrote down
        ``density_x_volume``  material density times solid volume, computed here

    ``detail`` carries ``method``, whatever property or geometry it came from,
    and ``is_estimate`` -- True only on the derived route. A rule that must not
    rest on arithmetic can read that flag and decline; one that can, gets an
    answer for the overwhelming majority of models, which author a material and
    a solid and no weight at all.

    ``None``, never 0.0, when neither route resolves. Zero mass generates zero
    seismic force and would pass every restraint rule ever written.
    """
    detail: dict = {"method": None, "source": None, "is_estimate": None, "unit": "kg"}

    if mass_scale_kg is None:
        mass_scale_kg = mass_unit_scale_kg(ifc_file)

    raw, where = find_property(element, MASS_PROPERTY_NAMES)
    authored = as_float(raw)
    if authored is not None and authored > 0:
        detail["method"] = "authored"
        detail["source"] = where
        detail["is_estimate"] = False
        detail["mass_unit_scale_kg"] = mass_scale_kg
        return round(authored * mass_scale_kg, 4), detail

    density, density_detail = material_density_kg_m3(element, ifc_file)
    volume, volume_detail = element_volume_m3(element, geometry_extractor, unit_scale_mm)
    detail["density"] = density_detail
    detail["volume"] = volume_detail
    if density is None or volume is None:
        detail["reason"] = "no authored mass, and density x volume is incomplete"
        return None, detail

    detail["method"] = "density_x_volume"
    detail["source"] = f"{density_detail.get('source')} x {volume_detail.get('source')}"
    detail["is_estimate"] = True
    return round(density * volume, 4), detail


# ── 2. Seismic force coefficient ──────────────────────────────────────────────

#: Property names for the dimensionless horizontal seismic coefficient applied
#: to a component's weight. Deliberately excludes a bare ``C``: a one-letter
#: property matches far too much -- a concrete grade, a cost code, a Revit mark
#: -- and a wrong coefficient scales every restraint force in the model.
SEISMIC_COEFFICIENT_PROPERTY_NAMES = (
    "SeismicForceCoefficient",
    "SeismicForceCoefficientC",
    "SeismicCoefficient",
    "SeismicCoefficientC",
    "HorizontalSeismicCoefficient",
    "SeismicDesignCoefficient",
    "DesignSeismicCoefficient",
    "Cp",
    "Cph",
)

#: The coefficient is dimensionless and multiplies a weight. Anything above
#: this is almost certainly a percentage (35 meaning 0.35) or a different
#: quantity wearing the same name; anything at or below zero cancels the force
#: entirely. Both are reported as undetermined rather than used.
_PLAUSIBLE_COEFFICIENT = (0.0, 10.0)

#: Where a project-wide coefficient is authored, most specific first. A value
#: on the building governs one on the site, which governs one on the project:
#: the narrower scope is the later decision.
_COEFFICIENT_HOST_CLASSES = ("IfcBuilding", "IfcSite", "IfcProject")


def _validated_coefficient(value: float, where, scope: str, detail: dict):
    """Accept a coefficient only inside :data:`_PLAUSIBLE_COEFFICIENT`."""
    low, high = _PLAUSIBLE_COEFFICIENT
    detail["source"] = where
    detail["scope"] = scope
    if not low < value <= high:
        detail["reason"] = (
            f"coefficient {value} outside ({low}, {high}]; "
            "reads as a percentage or a different quantity"
        )
        return None, detail
    return round(value, 6), detail


def project_seismic_coefficient(ifc_file) -> tuple[float | None, dict]:
    """Return the model-wide seismic coefficient, read from the spatial tree.

    Split out from :func:`seismic_force_coefficient` so a caller running over
    thousands of elements can resolve it once. It is a property of the design,
    not of any component, and re-reading the building's Psets per pipe is pure
    waste.
    """
    detail: dict = {"source": None, "scope": None}
    if ifc_file is None:
        detail["reason"] = "no model to read a project-level coefficient from"
        return None, detail

    for ifc_class in _COEFFICIENT_HOST_CLASSES:
        try:
            hosts = ifc_file.by_type(ifc_class)
        except Exception:
            continue
        for host in hosts or []:
            raw, where = find_property(
                host, SEISMIC_COEFFICIENT_PROPERTY_NAMES, include_type=False
            )
            value = as_float(raw)
            if value is not None:
                return _validated_coefficient(value, where, ifc_class, detail)

    detail["reason"] = "no seismic coefficient authored on the building, site or project"
    return None, detail


def seismic_force_coefficient(
    ifc_file, element=None, project_value: tuple | None = None
) -> tuple[float | None, dict]:
    """Return the governing seismic force coefficient, or ``None``.

    The element is searched first when one is given: a coefficient authored on
    the component itself is a statement about that component and outranks the
    project default. Otherwise the spatial tree is read, via
    :func:`project_seismic_coefficient`.

    ``project_value`` lets a caller supply that already-resolved project result
    rather than have it re-derived per element.

    ``None`` when nothing authors it. There is no default -- 0.0 would delete
    the seismic demand and pass every restraint rule, and any non-zero stand-in
    would be this module inventing a design parameter, which belongs to an
    engineer and a loadings standard rather than to an extractor.
    """
    if element is not None:
        raw, where = find_property(element, SEISMIC_COEFFICIENT_PROPERTY_NAMES)
        value = as_float(raw)
        if value is not None:
            return _validated_coefficient(
                value, where, "element", {"source": None, "scope": None}
            )

    if project_value is not None:
        return project_value
    return project_seismic_coefficient(ifc_file)


# ── 3. Flexible couplings ─────────────────────────────────────────────────────

#: Name fragments identifying a flexible coupling, matched case-insensitively
#: as substrings of Name / ObjectType / Description / Tag.
#:
#: An expansion joint is deliberately absent. It accommodates thermal movement
#: along the pipe axis and is not the seismic detail the exemption turns on;
#: accepting it would waive findings on runs with no flexibility where the
#: standard requires it.
FLEXIBLE_NAME_TOKENS = (
    "flexible coupling",
    "flex coupling",
    "flexcoupling",
    "flexible connector",
    "flex connector",
    "flexible joint",
    "flexible hose",
    "flexible pipe connector",
    "grooved flexible",
)

#: Property names asserting flexibility outright, in whatever set they sit.
FLEXIBLE_PROPERTY_NAMES = (
    "IsFlexible",
    "FlexibleCoupling",
    "IsFlexibleCoupling",
    "FlexibleConnection",
)

#: PredefinedType values that state flexibility in the schema itself, keyed by
#: (class, value), both upper-cased. IfcPipeFittingTypeEnum has no FLEXIBLE
#: member -- the schema simply cannot say it for a fitting -- so a fitting is
#: identified by name or by property instead. IfcPipeSegment *can* say it, and
#: where it does that is the strongest evidence available.
_FLEXIBLE_PREDEFINED = {
    ("IFCPIPESEGMENT", "FLEXIBLESEGMENT"): "IfcPipeSegment.FLEXIBLESEGMENT",
    ("IFCPIPESEGMENTTYPE", "FLEXIBLESEGMENT"): "IfcPipeSegmentType.FLEXIBLESEGMENT",
    ("IFCDUCTSEGMENT", "FLEXIBLESEGMENT"): "IfcDuctSegment.FLEXIBLESEGMENT",
}

#: Classes worth examining. IfcFlowFitting catches IFC2X3 exports that never
#: specialised down to IfcPipeFitting.
_COUPLING_CLASSES = (
    "IfcPipeFitting",
    "IfcPipeSegment",
    "IfcFlowFitting",
    "IfcDiscreteAccessory",
)


def is_flexible_coupling(element) -> tuple[bool, str | None]:
    """Return ``(True, evidence)`` when this element is a flexible coupling.

    Evidence names what decided it, so a reviewer can see whether the answer
    rests on a schema enumeration, an authored property, or a name somebody
    typed. Those are not equally trustworthy and the caller should be able to
    tell them apart.
    """
    try:
        ifc_class = element.is_a().upper()
        predefined = str(getattr(element, "PredefinedType", "") or "").upper()
    except Exception:
        return False, None

    evidence = _FLEXIBLE_PREDEFINED.get((ifc_class, predefined))
    if evidence:
        return True, evidence

    raw, where = find_property(element, FLEXIBLE_PROPERTY_NAMES)
    if as_tristate_bool(raw) is True:
        return True, where

    haystack = " ".join(
        str(getattr(element, attr, "") or "")
        for attr in ("Name", "ObjectType", "Description", "Tag")
    ).casefold()
    for token in FLEXIBLE_NAME_TOKENS:
        if token in haystack:
            return True, f"name:{token}"
    return False, None


def build_flexible_coupling_index(ifc_file) -> list[dict]:
    """Return every flexible coupling in the model, scanned once.

    Scanned once and reused for the same reason the support and interference
    indexes are: the search has no relationship to follow and would otherwise
    re-scan the file for every pipe in it.
    """
    index: list[dict] = []
    if ifc_file is None:
        return index
    seen: set[int] = set()
    for ifc_class in _COUPLING_CLASSES:
        try:
            candidates = ifc_file.by_type(ifc_class)
        except Exception:
            continue
        for candidate in candidates or []:
            try:
                candidate_id = candidate.id()
            except Exception:
                continue
            if candidate_id in seen:
                continue
            matched, evidence = is_flexible_coupling(candidate)
            if not matched:
                continue
            seen.add(candidate_id)
            index.append(
                {
                    "element": candidate,
                    "guid": getattr(candidate, "GlobalId", None),
                    "name": getattr(candidate, "Name", None),
                    "ifc_class": candidate.is_a(),
                    "evidence": evidence,
                }
            )
    return index


def nearest_flexible_coupling_mm(
    reference_point: Vec3 | None,
    coupling_index: list[dict] | None,
    geometry_extractor=None,
) -> tuple[float | None, dict]:
    """Return the distance in mm to the nearest flexible coupling.

    ``None`` in four cases, all of them genuinely unanswerable: the reference
    point will not resolve, there is no geometry to position couplings with,
    the model contains no flexible coupling at all, or no coupling's position
    resolves.

    THE THIRD IS THE ONE WORTH ARGUING ABOUT. An empty index could mean the run
    truly has no coupling, in which case a large distance would be the honest
    answer and the exemption would correctly fail to apply. But it far more
    often means the couplings were never modelled -- they are small parts that
    plenty of exports drop -- and this module cannot tell the two apart.
    ``None`` is the only reading that is safe in both directions: as a waiver
    predicate it declines to excuse the finding, and as a scope predicate it
    declines to drop the element out of the check. A large number would be safe
    as a waiver and unsafe as a narrowing, and nothing here knows which one the
    rule wrote.

    A model that does contain couplings, none of them near this point, is a
    different and perfectly determinate answer: the real distance, however big.
    """
    detail: dict = {"unit": "mm", "coupling_count": len(coupling_index or [])}

    if reference_point is None:
        detail["reason"] = "reference point not resolvable"
        return None, detail
    if not coupling_index:
        detail["reason"] = "no flexible coupling found in the model"
        return None, detail
    if geometry_extractor is None:
        detail["reason"] = "no geometry extractor; coupling positions unavailable"
        return None, detail

    best: float | None = None
    best_entry: dict | None = None
    positioned = 0
    for entry in coupling_index:
        try:
            centre = geometry_extractor.get_centroid_or_none(entry.get("element"))
        except Exception:
            centre = None
        if centre is None:
            continue
        positioned += 1
        distance = math.dist(reference_point, centre)
        if best is None or distance < best:
            best, best_entry = distance, entry

    detail["positioned_coupling_count"] = positioned
    if best is None:
        detail["reason"] = "no flexible coupling could be positioned"
        return None, detail

    detail["nearest_guid"] = (best_entry or {}).get("guid")
    detail["nearest_name"] = (best_entry or {}).get("name")
    detail["nearest_evidence"] = (best_entry or {}).get("evidence")
    return round(best, 4), detail


# ── 4. Restraint detail flags ─────────────────────────────────────────────────

#: The detail that stops a hanger rod bending under lateral load -- a stiffener,
#: a strut, or a rod short enough to restrain itself.
ROD_BENDING_PROPERTY_NAMES = (
    "DetailsPreventRodBending",
    "PreventsRodBending",
    "RodBendingPrevented",
    "RodBendingRestrained",
    "RodStiffened",
    "StiffenedRod",
    "BendingRestraintProvided",
)

#: The factor by which a detail permits the tabulated support spacing to be
#: extended. 1.0 means "no extension", which is a real answer, not a missing one.
SPACING_EXTENSION_PROPERTY_NAMES = (
    "SpacingExtensionMultiplier",
    "SpacingExtensionFactor",
    "SpacingMultiplier",
    "MaximumSpacingMultiplier",
    "SpacingIncreaseFactor",
)

#: Whether the hanger is carried by structure on both sides rather than
#: cantilevered off one.
DUAL_SUPPORT_PROPERTY_NAMES = (
    "HasDualStructuralSupports",
    "DualStructuralSupports",
    "DualStructuralSupport",
    "TwoStructuralSupports",
    "DoubleSidedSupport",
    "SupportedBothSides",
)

#: Which supports the three detailing properties are read from. All three
#: describe a HANGER -- whether its rod can bend, whether it is carried on both
#: sides, what spacing its detail permits -- so a sway brace has no business
#: answering them. Folding braces in would make every braced run undetermined,
#: because a brace is silent on properties that were never about it, and that
#: silence would then outvote hangers that did answer.
#:
#: Kind comes from ``ifc_supports.classify_support``; the classes catch the
#: fasteners and accessories an exporter did not classify as anything.
_DETAILING_SUPPORT_KINDS = frozenset({"HANGER"})
_DETAILING_SUPPORT_CLASSES = ("IfcMechanicalFastener", "IfcDiscreteAccessory")

#: A multiplier below 1 shortens the allowed spacing rather than extending it,
#: and one above this is not a detailing allowance but a typo or a different
#: quantity. Both are undetermined rather than applied.
_PLAUSIBLE_SPACING_MULTIPLIER = (1.0, 4.0)


def restraint_flag(element, names: tuple[str, ...]) -> tuple[bool | None, dict]:
    """Return a tri-state detailing boolean, with where it came from.

    ``None`` means no property in ``names`` was authored, or one was authored
    with a value this cannot read. Both are "the model does not say", which is
    exactly what the caller has to be told: these flags relax rules, so a
    fabricated False fails compliant work and a fabricated True passes work
    that is not.
    """
    raw, where = find_property(element, names)
    if raw is None:
        return None, {"source": None, "reason": "not authored"}
    value = as_tristate_bool(raw)
    if value is None:
        return None, {
            "source": where,
            "raw": raw,
            "reason": "value is not a readable boolean",
        }
    return value, {"source": where, "raw": raw}


def spacing_extension_multiplier(element) -> tuple[float | None, dict]:
    """Return the authored spacing-extension multiplier, or ``None``.

    Bounded by :data:`_PLAUSIBLE_SPACING_MULTIPLIER`. This is the one value
    here that directly loosens a limit, so an out-of-range one is refused
    rather than clamped: clamping 40 to 4.0 would quadruple the permitted
    spacing on the strength of a typo.
    """
    raw, where = find_property(element, SPACING_EXTENSION_PROPERTY_NAMES)
    value = as_float(raw)
    if value is None:
        return None, {"source": where, "reason": "not authored or not numeric"}
    low, high = _PLAUSIBLE_SPACING_MULTIPLIER
    if not low <= value <= high:
        return None, {
            "source": where,
            "raw": raw,
            "reason": f"multiplier {value} outside {low}-{high}",
        }
    return round(value, 4), {"source": where}


def _all_or_none(values: list) -> bool | None:
    """Return True only when every value is True; False as soon as one is False."""
    if not values:
        return None
    if any(value is False for value in values):
        return False
    if all(value is True for value in values):
        return True
    return None


def _governing_multiplier(values: list) -> float | None:
    """Return the least generous authored multiplier, or ``None`` if any is missing."""
    if not values or any(value is None for value in values):
        return None
    return round(min(values), 4)


def aggregate_restraint_flags(
    elements: list, element_labels: list | None = None, run_element=None
) -> dict:
    """Fold the three detailing properties over a run's hangers.

    Booleans use ALL semantics: an explicit False on any hanger makes the run
    False, and True requires every hanger to say so. A run where some hangers
    are silent is ``None`` -- "most of the hangers are detailed correctly" is
    not a statement any of these rules accepts, and reading it as True would
    let one authored hanger vouch for a dozen nobody ever checked.

    The multiplier takes the MINIMUM of the authored values, since the least
    generous detail governs the run, and is ``None`` unless every hanger
    authors one, for the same reason.

    ``run_element`` -- the pipe itself -- is consulted FIRST and outranks the
    fold. All three properties describe how a run is detailed, and a value
    authored on the run is a direct statement about exactly that, where the
    fold is this module reasoning from the parts. Where the run says nothing,
    which is the common case, the fold is all there is.
    """
    labels = element_labels or [None] * len(elements)
    per_element: list[dict] = []
    bending: list = []
    dual: list = []
    multipliers: list = []

    for element, label in zip(elements, labels):
        bend_value, bend_detail = restraint_flag(element, ROD_BENDING_PROPERTY_NAMES)
        dual_value, dual_detail = restraint_flag(element, DUAL_SUPPORT_PROPERTY_NAMES)
        mult_value, mult_detail = spacing_extension_multiplier(element)
        bending.append(bend_value)
        dual.append(dual_value)
        multipliers.append(mult_value)
        per_element.append(
            {
                "guid": label or getattr(element, "GlobalId", None),
                "details_prevent_rod_bending": bend_value,
                "details_prevent_rod_bending_source": bend_detail.get("source"),
                "has_dual_structural_supports": dual_value,
                "has_dual_structural_supports_source": dual_detail.get("source"),
                "spacing_extension_multiplier": mult_value,
                "spacing_extension_multiplier_source": mult_detail.get("source"),
            }
        )

    folded = {
        "details_prevent_rod_bending": _all_or_none(bending),
        "has_dual_structural_supports": _all_or_none(dual),
        "spacing_extension_multiplier": _governing_multiplier(multipliers),
    }
    on_run: dict = {}
    if run_element is not None:
        run_bending, _ = restraint_flag(run_element, ROD_BENDING_PROPERTY_NAMES)
        run_dual, _ = restraint_flag(run_element, DUAL_SUPPORT_PROPERTY_NAMES)
        run_multiplier, _ = spacing_extension_multiplier(run_element)
        on_run = {
            "details_prevent_rod_bending": run_bending,
            "has_dual_structural_supports": run_dual,
            "spacing_extension_multiplier": run_multiplier,
        }

    return {
        **{
            key: (on_run.get(key) if on_run.get(key) is not None else value)
            for key, value in folded.items()
        },
        "authored_on_run": {k: v for k, v in on_run.items() if v is not None},
        "folded_over_hangers": folded,
        "evaluated_support_count": len(elements),
        "per_support": per_element,
    }


# ── Assembled context ─────────────────────────────────────────────────────────


def _carries_detailing(support: dict) -> bool:
    """Whether this support is the kind the detailing properties describe."""
    element = support.get("element")
    if element is None:
        return False
    if support.get("kind") in _DETAILING_SUPPORT_KINDS:
        return True
    try:
        return any(element.is_a(cls) for cls in _DETAILING_SUPPORT_CLASSES)
    except Exception:
        return False


def _worst_coupling_distance(
    supports: list[dict],
    reference_points: list | None,
    coupling_index: list[dict] | None,
    geometry_extractor,
) -> tuple[float | None, dict]:
    """Nearest-coupling distance for whichever reference fares worst."""
    detail: dict = {"unit": "mm", "references": []}

    if reference_points is None:
        reference_points = []
        for support in supports:
            point = support.get("position_mm")
            element = support.get("element")
            if point is None and geometry_extractor is not None and element is not None:
                try:
                    point = geometry_extractor.get_centroid_or_none(element)
                except Exception:
                    point = None
            reference_points.append((support.get("guid"), point))

    if not reference_points:
        detail["reason"] = "no brace or support to measure from"
        return None, detail

    worst: float | None = None
    for label, point in reference_points:
        distance, per_reference = nearest_flexible_coupling_mm(
            point, coupling_index, geometry_extractor
        )
        detail["references"].append(
            {"reference": label, "distance_mm": distance, **per_reference}
        )
        if distance is None:
            detail["reason"] = f"distance unresolved for reference {label!r}"
            return None, detail
        if worst is None or distance > worst:
            worst = distance

    detail["reference_count"] = len(reference_points)
    return worst, detail


def seismic_context(
    element,
    ifc_file=None,
    geometry_extractor=None,
    unit_scale_mm: float = 1.0,
    coupling_index: list[dict] | None = None,
    support_index: list | None = None,
    supports: list[dict] | None = None,
    reference_points: list | None = None,
    project_coefficient: tuple | None = None,
    mass_scale_kg: float | None = None,
) -> dict:
    """Gather every seismic restraint input for one element.

    The shape ``extract_for_compliance`` attaches to an element record,
    assembled here so the traversal is written and tested in one place -- the
    arrangement ``ifc_penetrations.penetration_context`` and
    ``ifc_supports.support_context`` already use.

    ``project_coefficient`` and ``mass_scale_kg`` are the two model-wide facts
    this needs. Both are resolved per call when omitted, but a caller looping
    over elements should resolve each once and pass it in -- neither varies
    between components, and both otherwise re-read the file per element.

    ``reference_points`` are the positions a flexible coupling has to be near,
    as ``(label, point_mm)`` pairs. They default to the supports holding this
    element, which is what the bracing rules mean by "within 300 mm of the
    brace". A caller measuring from something else -- the point where the run
    passes through a wall, for the penetration exemption -- passes its own,
    because this module has no way to know which reference a rule intended and
    picking one silently would answer a question nobody asked.

    THE WORST REFERENCE GOVERNS. With several braces, the reported distance is
    the largest of their nearest-coupling distances: an exemption is earned
    when every brace has a coupling close by, so the brace furthest from one
    decides whether the run qualifies. A single unresolvable reference makes
    the whole answer ``None`` for the same reason -- a brace whose distance is
    unknown cannot be shown to clear the limit.
    """
    if supports is None and _SUPPORTS_AVAILABLE:
        try:
            supports = find_supports(
                element,
                geometry_extractor=geometry_extractor,
                unit_scale_mm=unit_scale_mm,
                support_index=support_index,
            )
        except Exception as exc:
            logger.debug("Support lookup failed for %s: %s", element, exc)
            supports = []
    supports = supports or []

    mass, mass_detail = element_mass_kg(
        element,
        ifc_file=ifc_file,
        geometry_extractor=geometry_extractor,
        unit_scale_mm=unit_scale_mm,
        mass_scale_kg=mass_scale_kg,
    )
    coefficient, coefficient_detail = seismic_force_coefficient(
        ifc_file, element, project_value=project_coefficient
    )

    hangers = [s for s in supports if _carries_detailing(s)]
    flags = aggregate_restraint_flags(
        [s["element"] for s in hangers],
        [s.get("guid") for s in hangers],
        run_element=element,
    )

    coupling_mm, coupling_detail = _worst_coupling_distance(
        supports, reference_points, coupling_index, geometry_extractor
    )

    return {
        "mass_kg": mass,
        "mass_detail": mass_detail,
        "seismic_force_coefficient_c": coefficient,
        "seismic_force_coefficient_detail": coefficient_detail,
        "flexible_coupling_within_mm": coupling_mm,
        "flexible_coupling_detail": coupling_detail,
        "details_prevent_rod_bending": flags["details_prevent_rod_bending"],
        "has_dual_structural_supports": flags["has_dual_structural_supports"],
        "spacing_extension_multiplier": flags["spacing_extension_multiplier"],
        "restraint_detail": flags,
    }
